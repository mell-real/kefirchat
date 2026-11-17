import asyncio
import websockets
import json
import sqlite3
import datetime
import os
import base64
import aiofiles

DB_PATH = "kefirchat_v6.db"
UPLOAD_DIR = "uploads"
CLIENTS = {}  # websocket: username
CHANNELS = {"general": {"name": "Общий чат", "type": "channel"}}
AVATARS = {}  # username: ascii_art

os.makedirs(UPLOAD_DIR, exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS messages
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  chat_id TEXT, user TEXT, text TEXT, file_name TEXT, timestamp TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS subscriptions
                 (user TEXT, chat_id TEXT, PRIMARY KEY (user, chat_id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS channels
                 (id TEXT PRIMARY KEY, name TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS profiles
                 (user TEXT PRIMARY KEY, avatar TEXT)''')
    
    # Загружаем аватарки и каналы
    c.execute("SELECT user, avatar FROM profiles")
    for user, avatar in c.fetchall():
        AVATARS[user] = avatar
        
    c.execute("SELECT id, name FROM channels")
    for row in c.fetchall():
        CHANNELS[row[0]] = {"name": row[1], "type": "channel"}
    conn.commit()
    conn.close()

def save_message(chat_id, user, text, file_name=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    c.execute("INSERT INTO messages (chat_id, user, text, file_name, timestamp) VALUES (?, ?, ?, ?, ?)",
              (chat_id, user, text, file_name, ts))
    conn.commit()
    conn.close()

def get_history(chat_id, limit=50):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user, text, file_name, timestamp FROM messages WHERE chat_id = ? ORDER BY id DESC LIMIT ?", (chat_id, limit))
    rows = c.fetchall()
    conn.close()
    return list(reversed(rows))

def subscribe(user, chat_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO subscriptions (user, chat_id) VALUES (?, ?)", (user, chat_id))
    conn.commit()
    conn.close()

def get_subscriptions(user):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT chat_id FROM subscriptions WHERE user = ?", (user,))
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def save_avatar(user, avatar):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO profiles (user, avatar) VALUES (?, ?)", (user, avatar))
    conn.commit()
    conn.close()
    AVATARS[user] = avatar

async def send_to_client(ws, payload):
    try:
        await ws.send(json.dumps(payload))
    except:
        pass

async def broadcast_to_all(payload):
    for ws in CLIENTS:
        await send_to_client(ws, payload)

async def handler(websocket):
    try:
        init_msg = await websocket.recv()
        username = json.loads(init_msg).get("user", "Anonymous")
        CLIENTS[websocket] = username
    except Exception:
        return

    subscribe(username, "general")
    await send_to_client(websocket, {"type": "channels", "channels": CHANNELS})
    await send_to_client(websocket, {"type": "subscriptions", "subscriptions": get_subscriptions(username)})
    await send_to_client(websocket, {"type": "avatars", "avatars": AVATARS})
    
    hist = get_history("general")
    await send_to_client(websocket, {"type": "history", "chat_id": "general", "messages": hist})
    await broadcast_to_all({"type": "system_notification", "text": f"Пользователь {username} зашел в сеть"})

    try:
        async for message in websocket:
            data = json.loads(message)
            action = data.get("type")

            if action == "message":
                chat_id = data.get("chat_id")
                text = data.get("text")
                
                if chat_id.startswith("dm_") and username not in chat_id:
                    continue
                elif not chat_id.startswith("dm_") and chat_id not in get_subscriptions(username):
                    continue

                save_message(chat_id, username, text)
                payload = {
                    "type": "message", "chat_id": chat_id, "user": username,
                    "text": text, "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
                }
                
                for ws, user in CLIENTS.items():
                    if chat_id.startswith("dm_"):
                        if user in chat_id:
                            await send_to_client(ws, payload)
                    else:
                        if chat_id in get_subscriptions(user):
                            await send_to_client(ws, payload)

            elif action == "upload_file":
                chat_id = data.get("chat_id")
                file_name = data.get("file_name")
                file_data_b64 = data.get("file_data")
                
                if file_name and file_data_b64 and chat_id:
                    file_bytes = base64.b64decode(file_data_b64)
                    safe_name = f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{file_name}"
                    filepath = os.path.join(UPLOAD_DIR, safe_name)
                    
                    async with aiofiles.open(filepath, 'wb') as f:
                        await f.write(file_bytes)
                    
                    save_message(chat_id, username, f"[ФАЙЛ] {file_name}", safe_name)
                    payload = {
                        "type": "message", "chat_id": chat_id, "user": username,
                        "text": f"[ФАЙЛ] {file_name}", "file_name": safe_name,
                        "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
                    }
                    for ws, user in CLIENTS.items():
                        if chat_id.startswith("dm_"):
                            if user in chat_id:
                                await send_to_client(ws, payload)
                        else:
                            if chat_id in get_subscriptions(user):
                                await send_to_client(ws, payload)

            elif action == "download_file":
                file_name = data.get("file_name")
                filepath = os.path.join(UPLOAD_DIR, file_name)
                if os.path.exists(filepath):
                    async with aiofiles.open(filepath, 'rb') as f:
                        file_bytes = await f.read()
                    b64_data = base64.b64encode(file_bytes).decode()
                    await send_to_client(websocket, {"type": "file_data", "file_name": file_name, "file_data": b64_data})

            elif action == "set_avatar":
                avatar_ascii = data.get("avatar")
                save_avatar(username, avatar_ascii)
                await broadcast_to_all({"type": "avatars", "avatars": AVATARS})
                await send_to_client(websocket, {"type": "system_notification", "text": "Аватарка обновлена"})

            elif action == "load_chat":
                chat_id = data.get("chat_id")
                if chat_id.startswith("dm_") and username not in chat_id:
                    continue
                hist = get_history(chat_id)
                await send_to_client(websocket, {"type": "history", "chat_id": chat_id, "messages": hist})

            elif action == "subscribe":
                chat_id = data.get("chat_id")
                if chat_id in CHANNELS:
                    subscribe(username, chat_id)
                    await send_to_client(websocket, {"type": "subscriptions", "subscriptions": get_subscriptions(username)})
                    await send_to_client(websocket, {"type": "system_notification", "text": f"Вы подписались на {CHANNELS[chat_id]['name']}"})

            elif action == "unsubscribe":
                chat_id = data.get("chat_id")
                if chat_id in CHANNELS:
                    conn = sqlite3.connect(DB_PATH)
                    c = conn.cursor()
                    c.execute("DELETE FROM subscriptions WHERE user = ? AND chat_id = ?", (username, chat_id))
                    conn.commit()
                    conn.close()
                    await send_to_client(websocket, {"type": "subscriptions", "subscriptions": get_subscriptions(username)})
                    await send_to_client(websocket, {"type": "system_notification", "text": f"Вы отписались от {CHANNELS[chat_id]['name']}"})

            elif action == "start_dm":
                target_user = data.get("target_user")
                if target_user and target_user in CLIENTS.values():
                    participants = sorted([username, target_user])
                    dm_id = f"dm_{participants[0]}_{participants[1]}"
                    hist = get_history(dm_id)
                    await send_to_client(websocket, {
                        "type": "dm_started", "chat_id": dm_id, "target": target_user, "messages": hist
                    })

            elif action == "create_channel":
                name = data.get("name")
                if name:
                    channel_id = name.lower().replace(" ", "_")
                    if channel_id not in CHANNELS:
                        conn = sqlite3.connect(DB_PATH)
                        c = conn.cursor()
                        c.execute("INSERT OR REPLACE INTO channels (id, name) VALUES (?, ?)", (channel_id, name))
                        conn.commit()
                        conn.close()
                        CHANNELS[channel_id] = {"name": name, "type": "channel"}
                        subscribe(username, channel_id)
                        await broadcast_to_all({"type": "channels", "channels": CHANNELS})
                        await send_to_client(websocket, {"type": "subscriptions", "subscriptions": get_subscriptions(username)})
                        await broadcast_to_all({"type": "system_notification", "text": f"Создан новый канал: {name}"})

    except websockets.ConnectionClosed:
        pass
    finally:
        if websocket in CLIENTS:
            del CLIENTS[websocket]
            await broadcast_to_all({"type": "system_notification", "text": f"Пользователь {username} вышел"})

async def main():
    init_db()
    async with websockets.serve(handler, "0.0.0.0", 8765):
        print("KefirChat Server v6 (Final) запущен на ws://0.0.0.0:8765")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
