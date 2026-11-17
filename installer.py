import os
import sys
import shutil
import urllib.request
from prompt_toolkit import prompt
from prompt_toolkit.styles import Style

# Стили
style = Style.from_dict({
    'prompt': 'ansicyan bold',
})

REPO_URL = "https://raw.githubusercontent.com/mell-real/kefirchat/main/"

# --- СЛОВАРИ ПЕРЕВОДОВ ---
TEXTS = {
    "en": {
        "header": "KefirChat Installation Wizard",
        "choose_lang": "Choose language (en/ru) [en]: ",
        "install_dir": "Install directory [Enter for ~/.local/share/kefirchat]: ",
        "downloading": "Downloading files from GitHub...",
        "dl_error": "Error downloading {file}: {error}",
        "creating_launcher": "Creating command 'kefirchat-cli'...",
        "path_warning": "IMPORTANT: Make sure ~/.local/bin is in your PATH.",
        "path_hint": "Add this line to ~/.bashrc or ~/.zshrc:",
        "creating_desktop": "Creating application menu shortcut...",
        "success": "Installation complete!",
        "run_cmd": "Run the messenger with: kefirchat-cli",
        "cancelled": "Installation cancelled."
    },
    "ru": {
        "header": "Мастер установки KefirChat",
        "choose_lang": "Выберите язык (en/ru) [ru]: ",
        "install_dir": "Папка установки [Enter для ~/.local/share/kefirchat]: ",
        "downloading": "Скачивание файлов с GitHub...",
        "dl_error": "Ошибка скачивания {file}: {error}",
        "creating_launcher": "Создание команды 'kefirchat-cli'...",
        "path_warning": "ВАЖНО: Убедитесь, что ~/.local/bin находится в PATH.",
        "path_hint": "Добавьте эту строку в ~/.bashrc или ~/.zshrc:",
        "creating_desktop": "Создание ярлыка в меню приложений...",
        "success": "Установка завершена!",
        "run_cmd": "Запустите мессенджер командой: kefirchat-cli",
        "cancelled": "Установка отменена."
    }
}

def t(key, lang, **kwargs):
    text = TEXTS.get(lang, TEXTS["en"]).get(key, key)
    return text.format(**kwargs) if kwargs else text

def download_file(filename, dest_dir, lang):
    url = REPO_URL + filename
    dest_path = os.path.join(dest_dir, filename)
    try:
        urllib.request.urlretrieve(url, dest_path)
        return True
    except Exception as e:
        print(f"[!] {t('dl_error', lang, file=filename, error=e)}")
        return False

def install():
    # Выбор языка
    lang_input = prompt("Choose language (en/ru) / Выберите язык (en/ru) [en]: ", style=style).strip().lower()
    lang = "ru" if lang_input == "ru" else "en"

    print("\n" + "="*50)
    print(f"       {t('header', lang)}")
    print("="*50)

    # Выбор папки
    default_dir = os.path.expanduser("~/.local/share/kefirchat")
    install_dir_input = prompt(t("install_dir", lang), style=style).strip()
    install_dir = install_dir_input if install_dir_input else default_dir
    
    os.makedirs(install_dir, exist_ok=True)
    print(f"[*] {t('downloading', lang)}")

    # Скачивание основных файлов
    files = ["client.py", "server.py"]
    for f in files:
        if not download_file(f, install_dir, lang):
            print(f"[!] {t('cancelled', lang)}")
            sys.exit(1)

    # Создание команды kefirchat-cli
    print(f"[*] {t('creating_launcher', lang)}")
    bin_dir = os.path.expanduser("~/.local/bin")
    os.makedirs(bin_dir, exist_ok=True)
    
    launcher_path = os.path.join(bin_dir, "kefirchat-cli")
    with open(launcher_path, "w") as f:
        f.write(f"#!/bin/bash\npython3 {install_dir}/client.py \"$@\"\n")
    os.chmod(launcher_path, 0o755)

    # Предупреждение про PATH
    print(f"\n[!] {t('path_warning', lang)}")
    print(f"{t('path_hint', lang)}")
    print('export PATH="$HOME/.local/bin:$PATH"')

    # Создание ярлыка
    print(f"[*] {t('creating_desktop', lang)}")
    desktop_dir = os.path.expanduser("~/.local/share/applications")
    os.makedirs(desktop_dir, exist_ok=True)
    
    desktop_file = os.path.join(desktop_dir, "kefirchat.desktop")
    with open(desktop_file, "w") as f:
        f.write("[Desktop Entry]\n")
        f.write("Type=Application\n")
        f.write("Name=KefirChat\n")
        f.write("Comment=Terminal Messenger\n")
        f.write(f"Exec={launcher_path}\n")
        f.write("Icon=utilities-terminal\n")
        f.write("Terminal=true\n")
        f.write("Categories=Network;Chat;\n")

    print(f"\n\033[1;32m[+] {t('success', lang)}\033[0m")
    print(f"{t('run_cmd', lang)}")

if __name__ == "__main__":
    try:
        install()
    except KeyboardInterrupt:
        print(f"\n[!] {t('cancelled', 'en')}")
        sys.exit(1)
