<img width="699" height="556" alt="изображение" src="https://github.com/user-attachments/assets/cd010b4e-37a3-46d8-b098-88ebd468af0b" />

Stronghold 2 AI Enabler for Proton

This application enables AI (bots) in Stronghold 2 multiplayer games on Linux via Proton. It automatically detects the game process and modifies memory to allow the addition of bots.

This application is designed for Linux and uses the PyQt5 library for its graphical user interface. It requires administrator privileges to read and write to the game's memory.

Instructions

English

1. Prerequisites

    Make sure you have python3 and pip installed.

    The application requires the PyQt5 library. If it's not installed, the script will attempt to install it automatically using your distribution's package manager (pacman, apt, dnf, zypper).

    To manage the game process memory, the application needs administrator rights. The script will automatically prompt for them using pkexec when launched.

2. How to Run

    Save the provided Python code as a file, for example, stronghold2_patcher.py.

    Open a terminal in the directory where you saved the file.

    Make the script executable:
    Bash

chmod +x stronghold2_patcher.py

Run the script from the terminal:
Bash

    ./stronghold2_patcher.py

    The application will ask for your administrator password via a graphical prompt (pkexec).

3. Using the Application

    Launch Stronghold 2 through Proton on Steam.

    Once the game is running, open the Stronghold 2 AI Enabler application.

    The application will display a status indicating that it is searching for the game.

    When the game is found, the status will change to "Stronghold 2 found."

    The AI will be automatically enabled in the game. You can now add bots in the multiplayer lobby.

    The application can be minimized to the system tray, where it will continue to monitor the game.


1. Требования

    Убедитесь, что у вас установлены python3 и pip.

    Приложению требуется библиотека PyQt5. Если она не установлена, скрипт попытается установить ее автоматически с помощью пакетного менеджера вашего дистрибутива (pacman, apt, dnf, zypper).

    Для работы с памятью игрового процесса приложению нужны права администратора. Скрипт автоматически запросит их при запуске с помощью pkexec.

2. Как запустить

    Сохраните предоставленный код Python в файл, например, stronghold2_patcher.py.

    Откройте терминал в папке, где вы сохранили файл.

    Сделайте скрипт исполняемым:
    Bash

chmod +x stronghold2_patcher.py

Запустите скрипт из терминала:
Bash

    ./stronghold2_patcher.py

    Приложение запросит ваш пароль администратора через графическое окно (pkexec).

3. Использование приложения

    Запустите Stronghold 2 через Proton в Steam.

    После того как игра запустится, откройте приложение Stronghold 2 AI Enabler.

    Приложение будет отображать статус, указывающий на поиск игры.

    Когда игра будет найдена, статус изменится на «Stronghold 2 found».

    ИИ будет автоматически включен в игре. Теперь вы можете добавлять ботов в многопользовательском лобби.

    Приложение можно свернуть в системный трей, где оно продолжит мониторить игру.
