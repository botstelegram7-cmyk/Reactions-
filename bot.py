#!/usr/bin/env python3
"""
ANIMATED REACTION BOT — FINAL VERSION
Features:
  ✅ Commands pe reaction nahi (sirf normal messages pe)
  ✅ Force sub nahi kiya → /start pe 💩 reaction
  ✅ Force sub kiya → random reaction
  ✅ Group me limited reactions → sirf allowed emojis use karta hai
  ✅ Group me all reactions allowed → puri list use karta hai
  ✅ Channel support (channel_post)
  ✅ Timeout fix, Queue workers, Rate limit retry
  ✅ Unknown command sirf private me reply karta hai
"""

import os
import sys
import random
import time
import threading
import queue
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests

import config

print("=" * 60)
print("🤖 ANIMATED REACTION BOT — FINAL")
print("=" * 60)

# ==================== LOAD CONFIG ====================
BOT_TOKENS = config.BOT_TOKENS
if not BOT_TOKENS:
    print("ERROR: No BOT_TOKENS found!")
    sys.exit(1)

OWNER_ID            = config.OWNER_ID
PORT                = config.PORT
FORCE_SUB_CHANNEL   = config.FORCE_SUB_CHANNEL
MAX_REACTIONS       = config.MAX_REACTIONS
BIG_REACTIONS_COUNT = config.BIG_REACTIONS_COUNT
START_PIC_URL       = config.START_PIC_URL
WELCOME_GIF_URL     = config.WELCOME_GIF_URL

LONG_POLL_TIMEOUT = 30
API_TIMEOUT       = 15
POLL_READ_TIMEOUT = LONG_POLL_TIMEOUT + 10

OWN_USERNAMES = set()

print(f"Tokens: {len(BOT_TOKENS)}")
print(f"Owner: {OWNER_ID}")
print(f"Force Sub: {FORCE_SUB_CHANNEL or 'Disabled'}")

# ==================== DATABASE ====================
class SimpleDB:
    def __init__(self):
        self.users          = set()
        self.reaction_count = 0
        self.locked         = False

    def add_user(self, uid):       self.users.add(uid)
    def get_user_count(self):      return len(self.users)
    def increment_reactions(self): self.reaction_count += 1
    def set_lock(self, v):         self.locked = v
    def is_locked(self):           return self.locked

db = SimpleDB()

# Cache: chat_id -> list of allowed emoji strings
_reaction_cache = {}
_reaction_cache_lock = threading.Lock()

# ==================== API HELPERS ====================
def api_request(bot_token, method, data=None, read_timeout=API_TIMEOUT):
    try:
        url  = f"https://api.telegram.org/bot{bot_token}/{method}"
        resp = requests.post(url, json=data, timeout=(10, read_timeout))
        return resp.json()
    except Exception as e:
        print(f"API Error [{method}]: {e}")
        return {"ok": False}


def send_message(chat_id, text, reply_markup=None, photo_url=None, animation_url=None):
    if photo_url:
        data, method = {"chat_id": chat_id, "photo": photo_url,
                        "caption": text, "parse_mode": "HTML"}, "sendPhoto"
    elif animation_url:
        data, method = {"chat_id": chat_id, "animation": animation_url,
                        "caption": text, "parse_mode": "HTML"}, "sendAnimation"
    else:
        data, method = {"chat_id": chat_id, "text": text,
                        "parse_mode": "HTML"}, "sendMessage"
    if reply_markup:
        data["reply_markup"] = reply_markup
    return api_request(BOT_TOKENS[0], method, data)


def fetch_own_usernames():
    for token in BOT_TOKENS:
        info = api_request(token, "getMe")
        if info.get("ok"):
            OWN_USERNAMES.add(info['result']['username'].lower())
    print(f"Own usernames: {OWN_USERNAMES}")


def get_all_bot_usernames():
    usernames = []
    for token in BOT_TOKENS:
        info = api_request(token, "getMe")
        if info.get("ok"):
            uname = info['result']['username']
            OWN_USERNAMES.add(uname.lower())
            usernames.append(f"@{uname}")
        else:
            usernames.append("Unknown")
    return usernames


