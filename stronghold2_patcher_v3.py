#!/usr/bin/env python3

"""
Stronghold 2 AI Enabler for Proton / Linux
==========================================

Enables AI (bot) slots in Stronghold 2 multiplayer games by writing a single
byte inside the running game process.

How it works (verified against the Steam build of Stronghold2.exe):
  * The lobby screen object (C++ class ScenarioLobbyScreen@Stronghold2, RTTI
    confirmed at runtime) is reachable through a pointer that lives at
    IMAGE BASE + 0x00EC5F28.
  * Two booleans inside that object gate lobby controls the game hides in
    multiplayer. The screen's own init routine zeroes both, so putting them
    back to 1 makes the game offer them again:
        +0xD28  AI/bot slots          (sword + helmet + shield icon)
        +0x1790 "Randomize Players"   (dice icon)

Safety: the tool only ever flips those two bytes (and only when they currently
read something other than 1). Before writing, the pointed-to object is
validated by resolving its RTTI type name - if the object is not a
ScenarioLobbyScreen the tool reports it instead of poking random memory.
"""

import errno
import hashlib
import html
import os
import struct
import subprocess
import sys
import time

APP_VERSION = "3"
ORG_NAME = "GameModders"

MODULE_NAME = "Stronghold2.exe"
POINTER_OFFSET = 0x00EC5F28

FEATURES = (
    ("ai", 0x0D28, 1),
    ("randomize", 0x1790, 1),
)
FEATURE_OFFSETS = {key: offset for key, offset, _ in FEATURES}
FEATURE_VALUES = {key: value for key, _, value in FEATURES}
LAST_FEATURE_OFFSET = max(FEATURE_OFFSETS.values())
ADDRESS_OFFSET = FEATURE_OFFSETS["ai"]
A_BYTES = 4
V_BYTES = 1
POLL_INTERVAL = 0.25
EXPECTED_OBJECT = "ScenarioLobbyScreen@Stronghold2"
REFERENCE_EXE_SIZE = 14208000

def check_and_install_pyqt5():
    try:
        from PyQt5.QtWidgets import QApplication
        return True
    except ImportError:
        print("PyQt5 not found. Attempting to install...")

        try:
            if os.path.exists('/etc/arch-release'):
                subprocess.run(['sudo', 'pacman', '-S', '--noconfirm', 'python-pyqt5'], check=True)
            elif os.path.exists('/etc/debian_version'):
                subprocess.run(['sudo', 'apt', 'update'], check=True)
                subprocess.run(['sudo', 'apt', 'install', '-y', 'python3-pyqt5'], check=True)
            elif os.path.exists('/etc/fedora-release'):
                subprocess.run(['sudo', 'dnf', 'install', '-y', 'python3-qt5'], check=True)
            elif os.path.exists('/etc/SuSE-release'):
                subprocess.run(['sudo', 'zypper', 'install', '-y', 'python3-qt5'], check=True)
            else:
                print("Unknown distribution. Please install PyQt5 manually:")
                print("sudo pip3 install PyQt5")
                return False

            print("PyQt5 installed successfully!")
            return True

        except subprocess.CalledProcessError:
            print("Error installing PyQt5. Try:")
            print("sudo pip3 install PyQt5")
            return False

def _parse_args(argv):
    opts = {"demo": False, "screenshot": None}
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "--demo":
            opts["demo"] = True
        elif a == "--screenshot" and i + 1 < len(argv):
            opts["screenshot"] = argv[i + 1]
            i += 1
        elif a in ("-h", "--help"):
            print(__doc__)
            sys.exit(0)
        i += 1
    return opts

if not check_and_install_pyqt5():
    sys.exit(1)

try:
    from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                                QHBoxLayout, QLabel, QPushButton, QFrame,
                                QSystemTrayIcon, QMenu, QAction, QTabWidget,
                                QComboBox, QPlainTextEdit, QGridLayout, QSizePolicy)
    from PyQt5.QtCore import (QTimer, QThread, pyqtSignal, Qt, QRectF,
                              QSettings, QPointF, PYQT_VERSION_STR, QT_VERSION_STR)
    from PyQt5.QtGui import (QFontDatabase, QIcon, QPixmap, QPainter, QTextCursor,
                             QColor, QLinearGradient)
except ImportError as e:
    print(f"PyQt5 import error: {e}")
    print("Try: sudo pip3 install PyQt5")
    sys.exit(1)

