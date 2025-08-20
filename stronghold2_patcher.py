#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import struct
import subprocess
import signal
import threading

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

if not check_and_install_pyqt5():
    sys.exit(1)

try:
    from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                                QHBoxLayout, QLabel, QPushButton, QTextEdit,
                                QFrame, QSystemTrayIcon, QMenu, QAction,
                                QMessageBox, QTabWidget, QComboBox)
    from PyQt5.QtCore import QTimer, QThread, pyqtSignal, Qt, QSize
    from PyQt5.QtGui import QFont, QIcon, QPixmap, QPainter, QColor, QPalette
except ImportError as e:
    print(f"PyQt5 import error: {e}")
    print("Try: sudo pip3 install PyQt5")
    sys.exit(1)

MODULE_NAME = "Stronghold2.exe"
POINTER_OFFSET = 0x00ec5f28
ADDRESS_OFFSET = 0xd28
A_BYTES = 4
V_BYTES = 1

class Stronghold2Worker(QThread):

    status_changed = pyqtSignal(str, bool)
    ai_enabled = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.running = False
        self.shpid = 0
        self.ai_address = 0

    def find_stronghold_pid(self):
        try:
            result = subprocess.run(['pgrep', '-f', 'Stronghold2.exe'],
                                  capture_output=True, text=True)

            if result.returncode == 0:
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    if pid.strip().isdigit():
                        pid_int = int(pid.strip())
                        if os.path.exists(f"/proc/{pid_int}"):
                            return pid_int
            return 0
        except Exception:
            return 0

    def get_base_address(self, pid):
        try:
            maps_path = f"/proc/{pid}/maps"
            if not os.path.exists(maps_path):
                return 0

            with open(maps_path, 'r') as f:
                for line in f:
                    if MODULE_NAME in line and 'r-xp' in line:
                        parts = line.split()
                        if parts:
                            addr_range = parts[0].split('-')
                            if len(addr_range) == 2:
                                return int(addr_range[0], 16)
            return 0
        except Exception:
            return 0

    def read_memory(self, pid, address, size):
        try:
            mem_path = f"/proc/{pid}/mem"
            with open(mem_path, 'rb') as mem_file:
                mem_file.seek(address)
                return mem_file.read(size)
        except Exception:
            return None

    def write_memory(self, pid, address, data):
        try:
            mem_path = f"/proc/{pid}/mem"
            with open(mem_path, 'wb') as mem_file:
                mem_file.seek(address)
                mem_file.write(data)
                return True
        except Exception:
            return False

    def get_ai_address(self, pid):
        base_addr = self.get_base_address(pid)
        if not base_addr:
            return 0

        pointer_addr = base_addr + POINTER_OFFSET
        pointer_data = self.read_memory(pid, pointer_addr, A_BYTES)

        if pointer_data and len(pointer_data) == A_BYTES:
            pointer_value = struct.unpack('<I', pointer_data)[0]
            return pointer_value + ADDRESS_OFFSET
        return 0

    def enable_ai(self, pid, address):
        try:
            data = struct.pack('B', 1)
            return self.write_memory(pid, address, data)
        except Exception:
            return False

    def run(self):
        self.running = True

        while self.running:
            current_pid = self.find_stronghold_pid()

            if not current_pid:
                self.status_changed.emit(LANG["status_waiting_for_sh2"][current_language], False)
                self.shpid = 0
                self.ai_address = 0
                time.sleep(2)
                continue

            if current_pid != self.shpid:
                self.shpid = current_pid
                self.ai_address = self.get_ai_address(self.shpid)

                if self.ai_address:
                    self.status_changed.emit(LANG["status_sh2_found"][current_language].format(pid=self.shpid), True)
                else:
                    self.status_changed.emit(LANG["status_failed_to_get_ai_address"][current_language], False)
                    time.sleep(2)
                    continue

            if self.ai_address and self.enable_ai(self.shpid, self.ai_address):
                self.ai_enabled.emit()
            else:
                self.status_changed.emit(LANG["status_error_enabling_ai"][current_language], False)

            time.sleep(1)

    def stop(self):
        self.running = False

