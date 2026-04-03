#!/usr/bin/env python3
"""
🤖 ANIMATED REACTION BOT – MULTI‑TOKEN + BIG REACTIONS
- Uses ALL bot tokens for reactions
- Start picture + animated GIF on /start
- Help button works
"""

import os
import sys
import random
import time
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests

import config

print("=" * 60)
print("🤖 ANIMATED REACTION BOT (ALL TOKENS USED)")
print("=" * 60)

# ==================== LOAD CONFIG ====================
BOT_TOKENS = config.BOT_TOKENS
if not BOT_TOKENS:
    print("❌ ERROR: No BOT_TOKENS found!")
    sys.exit(1)

OWNER_ID = config.OWNER_ID
PORT = config.PORT
FORCE_SUB_CHANNEL = config.FORCE_SUB_CHANNEL
MAX_REACTIONS = config.MAX_REACTIONS
BIG_REACTIONS_COUNT = config.BIG_REACTIONS_COUNT
START_PIC_URL = config.START_PIC_URL
WELCOME_GIF_URL = config.WELCOME_GIF_URL

print(f"✅ Total Bot Tokens: {len(BOT_TOKENS)}")
print(f"🎯 Max reactions per message: {MAX_REACTIONS}")
print(f"🔥 First {BIG_REACTIONS_COUNT} reactions will be BIG/animated")
print(f"👑 Owner ID: {OWNER_ID}")
print(f"📢 Force Sub: {FORCE_SUB_CHANNEL or 'Disabled'}")
print(f"🌐 Health Port: {PORT}")

# ==================== SIMPLE DATABASE ====================
class SimpleDB:
    def __init__(self):
        self.users = set()
        self.reaction_count = 0
        self.locked = False
    
    def add_user(self, user_id: int):
        self.users.add(user_id)
    
    def get_user_count(self):
        return len(self.users)
    
    def increment_reactions(self):
        self.reaction_count += 1
    
    def set_lock(self, locked: bool):
        self.locked = locked
    
    def is_locked(self):
        return self.locked

db = SimpleDB()

# ==================== TELEGRAM API HELPERS ====================
def api_request(bot_token: str, method: str, data: dict = None):
    try:
        url = f"https://api.telegram.org/bot{bot_token}/{method}"
        resp = requests.post(url, json=data, timeout=10)
        return resp.json()
    except Exception as e:
        print(f"❌ API Error ({method}): {e}")
        return {"ok": False}

def send_message(chat_id: int, text: str, reply_markup=None, photo_url=None, animation_url=None):
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        data["reply_markup"] = reply_markup

    if photo_url:
        # send photo instead of plain text
        photo_data = {"chat_id": chat_id, "photo": photo_url, "caption": text, "parse_mode": "HTML"}
        if reply_markup:
            photo_data["reply_markup"] = reply_markup
        return api_request(BOT_TOKENS[0], "sendPhoto", photo_data)
    elif animation_url:
        # send GIF animation
        gif_data = {"chat_id": chat_id, "animation": animation_url, "caption": text, "parse_mode": "HTML"}
        if reply_markup:
            gif_data["reply_markup"] = reply_markup
        return api_request(BOT_TOKENS[0], "sendAnimation", gif_data)
    else:
        return api_request(BOT_TOKENS[0], "sendMessage", data)

def send_reaction(token: str, chat_id: int, message_id: int, emoji: str, is_big: bool = True):
    data = {
        "chat_id": chat_id,
        "message_id": message_id,
        "reaction": [{"type": "emoji", "emoji": emoji}],
        "is_big": is_big
    }
    result = api_request(token, "setMessageReaction", data)
    if not result.get("ok") and is_big:
        data["is_big"] = False
        result = api_request(token, "setMessageReaction", data)
    return result.get("ok", False)

def get_all_bot_usernames():
    usernames = []
    for token in BOT_TOKENS:
        info = api_request(token, "getMe")
        if info.get("ok"):
            usernames.append(f"@{info['result']['username']}")
        else:
            usernames.append("Unknown")
    return usernames