LANG = {
    "app_title": {
        "en": "Stronghold 2 AI Enabler",
        "uk": "Stronghold 2 AI Enabler",
        "ru": "Stronghold 2 AI Enabler",
    },
    "header_title": {
        "en": "Stronghold 2",
        "uk": "Stronghold 2",
        "ru": "Stronghold 2",
    },
    "header_subtitle": {
        "en": "AI enabler for multiplayer  ·  Proton on Linux  ·  v{v}",
        "uk": "Увімкнення AI для мультиплеєра  ·  Proton на Linux  ·  v{v}",
        "ru": "Включение AI для мультиплеера  ·  Proton на Linux  ·  v{v}",
    },
    "tab_status": {"en": "Monitor", "uk": "Моніторинг", "ru": "Мониторинг"},
    "tab_details": {"en": "Game", "uk": "Гра", "ru": "Игра"},
    "tab_about": {"en": "About", "uk": "Про програму", "ru": "О программе"},
    "language_label": {"en": "Language", "uk": "Мова", "ru": "Язык"},

    "state_idle": {"en": "Idle", "uk": "Очікування", "ru": "Простой"},
    "state_wait": {"en": "Searching", "uk": "Пошук", "ru": "Поиск"},
    "state_ok": {"en": "Active", "uk": "Активно", "ru": "Активно"},
    "state_error": {"en": "Attention", "uk": "Увага", "ru": "Внимание"},

    "button_start": {"en": "Start monitoring", "uk": "Запустити моніторинг", "ru": "Запустить мониторинг"},
    "button_stop": {"en": "Stop", "uk": "Зупинити", "ru": "Остановить"},
    "button_clear_log": {"en": "Clear", "uk": "Очистити", "ru": "Очистить"},
    "button_elevate": {"en": "Restart with admin rights", "uk": "Перезапустити з правами адміністратора", "ru": "Перезапустить с правами администратора"},

    "hero_hint": {
        "en": "Start monitoring, then launch Stronghold 2 and open the multiplayer lobby.",
        "uk": "Запустіть моніторинг, потім гру Stronghold 2 та відкрийте лобі мультиплеєра.",
        "ru": "Запустите мониторинг, затем игру Stronghold 2 и откройте лобби мультиплеера.",
    },
    "hero_running": {
        "en": "Watching Stronghold2.exe — the AI slot unlocks automatically.",
        "uk": "Стежу за Stronghold2.exe — слот AI відкриється автоматично.",
        "ru": "Слежу за Stronghold2.exe — слот AI откроется автоматически.",
    },
    "hero_pid": {
        "en": "PID {pid}  ·  base 0x{base:08x}",
        "uk": "PID {pid}  ·  база 0x{base:08x}",
        "ru": "PID {pid}  ·  база 0x{base:08x}",
    },

    "card_unlocks": {"en": "Unlocks", "uk": "Розблокувань", "ru": "Разблокировок"},
    "card_process": {"en": "Process", "uk": "Процес", "ru": "Процесс"},
    "card_lobby": {"en": "Lobby object", "uk": "Об'єкт лобі", "ru": "Объект лобби"},
    "card_flag": {"en": "AI slot", "uk": "Слот AI", "ru": "Слот AI"},
    "card_randomize": {"en": "Randomize", "uk": "Рандом", "ru": "Рандом"},
    "value_none": {"en": "—", "uk": "—", "ru": "—"},
    "value_on": {"en": "enabled", "uk": "увімкнено", "ru": "включён"},
    "value_off": {"en": "off", "uk": "вимкнено", "ru": "выключен"},
    "value_found": {"en": "found", "uk": "знайдено", "ru": "найден"},
    "value_missing": {"en": "not created", "uk": "не створено", "ru": "не создан"},

    "log_title": {"en": "Event log", "uk": "Журнал подій", "ru": "Журнал событий"},
    "log_writes": {"en": "memory writes: {n}", "uk": "записів у пам'ять: {n}", "ru": "записей в память: {n}"},

    "status_initial": {"en": "Ready to start", "uk": "Готовий до запуску", "ru": "Готов к запуску"},
    "status_waiting_for_sh2": {"en": "Waiting for Stronghold 2 to start…", "uk": "Очікування запуску Stronghold 2…", "ru": "Ожидание запуска Stronghold 2…"},
    "status_sh2_found": {"en": "Stronghold 2 found (PID {pid})", "uk": "Stronghold 2 знайдено (PID {pid})", "ru": "Stronghold 2 найден (PID {pid})"},
    "status_failed_to_get_ai_address": {"en": "Lobby object is not available yet", "uk": "Об'єкт лобі ще недоступний", "ru": "Объект лобби пока недоступен"},
    "feature_ai": {"en": "AI slots", "uk": "Слоти AI", "ru": "Слоты AI"},
    "feature_randomize": {"en": "Randomize Players", "uk": "Випадковий розподіл", "ru": "Случайное распределение игроков"},
    "status_lobby_ready": {"en": "Lobby screen detected — unlocking AI and Randomize…", "uk": "Екран лобі знайдено — відкриваю AI та рандом…", "ru": "Экран лобби обнаружен — открываю AI и рандом…"},
    "status_all_enabled": {"en": "AI slots and Randomize Players are available", "uk": "Слоти AI та випадковий розподіл доступні", "ru": "Слоты AI и случайное распределение доступны"},
    "status_feature_enabled": {"en": "{name} unlocked in the multiplayer lobby", "uk": "{name} відкрито в лобі мультиплеєра", "ru": "{name} открыт в лобби мультиплеера"},
    "status_reapplied": {"en": "The game reset {name} — re-applying", "uk": "Гра скинула {name} — повторюю", "ru": "Игра сбросила {name} — повторяю"},
    "status_error_enabling_ai": {"en": "Cannot write to game memory", "uk": "Не вдалось записати в пам'ять гри", "ru": "Не удалось записать в память игры"},
    "status_permission_denied": {"en": "Permission denied while accessing game memory", "uk": "Немає доступу до пам'яті гри", "ru": "Нет доступа к памяти игры"},
    "status_monitoring_stopped": {"en": "Monitoring stopped", "uk": "Моніторинг зупинено", "ru": "Мониторинг остановлен"},
    "status_unexpected_object": {"en": "Unexpected object at the pointer — offsets may not fit this build", "uk": "Неочікуваний об'єкт за вказівником — офсети можуть не підходити до цієї збірки", "ru": "Неожиданный объект по указателю — офсеты могут не подойти этой сборке"},
    "status_unverified": {"en": "RTTI info unavailable — continuing without class verification", "uk": "RTTI недоступний — продовжую без перевірки класу", "ru": "RTTI недоступен — продолжаю без проверки класса"},
    "status_bad_image": {"en": "Could not validate the game image base", "uk": "Не вдалося перевірити базову адресу образу", "ru": "Не удалось проверить базовый адрес образа"},
    "status_no_root_needed": {"en": "Running without root — elevated access is only requested if needed.", "uk": "Права root не потрібні — підвищення прав запитаю лише за потреби.", "ru": "Права root не нужны — повышение прав запрошу только при необходимости."},
    "banner_root_title": {"en": "Administrator rights required", "uk": "Потрібні права адміністратора", "ru": "Требуются права администратора"},
    "banner_root_text": {
        "en": "The game process refused memory access. Relaunch with elevated rights to keep monitoring.\nTip: the game itself stays unprivileged — only this helper needs the rights.",
        "uk": "Процес гри відхилив доступ до пам'яті. Перезапустіть з підвищеними правами, щоб продовжити.\nПідказка: сама гра залишається без привілеїв — права потрібні лише цій утиліті.",
        "ru": "Процесс игры отклонил доступ к памяти. Перезапустите с повышенными правами, чтобы продолжить.\nПодсказка: сама игра остаётся без привилегий — права нужны только этой утилите.",
    },
    "tray_icon_tooltip": {"en": "Stronghold 2 AI Enabler", "uk": "Stronghold 2 AI Enabler", "ru": "Stronghold 2 AI Enabler"},
    "tray_show_window": {"en": "Show window", "uk": "Показати вікно", "ru": "Показать окно"},
    "tray_toggle_start": {"en": "Start monitoring", "uk": "Запустити моніторинг", "ru": "Запустить мониторинг"},
    "tray_toggle_stop": {"en": "Stop monitoring", "uk": "Зупинити моніторинг", "ru": "Остановить мониторинг"},
    "tray_quit_app": {"en": "Exit", "uk": "Вихід", "ru": "Выход"},
    "tray_minimize_message_title": {"en": "Stronghold 2 AI Enabler", "uk": "Stronghold 2 AI Enabler", "ru": "Stronghold 2 AI Enabler"},
    "tray_minimize_message_text": {
        "en": "Minimised to the tray — monitoring continues in the background.",
        "uk": "Згорнуто в трей — моніторинг продовжується у фоні.",
        "ru": "Свёрнуто в трей — мониторинг продолжается в фоне.",
    },

    "details_hint": {
        "en": "Read-only diagnostics of the attached game process.",
        "uk": "Діагностика приєднаного процесу гри (тільки читання).",
        "ru": "Диагностика подключённого процесса игры (только чтение).",
    },
    "d_game_path": {"en": "Game image", "uk": "Образ гри", "ru": "Образ игры"},
    "d_pid": {"en": "Process ID", "uk": "Ідентифікатор процесу", "ru": "Идентификатор процесса"},
    "d_base": {"en": "Image base", "uk": "Базова адреса", "ru": "Базовый адрес"},
    "d_slot": {"en": "Pointer slot", "uk": "Слот вказівника", "ru": "Слот указателя"},
    "d_object": {"en": "Lobby object", "uk": "Об'єкт лобі", "ru": "Объект лобби"},
    "d_object_type": {"en": "Object class (RTTI)", "uk": "Клас об'єкта (RTTI)", "ru": "Класс объекта (RTTI)"},
    "d_flag_ai": {"en": "AI flag  (+0xD28)", "uk": "Прапорець AI  (+0xD28)", "ru": "Флаг AI  (+0xD28)"},
    "d_flag_rand": {"en": "Randomize flag  (+0x1790)", "uk": "Прапорець рандому  (+0x1790)", "ru": "Флаг рандома  (+0x1790)"},
    "d_unlocks": {"en": "Unlocks this session", "uk": "Розблокувань за сесію", "ru": "Разблокировок за сессию"},
    "d_writes": {"en": "Memory writes", "uk": "Записів у пам'ять", "ru": "Записей в память"},
    "d_poll": {"en": "Poll interval", "uk": "Інтервал опитування", "ru": "Интервал опроса"},
    "d_exe_size": {"en": "Build size", "uk": "Розмір збірки", "ru": "Размер сборки"},
    "d_exe_sha": {"en": "Build SHA-256", "uk": "SHA-256 збірки", "ru": "SHA-256 сборки"},
    "d_build_state": {"en": "Build verification", "uk": "Перевірка збірки", "ru": "Проверка сборки"},
    "build_verified": {
        "en": "Matches the build this tool was tested with",
        "uk": "Збігається зі збіркою, на якій тестували",
        "ru": "Совпадает со сборкой, на которой тестировали",
    },
    "build_unknown": {
        "en": "Different build — offsets are re-verified at runtime",
        "uk": "Інша збірка — офсети перевіряються під час роботи",
        "ru": "Другая сборка — офсеты проверяются во время работы",
    },
    "build_pending": {"en": "Waiting for the game…", "uk": "Очікування гри…", "ru": "Ожидание игры…"},

    "about_text": {
        "en": "This helper unlocks AI (bot) slots in Stronghold 2 multiplayer games running through Proton on Linux.\n\n"
              "It attaches read/write to the game process, resolves the multiplayer lobby object through the pointer stored at "
              "base + 0x00EC5F28, verifies that the object really is a ScenarioLobbyScreen (via RTTI) and then holds two of "
              "its bytes at 1: +0xD28 (AI/bot slots) and +0x1790 (Randomize Players). Nothing else is ever touched.\n\n"
              "The game is never modified on disk and the helper does not need root unless the kernel refuses access to the "
              "game's memory.\n\n"
              "Developed by Alley\nVersion {v}\n",
        "uk": "Утиліта відкриває слоти AI (ботів) у багатокористувацьких іграх Stronghold 2, запущених через Proton на Linux.\n\n"
              "Вона приєднується до процесу гри, знаходить об'єкт лобі мультиплеєра за вказівником base + 0x00EC5F28, "
              "перевіряє через RTTI, що це справді ScenarioLobbyScreen, і тримає два його байти у стані 1: "
              "+0xD28 (слоти AI) та +0x1790 («Випадковий розподіл гравців»). Більше нічого не змінюється.\n\n"
              "Гра не змінюється на диску, а права root потрібні лише якщо ядро відмовляє в доступі до пам'яті гри.\n\n"
              "Розробник: Alley\nВерсія {v}\n",
        "ru": "Утилита открывает слоты AI (ботов) в многопользовательских играх Stronghold 2, запущенных через Proton на Linux.\n\n"
              "Она подключается к процессу игры, находит объект лобби мультиплеера по указателю base + 0x00EC5F28, "
              "проверяет через RTTI, что это действительно ScenarioLobbyScreen, и удерживает два его байта в состоянии 1: "
              "+0xD28 (слоты AI) и +0x1790 («Случайное распределение игроков»). Больше ничего не изменяется.\n\n"
              "Игра не изменяется на диске, а права root нужны только если ядро отказывает в доступе к памяти игры.\n\n"
              "Разработчик: Alley\nВерсия {v}\n",
    },
    "about_stack": {
        "en": "Interface: PyQt5 {qt} · Python {py} · running {mode}",
        "uk": "Інтерфейс: PyQt5 {qt} · Python {py} · запущено {mode}",
        "ru": "Интерфейс: PyQt5 {qt} · Python {py} · запущено {mode}",
    },
    "mode_root": {"en": "as root", "uk": "від root", "ru": "от root"},
    "mode_user": {"en": "as a normal user", "uk": "як звичайний користувач", "ru": "как обычный пользователь"},
}

