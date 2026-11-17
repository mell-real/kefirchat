import asyncio
import websockets
import json
import base64
import os
import subprocess
from PIL import Image
from prompt_toolkit import Application
from prompt_toolkit.layout import Layout, HSplit, VSplit, Window, FormattedTextControl
from prompt_toolkit.widgets import Frame, TextArea
from prompt_toolkit.styles import Style
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.key_binding import KeyBindings

# Глобальная переменная для URI (будет изменена после ввода)
SERVER_URI = "ws://127.0.0.1:8765"
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# --- ПРОСТЫЕ ПЕРЕВОДЫ ---
LANGUAGES = {
    "ru": {
        "chats": "--- ЧАТЫ ---", 
        "my_av": "--- МОЯ АВАТАРКА ---", 
        "no_av": "Нет аватарки.\n/avatar путь", 
        "input": "Ввод", 
        "help": "Команды:\n/help - справка\n/avatar путь - установить аву\n/dm имя - личка\n/cc канал - создать канал\n/switch id - переключить чат\n/sendfile путь - отправить файл\n/dl имя - скачать файл\n/play путь - включить музыку\n/lang en/ru - язык\n/back - выйти из профиля"
    },
    "en": {
        "chats": "--- CHATS ---", 
        "my_av": "--- MY AVATAR ---", 
        "no_av": "No avatar.\n/avatar path", 
        "input": "Input", 
        "help": "Commands:\n/help - help\n/avatar path - set avatar\n/dm name - direct message\n/cc channel - create channel\n/switch id - switch chat\n/sendfile path - upload file\n/dl name - download file\n/play path - play music\n/lang en/ru - language\n/back - exit profile"
    }
}
current_lang = "ru"

def t(key):
    return LANGUAGES.get(current_lang, LANGUAGES["ru"]).get(key, key)

# --- КОНВЕРТАЦИЯ АВАТАРКИ ---
def convert_to_ansi_avatar(image_path, width=30):
    try:
        img = Image.open(image_path)
        aspect_ratio = img.height / img.width
        height = int(aspect_ratio * width * 0.45)
        img = img.resize((width, height)).convert("RGB")
        ascii_str = ""
        for y in range(img.height):
            for x in range(img.width):
                r, g, b = img.getpixel((x, y))
                ascii_str += f"\033[48;2;{r};{g};{b}m \033[0m"
            ascii_str += "\n"
        return ascii_str
    except Exception as e:
        return f"Error: {e}"

# --- ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ---
style = Style.from_dict({'frame.border': '#888888', 'chat_list': '#aaaaaa', 'notification': 'bg:#444400 #ffff00'})
channels, subscriptions, avatars = {}, [], {}
active_chat_id = "general"
messages, notifications = [], []
ws_connection, app, input_field = None, None, None
username = ""
viewing_profile = None

def get_chat_list_text():
    lines = [t("chats")]
    for sub in subscriptions:
        marker = "> " if sub == active_chat_id else "  "
        name = channels.get(sub, {}).get("name", sub)
        lines.append(f"{marker}{name}")
    
    dm_chats = set(m["chat_id"] for m in messages if m["chat_id"].startswith("dm_") and m["chat_id"] != "SYSTEM")
    if dm_chats:
        lines.append("--- ЛС ---")
        for dm in dm_chats:
            marker = "> " if dm == active_chat_id else "  "
            lines.append(f"{marker}{dm}")
            
    lines.append("\n" + t("my_av"))
    lines.append(avatars.get(username, t("no_av")))
    return ANSI("\n".join(lines))

def get_messages_text():
    global viewing_profile
    lines = []
    if viewing_profile:
        lines.append(f"=== ПРОФИЛЬ: {viewing_profile} ===")
        lines.append(avatars.get(viewing_profile, "У пользователя нет аватарки."))
        lines.append("\nВведите /back чтобы вернуться.")
        return ANSI("\n".join(lines))

    if notifications:
        for n in notifications[-3:]:
            lines.append(f"[УВЕДОМЛЕНИЕ] {n}")
        lines.append("─" * 30)
    
    for msg in messages:
        if msg["chat_id"] == active_chat_id:
            text = msg["text"]
            if "file_name" in msg:
                lines.append(f"{msg['timestamp']} {msg['user']}: 📎 {text} (/dl {msg['file_name']})")
            else:
                lines.append(f"{msg['timestamp']} {msg['user']}: {text}")
    return ANSI("\n".join(lines)) if lines else ANSI("Нет сообщений.")

async def send_to_server(text, chat_id):
    global ws_connection
    if ws_connection:
        await ws_connection.send(json.dumps({"type": "message", "chat_id": chat_id, "text": text}))

