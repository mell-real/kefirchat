import os
import sys
import urllib.request
from prompt_toolkit import Application
from prompt_toolkit.layout import Layout, HSplit, Window, FormattedTextControl
from prompt_toolkit.widgets import Frame, Label, Button, Box
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style
from prompt_toolkit.layout.dimension import Dimension

# Стили в духе Windows 98 (серый фон, синий заголовок)
win98_style = Style.from_dict({
    'frame.border': '#808080 bg:#c0c0c0',
    'frame.label': 'bg:#000080 #ffffff bold',
    'text': 'bg:#c0c0c0 #000000',
    'button': 'bg:#c0c0c0 #000000',
    'button.focused': 'bg:#000080 #ffffff',
})

REPO_URL = "https://raw.githubusercontent.com/mell-real/kefirchat/main/"

class InstallerApp:
    def __init__(self):
        self.install_dir = os.path.expanduser("~/.local/share/kefirchat")
        self.status = "Готов к установке"
        self.is_done = False

        # Текст лога
        self.log_text = "KefirChat Setup\n\nНажмите 'Установить', чтобы начать.\n"

        # Кнопки
        self.btn_install = Button("Установить", handler=self.start_install)
        self.btn_exit = Button("Выход", handler=self.exit_app)

        # Основной контейнер
        self.container = HSplit([
            Frame(
                body=Window(content=FormattedTextControl(text=lambda: self.log_text), wrap_lines=True),
                title="KefirChat Setup",
                style='class:frame'
            ),
            Window(height=1), # Отступ
            HSplit([
                self.btn_install,
                self.btn_exit,
            ])
        ])

        self.layout = Layout(self.container, focused_element=self.btn_install)

    def start_install(self):
        self.log_text += "\n[*] Установка...\n"
        try:
            os.makedirs(self.install_dir, exist_ok=True)
            files = ["client.py", "server.py"]
            for f in files:
                url = REPO_URL + f
                dest = os.path.join(self.install_dir, f)
                urllib.request.urlretrieve(url, dest)
                self.log_text += f"[+] Скачан {f}\n"

            # Создание команд
            bin_dir = os.path.expanduser("~/.local/bin")
            os.makedirs(bin_dir, exist_ok=True)
            
            # 1. Клиент (kefirchat-cli)
            launcher_cli = os.path.join(bin_dir, "kefirchat-cli")
            with open(launcher_cli, "w") as f:
                f.write(f"#!/bin/bash\npython3 {self.install_dir}/client.py \"$@\"\n")
            os.chmod(launcher_cli, 0o755)
            self.log_text += "[+] Создана команда: kefirchat-cli\n"

            # 2. Сервер (kefirchat-server)
            launcher_server = os.path.join(bin_dir, "kefirchat-server")
            with open(launcher_server, "w") as f:
                f.write(f"#!/bin/bash\npython3 {self.install_dir}/server.py \"$@\"\n")
            os.chmod(launcher_server, 0o755)
            self.log_text += "[+] Создана команда: kefirchat-server\n"

            # Ярлык в меню (для клиента)
            desktop_dir = os.path.expanduser("~/.local/share/applications")
            os.makedirs(desktop_dir, exist_ok=True)
            desktop_file = os.path.join(desktop_dir, "kefirchat.desktop")
            with open(desktop_file, "w") as f:
                f.write("[Desktop Entry]\nType=Application\nName=KefirChat\nExec=kefirchat-cli\nTerminal=true\nIcon=utilities-terminal\nCategories=Network;Chat;\n")
            self.log_text += "[+] Создан ярлык\n"

            self.log_text += "\n[+] УСТАНОВКА ЗАВЕРШЕНА!\n"
            self.status = "Готово"
        except Exception as e:
            self.log_text += f"\n[!] Ошибка: {e}\n"

    def exit_app(self):
        self.app.exit()

    async def run(self):
        self.app = Application(
            layout=self.layout,
            style=win98_style,
            full_screen=True,
        )
        await self.app.run_async()

if __name__ == "__main__":
    app = InstallerApp()
    import asyncio
    asyncio.run(app.run())