# ==================== VALID TELEGRAM REACTION EMOJIS ====================
# NOTE: Use plain heart (U+2764) NOT the emoji variant (U+2764 U+FE0F)
# Telegram Bot API setMessageReaction only accepts specific emojis.
ALL_VALID_REACTIONS = [
    "👍", "👎", "❤", "🔥", "😂", "😢", "😮", "👏",
    "😁", "🤩", "🤔", "🤯", "😡", "🥳", "😎", "🙏",
    "💯", "🤝", "🥺", "🤡", "🤮", "💔", "💩", "⚡", "🎉",
    "🥰", "😍", "👌", "🏆", "🤣", "😱", "🌚", "🕊",
    "👻", "😴", "😇", "🤗", "🤪", "🥱", "😈", "👀",
]


def get_allowed_reactions(chat_id):
    """
    Returns allowed emoji list for this chat.
    - All reactions allowed  → full ALL_VALID_REACTIONS list
    - Limited reactions      → only those the group admin enabled
    - Caches result, refreshes every 30 min
    """
    with _reaction_cache_lock:
        cached = _reaction_cache.get(chat_id)
        if cached is not None:
            return cached

    result  = api_request(BOT_TOKENS[0], "getChat", {"chat_id": chat_id})
    allowed = ALL_VALID_REACTIONS  # safe default

    if result.get("ok"):
        avail = result["result"].get("available_reactions")

        if avail is None:
            allowed = ALL_VALID_REACTIONS

        elif isinstance(avail, dict):
            if avail.get("type") == "all":
                allowed = ALL_VALID_REACTIONS
            elif avail.get("type") == "some":
                chat_emojis = {r["emoji"] for r in avail.get("reactions", [])
                               if r.get("type") == "emoji"}
                filtered = [e for e in ALL_VALID_REACTIONS if e in chat_emojis]
                allowed  = filtered if filtered else ALL_VALID_REACTIONS

        elif isinstance(avail, list):
            chat_emojis = {r["emoji"] for r in avail
                           if isinstance(r, dict) and r.get("type") == "emoji"}
            filtered = [e for e in ALL_VALID_REACTIONS if e in chat_emojis]
            allowed  = filtered if filtered else ALL_VALID_REACTIONS

    with _reaction_cache_lock:
        _reaction_cache[chat_id] = allowed

    print(f"Chat {chat_id}: {len(allowed)} reactions allowed")
    return allowed


def _cache_refresh_loop():
    while True:
        time.sleep(30 * 60)
        with _reaction_cache_lock:
            _reaction_cache.clear()
        print("Reaction cache refreshed")

threading.Thread(target=_cache_refresh_loop, daemon=True).start()


# ==================== REACTION SENDING ====================
def send_single_reaction(token, chat_id, msg_id, emoji, is_big, max_retries=3):
    for attempt in range(max_retries):
        data = {
            "chat_id":    chat_id,
            "message_id": msg_id,
            "reaction":   [{"type": "emoji", "emoji": emoji}],
            "is_big":     is_big,
        }
        result = api_request(token, "setMessageReaction", data)

        if result.get("ok"):
            return True

        err_code = result.get("error_code", "?")
        err_desc = result.get("description", "unknown")
        print(f"Reaction fail [{emoji}] msg={msg_id} | {err_code}: {err_desc}")

        if err_code == 429:
            wait = result.get("parameters", {}).get("retry_after", 5)
            print(f"Flood wait {wait}s")
            time.sleep(wait + 1)
            continue

        # Big not supported -> try small
        if is_big and attempt == 0:
            data["is_big"] = False
            r2 = api_request(token, "setMessageReaction", data)
            if r2.get("ok"):
                return True
            print(f"Small also failed: {r2.get('description')}")
            break

        if attempt < max_retries - 1:
            time.sleep(2)

    return False