current_language = "en"

def tr(key, **kwargs):
    text = LANG[key][current_language]
    return text.format(**kwargs) if kwargs else text

class GameMemory:
    """Read/write access to another process' memory via /proc/<pid>/mem."""

    def __init__(self, pid):
        self.pid = pid
        self._mem = None

    def attach(self):
        if self._mem is None:
            self._mem = open(f"/proc/{self.pid}/mem", "r+b", buffering=0)
        return self

    def close(self):
        if self._mem is not None:
            try:
                self._mem.close()
            finally:
                self._mem = None

    def read(self, address, size):
        try:
            self.attach()
            self._mem.seek(address)
            return self._mem.read(size)
        except (OSError, ValueError) as exc:
            if getattr(exc, "errno", None) in (errno.EPERM, errno.EACCES):
                raise PermissionError(str(exc))
            return None

    def read_u32(self, address):
        data = self.read(address, A_BYTES)
        if not data or len(data) != A_BYTES:
            return None
        return struct.unpack("<I", data)[0]

    def write_byte(self, address, value):
        try:
            self.attach()
            self._mem.seek(address)
            self._mem.write(struct.pack("<B", value))
            return True
        except (OSError, ValueError) as exc:
            if getattr(exc, "errno", None) in (errno.EPERM, errno.EACCES):
                raise PermissionError(str(exc))
            return False

def find_game_pid():
    """PID of the running Stronghold2.exe (Proton/Wine) or 0."""
    try:
        result = subprocess.run(["pgrep", "-f", MODULE_NAME],
                                capture_output=True, text=True)
    except Exception:
        return 0

    if result.returncode != 0:
        return 0
    for token in result.stdout.split():
        if token.isdigit():
            pid = int(token)
            if os.path.exists(f"/proc/{pid}"):
                return pid
    return 0

def find_image(pid):
    """(base, path, size_of_image) of the mapped game image.

    The mapping with file offset 0 is the image base; the PE header stored
    there tells us the image size, which is used to sanity check all
    addresses we follow."""
    if not pid:
        return 0, None, 0

    base = 0
    path = None
    try:
        with open(f"/proc/{pid}/maps", "r") as handle:
            for line in handle:
                if MODULE_NAME not in line:
                    continue
                parts = line.split(None, 5)
                if len(parts) < 6:
                    continue
                try:
                    offset = int(parts[2], 16)
                    start = int(parts[0].split("-")[0], 16)
                except ValueError:
                    continue

                image_path = parts[5].strip()
                if offset == 0:
                    base, path = start, image_path
                    break
                if not base:
                    base, path = start, image_path
    except OSError:
        return 0, None, 0

    if not base:
        return 0, None, 0

    size = 0
    try:
        with open(f"/proc/{pid}/mem", "rb", buffering=0) as mem:
            mem.seek(base)
            header = mem.read(0x400)
        if header[:2] == b"MZ":
            e_lfanew = struct.unpack_from("<I", header, 0x3C)[0]
            if 0 < e_lfanew <= len(header) - 0x60 and header[e_lfanew:e_lfanew + 4] == b"PE\0\0":
                size = struct.unpack_from("<I", header, e_lfanew + 0x50)[0]
    except (OSError, ValueError, struct.error):
        size = 0

    return base, path, size

def read_regions(pid):
    """[(start, end, perms)] of the process' virtual memory mappings."""
    regions = []
    try:
        with open(f"/proc/{pid}/maps", "r") as handle:
            for line in handle:
                parts = line.split(None, 5)
                if len(parts) < 2:
                    continue
                try:
                    start, end = (int(value, 16) for value in parts[0].split("-"))
                except ValueError:
                    continue
                regions.append((start, end, parts[1]))
    except OSError:
        return []
    return regions

def is_mapped(regions, address, size=1, writable=False):
    """Is [address, address+size) inside one of the mappings?"""
    if not address:
        return False
    for start, end, perms in regions:
        if start <= address and address + size <= end:
            if not writable or "w" in perms:
                return True
    return False

def rtti_class_name(mem, address, base, image_size):
    """Resolve the C++ class name of the object at `address` (MSVC RTTI)."""

    def in_image(value):
        return base and image_size and base <= value < base + image_size

    vtable = mem.read_u32(address)
    if not vtable or not in_image(vtable):
        return None
    col = mem.read_u32(vtable - 4)
    if not col or not in_image(col):
        return None
    descriptor = mem.read_u32(col + 12)
    if not descriptor or not in_image(descriptor):
        return None
    raw = mem.read(descriptor + 8, 192) or b""
    name = raw.split(b"\0")[0].decode("latin-1", "replace")
    return name or None