# ==================== REACTIONS (USE ALL TOKENS) ====================
def send_multiple_reactions(chat_id: int, message_id: int, msg_type: str = "text"):
    if db.is_locked():
        return
    
    available = BOT_TOKENS
    if not available:
        return
    
    # Use ALL available tokens (no limit except what Telegram can handle)
    num = min(len(available), MAX_REACTIONS)  # MAX_REACTIONS = len(BOT_TOKENS) now
    if num < 1:
        return
    
    emoji_pool = {
        "text":   ["❤️","🔥","👍","👏","🎉","🤔","😮","🤝","💯","⚡","🥰","😍","🤩","✨","🌟"],
        "photo":  ["❤️","🔥","👍","👏","😍","🤩","✨","🌟","🎯","🏆","💖","🎨","📸","🌅","🖼️"],
        "video":  ["🔥","🎬","👍","👏","😎","💯","⚡","🚀","🎉","🏅","📹","🎥","🌟","🎞️","🎬"],
        "sticker":["😄","😂","🤣","😍","😎","🤩","🎭","✨","👍","👌","🥴","😇","🫶","🎉","💫"],
        "document":["📄","👍","👌","✅","💾","📎","🔗","📊","📑","📁","🗂️","📃","📜","📰","📘"]
    }
    emojis = emoji_pool.get(msg_type, emoji_pool["text"])
    selected = random.sample(emojis, min(num, len(emojis)))
    
    print(f"🎯 Adding {num} reactions to message {message_id} (using all {len(available)} tokens)")
    
    success = 0
    threads = []
    for i in range(num):
        token = available[i % len(available)]
        emoji = selected[i]
        is_big = (i < BIG_REACTIONS_COUNT)
        
        t = threading.Thread(
            target=lambda tkn=token, e=emoji, big=is_big: (
                send_reaction(tkn, chat_id, message_id, e, big) and db.increment_reactions()
            ),
            daemon=True
        )
        threads.append(t)
        t.start()
        time.sleep(random.uniform(0.3, 1.0))  # small delay between reactions
    
    for t in threads:
        t.join(timeout=5)
        success += 1
    
    print(f"✅ {success}/{num} reactions sent (first {BIG_REACTIONS_COUNT} BIG)")

# ==================== INLINE KEYBOARDS ====================
def get_main_keyboard():
    """Main menu: Update Channel, Developer, Help, Report Error"""
    keyboard = [
        [{"text": "📢 Update Channel", "url": config.UPDATE_CHANNEL_URL}],
        [{"text": "👨‍💻 Developer", "url": f"https://t.me/{config.DEVELOPER_USERNAME}"},
         {"text": "❓ Help", "callback_data": "help"}],
        [{"text": "⚠️ Report Error", "url": config.ERROR_REPORT_BOT}]
    ]
    return {"inline_keyboard": keyboard}

def get_force_sub_keyboard():
    if not FORCE_SUB_CHANNEL:
        return None
    channel = FORCE_SUB_CHANNEL.lstrip('@')
    return {
        "inline_keyboard": [
            [{"text": "📢 Join Channel", "url": f"https://t.me/{channel}"}],
            [{"text": "✅ I've Joined", "callback_data": "check_sub"}]
        ]
    }