def send_multiple_reactions(chat_id, msg_id, forced_emoji=None):
    if db.is_locked():
        return

    num = min(len(BOT_TOKENS), MAX_REACTIONS)
    if num < 1:
        return

    if forced_emoji:
        # e.g. force sub not done -> all bots send 💩
        selected = [forced_emoji] * num
        print(f"Forced [{forced_emoji}] x{num} -> msg={msg_id}")
    else:
        allowed  = get_allowed_reactions(chat_id)
        selected = random.sample(allowed, min(num, len(allowed)))
        while len(selected) < num:
            selected.append(random.choice(allowed))
        print(f"Random {num} reactions -> msg={msg_id} chat={chat_id}")

    success = 0
    for i, (token, emoji) in enumerate(zip(BOT_TOKENS[:num], selected)):
        is_big = (i < BIG_REACTIONS_COUNT)
        ok = send_single_reaction(token, chat_id, msg_id, emoji, is_big)
        if ok:
            success += 1
            db.increment_reactions()
        time.sleep(random.uniform(0.5, 1.2))

    print(f"Done {success}/{num} | msg={msg_id}")


# ==================== TASK QUEUE ====================
reaction_queue   = queue.Queue()
REACTION_WORKERS = 4


def reaction_worker():
    while True:
        try:
            chat_id, msg_id, forced_emoji = reaction_queue.get(timeout=2)
        except queue.Empty:
            continue
        try:
            send_multiple_reactions(chat_id, msg_id, forced_emoji)
        except Exception as e:
            print(f"Worker error: {e}")
        finally:
            reaction_queue.task_done()


def start_reaction_workers():
    for i in range(REACTION_WORKERS):
        threading.Thread(target=reaction_worker, daemon=True,
                         name=f"Worker-{i}").start()
    print(f"{REACTION_WORKERS} workers started")


def queue_reaction(chat_id, msg_id, forced_emoji=None):
    reaction_queue.put((chat_id, msg_id, forced_emoji))
    print(f"Queued msg={msg_id} forced={forced_emoji or 'random'} pending={reaction_queue.qsize()}")


# ==================== COMMAND FILTER ====================
def should_handle_command(command_text, chat_type):
    if chat_type == "private":
        return True
    parts = command_text.split()[0]
    if '@' in parts:
        target = parts.split('@', 1)[1].lower()
        return target in OWN_USERNAMES
    return parts.lower() in ('/lock', '/unlock', '/stats', '/bots', '/broadcast')


# ==================== KEYBOARDS ====================
def get_main_keyboard():
    return {"inline_keyboard": [
        [{"text": "📢 Update Channel",  "url": config.UPDATE_CHANNEL_URL}],
        [{"text": "👨‍💻 Developer", "url": f"https://t.me/{config.DEVELOPER_USERNAME}"},
         {"text": "❓ Help",            "callback_data": "help"}],
        [{"text": "⚠️ Report Error",    "url": config.ERROR_REPORT_BOT}],
    ]}


def get_force_sub_keyboard():
    if not FORCE_SUB_CHANNEL:
        return None
    return {"inline_keyboard": [
        [{"text": "📢 Join Channel",
          "url": f"https://t.me/{FORCE_SUB_CHANNEL.lstrip('@')}"}],
        [{"text": "✅ I've Joined", "callback_data": "check_sub"}],
    ]}


def check_subscription(user_id):
    if not FORCE_SUB_CHANNEL:
        return True
    try:
        resp = api_request(BOT_TOKENS[0], "getChatMember",
                           {"chat_id": FORCE_SUB_CHANNEL, "user_id": user_id})
        return (resp.get("ok") and
                resp["result"]["status"] in ["member", "administrator", "creator"])
    except:
        return False