def accept_input(buff):
    global active_chat_id, username, viewing_profile, current_lang
    text = buff.text.strip()
    if text:
        if text.startswith("/"):
            parts = text.split(maxsplit=1)
            cmd = parts[0].lower()
            
            if cmd == "/help":
                notifications.append(t("help"))
            elif cmd == "/lang" and len(parts) > 1:
                lang = parts[1].lower()
                if lang in LANGUAGES:
                    current_lang = lang
                    notifications.append(f"Language: {lang}")
                else:
                    notifications.append("Unknown language")
            elif cmd == "/dm" and len(parts) > 1:
                asyncio.create_task(ws_connection.send(json.dumps({"type": "start_dm", "target_user": parts[1]})))
            elif cmd == "/sub" and len(parts) > 1:
                asyncio.create_task(ws_connection.send(json.dumps({"type": "subscribe", "chat_id": parts[1]})))
            elif cmd == "/unsub" and len(parts) > 1:
                asyncio.create_task(ws_connection.send(json.dumps({"type": "unsubscribe", "chat_id": parts[1]})))
            elif cmd == "/cc" and len(parts) > 1:
                asyncio.create_task(ws_connection.send(json.dumps({"type": "create_channel", "name": parts[1]})))
            elif cmd == "/switch" and len(parts) > 1:
                active_chat_id = parts[1]
                viewing_profile = None
                asyncio.create_task(load_chat_history(active_chat_id))
            elif cmd == "/avatar" and len(parts) > 1:
                ansi_art = convert_to_ansi_avatar(parts[1])
                asyncio.create_task(ws_connection.send(json.dumps({"type": "set_avatar", "avatar": ansi_art})))
            elif cmd == "/profile" and len(parts) > 1:
                viewing_profile = parts[1]
            elif cmd == "/back":
                viewing_profile = None
            elif cmd == "/sendfile" and len(parts) > 1:
                filepath = parts[1]
                if os.path.exists(filepath):
                    with open(filepath, "rb") as f:
                        file_data = base64.b64encode(f.read()).decode()
                    asyncio.create_task(ws_connection.send(json.dumps({
                        "type": "upload_file", "chat_id": active_chat_id,
                        "file_name": os.path.basename(filepath), "file_data": file_data
                    })))
                    notifications.append(f"Отправка {filepath}...")
                else:
                    notifications.append("Файл не найден")
            elif cmd == "/dl" and len(parts) > 1:
                asyncio.create_task(ws_connection.send(json.dumps({"type": "download_file", "file_name": parts[1]})))
                notifications.append("Загрузка...")
            elif cmd == "/play" and len(parts) > 1:
                if os.path.exists(parts[1]):
                    subprocess.Popen(["mpv", parts[1]])
                    notifications.append(f"Играет: {parts[1]}")
                else:
                    notifications.append("Файл не найден локально. /dl сначала.")
            else:
                notifications.append("Неизвестная команда. Введи /help")
        else:
            if viewing_profile:
                notifications.append("Вы в профиле. /back")
            else:
                asyncio.create_task(send_to_server(text, active_chat_id))
        buff.text = ""
        if app: app.invalidate()

async def load_chat_history(chat_id):
    if ws_connection:
        await ws_connection.send(json.dumps({"type": "load_chat", "chat_id": chat_id}))

async def receive_messages():
    global messages, channels, subscriptions, active_chat_id, app, notifications, avatars
    while True:
        try:
            message = await ws_connection.recv()
            data = json.loads(message)
            if data["type"] == "channels": channels = data["channels"]
            elif data["type"] == "subscriptions": subscriptions = data["subscriptions"]
            elif data["type"] == "avatars": avatars = data["avatars"]
            elif data["type"] == "history":
                messages = [m for m in messages if m["chat_id"] != data["chat_id"]]
                for m in data["messages"]:
                    msg = {"chat_id": data["chat_id"], "user": m[0], "text": m[1], "timestamp": m[3]}
                    if m[2]: msg["file_name"] = m[2]
                    messages.append(msg)
                active_chat_id = data["chat_id"]
            elif data["type"] == "dm_started":
                active_chat_id = data["chat_id"]
                messages = [m for m in messages if m["chat_id"] != active_chat_id]
                for m in data["messages"]:
                    msg = {"chat_id": active_chat_id, "user": m[0], "text": m[1], "timestamp": m[3]}
                    if m[2]: msg["file_name"] = m[2]
                    messages.append(msg)
                notifications.append(f"ЛС с {data['target']}")
            elif data["type"] == "message":
                messages.append(data)
            elif data["type"] == "file_data":
                filepath = os.path.join(DOWNLOAD_DIR, data["file_name"])
                with open(filepath, "wb") as f:
                    f.write(base64.b64decode(data["file_data"]))
                notifications.append(f"Сохранено: {filepath} (/play {filepath})")
            elif data["type"] == "system_notification":
                notifications.append(data["text"])
                if len(notifications) > 10: notifications.pop(0)
            if app: app.invalidate()
        except Exception as e:
            print(f"Error: {e}")
            break

kb = KeyBindings()
@kb.add('c-c')
@kb.add('c-q')
def _(event): event.app.exit()

async def main():
    global ws_connection, app, input_field, username, avatars, SERVER_URI
    
    # --- ВВОД IP СЕРВЕРА ---
    print("=" * 50)
    print("Введите IP сервера для подключения.")
    print("Например, ваш внешний IP: 95.27.87.62")
    print("Если сервер на этом же ПК, просто нажмите Enter.")
    print("=" * 50)
    ip_input = input("IP сервера > ").strip()
    
    if ip_input:
        SERVER_URI = f"ws://{ip_input}:8765"
    else:
        SERVER_URI = "ws://127.0.0.1:8765"
    
    print(f"Подключение к {SERVER_URI}...")
    
    while not username.strip():
        username = input("Введите ваше имя: ").strip()
    
    try:
        async with websockets.connect(SERVER_URI) as ws:
            ws_connection = ws
            await ws.send(json.dumps({"user": username}))
            asyncio.create_task(receive_messages())
            
            chat_list_window = Window(content=FormattedTextControl(get_chat_list_text), width=Dimension(min=35, max=45), style='class:chat_list')
            messages_window = Window(content=FormattedTextControl(get_messages_text), wrap_lines=True)
            input_field = TextArea(height=1, prompt="> ", multiline=False, accept_handler=accept_input)
            input_frame = Frame(body=input_field, title=t("input"))
            
            root = VSplit([Frame(body=chat_list_window, title="Chats"), HSplit([messages_window, input_frame])])
            app = Application(layout=Layout(root, focused_element=input_field), style=style, full_screen=True, key_bindings=kb)
            await app.run_async()
    except Exception as e:
        print(f"Ошибка: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nВыход...")
