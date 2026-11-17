import os
import sys
import urllib.request

# Простой и понятный установщик без сложного TUI
REPO_URL = "https://raw.githubusercontent.com/mell-real/kefirchat/main/"
INSTALL_DIR = os.path.expanduser("~/.local/share/kefirchat")
BIN_DIR = os.path.expanduser("~/.local/bin")

def print_banner():
    print("=" * 50)
    print("       KefirChat Installation Wizard")
    print("=" * 50)

def install():
    print_banner()
    
    # Выбор языка
    lang = input("Choose language (en/ru) / Выберите язык (en/ru) [en]: ").strip().lower()
    if lang not in ["en", "ru"]:
        lang = "en"
    
    # Выбор папки
    default_dir = INSTALL_DIR
    user_dir = input(f"Install directory / Папка установки [Enter для {default_dir}]: ").strip()
    install_dir = user_dir if user_dir else default_dir
    
    os.makedirs(install_dir, exist_ok=True)
    print(f"\n[*] Downloading files to {install_dir}...")

    files = ["client.py", "server.py"]
    for f in files:
        url = REPO_URL + f
        dest = os.path.join(install_dir, f)
        try:
            print(f"[*] Downloading {f}...")
            urllib.request.urlretrieve(url, dest)
        except Exception as e:
            print(f"[!] Error downloading {f}: {e}")
            sys.exit(1)

    # Создание команд
    print("[*] Creating commands...")
    os.makedirs(BIN_DIR, exist_ok=True)
    
    # Клиент
    launcher_cli = os.path.join(BIN_DIR, "kefirchat-cli")
    with open(launcher_cli, "w") as f:
        f.write(f"#!/bin/bash\npython3 {install_dir}/client.py \"$@\"\n")
    os.chmod(launcher_cli, 0o755)
    
    # Сервер
    launcher_server = os.path.join(BIN_DIR, "kefirchat-server")
    with open(launcher_server, "w") as f:
        f.write(f"#!/bin/bash\npython3 {install_dir}/server.py \"$@\"\n")
    os.chmod(launcher_server, 0o755)

    # Ярлык в меню
    desktop_dir = os.path.expanduser("~/.local/share/applications")
    os.makedirs(desktop_dir, exist_ok=True)
    desktop_file = os.path.join(desktop_dir, "kefirchat.desktop")
    with open(desktop_file, "w") as f:
        f.write("[Desktop Entry]\nType=Application\nName=KefirChat\nExec=kefirchat-cli\nTerminal=true\nIcon=utilities-terminal\nCategories=Network;Chat;\n")

    print("\n" + "=" * 50)
    print("[+] Installation complete! / Установка завершена!")
    print(f"Run client:  kefirchat-cli")
    print(f"Run server:  kefirchat-server")
    print("=" * 50)

if __name__ == "__main__":
    try:
        install()
    except KeyboardInterrupt:
        print("\n[!] Installation cancelled by user.")
        sys.exit(1)