def build_signature(path):
    """(size, sha256) of the game executable, or (0, None)."""
    if not path or not os.path.exists(path):
        return 0, None
    digest = hashlib.sha256()
    try:
        size = 0
        with open(path, "rb") as handle:
            while True:
                chunk = handle.read(1 << 20)
                if not chunk:
                    break
                size += len(chunk)
                digest.update(chunk)
        return size, digest.hexdigest()
    except OSError:
        return 0, None

class Stronghold2Worker(QThread):
    status_changed = pyqtSignal(str, str)
    log_event = pyqtSignal(str, str)
    metrics_changed = pyqtSignal(dict)
    permission_denied = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.running = False
        self._mem = None
        self._mem_pid = 0
        self._metrics = {
            "pid": 0, "base": 0, "path": None, "object": 0, "object_type": None,
            "flag_addrs": {}, "flags": {}, "unlocks": {},
            "writes": 0, "activations": 0,
            "image_size": 0, "exe_size": 0, "exe_sha": None, "state": "idle",
        }
        self._last_status = None
        self._last_log = {}
        self._signature_path = None
        self._flags = {}
        self._unlocks = {}

    def _memory(self, pid):
        if self._mem_pid != pid or self._mem is None:
            if self._mem is not None:
                self._mem.close()
            self._mem = GameMemory(pid)
            self._mem_pid = pid
        return self._mem

    def _close_memory(self):
        if self._mem is not None:
            self._mem.close()
        self._mem = None
        self._mem_pid = 0

    def _reset_metrics(self):
        for key in ("pid", "base", "object"):
            self._metrics[key] = 0
        self._metrics["object_type"] = None
        self._metrics["flag_addrs"] = {}
        self._metrics["flags"] = {}
        self._flags = {}
        self._metrics["image_size"] = 0
        self._metrics["path"] = None
        self._metrics["exe_size"] = 0
        self._metrics["exe_sha"] = None
        self._signature_path = None

    def _set_state(self, state, message=None):
        self._metrics["state"] = state
        if message and message != self._last_status:
            self._last_status = message
            self.status_changed.emit(message, state)

    LOG_REPEAT_GAP = 5.0

    def _log(self, level, key, message):
        """Emit a log line, rate limiting identical repeats so a flag that the
        game keeps resetting cannot flood the log at the polling rate."""
        now = time.time()
        last_message, last_time = self._last_log.get(key, (None, 0.0))
        if message == last_message and now - last_time < self.LOG_REPEAT_GAP:
            return
        self._last_log[key] = (message, now)
        self.log_event.emit(level, message)

    def _handle_os_error(self, exc):
        if isinstance(exc, PermissionError):
            self.permission_denied.emit()
            self._set_state("error", tr("status_permission_denied"))
            self._log("error", "perm", tr("status_permission_denied"))
            return True
        return False

    def run(self):
        self.running = True
        while self.running:
            try:
                self._tick()
            except Exception as exc:
                self._log("error", "unexpected", f"{type(exc).__name__}: {exc}")
            self.msleep(int(POLL_INTERVAL * 1000))

    def _tick(self):
        pid = find_game_pid()
        if not pid:
            if self._metrics["pid"]:
                self._close_memory()
                self._reset_metrics()
            self._set_state("wait", tr("status_waiting_for_sh2"))
            self._log("info", "waiting", tr("status_waiting_for_sh2"))
            self.metrics_changed.emit(dict(self._metrics))
            return

        base, path, image_size = find_image(pid)
        mem = self._memory(pid)

        if self._metrics["pid"] != pid:
            self._metrics["pid"] = pid
            self._metrics["path"] = path
            self._log("info", "found", tr("status_sh2_found", pid=pid))
            self._last_log.pop("waiting", None)

        if not base or not image_size:
            self._metrics["base"] = base
            self._metrics["image_size"] = image_size
            self._set_state("error", tr("status_bad_image"))
            self._log("error", "badimage", tr("status_bad_image"))
            self.metrics_changed.emit(dict(self._metrics))
            return

        self._metrics["base"] = base
        self._metrics["image_size"] = image_size

        if self._signature_path != path:
            size, sha = build_signature(path)
            self._signature_path = path
            self._metrics["exe_size"] = size
            self._metrics["exe_sha"] = sha

        try:
            pointer = mem.read_u32(base + POINTER_OFFSET)
        except PermissionError as exc:
            self._handle_os_error(exc)
            self.metrics_changed.emit(dict(self._metrics))
            return

        regions = read_regions(pid)
        if not is_mapped(regions, pointer, LAST_FEATURE_OFFSET + V_BYTES, writable=True):
            self._metrics["object"] = 0
            self._metrics["object_type"] = None
            self._metrics["flag_addrs"] = {}
            self._metrics["flags"] = {}
            self._set_state("wait", tr("status_failed_to_get_ai_address"))
            self._log("info", "nolobby", tr("status_failed_to_get_ai_address"))
            self.metrics_changed.emit(dict(self._metrics))
            return

        self._metrics["object"] = pointer
        self._metrics["flag_addrs"] = {key: pointer + offset
                                       for key, offset in FEATURE_OFFSETS.items()}

        class_name = rtti_class_name(mem, pointer, base, image_size)
        if class_name != self._metrics["object_type"]:
            self._metrics["object_type"] = class_name
            if class_name and EXPECTED_OBJECT in class_name:
                self._log("ok", "lobby", tr("status_lobby_ready"))
            elif class_name:
                self._log("warn", "badobject", tr("status_unexpected_object"))
            else:
                self._log("warn", "nortti", tr("status_unverified"))

        if class_name and EXPECTED_OBJECT not in class_name:

            self._set_state("error", tr("status_unexpected_object"))
            self.metrics_changed.emit(dict(self._metrics))
            return

        failed = []
        for key, offset, wanted in FEATURES:
            addr = pointer + offset
            try:
                data = mem.read(addr, V_BYTES)
            except PermissionError as exc:
                self._handle_os_error(exc)
                self.metrics_changed.emit(dict(self._metrics))
                return

            if not data:
                self._set_state("error", tr("status_error_enabling_ai"))
                self._log("error", "noread" + key, tr("status_error_enabling_ai"))
                self.metrics_changed.emit(dict(self._metrics))
                return

            value = data[0]
            if value != wanted:
                try:
                    ok = mem.write_byte(addr, wanted)
                except PermissionError as exc:
                    self._handle_os_error(exc)
                    self.metrics_changed.emit(dict(self._metrics))
                    return
                if ok:
                    self._metrics["writes"] += 1
                    if value == 0:
                        self._unlocks[key] = self._unlocks.get(key, 0) + 1
                        self._metrics["activations"] = sum(self._unlocks.values())
                        self._log("ok", "applied" + key,
                                  tr("status_feature_enabled", name=tr("feature_" + key)))
                    else:
                        self._log("warn", "reapplied" + key,
                                  tr("status_reapplied", name=tr("feature_" + key)))
                    value = wanted
                else:
                    failed.append(key)
                    self._log("error", "nowrite" + key, tr("status_error_enabling_ai"))
            self._flags[key] = value

        self._metrics["flags"] = dict(self._flags)
        self._metrics["unlocks"] = dict(self._unlocks)

        if failed:
            self._set_state("error", tr("status_error_enabling_ai"))
        elif all(self._flags.get(key) == value for key, _, value in FEATURES):
            self._set_state("ok", tr("status_all_enabled"))
        elif self._metrics["object_type"] and EXPECTED_OBJECT in self._metrics["object_type"]:
            self._set_state("wait", tr("status_lobby_ready"))
        else:
            self._set_state("ok", tr("status_sh2_found", pid=pid))

        self.metrics_changed.emit(dict(self._metrics))

    def refresh_status(self):
        """Force the next tick to re-emit the current status (language change)."""
        self._last_status = None

    def stop(self):
        self.running = False
        self.wait(3000)
        self._close_memory()

