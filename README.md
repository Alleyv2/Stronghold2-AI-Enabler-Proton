# Stronghold 2 AI Enabler for Proton

**Version 3** · see [CHANGELOG_v3.md](CHANGELOG_v3.md) for the full list of changes since v2

<img width="699" height="556" alt="Stronghold 2 AI Enabler" src="https://github.com/user-attachments/assets/cd010b4e-37a3-46d8-b098-88ebd468af0b" />

Enables AI (bots) in Stronghold 2 multiplayer games on Linux running under Proton. The tool
detects the game process, verifies the target object, and holds the lobby flags that allow
adding bots. It works purely in memory, the game files on disk are never modified.

Built with Python 3 and PyQt5. Memory access normally works unprivileged when the game runs
under the same user as the tool, which is the usual case for a Steam/Proton launch. Elevation
is requested only if the kernel denies access, and only by an explicit user action.

> **Note:** use only `stronghold2_patcher_v3.py`. The older `stronghold2_patcher.py` is kept for
> history and is not the version described here.

---

## Features

* Holds two lobby flags: AI slots (`+0xD28`) and Randomize Players (`+0x1790`).
* **RTTI verification:** bytes are written only if the object really is
  `ScenarioLobbyScreen@Stronghold2`.
* **Image validation:** the base is taken from the mapping with file offset 0, the `MZ` /
  `PE\0\0` signatures are checked, `SizeOfImage` is read, and every followed address must fall
  inside the image.
* The target range must be **writable** before any write.
* **Writes only when necessary:** a byte is written only when it does not already hold the
  wanted value, so there is no rewriting in a loop.
* **Memory write counter** is shown, so you can see what the tool is actually doing.
* The pointer is re-read every cycle (4 times per second) to survive lobby object recreation.
* **Build fingerprint:** size and SHA-256 of `Stronghold2.exe` are compared against the
  verified build (14 208 000 bytes).
* Event log with levels (`info` / `ok` / `warn` / `error`), 400-line cap, rate-limited
  duplicates.
* Tray menu can start and stop monitoring.
* Interface language and window size are remembered between runs (`QSettings`).
* Developer flags: `--demo` and `--screenshot out.png`.

---

## Instructions

### English

#### 1. Prerequisites

* `python3` (`pip` only if you install PyQt5 manually).
* `PyQt5`. If missing, the script will try to install it via your distribution's package
  manager (pacman, apt, dnf, zypper).
* No root needed at start-up. If the kernel denies memory access, the tool will offer to
  elevate.

#### 2. How to run

1. Clone the repository or save the script as `stronghold2_patcher_v3.py`.
2. Open a terminal in that directory.
3. Make it executable:

   ```bash
   chmod +x stronghold2_patcher_v3.py
   ```

4. Run it:

   ```bash
   ./stronghold2_patcher_v3.py
   ```

#### 3. Using the application

1. Launch Stronghold 2 through Proton on Steam.
2. Start the tool. The status shows that it is searching for the game.
3. When the game is found, the status changes to `Stronghold 2 found (PID 6834)`.
4. Open the multiplayer lobby screen. Only then does the lobby object appear: the status
   changes to `Lobby screen detected — unlocking AI and Randomize…`, and the AI slot selector
   (sword + helmet + shield icon) and the Randomize Players dice become available in the
   lobby itself.
5. Once both flags are held, the status shows
   `AI slots and Randomize Players are available`.
6. The window can be minimized to the system tray, where monitoring continues. Start and stop
   are available from the tray menu.

### Русский

#### 1. Требования

* `python3` (`pip` — только если ставите PyQt5 вручную).
* `PyQt5`. Если библиотеки нет, скрипт попробует установить её через пакетный менеджер
  вашего дистрибутива (pacman, apt, dnf, zypper).
* Права root при запуске не нужны. Если ядро откажет в доступе к памяти, утилита предложит
  повысить права.

#### 2. Как запустить

1. Склонируйте репозиторий или сохраните скрипт как `stronghold2_patcher_v3.py`.
2. Откройте терминал в этой папке.
3. Сделайте скрипт исполняемым:

   ```bash
   chmod +x stronghold2_patcher_v3.py
   ```

4. Запустите:

   ```bash
   ./stronghold2_patcher_v3.py
   ```

#### 3. Использование

1. Запустите Stronghold 2 через Proton в Steam.
2. Откройте утилиту. Статус покажет, что идёт поиск игры.
3. Когда игра найдена, статус сменится на `Stronghold 2 найден (PID 6834)`.
4. Откройте экран многопользовательского лобби. Только тогда появится объект лобби: статус
   сменится на `Экран лобби обнаружен — открываю AI и рандом…`, а в самом лобби станут
   доступны выбор AI-слотов (иконка меч + шлем + щит) и кубик «Randomize Players».
5. Когда оба флага удерживаются, статус покажет
   `Слоты AI и случайное распределение доступны`.
6. Окно можно свернуть в системный трей, мониторинг продолжится. Старт и стоп доступны из
   меню трея.

---

## Troubleshooting

Status messages are shown in the language selected in the tool, so both spellings are listed
below.

### English

| Status | What to do |
| --- | --- |
| `Lobby object is not available yet` | Normal while the lobby is not open. The tool keeps retrying every 250 ms. |
| `Permission denied while accessing game memory` | Click **Restart with admin rights** in the banner. |
| `Unexpected object at the pointer — offsets may not fit this build` | A different build of the game; the offsets have to be re-verified. |
| `AI slots and Randomize Players are available` | Everything worked. |

### Русский

| Статус | Что делать |
| --- | --- |
| `Объект лобби пока недоступен` | Нормально, пока лобби не открыто. Попытки повторяются каждые 250 мс. |
| `Нет доступа к памяти игры` | Нажмите «Перезапустить с правами администратора» в баннере. |
| `Неожиданный объект по указателю — офсеты могут не подойти этой сборке` | Другая сборка игры, офсеты надо проверять. |
| `Слоты AI и случайное распределение доступны` | Всё сработало. |

If something still does not work, attach a screenshot of the **Game** tab (addresses, RTTI
class, flag values, build fingerprint) to the issue — it contains everything needed to see why
the tool refused to write. При проблемах приложите к issue скриншот вкладки **Игра** (адреса,
класс объекта по RTTI, значения флагов, отпечаток сборки).

---

## Notes

* Verified build: Steam PE32 `Stronghold2.exe`, size 14 208 000 B, image `0x00400000`,
  pointer `base + 0x00EC5F28`.
* Only two bytes are ever written inside the verified lobby object: `+0xD28` (AI slots) and
  `+0x1790` (Randomize Players).
* A different build of `Stronghold2.exe` may need new offsets. The fingerprint check reports a
  mismatch as soon as it is detected.
* The game files on disk are never modified.

Developed by Alley