# ==================== COMMAND HANDLERS ====================
def handle_command(command: str, chat_id: int, user_id: int, username: str = ""):
    if command == '/start':
        db.add_user(user_id)
        is_owner = (user_id == OWNER_ID)
        
        # Force subscription check
        if FORCE_SUB_CHANNEL and not is_owner:
            try:
                url = f"https://api.telegram.org/bot{BOT_TOKENS[0]}/getChatMember"
                data = {"chat_id": FORCE_SUB_CHANNEL, "user_id": user_id}
                resp = requests.post(url, json=data).json()
                subscribed = resp.get("ok") and resp["result"]["status"] in ["member","administrator","creator"]
            except:
                subscribed = False
            
            if not subscribed:
                text = f"🔒 <b>Channel Membership Required</b>\n\nTo use this bot, please join our channel first:\n{FORCE_SUB_CHANNEL}\n\nAfter joining, click '✅ I've Joined'."
                send_message(chat_id, text, get_force_sub_keyboard())
                return
        
        # Welcome message (without "How it works")
        welcome_text = f"""🌸 <b>Welcome {username or 'User'}!</b>

✨ I add <b>multiple animated reactions</b> to your messages using all my bot tokens.

<b>Stats:</b>
• Active Bots: {len(BOT_TOKENS)}
• Reactions sent: {db.reaction_count:,}
• Users: {db.get_user_count():,}

<b>Owner:</b> @technicalSerena

👉 Click <b>Help</b> below to see how to use me."""
        
        # Send with GIF animation (fire) + optional start picture
        if START_PIC_URL:
            # send photo with caption
            send_message(chat_id, welcome_text, get_main_keyboard(), photo_url=START_PIC_URL)
        elif WELCOME_GIF_URL:
            # send animated GIF
            send_message(chat_id, welcome_text, get_main_keyboard(), animation_url=WELCOME_GIF_URL)
        else:
            send_message(chat_id, welcome_text, get_main_keyboard())
    
    elif command == '/stats' and user_id == OWNER_ID:
        text = f"""📊 <b>Bot Statistics</b>
• Users: {db.get_user_count():,}
• Reactions Sent: {db.reaction_count:,}
• Active Bots: {len(BOT_TOKENS)}
• Status: {'🔒 Locked' if db.is_locked() else '✅ Active'}
• Force Sub: {'✅' if FORCE_SUB_CHANNEL else '❌'}"""
        send_message(chat_id, text)
    
    elif command == '/bots' and user_id == OWNER_ID:
        usernames = get_all_bot_usernames()
        text = "🤖 <b>All Bot Usernames</b>\n\nAdd these bots as admins in your channel/group and enable <b>Add Reactions</b> permission:\n\n"
        for idx, uname in enumerate(usernames, 1):
            text += f"{idx}. {uname}\n"
        text += "\n💡 After adding them, every message will get multiple animated reactions!"
        send_message(chat_id, text)
    
    elif command == '/lock' and user_id == OWNER_ID:
        db.set_lock(True)
        send_message(chat_id, "🔒 Bot locked. Reactions disabled.")
    
    elif command == '/unlock' and user_id == OWNER_ID:
        db.set_lock(False)
        send_message(chat_id, "🔓 Bot unlocked. Reactions enabled.")
    
    elif command == '/broadcast' and user_id == OWNER_ID:
        send_message(chat_id, "📢 Reply to a message with /broadcast to send to all users.")
    
    elif command == '/premium':
        text = "💎 <b>Premium Plan</b>\n\n• Unlimited reactions\n• Priority support\n• Custom reaction sets\n\nContact @technicalSerena to upgrade."
        send_message(chat_id, text)
    
    else:
        send_message(chat_id, "❓ Unknown command. Send /start for help.")

# ==================== CALLBACK QUERY HANDLER ====================
def handle_callback(callback_data: str, chat_id: int, message_id: int, user_id: int):
    if callback_data == "help":
        # Full help text (includes "How it works")
        help_text = """❓ <b>Help Center</b>

<b>How it works:</b>
• Each bot token adds one reaction
• First 3 reactions are <b>BIG & ANIMATED</b> (long‑press effect)
• Works in channels, groups, and private chats

<b>Setup for channels/groups:</b>
1. Add all bot tokens as admins
2. Enable <b>Add Reactions</b> permission
3. Post any message – I will react automatically

<b>Commands:</b>
/start – Show this menu
/stats – Bot statistics (owner)
/lock – Disable reactions (owner)
/unlock – Enable reactions (owner)
/bots – List all bot usernames (owner)

<b>Owner:</b> @technicalSerena"""
        send_message(chat_id, help_text)
    
    elif callback_data == "stats" and user_id == OWNER_ID:
        text = f"📊 <b>Stats</b>\nUsers: {db.get_user_count()}\nReactions: {db.reaction_count}"
        send_message(chat_id, text)
    
    elif callback_data == "bots" and user_id == OWNER_ID:
        usernames = get_all_bot_usernames()
        text = "🤖 <b>Bot Usernames</b>\n\n" + "\n".join(usernames)
        send_message(chat_id, text)
    
    elif callback_data == "lock" and user_id == OWNER_ID:
        db.set_lock(True)
        send_message(chat_id, "🔒 Locked")
    
    elif callback_data == "unlock" and user_id == OWNER_ID:
        db.set_lock(False)
        send_message(chat_id, "🔓 Unlocked")
    
    elif callback_data == "check_sub":
        if FORCE_SUB_CHANNEL:
            try:
                url = f"https://api.telegram.org/bot{BOT_TOKENS[0]}/getChatMember"
                data = {"chat_id": FORCE_SUB_CHANNEL, "user_id": user_id}
                resp = requests.post(url, json=data).json()
                if resp.get("ok") and resp["result"]["status"] in ["member","administrator","creator"]:
                    send_message(chat_id, "✅ Verified! Send /start again.")
                else:
                    send_message(chat_id, "❌ Still not subscribed. Please join the channel first.")
            except:
                send_message(chat_id, "❌ Error checking subscription. Try again later.")
    else:
        send_message(chat_id, "⚠️ Unknown action")