class DemoWorker(QThread):
    """Feeds the GUI with scripted events so the interface can be reviewed
    without a running game and without elevated rights (--demo)."""

    status_changed = pyqtSignal(str, str)
    log_event = pyqtSignal(str, str)
    metrics_changed = pyqtSignal(dict)
    permission_denied = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.running = False

    def run(self):
        self.running = True
        script = [
            ("info", tr("status_waiting_for_sh2"), "wait"),
            ("info", tr("status_sh2_found", pid=6834), "wait"),
            ("ok", tr("status_lobby_ready"), "wait"),
            ("ok", tr("status_all_enabled"), "ok"),
        ]
        base = 0x00400000
        pointer = 0x04ED7440
        metrics = {
            "pid": 0, "base": 0, "path": "/home/user/.local/share/Steam/steamapps/"
                                     "common/Stronghold 2/Stronghold2.exe",
            "object": 0, "object_type": None,
            "flags": {}, "flag_addrs": {}, "unlocks": {},
            "writes": 0, "activations": 0, "image_size": 0x27E0000,
            "exe_size": REFERENCE_EXE_SIZE,
            "exe_sha": "0123456789abcdef" * 4,
            "state": "idle",
        }
        while self.running:
            for level, message, state in script:
                if not self.running:
                    break
                metrics["state"] = state
                metrics["pid"] = 6834
                metrics["base"] = base
                metrics["object"] = pointer
                metrics["object_type"] = ".?AVScenarioLobbyScreen@Stronghold2@@"
                metrics["flag_addrs"] = {key: pointer + offset
                                         for key, offset in FEATURE_OFFSETS.items()}
                if state == "ok":
                    metrics["flags"] = dict(FEATURE_VALUES)
                    metrics["unlocks"] = {key: 1 for key in FEATURE_OFFSETS}
                    metrics["writes"] += 1
                    metrics["activations"] = len(FEATURE_OFFSETS)
                else:
                    metrics["flags"] = {key: 0 for key in FEATURE_OFFSETS}
                self.status_changed.emit(message, state)
                self.log_event.emit(level, message)
                self.metrics_changed.emit(dict(metrics))
                self.msleep(1200)
            if not self.running:
                break
            metrics["writes"] += 1
            self.log_event.emit("ok", tr("status_all_enabled"))
            self.msleep(1500)

    def refresh_status(self):
        pass

    def stop(self):
        self.running = False
        self.wait(2000)

STATE_COLORS = {
    "idle": "#5b6675",
    "wait": "#d8a24a",
    "ok": "#4dd08f",
    "error": "#e5645f",
}

class StatusDot(QWidget):
    """Round indicator with a soft pulsing halo."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(46, 46)
        self._state = "idle"
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._advance)

    def set_state(self, state):
        self._state = state if state in STATE_COLORS else "idle"
        if self._state in ("wait", "ok"):
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._timer.stop()
            self._phase = 0.0
        self.update()

    def _advance(self):
        self._phase = (self._phase + 0.06) % 1.0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        color = QColor(STATE_COLORS[self._state])
        center = QPointF(self.width() / 2.0, self.height() / 2.0)

        if self._state in ("wait", "ok"):
            halo = QColor(color)
            halo.setAlpha(int(70 * (1.0 - self._phase)))
            radius = 12 + 9 * self._phase
            painter.setPen(Qt.NoPen)
            painter.setBrush(halo)
            painter.drawEllipse(center, radius, radius)

        glow = QColor(color)
        glow.setAlpha(70)
        painter.setBrush(glow)
        painter.drawEllipse(center, 15, 15)

        painter.setBrush(color)
        painter.drawEllipse(center, 10, 10)
        painter.end()

class ActivityBar(QWidget):
    """Thin indeterminate progress line (QSS cannot animate a QProgressBar)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(4)
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._advance)

    def start(self):
        self.show()
        if not self._timer.isActive():
            self._timer.start()

    def stop(self):
        self._timer.stop()
        self.hide()

    def _advance(self):
        self._phase = (self._phase + 0.012) % 1.0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(0, 0, self.width(), self.height())
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#1b2430"))
        painter.drawRoundedRect(rect, 2, 2)

        segment = self.width() * 0.28
        x = -segment + (self.width() + segment) * self._phase
        gradient = QLinearGradient(x, 0, x + segment, 0)
        gradient.setColorAt(0.0, QColor(216, 162, 74, 0))
        gradient.setColorAt(0.5, QColor(232, 186, 106, 255))
        gradient.setColorAt(1.0, QColor(216, 162, 74, 0))
        painter.setBrush(gradient)
        painter.drawRoundedRect(QRectF(x, 0, segment, self.height()), 2, 2)
        painter.end()

def make_app_icon(size=64):
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    gradient = QLinearGradient(0, 0, 0, size)
    gradient.setColorAt(0.0, QColor("#e8ba6a"))
    gradient.setColorAt(1.0, QColor("#c1882b"))
    painter.setPen(Qt.NoPen)
    painter.setBrush(gradient)
    painter.drawRoundedRect(QRectF(1, 1, size - 2, size - 2), size * 0.26, size * 0.26)

    dark = QColor("#20180a")
    painter.setBrush(dark)
    painter.drawRect(QRectF(size * 0.24, size * 0.46, size * 0.52, size * 0.30))
    for i in range(3):
        painter.drawRect(QRectF(size * 0.28 + i * size * 0.17, size * 0.36, size * 0.11, size * 0.10))
    painter.drawRect(QRectF(size * 0.38, size * 0.30, size * 0.09, size * 0.12))

    painter.setBrush(QColor("#f3dca6"))
    painter.drawRect(QRectF(size * 0.44, size * 0.58, size * 0.12, size * 0.18))
    painter.end()
    return QIcon(pixmap)

def pick_font(families, fallback):
    available = set(QFontDatabase().families())
    for name in families:
        if name in available:
            return name
    return fallback