# ==================== COMMAND HANDLERS ====================
def handle_command(command, chat_id, msg_id, user_id, username="", chat_type="private"):
    cmd      = command.split()[0].split('@')[0].lower()
    is_owner = (user_id == OWNER_ID)

    if cmd == '/start':
        db.add_user(user_id)

        if FORCE_SUB_CHANNEL and not is_owner:
            if not check_subscription(user_id):
                # React with 💩 on their /start message
                queue_reaction(chat_id, msg_id, forced_emoji="💩")
                send_message(chat_id,
                    "🔒 <b>Channel Membership Required</b>\n\n"
                    f"Please join:\n{FORCE_SUB_CHANNEL}\n\n"
                    "Then click '✅ I've Joined'.",
                    get_force_sub_keyboard())
                return

        # Subscribed or no force sub -> random reaction on /start
        queue_reaction(chat_id, msg_id)

        welcome = (
            f"🌸 <b>Welcome {username or 'User'}!</b>\n\n"
            "✨ I add <b>multiple animated reactions</b> using all bot tokens.\n\n"
            "<b>Stats:</b>\n"
            f"• Active Bots: {len(BOT_TOKENS)}\n"
            f"• Reactions sent: {db.reaction_count:,}\n"
            f"• Users: {db.get_user_count():,}\n\n"
            "<b>Owner:</b> @technicalSerena\n\n"
            "👉 Click <b>Help</b> for setup guide."
        )
        if WELCOME_GIF_URL:
            send_message(chat_id, welcome, get_main_keyboard(), animation_url=WELCOME_GIF_URL)
        elif START_PIC_URL:
            send_message(chat_id, welcome, get_main_keyboard(), photo_url=START_PIC_URL)
        else:
            send_message(chat_id, welcome, get_main_keyboard())

    elif cmd == '/help':
        send_message(chat_id,
            "❓ <b>Help Center</b>\n\n"
            "<b>How it works:</b>\n"
            "• Each bot token = one reaction\n"
            f"• First {BIG_REACTIONS_COUNT} reactions are <b>BIG & ANIMATED</b>\n"
            "• Works in channels, groups, private chats\n"
            "• Auto detects group's allowed reactions\n"
            "• Queue → no message ever missed\n"
            "• Auto retry on rate limits\n\n"
            "<b>Setup for channels/groups:</b>\n"
            "1. /bots → get all bot usernames\n"
            "2. Add each as admin\n"
            "3. Enable <b>Add Reactions</b> permission\n"
            "4. Post any message → reactions aayenge!\n\n"
            "<b>Commands:</b>\n"
            "/start /help /bots /stats /lock /unlock /premium\n\n"
            "<b>Owner:</b> @technicalSerena"
        )

    elif cmd == '/bots':
        usernames = get_all_bot_usernames()
        text = "🤖 <b>All Bot Usernames</b>\n\nAdd as admins + enable <b>Add Reactions</b>:\n\n"
        for idx, uname in enumerate(usernames, 1):
            text += f"{idx}. {uname}\n"
        text += "\n💡 Every message gets multiple animated reactions!"
        send_message(chat_id, text)

    elif cmd == '/stats' and is_owner:
        send_message(chat_id,
            "📊 <b>Bot Statistics</b>\n"
            f"• Users: {db.get_user_count():,}\n"
            f"• Reactions: {db.reaction_count:,}\n"
            f"• Bots: {len(BOT_TOKENS)}\n"
            f"• Queue: {reaction_queue.qsize()} pending\n"
            f"• Cached chats: {len(_reaction_cache)}\n"
            f"• Status: {'Locked' if db.is_locked() else 'Active'}\n"
            f"• Force Sub: {'Yes' if FORCE_SUB_CHANNEL else 'No'}"
        )

    elif cmd == '/lock' and is_owner:
        db.set_lock(True)
        send_message(chat_id, "🔒 Reactions disabled.")

    elif cmd == '/unlock' and is_owner:
        db.set_lock(False)
        send_message(chat_id, "🔓 Reactions enabled.")

    elif cmd == '/broadcast' and is_owner:
        send_message(chat_id, "📢 /broadcast — reply to a message to broadcast.")

    elif cmd == '/premium':
        send_message(chat_id,
            "💎 <b>Premium Plan</b>\n\nContact @technicalSerena to upgrade.")

    else:
        # Only reply in PRIVATE — never spam in groups
        if chat_type == "private":
            send_message(chat_id, "❓ Unknown command. Send /start for help.")