# ==================== LONG POLLING ====================
def start_polling():
    print("🔄 Starting long polling...")
    offset = 0
    main_token = BOT_TOKENS[0]
    
    while True:
        try:
            resp = api_request(main_token, "getUpdates", {"offset": offset, "timeout": 30})
            if not resp.get("ok"):
                time.sleep(5)
                continue
            
            updates = resp.get("result", [])
            for upd in updates:
                offset = upd["update_id"] + 1
                
                if "callback_query" in upd:
                    cb = upd["callback_query"]
                    cb_data = cb.get("data")
                    chat_id = cb["message"]["chat"]["id"]
                    msg_id = cb["message"]["message_id"]
                    user_id = cb["from"]["id"]
                    handle_callback(cb_data, chat_id, msg_id, user_id)
                    api_request(main_token, "answerCallbackQuery", {"callback_query_id": cb["id"]})
                    continue
                
                if "message" in upd:
                    msg = upd["message"]
                    chat_id = msg["chat"]["id"]
                    msg_id = msg["message_id"]
                    
                    if "text" in msg and msg["text"].startswith('/'):
                        user_id = msg["from"]["id"] if "from" in msg else 0
                        username = msg["from"].get("username", "") if "from" in msg else ""
                        handle_command(msg["text"], chat_id, user_id, username)
                        continue
                    
                    if "from" in msg:
                        db.add_user(msg["from"]["id"])
                    
                    msg_type = "text"
                    if "photo" in msg:
                        msg_type = "photo"
                    elif "video" in msg:
                        msg_type = "video"
                    elif "sticker" in msg:
                        msg_type = "sticker"
                    elif "document" in msg:
                        msg_type = "document"
                    
                    threading.Thread(
                        target=send_multiple_reactions,
                        args=(chat_id, msg_id, msg_type),
                        daemon=True
                    ).start()
            
        except Exception as e:
            print(f"⚠️ Polling error: {e}")
            time.sleep(10)

# ==================== HEALTH SERVER ====================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        stats = f"""🤖 ANIMATED REACTION BOT

✅ Status: ACTIVE
👥 Users: {db.get_user_count():,}
🎭 Reactions: {db.reaction_count:,}
🤖 Tokens: {len(BOT_TOKENS)} (all used)
🔒 Locked: {db.is_locked()}
📢 Force Sub: {FORCE_SUB_CHANNEL or 'Disabled'}

👑 Owner: @technicalSerena
🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
        self.wfile.write(stats.encode())
    
    def log_message(self, format, *args):
        pass

def run_health_server():
    try:
        server = HTTPServer(('0.0.0.0', PORT), HealthHandler)
        print(f"✅ Health server on port {PORT}")
        server.serve_forever()
    except Exception as e:
        print(f"⚠️ Health error: {e}")

def main():
    print("\n" + "=" * 60)
    print("🚀 ANIMATED REACTION BOT STARTING...")
    print("=" * 60)
    
    for t in BOT_TOKENS[:3]:
        api_request(t, "deleteWebhook", {"drop_pending_updates": True})
    
    threading.Thread(target=run_health_server, daemon=True).start()
    
    bot_info = api_request(BOT_TOKENS[0], "getMe")
    if bot_info.get("ok"):
        print(f"🤖 Main Bot: @{bot_info['result']['username']}")
    print(f"📊 Users: {db.get_user_count()}")
    print(f"🤖 Tokens: {len(BOT_TOKENS)}")
    print("\n💡 Send /start in Telegram")
    print("=" * 60)
    
    start_polling()

if __name__ == '__main__':
    main()