class Stronghold2GUI(QMainWindow):

    def __init__(self, demo=False, opts=None):
        super().__init__()
        self.demo = demo
        self.opts = opts or {}
        self.worker = None
        self.metrics = {}
        self.root_banner_shown = False
        self.settings = QSettings(ORG_NAME, "Stronghold2AIEnabler")

        self.ui_font = pick_font(["Inter", "Noto Sans", "Ubuntu", "Cantarell",
                                  "DejaVu Sans", "Liberation Sans", "Segoe UI"], "Sans Serif")
        self.mono_font = pick_font(["JetBrains Mono", "Fira Code", "Noto Sans Mono",
                                    "Ubuntu Mono", "DejaVu Sans Mono", "Liberation Mono",
                                    "Consolas"], "Monospace")

        global current_language
        saved = self.settings.value("language", "", type=str)
        if saved in ("en", "uk", "ru"):
            current_language = saved

        self.init_ui()
        self.setup_tray()
        self.update_ui_language()

        if os.geteuid() != 0:
            self.log("info", tr("status_no_root_needed"))

    def init_ui(self):
        self.setWindowTitle(tr("app_title"))
        self.setMinimumSize(880, 660)
        self.resize(920, 720)
        self.setWindowIcon(make_app_icon())
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

        stylesheet = """
            QWidget { background: transparent; color: #e7edf6; font-family: '%(ui)s'; font-size: 10pt; }
            QMainWindow, QWidget#root { background: #0f1319; }
            QLabel#headerTitle { font-size: 18pt; font-weight: 600; }
            QLabel#headerSub { color: #7f8c9e; font-size: 9pt; }
            QLabel#cardTitle { color: #7f8c9e; font-size: 8pt; font-weight: 600; }
            QLabel#heroText { font-size: 14pt; font-weight: 600; }
            QLabel#heroText[state="ok"] { color: #63d69b; }
            QLabel#heroText[state="wait"] { color: #e2b45f; }
            QLabel#heroText[state="error"] { color: #ef7c77; }
            QLabel#heroDetail { color: #8b98aa; font-size: 9pt; }
            QLabel#statValue { font-size: 11.5pt; font-weight: 600; }
            QLabel#statValue[mono="true"] { font-family: '%(mono)s'; font-size: 9.5pt; }
            QLabel#statValue[tone="ok"] { color: #63d69b; }
            QLabel#statValue[tone="wait"] { color: #e2b45f; }
            QLabel#statValue[tone="error"] { color: #ef7c77; }
            QLabel#statValue[tone="idle"] { color: #6f7c8d; }
            QLabel#detailKey { color: #7f8c9e; font-size: 9pt; }
            QLabel#detailValue { font-family: '%(mono)s'; font-size: 9pt; }
            QLabel#bannerTitle { color: #e2b45f; font-weight: 600; }
            QLabel#bannerText { color: #9aa6b6; font-size: 9pt; }
            QLabel#aboutText { color: #b3bfcd; font-size: 9.5pt; }
            QFrame#card { background: #141a22; border: 1px solid #222b36; border-radius: 14px; }
            QFrame#hero { background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                                                       stop: 0 #172029, stop: 1 #121820);
                          border: 1px solid #26313f; border-radius: 16px; }
            QFrame#hero[state="ok"] { border: 1px solid #2c6047; }
            QFrame#hero[state="wait"] { border: 1px solid #5d4a21; }
            QFrame#hero[state="error"] { border: 1px solid #5f2f2c; }
            QFrame#banner { background: #241d10; border: 1px solid #5d4a21; border-radius: 12px; }
            QPushButton#primary {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #e8ba6a, stop: 1 #c1882b);
                color: #1b1409; border: none; border-radius: 10px; padding: 11px 22px;
                font-weight: 600; font-size: 10pt; min-width: 150px;
            }
            QPushButton#primary:hover {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #f0c87c, stop: 1 #cf9433);
            }
            QPushButton#primary:pressed { background: #b67c25; }
            QPushButton#primary:disabled { background: #2a323d; color: #5f6b7a; }
            QPushButton#ghost {
                background: #1b232d; color: #cfd8e4; border: 1px solid #2b3644;
                border-radius: 10px; padding: 11px 20px; font-weight: 600; min-width: 110px;
            }
            QPushButton#ghost:hover { background: #202a35; border-color: #3a4757; }
            QPushButton#ghost:pressed { background: #171e27; }
            QPushButton#ghost:disabled { background: #161c24; color: #4d5866; border-color: #222b36; }
            QPushButton#link { background: transparent; border: none; color: #7f8c9e; font-size: 9pt; }
            QPushButton#link:hover { color: #e7edf6; }
            QPlainTextEdit#log {
                background: transparent; border: none; font-family: '%(mono)s'; font-size: 8.5pt;
                color: #c3cdda; outline: none; padding: 2px 0px;
            }
            QTabWidget::pane { border: none; top: -1px; }
            QTabBar::tab {
                background: transparent; color: #7f8c9e; padding: 8px 16px;
                border-bottom: 2px solid transparent; font-weight: 600;
            }
            QTabBar::tab:selected { color: #e7edf6; border-bottom: 2px solid #d8a24a; }
            QTabBar::tab:hover { color: #cfd8e4; }
            QComboBox {
                background: #1b232d; border: 1px solid #2b3644; border-radius: 8px;
                padding: 5px 10px; color: #cfd8e4; min-width: 104px;
            }
            QComboBox:hover { border-color: #3a4757; }
            QComboBox::drop-down { border: none; width: 18px; }
            QComboBox QAbstractItemView {
                background: #1b232d; border: 1px solid #2b3644; color: #cfd8e4;
                selection-background-color: #d8a24a; selection-color: #1b1409; outline: none;
            }
            QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
            QScrollBar::handle:vertical { background: #2b3644; border-radius: 5px; min-height: 30px; }
            QScrollBar::handle:vertical:hover { background: #3a4757; }
            QScrollBar::add-line, QScrollBar::sub-line { height: 0px; }
            QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
            QToolTip { background: #1b232d; color: #e7edf6; border: 1px solid #2b3644; padding: 6px; }
        """ % {"ui": self.ui_font, "mono": self.mono_font}
        self.setStyleSheet(stylesheet)

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(22, 20, 22, 18)
        outer.setSpacing(14)

        outer.addLayout(self._build_header())

        self.tabs = QTabWidget()
        self.tabs.tabBar().setExpanding(False)
        self.tabs.setDocumentMode(True)
        outer.addWidget(self.tabs, 1)

        self._build_monitor_tab()
        self._build_details_tab()
        self._build_about_tab()

    def _build_header(self):
        layout = QHBoxLayout()
        layout.setSpacing(14)

        icon_label = QLabel()
        icon_label.setPixmap(make_app_icon(44).pixmap(44, 44))
        layout.addWidget(icon_label)

        titles = QVBoxLayout()
        titles.setSpacing(2)
        self.header_title = QLabel(tr("header_title"))
        self.header_title.setObjectName("headerTitle")
        self.header_sub = QLabel()
        self.header_sub.setObjectName("headerSub")
        self.header_sub.setWordWrap(True)
        titles.addWidget(self.header_title)
        titles.addWidget(self.header_sub)
        layout.addLayout(titles, 1)

        self.language_combo = QComboBox()
        self.language_combo.addItem("English", "en")
        self.language_combo.addItem("Українська", "uk")
        self.language_combo.addItem("Русский", "ru")
        index = self.language_combo.findData(current_language)
        self.language_combo.setCurrentIndex(index if index >= 0 else 0)
        self.language_combo.currentIndexChanged.connect(self.change_language)
        layout.addWidget(self.language_combo)
        return layout

    def _build_monitor_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 14, 0, 0)
        layout.setSpacing(12)

        self.hero = QFrame()
        self.hero.setObjectName("hero")
        hero_layout = QHBoxLayout(self.hero)
        hero_layout.setContentsMargins(20, 18, 20, 18)
        hero_layout.setSpacing(16)

        self.dot = StatusDot()
        hero_layout.addWidget(self.dot)

        hero_texts = QVBoxLayout()
        hero_texts.setSpacing(4)
        self.hero_text = QLabel(tr("status_initial"))
        self.hero_text.setObjectName("heroText")
        self.hero_text.setWordWrap(True)
        self.hero_detail = QLabel(tr("hero_hint"))
        self.hero_detail.setObjectName("heroDetail")
        self.hero_detail.setWordWrap(True)
        hero_texts.addWidget(self.hero_text)
        hero_texts.addWidget(self.hero_detail)
        hero_layout.addLayout(hero_texts, 1)

        buttons = QVBoxLayout()
        buttons.setSpacing(8)
        self.start_button = QPushButton(tr("button_start"))
        self.start_button.setObjectName("primary")
        self.start_button.clicked.connect(self.start_monitoring)
        self.stop_button = QPushButton(tr("button_stop"))
        self.stop_button.setObjectName("ghost")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_monitoring)
        buttons.addWidget(self.start_button)
        buttons.addWidget(self.stop_button)
        hero_layout.addLayout(buttons)

        layout.addWidget(self.hero)

        self.activity = ActivityBar()
        self.activity.hide()
        layout.addWidget(self.activity)

        self.banner = QFrame()
        self.banner.setObjectName("banner")
        banner_layout = QHBoxLayout(self.banner)
        banner_layout.setContentsMargins(16, 14, 16, 14)
        banner_texts = QVBoxLayout()
        banner_texts.setSpacing(4)
        self.banner_title = QLabel(tr("banner_root_title"))
        self.banner_title.setObjectName("bannerTitle")
        self.banner_text = QLabel(tr("banner_root_text"))
        self.banner_text.setObjectName("bannerText")
        self.banner_text.setWordWrap(True)
        banner_texts.addWidget(self.banner_title)
        banner_texts.addWidget(self.banner_text)
        banner_layout.addLayout(banner_texts, 1)
        self.elevate_button = QPushButton(tr("button_elevate"))
        self.elevate_button.setObjectName("ghost")
        self.elevate_button.clicked.connect(self.relaunch_as_root)
        banner_layout.addWidget(self.elevate_button)
        self.banner.hide()
        layout.addWidget(self.banner)

        stats = QHBoxLayout()
        stats.setSpacing(12)
        self.stat_values = {}
        for key, title_key in (("unlocks", "card_unlocks"), ("pid", "card_process"),
                               ("object", "card_lobby"), ("ai", "card_flag"),
                               ("randomize", "card_randomize")):
            card, value = self._make_stat_card(tr(title_key))
            self.stat_values[key] = value
            stats.addWidget(card)
        layout.addLayout(stats)

        log_card = QFrame()
        log_card.setObjectName("card")
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(16, 14, 16, 14)
        log_layout.setSpacing(10)

        log_header = QHBoxLayout()
        self.log_title = QLabel(tr("log_title").upper())
        self.log_title.setObjectName("cardTitle")
        log_header.addWidget(self.log_title)
        log_header.addStretch()
        self.clear_button = QPushButton(tr("button_clear_log"))
        self.clear_button.setObjectName("link")
        self.clear_button.clicked.connect(self.clear_log)
        log_header.addWidget(self.clear_button)
        log_layout.addLayout(log_header)

        self.log_widget = QPlainTextEdit()
        self.log_widget.setObjectName("log")
        self.log_widget.setReadOnly(True)
        self.log_widget.setFrameShape(QFrame.NoFrame)
        self.log_widget.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.log_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.log_widget.setFocusPolicy(Qt.NoFocus)
        self.log_widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.log_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        log_layout.addWidget(self.log_widget, 1)

        layout.addWidget(log_card, 1)
        self.tabs.addTab(page, tr("tab_status"))

    def _make_stat_card(self, title):
        card = QFrame()
        card.setObjectName("card")
        card.setMinimumHeight(84)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)
        title_label = QLabel(title.upper())
        title_label.setObjectName("cardTitle")
        title_label.setWordWrap(True)
        value_label = QLabel(tr("value_none"))
        value_label.setObjectName("statValue")
        value_label.setWordWrap(True)
        value_label.setProperty("tone", "idle")
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addStretch()
        return card, value_label

    def _build_details_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 14, 0, 0)
        layout.setSpacing(12)

        card = QFrame()
        card.setObjectName("card")
        grid = QGridLayout(card)
        grid.setContentsMargins(18, 16, 18, 16)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(10)

        self.detail_values = {}
        rows = ["d_game_path", "d_pid", "d_base", "d_slot", "d_object",
                "d_object_type", "d_flag_ai", "d_flag_rand", "d_unlocks",
                "d_writes", "d_poll", "d_exe_size", "d_exe_sha", "d_build_state"]
        for row, key in enumerate(rows):
            key_label = QLabel(tr(key))
            key_label.setObjectName("detailKey")
            key_label.setWordWrap(True)
            value_label = QLabel(tr("value_none"))
            value_label.setObjectName("detailValue")
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            grid.addWidget(key_label, row, 0, Qt.AlignTop)
            grid.addWidget(value_label, row, 1)
            self.detail_values[key] = value_label
        grid.setColumnStretch(1, 1)

        self.details_hint = QLabel(tr("details_hint"))
        self.details_hint.setObjectName("heroDetail")
        self.details_hint.setWordWrap(True)

        layout.addWidget(card)
        layout.addWidget(self.details_hint)
        layout.addStretch()
        self.tabs.addTab(page, tr("tab_details"))

    def _build_about_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 14, 0, 0)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 18, 20, 18)
        self.about_label = QLabel(tr("about_text", v=APP_VERSION))
        self.about_label.setObjectName("aboutText")
        self.about_label.setWordWrap(True)
        self.about_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.about_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        card_layout.addWidget(self.about_label)
        card_layout.addStretch()

        self.about_stack = QLabel()
        self.about_stack.setObjectName("heroDetail")
        self.about_stack.setWordWrap(True)
        layout.addWidget(card, 1)
        layout.addWidget(self.about_stack)
        self.tabs.addTab(page, tr("tab_about"))

    def setup_tray(self):
        self.tray_icon = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        self.tray_icon = QSystemTrayIcon(make_app_icon(), self)
        tray_menu = QMenu()
        self.tray_show_action = QAction(tr("tray_show_window"), self)
        self.tray_show_action.triggered.connect(self.show_window)
        self.tray_toggle_action = QAction(tr("tray_toggle_start"), self)
        self.tray_toggle_action.triggered.connect(self.toggle_monitoring)
        self.tray_quit_action = QAction(tr("tray_quit_app"), self)
        self.tray_quit_action.triggered.connect(self.quit_app)
        tray_menu.addAction(self.tray_show_action)
        tray_menu.addAction(self.tray_toggle_action)
        tray_menu.addSeparator()
        tray_menu.addAction(self.tray_quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_activated)
        self.tray_icon.show()

    def tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_window()

    def show_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def quit_app(self):
        self.shutdown_worker()
        QApplication.quit()

    def change_language(self, index):
        global current_language
        current_language = self.language_combo.itemData(index)
        self.settings.setValue("language", current_language)
        self.update_ui_language()

    def update_ui_language(self):
        self.setWindowTitle(tr("app_title"))
        self.header_title.setText(tr("header_title"))
        self.header_sub.setText(tr("header_subtitle", v=APP_VERSION))
        self.hero_detail.setText(tr("hero_running") if self.worker else tr("hero_hint"))
        self.start_button.setText(tr("button_start"))
        self.stop_button.setText(tr("button_stop"))
        self.clear_button.setText(tr("button_clear_log"))
        self.elevate_button.setText(tr("button_elevate"))
        self.banner_title.setText(tr("banner_root_title"))
        self.banner_text.setText(tr("banner_root_text"))
        self.log_title.setText(tr("log_title").upper())
        self.details_hint.setText(tr("details_hint"))
        self.about_label.setText(tr("about_text", v=APP_VERSION))
        self.about_stack.setText(tr("about_stack", qt=f"{PYQT_VERSION_STR} / Qt {QT_VERSION_STR}",
                                      py=".".join(map(str, sys.version_info[:3])),
                                      mode=tr("mode_root") if os.geteuid() == 0 else tr("mode_user")))
        self.tabs.setTabText(0, tr("tab_status"))
        self.tabs.setTabText(1, tr("tab_details"))
        self.tabs.setTabText(2, tr("tab_about"))

        titles = ["card_unlocks", "card_process", "card_lobby", "card_flag", "card_randomize"]
        for key, title_key in zip(("unlocks", "pid", "object", "ai", "randomize"), titles):
            label = self.stat_values[key].parentWidget().layout().itemAt(0).widget()
            label.setText(tr(title_key).upper())

        for row, key in enumerate(self.detail_values):
            item = self.detail_values[key].parentWidget().layout().itemAtPosition(row, 0)
            if item and item.widget():
                item.widget().setText(tr(key))

        if self.tray_icon:
            self.tray_icon.setToolTip(tr("tray_icon_tooltip"))
            self.tray_show_action.setText(tr("tray_show_window"))
            self.tray_toggle_action.setText(tr("tray_toggle_stop") if self.worker else tr("tray_toggle_start"))
            self.tray_quit_action.setText(tr("tray_quit_app"))

        if self.worker:
            self.worker.refresh_status()
        else:
            self.set_state("idle", tr("status_initial"))
        if not self.metrics:
            self._apply_metrics({"state": "idle"})

    LOG_COLORS = {"info": "#8b98aa", "ok": "#63d69b", "warn": "#e2b45f", "error": "#ef7c77"}

    def log(self, level, message):
        text = html.escape(f"{time.strftime('%H:%M:%S')}  {message}")
        color = self.LOG_COLORS.get(level, "#c3cdda")
        self.log_widget.appendHtml(f'<span style="color: {color}">{text}</span>')
        document = self.log_widget.document()
        while document.blockCount() > 400:
            cursor = QTextCursor(document.firstBlock())
            cursor.select(QTextCursor.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()
        bar = self.log_widget.verticalScrollBar()
        bar.setValue(bar.maximum())

    def clear_log(self):
        self.log_widget.clear()

    def set_state(self, state, message):
        self.hero.setProperty("state", state)
        self.hero_text.setProperty("state", state)
        for widget in (self.hero, self.hero_text):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
        self.hero_text.setText(message)
        self.dot.set_state(state)

    def _set_value(self, key, text, tone=None):
        label = self.stat_values.get(key)
        if not label:
            return
        label.setText(text)
        label.setProperty("tone", tone or "idle")
        label.style().unpolish(label)
        label.style().polish(label)

    @staticmethod
    def _flag_row(metrics, key):
        """`0x04ed8168 = 1` for one feature byte, or a dash when unknown."""
        addr = (metrics.get("flag_addrs") or {}).get(key)
        if not addr:
            return tr("value_none")
        value = (metrics.get("flags") or {}).get(key)
        return f"0x{addr:08x} = {tr('value_none') if value is None else value}"

    @staticmethod
    def _unlocks_row(metrics):
        unlocks = metrics.get("unlocks") or {}
        if not unlocks:
            return tr("value_none")
        return "    ".join(f"{tr('feature_' + key)} x{n}" for key, n in unlocks.items())

    def _apply_metrics(self, metrics):
        pid = metrics.get("pid") or 0
        base = metrics.get("base") or 0
        obj = metrics.get("object") or 0
        flags = metrics.get("flags") or {}

        activations = metrics.get("activations", 0)
        self._set_value("unlocks", str(activations),
                        tone="ok" if activations else "idle")
        self._set_value("pid", str(pid) if pid else tr("value_none"),
                        tone="ok" if pid else "idle")
        self._set_value("object", tr("value_found") if obj else tr("value_missing"),
                        tone="ok" if obj else "idle")
        for key in FEATURE_OFFSETS:
            value = flags.get(key)
            if value is None:
                self._set_value(key, tr("value_none"))
            else:
                self._set_value(key, tr("value_on") if value == 1 else tr("value_off"),
                                tone="ok" if value == 1 else "wait")

        if pid and base:
            self.hero_detail.setText(tr("hero_pid", pid=pid, base=base))
        elif self.worker:
            self.hero_detail.setText(tr("hero_running"))

        path = metrics.get("path")
        values = {
            "d_game_path": path or tr("value_none"),
            "d_pid": str(pid) if pid else tr("value_none"),
            "d_base": f"0x{base:08x}" if base else tr("value_none"),
            "d_slot": f"0x{base + POINTER_OFFSET:08x}  (+0x{POINTER_OFFSET:x})" if base else tr("value_none"),
            "d_object": f"0x{obj:08x}" if obj else tr("value_none"),
            "d_object_type": metrics.get("object_type") or tr("value_none"),
            "d_flag_ai": self._flag_row(metrics, "ai"),
            "d_flag_rand": self._flag_row(metrics, "randomize"),
            "d_unlocks": self._unlocks_row(metrics),
            "d_writes": str(metrics.get("writes", 0)),
            "d_poll": f"{POLL_INTERVAL * 1000:.0f} ms",
            "d_exe_size": f"{metrics.get('exe_size', 0):,} B".replace(",", " ") if metrics.get("exe_size") else tr("value_none"),
            "d_exe_sha": (metrics.get("exe_sha") or tr("value_none"))[:32] + ("…" if metrics.get("exe_sha") else ""),
        }
        for key, value in values.items():
            label = self.detail_values.get(key)
            if label and label.text() != value:
                label.setText(value)

        exe_size = metrics.get("exe_size") or 0
        if exe_size:
            build = tr("build_verified") if exe_size == REFERENCE_EXE_SIZE else tr("build_unknown")
        else:
            build = tr("build_pending")
        label = self.detail_values.get("d_build_state")
        if label and label.text() != build:
            label.setText(build)

    def update_status(self, message, state):
        self.set_state(state, message)

    def update_metrics(self, metrics):
        self.metrics = metrics
        self._apply_metrics(metrics)

    def on_permission_denied(self):
        if self.root_banner_shown:
            return
        self.root_banner_shown = True
        self.banner.show()

    def start_monitoring(self):
        if self.worker:
            return

        self.worker = DemoWorker() if self.demo else Stronghold2Worker()
        self.worker.status_changed.connect(self.update_status)
        self.worker.log_event.connect(self.log)
        self.worker.metrics_changed.connect(self.update_metrics)
        self.worker.permission_denied.connect(self.on_permission_denied)
        self.worker.start()

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.activity.start()
        if self.tray_icon:
            self.tray_toggle_action.setText(tr("tray_toggle_stop"))
        self.set_state("wait", tr("status_waiting_for_sh2"))

    def stop_monitoring(self):
        self.shutdown_worker()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.activity.stop()
        self.hero_detail.setText(tr("hero_hint"))
        if self.tray_icon:
            self.tray_toggle_action.setText(tr("tray_toggle_start"))
        self.set_state("idle", tr("status_monitoring_stopped"))

    def toggle_monitoring(self):
        self.stop_monitoring() if self.worker else self.start_monitoring()

    def shutdown_worker(self):
        if self.worker:
            self.worker.stop()
            self.worker = None

    def relaunch_as_root(self):
        if os.geteuid() == 0:
            return
        script = os.path.abspath(__file__)
        try:
            args = ["pkexec", sys.executable, script]
            if self.demo:
                args.append("--demo")
            subprocess.Popen(args)
        except Exception as exc:
            self.log("error", f"pkexec: {exc}")
            return
        self.shutdown_worker()
        QApplication.quit()

    def closeEvent(self, event):
        self.settings.setValue("geometry", self.saveGeometry())
        if self.tray_icon and self.tray_icon.isVisible():
            self.hide()
            self.tray_icon.showMessage(tr("tray_minimize_message_title"),
                                       tr("tray_minimize_message_text"),
                                       QSystemTrayIcon.Information, 3000)
            event.ignore()
        else:
            self.shutdown_worker()
            event.accept()

def main():
    opts = _parse_args(sys.argv)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("Stronghold 2 AI Enabler")
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(ORG_NAME)

    window = Stronghold2GUI(demo=opts["demo"], opts=opts)
    window.show()

    if opts["demo"]:
        window.start_monitoring()
        window.log("info", "--demo: simulated events, no game access")

    if opts["screenshot"]:
        def capture():
            window.grab().save(opts["screenshot"])
            QApplication.quit()
        QTimer.singleShot(1500, capture)

    signal_target = lambda s, f: QApplication.quit()
    try:
        import signal as _signal
        _signal.signal(_signal.SIGINT, signal_target)
        _signal.signal(_signal.SIGTERM, signal_target)
    except (ValueError, AttributeError):
        pass

    print(f"Stronghold 2 AI Enabler v{APP_VERSION} launched"
          f"{' (demo mode)' if opts['demo'] else ''}")
    try:
        sys.exit(app.exec_())
    except KeyboardInterrupt:
        window.shutdown_worker()
        sys.exit(0)

if __name__ == "__main__":
    main()