LANG = {
    "app_title": {
        "en": "Stronghold 2 AI Enabler v2.0",
        "uk": "Stronghold 2 AI Enabler v2.0",
        "ru": "Stronghold 2 AI Enabler v2.0"
    },
    "tab_status": {
        "en": "Status",
        "uk": "Статус",
        "ru": "Статус"
    },
    "tab_about": {
        "en": "About",
        "uk": "Про програму",
        "ru": "О программе"
    },
    "title_main": {
        "en": "🏰 Stronghold 2 AI Enabler",
        "uk": "🏰 Stronghold 2 AI Enabler",
        "ru": "🏰 Stronghold 2 AI Enabler"
    },
    "status_initial": {
        "en": "🔄 Ready to start",
        "uk": "🔄 Готовий до запуску",
        "ru": "🔄 Готов к запуску"
    },
    "ai_counter": {
        "en": "🤖 AI Activated: {} times",
        "uk": "🤖 AI активовано: {} разів",
        "ru": "🤖 AI активировано: {} раз"
    },
    "button_start": {
        "en": "▶️ Start Monitoring",
        "uk": "▶️ Запустити моніторинг",
        "ru": "▶️ Запустить мониторинг"
    },
    "button_stop": {
        "en": "⏹️ Stop",
        "uk": "⏹️ Зупинити",
        "ru": "⏹️ Остановить"
    },
    "about_text": {
        "en": "This application helps to enable AI (bots) in Stronghold 2 multiplayer games. It monitors the game process and injects the necessary values into memory, allowing you to easily add bots when playing on Linux via Proton.\n\n"
              "Developed by Alley\n"
              "Version: 2.0\n",
        "uk": "Ця програма допомагає увімкнути AI (ботів) у багатокористувацьких іграх Stronghold 2. Вона моніторить ігровий процес та вводить необхідні значення в пам'ять, дозволяючи легко додавати ботів під час гри на Linux через Proton.\n\n"
              "Розроблено Alley\n"
              "Версія: 2.0\n",
        "ru": "Это приложение помогает включить AI (ботов) в многопользовательских играх Stronghold 2. Оно отслеживает игровой процесс и внедряет необходимые значения в память, позволяя легко добавлять ботов при игре на Linux через Proton.\n\n"
              "Разработано Alley\n"
              "Версия: 2.0\n"
    },
    "tray_icon_tooltip": {
        "en": "Stronghold 2 AI Enabler",
        "uk": "Stronghold 2 AI Enabler",
        "ru": "Stronghold 2 AI Enabler"
    },
    "tray_show_window": {
        "en": "Show Window",
        "uk": "Показати вікно",
        "ru": "Показать окно"
    },
    "tray_quit_app": {
        "en": "Exit",
        "uk": "Вихід",
        "ru": "Выход"
    },
    "tray_minimize_message_title": {
        "en": "Stronghold 2 AI Enabler",
        "uk": "Stronghold 2 AI Enabler",
        "ru": "Stronghold 2 AI Enabler"
    },
    "tray_minimize_message_text": {
        "en": "Application minimized to tray. To exit completely, use the tray menu.",
        "uk": "Програма згорнута в трей. Для повного виходу використовуйте меню трею.",
        "ru": "Приложение свёрнуто в трей. Для полного выхода используйте меню трея."
    },
    "status_acquiring_root": {
        "en": "🔐 Acquiring administrator rights...",
        "uk": "🔐 Отримання прав адміністратора...",
        "ru": "🔐 Получение прав администратора..."
    },
    "status_root_error": {
        "en": "❌ Error acquiring root rights: {}",
        "uk": "❌ Помилка отримання прав root: {}",
        "ru": "❌ Ошибка получения прав root: {}"
    },
    "status_root_acquired": {
        "en": "✅ Administrator rights acquired",
        "uk": "✅ Права адміністратора отримано",
        "ru": "✅ Права администратора получены"
    },
    "status_monitoring_stopped": {
        "en": "⏹️ Monitoring stopped",
        "uk": "⏹️ Моніторинг зупинено",
        "ru": "⏹️ Мониторинг остановлен"
    },
    "status_error": {
        "en": "❌ Error: {}",
        "uk": "❌ Помилка: {}",
        "ru": "❌ Ошибка: {}"
    },
    "status_waiting_for_sh2": {
        "en": "🔍 Waiting for Stronghold 2 to start...",
        "uk": "🔍 Очікування запуску Stronghold 2...",
        "ru": "🔍 Ожидание запуска Stronghold 2..."
    },
    "status_sh2_found": {
        "en": "✅ Stronghold 2 found (PID: {pid})",
        "uk": "✅ Stronghold 2 знайдено (PID: {pid})",
        "ru": "✅ Stronghold 2 найден (PID: {pid})"
    },
    "status_failed_to_get_ai_address": {
        "en": "❌ Failed to get AI address",
        "uk": "❌ Не вдалося отримати адресу AI",
        "ru": "❌ Не удалось получить адрес AI"
    },
    "status_error_enabling_ai": {
        "en": "❌ Error enabling AI",
        "uk": "❌ Помилка увімкнення AI",
        "ru": "❌ Ошибка включения AI"
    },
    "status_ai_active": {
        "en": "🤖 AI active in multiplayer!",
        "uk": "🤖 AI активний у мультиплеєрі!",
        "ru": "🤖 AI активен в мультиплеере!"
    },
    "language_label": {
        "en": "Language:",
        "uk": "Мова:",
        "ru": "Язык:"
    }
}