# ==================== CALLBACK HANDLER ====================
def handle_callback(callback_data, chat_id, msg_id, user_id):
    if callback_data == "help":
        handle_command('/help', chat_id, msg_id, user_id, chat_type="private")
    elif callback_data == "check_sub":
        if FORCE_SUB_CHANNEL:
            if check_subscription(user_id):
                send_message(chat_id, "✅ Verified! Send /start again.")
            else:
                send_message(chat_id, "❌ Still not subscribed. Please join first.")


# ==================== POLLING ====================
def start_polling():
    print("Starting long polling...")
    offset     = 0
    main_token = BOT_TOKENS[0]

    while True:
        try:
            resp = api_request(
                main_token, "getUpdates",
                {"offset": offset, "timeout": LONG_POLL_TIMEOUT},
                read_timeout=POLL_READ_TIMEOUT
            )

            if not resp.get("ok"):
                print(f"getUpdates failed: {resp.get('description')}")
                time.sleep(5)
                continue

            for upd in resp.get("result", []):
                offset = upd["update_id"] + 1

                # Callback
                if "callback_query" in upd:
                    cb = upd["callback_query"]
                    handle_callback(cb.get("data"),
                                    cb["message"]["chat"]["id"],
                                    cb["message"]["message_id"],
                                    cb["from"]["id"])
                    api_request(main_token, "answerCallbackQuery",
                                {"callback_query_id": cb["id"]})
                    continue

                # Group / Private message
                if "message" in upd:
                    msg       = upd["message"]
                    chat_id   = msg["chat"]["id"]
                    msg_id    = msg["message_id"]
                    chat_type = msg["chat"].get("type", "private")

                    if "from" in msg:
                        db.add_user(msg["from"]["id"])

                    if "text" in msg and msg["text"].startswith('/'):
                        cmd_text = msg["text"]
                        if not should_handle_command(cmd_text, chat_type):
                            # Other bot's command — skip entirely, no reaction
                            continue
                        handle_command(cmd_text, chat_id, msg_id,
                                       msg.get("from", {}).get("id", 0),
                                       msg.get("from", {}).get("username", ""),
                                       chat_type=chat_type)
                        continue

                    # Normal message -> random reaction
                    queue_reaction(chat_id, msg_id)

                # Channel post
                elif "channel_post" in upd:
                    post    = upd["channel_post"]
                    chat_id = post["chat"]["id"]
                    msg_id  = post["message_id"]
                    if "text" in post and post["text"].startswith('/'):
                        continue
                    queue_reaction(chat_id, msg_id)

        except Exception as e:
            print(f"Polling error: {e}")
            time.sleep(10)


# ==================== HEALTH SERVER ====================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write((
            f"ANIMATED REACTION BOT - ACTIVE\n\n"
            f"Users:     {db.get_user_count():,}\n"
            f"Reactions: {db.reaction_count:,}\n"
            f"Tokens:    {len(BOT_TOKENS)}\n"
            f"Queue:     {reaction_queue.qsize()} pending\n"
            f"Chats:     {len(_reaction_cache)} cached\n"
            f"Locked:    {db.is_locked()}\n"
            f"ForceSub:  {FORCE_SUB_CHANNEL or 'Disabled'}\n\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        ).encode())

    def log_message(self, format, *args):
        pass


def run_health_server():
    try:
        server = HTTPServer(('0.0.0.0', PORT), HealthHandler)
        print(f"Health server on port {PORT}")
        server.serve_forever()
    except Exception as e:
        print(f"Health error: {e}")


# ==================== MAIN ====================
def main():
    print("=" * 60)
    print("BOT STARTING...")
    print("=" * 60)

    for t in BOT_TOKENS[:3]:
        api_request(t, "deleteWebhook", {"drop_pending_updates": True})

    fetch_own_usernames()
    start_reaction_workers()
    threading.Thread(target=run_health_server, daemon=True).start()

    bot_info = api_request(BOT_TOKENS[0], "getMe")
    if bot_info.get("ok"):
        print(f"Main Bot: @{bot_info['result']['username']}")
    print(f"Total Tokens: {len(BOT_TOKENS)}")
    print(f"Valid Emojis: {len(ALL_VALID_REACTIONS)}")
    print("=" * 60)

    start_polling()


if __name__ == '__main__':
    main()