current_language = "en"

class Stronghold2GUI(QMainWindow):

    def __init__(self):
        super().__init__()
        self.worker = None
        self.ai_count = 0
        self.init_ui()
        self.setup_tray()
        self.check_root_privileges()
        self.update_ui_language()

    def init_ui(self):
        self.setWindowTitle(LANG["app_title"][current_language])
        self.setMinimumSize(600, 500)

        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #2c3e50, stop: 1 #34495e);
            }
            QWidget {
                background: transparent;
                color: #ecf0f1;
                font-family: 'Segoe UI', 'Ubuntu', sans-serif;
            }
            QTabWidget::pane {
                border-top: 2px solid #3498db;
                border-radius: 10px;
                background: rgba(44, 62, 80, 0.7);
            }
            QTabBar::tab {
                background: #34495e;
                border: 2px solid #2c3e50;
                border-bottom-color: #3498db;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 10px 15px;
                color: #ecf0f1;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background: #3498db;
                border-color: #3498db;
                border-bottom-color: #3498db;
                margin-bottom: -2px;
            }
            QTabBar::tab:hover {
                background: #3fb4f3;
            }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)

        language_layout = QHBoxLayout()
        self.language_label = QLabel(LANG["language_label"][current_language])
        self.language_label.setStyleSheet("color: #ecf0f1; font-size: 14px;")
        language_layout.addWidget(self.language_label)

        self.language_combo = QComboBox()
        self.language_combo.addItem("English", "en")
        self.language_combo.addItem("Українська", "uk")
        self.language_combo.addItem("Русский", "ru")
        self.language_combo.currentIndexChanged.connect(self.change_language)
        self.language_combo.setCurrentIndex(self.language_combo.findData("en"))

        self.language_combo.setStyleSheet("""
            QComboBox {
                background: #34495e;
                border: 1px solid #2c3e50;
                border-radius: 5px;
                padding: 5px;
                color: #ecf0f1;
                min-width: 100px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: url(data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAcAAAAECAYAAADtTWMxAAAAAXNSR0IArs4c6QAAADFJREFUCJljYGBgeP///38gWzABoGNgYGAg2RkYQPiFgX0Ggg+FGBgQCJtBwAgAUv8F/R0s/WwAAAAASUVORK5CYII=);
                width: 10px;
                height: 10px;
            }
            QComboBox QAbstractItemView {
                background: #34495e;
                border: 1px solid #2c3e50;
                selection-background-color: #3498db;
                color: #ecf0f1;
            }
        """)
        language_layout.addWidget(self.language_combo)
        language_layout.addStretch()
        main_layout.addLayout(language_layout)

        self.tabs = QTabWidget()
        self.tabs.tabBar().setExpanding(True)
        self.tabs.setStyleSheet("""
            QTabWidget {
                border-radius: 10px;
            }
        """)
        main_layout.addWidget(self.tabs)

        self.create_status_tab()
        self.create_about_tab()

        main_layout.addStretch()

    def create_status_tab(self):
        status_tab = QWidget()
        status_layout = QVBoxLayout(status_tab)
        status_layout.setSpacing(25)
        status_layout.setContentsMargins(30, 20, 30, 20)

        self.title_label = QLabel(LANG["title_main"][current_language])
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("""
            QLabel {
                font-size: 28px;
                font-weight: bold;
                color: #3498db;
                padding: 25px;
                border-bottom: 3px solid #3498db;
                margin-bottom: 15px;
                background: rgba(52, 152, 219, 0.1);
                border-radius: 10px;
            }
        """)
        status_layout.addWidget(self.title_label)

        self.status_label = QLabel(LANG["status_initial"][current_language])
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("""
            QLabel {
                background: rgba(149, 165, 166, 0.2);
                border: 2px solid #95a5a6;
                border-radius: 12px;
                padding: 20px;
                font-size: 18px;
                font-weight: bold;
                color: #ecf0f1;
                min-height: 40px;
            }
        """)
        status_layout.addWidget(self.status_label)

        self.counter_label = QLabel(LANG["ai_counter"][current_language].format(self.ai_count))
        self.counter_label.setAlignment(Qt.AlignCenter)
        self.counter_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                color: #bdc3c7;
                padding: 15px;
                background: rgba(127, 140, 141, 0.1);
                border-radius: 8px;
                margin: 10px 0;
            }
        """)
        status_layout.addWidget(self.counter_label)

        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(20)

        self.start_button = QPushButton(LANG["button_start"][current_language])
        self.start_button.clicked.connect(self.start_monitoring)
        self.start_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #27ae60, stop: 1 #2ecc71);
                border: none;
                color: white;
                padding: 15px 25px;
                border-radius: 10px;
                font-size: 16px;
                font-weight: bold;
                min-width: 180px;
                min-height: 50px;
            }
            QPushButton:hover {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #2ecc71, stop: 1 #27ae60);
                transform: translateY(-2px);
            }
            QPushButton:pressed {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #229954, stop: 1 #27ae60);
            }
            QPushButton:disabled {
                background: #7f8c8d;
                color: #bdc3c7;
            }
        """)
        buttons_layout.addWidget(self.start_button)

        self.stop_button = QPushButton(LANG["button_stop"][current_language])
        self.stop_button.clicked.connect(self.stop_monitoring)
        self.stop_button.setEnabled(False)
        self.stop_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #e74c3c, stop: 1 #c0392b);
                border: none;
                color: white;
                padding: 15px 25px;
                border-radius: 10px;
                font-size: 16px;
                font-weight: bold;
                min-width: 180px;
                min-height: 50px;
            }
            QPushButton:hover {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ec7063, stop: 1 #e74c3c);
            }
            QPushButton:pressed {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #c0392b, stop: 1 #a93226);
            }
            QPushButton:disabled {
                background: #7f8c8d;
                color: #bdc3c7;
            }
        """)
        buttons_layout.addWidget(self.stop_button)

        status_layout.addLayout(buttons_layout)
        status_layout.addStretch()

        self.tabs.addTab(status_tab, LANG["tab_status"][current_language])

    def create_about_tab(self):
        about_tab = QWidget()
        about_layout = QVBoxLayout(about_tab)
        about_layout.setSpacing(20)
        about_layout.setContentsMargins(30, 20, 30, 20)

        about_label = QLabel(LANG["about_text"][current_language])
        about_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        about_label.setWordWrap(True)
        about_label.setStyleSheet("""
            QLabel {
                background: rgba(52, 73, 94, 0.4);
                border: 2px solid #5d6d7e;
                border-radius: 12px;
                padding: 20px;
                font-size: 14px;
                color: #bdc3c7;
                line-height: 1.4;
            }
        """)
        about_layout.addWidget(about_label)
        about_layout.addStretch()

        self.tabs.addTab(about_tab, LANG["tab_about"][current_language])
        self.about_label = about_label

    def change_language(self, index):
        global current_language
        current_language = self.language_combo.itemData(index)
        self.update_ui_language()

    def update_ui_language(self):
        self.setWindowTitle(LANG["app_title"][current_language])
        self.language_label.setText(LANG["language_label"][current_language])
        self.title_label.setText(LANG["title_main"][current_language])
        self.status_label.setText(LANG["status_initial"][current_language])
        self.counter_label.setText(LANG["ai_counter"][current_language].format(self.ai_count))
        self.start_button.setText(LANG["button_start"][current_language])
        self.stop_button.setText(LANG["button_stop"][current_language])
        self.about_label.setText(LANG["about_text"][current_language])

        self.tabs.setTabText(0, LANG["tab_status"][current_language])
        self.tabs.setTabText(1, LANG["tab_about"][current_language])

        if hasattr(self, 'tray_icon'):
            self.tray_icon.setToolTip(LANG["tray_icon_tooltip"][current_language])
            tray_menu = self.tray_icon.contextMenu()
            if tray_menu:
                show_action = tray_menu.actions()[0]
                quit_action = tray_menu.actions()[1]
                show_action.setText(LANG["tray_show_window"][current_language])
                quit_action.setText(LANG["tray_quit_app"][current_language])


    def setup_tray(self):
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon = QSystemTrayIcon(self)

            pixmap = QPixmap(32, 32)
            pixmap.fill(QColor(52, 152, 219))
            painter = QPainter(pixmap)
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(pixmap.rect(), Qt.AlignCenter, "SH2")
            painter.end()

            self.tray_icon.setIcon(QIcon(pixmap))
            self.tray_icon.setToolTip(LANG["tray_icon_tooltip"][current_language])

            tray_menu = QMenu()

            show_action = QAction(LANG["tray_show_window"][current_language], self)
            show_action.triggered.connect(self.show_window)
            tray_menu.addAction(show_action)

            quit_action = QAction(LANG["tray_quit_app"][current_language], self)
            quit_action.triggered.connect(self.quit_app)
            tray_menu.addAction(quit_action)

            self.tray_icon.setContextMenu(tray_menu)
            self.tray_icon.activated.connect(self.tray_activated)
            self.tray_icon.show()

    def show_window(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def quit_app(self):
        if self.worker:
            self.worker.stop()
            self.worker.wait()
        QApplication.quit()

    def tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_window()

    def check_root_privileges(self):
        if os.geteuid() != 0:
            self.set_status(LANG["status_acquiring_root"][current_language], False)
            QApplication.processEvents()

            try:
                current_script = os.path.abspath(__file__)
                subprocess.Popen([
                    'pkexec', 'python3', current_script
                ])
                sys.exit(0)
            except Exception as e:
                self.set_status(LANG["status_root_error"][current_language].format(e), False)
        else:
            self.set_status(LANG["status_root_acquired"][current_language], True)

    def set_status(self, message, is_success=None):
        self.status_label.setText(message)

        if is_success is True:
            self.status_label.setStyleSheet("""
                QLabel {
                    background: rgba(39, 174, 96, 0.3);
                    border: 2px solid #27ae60;
                    border-radius: 12px;
                    padding: 20px;
                    font-size: 18px;
                    font-weight: bold;
                    color: #2ecc71;
                    min-height: 40px;
                }
            """)
        elif is_success is False:
            self.status_label.setStyleSheet("""
                QLabel {
                    background: rgba(231, 76, 60, 0.3);
                    border: 2px solid #e74c3c;
                    border-radius: 12px;
                    padding: 20px;
                    font-size: 18px;
                    font-weight: bold;
                    color: #e74c3c;
                    min-height: 40px;
                }
            """)
        else:
            self.status_label.setStyleSheet("""
                QLabel {
                    background: rgba(149, 165, 166, 0.2);
                    border: 2px solid #95a5a6;
                    border-radius: 12px;
                    padding: 20px;
                    font-size: 18px;
                    font-weight: bold;
                    color: #ecf0f1;
                    min-height: 40px;
                }
            """)

    def start_monitoring(self):
        self.worker = Stronghold2Worker()
        self.worker.status_changed.connect(self.update_status)
        self.worker.ai_enabled.connect(self.ai_activated)
        self.worker.error_occurred.connect(self.handle_error)

        self.worker.start()

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.ai_count = 0
        self.update_counter()

    def stop_monitoring(self):
        if self.worker:
            self.worker.stop()
            self.worker.wait()
            self.worker = None

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.set_status(LANG["status_monitoring_stopped"][current_language])

    def update_status(self, message, is_success):
        self.set_status(message, is_success)
        if hasattr(self, 'tray_icon'):
            self.tray_icon.setToolTip(f"{LANG['tray_icon_tooltip'][current_language]} - {message}")

    def ai_activated(self):
        self.ai_count += 1
        self.update_counter()
        self.set_status(LANG["status_ai_active"][current_language], True)

    def update_counter(self):
        self.counter_label.setText(LANG["ai_counter"][current_language].format(self.ai_count))

    def handle_error(self, error):
        self.set_status(LANG["status_error"][current_language].format(error), False)

    def closeEvent(self, event):
        if hasattr(self, 'tray_icon') and self.tray_icon.isVisible():
            self.hide()
            if hasattr(self, 'tray_icon'):
                self.tray_icon.showMessage(
                    LANG["tray_minimize_message_title"][current_language],
                    LANG["tray_minimize_message_text"][current_language],
                    QSystemTrayIcon.Information,
                    3000
                )
            event.ignore()
        else:
            if self.worker:
                self.worker.stop()
                self.worker.wait()
            event.accept()

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    app.setApplicationName("Stronghold 2 AI Enabler")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("GameModders")

    window = Stronghold2GUI()
    window.show()

    signal.signal(signal.SIGINT, lambda s, f: app.quit())
    signal.signal(signal.SIGTERM, lambda s, f: app.quit())

    print("🏰 Stronghold 2 AI Enabler v2.0 launched!")
    print("   Use GUI to control or Ctrl+C to exit")

    try:
        sys.exit(app.exec_())
    except KeyboardInterrupt:
        print("\n⏹️ Program stopped by user")
        if window.worker:
            window.worker.stop()
            window.worker.wait()
        sys.exit(0)

if __name__ == "__main__":
    main()
