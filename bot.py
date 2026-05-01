#!/usr/bin/env python3
"""
ANIMATED REACTION BOT – FIXED VERSION
Fixes:
  1. ✅ Channel support  → channel_post handling added (was the root bug)
  2. ✅ No message miss  → Queue + worker thread system
  3. ✅ Rate limit safe  → Auto retry on 429 / flood wait
  4. ✅ Views support    → Optional Pyrogram userbot (set USER_SESSION in env)
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
print("🤖 ANIMATED REACTION BOT")
print("=" * 60)

# ==================== LOAD CONFIG ====================
BOT_TOKENS = config.BOT_TOKENS
if not BOT_TOKENS:
    print("❌ ERROR: No BOT_TOKENS found!")
    sys.exit(1)

OWNER_ID        = config.OWNER_ID
PORT            = config.PORT
FORCE_SUB_CHANNEL = config.FORCE_SUB_CHANNEL
MAX_REACTIONS   = config.MAX_REACTIONS
BIG_REACTIONS_COUNT = config.BIG_REACTIONS_COUNT
START_PIC_URL   = config.START_PIC_URL
WELCOME_GIF_URL = config.WELCOME_GIF_URL

print(f"✅ Tokens: {len(BOT_TOKENS)} (all used)")
print(f"🎯 Max reactions: {MAX_REACTIONS} (first {BIG_REACTIONS_COUNT} big)")
print(f"👑 Owner: {OWNER_ID}")
print(f"📢 Force Sub: {FORCE_SUB_CHANNEL or 'Disabled'}")

# ==================== DATABASE ====================
class SimpleDB:
    def __init__(self):
        self.users          = set()
        self.reaction_count = 0
        self.view_count     = 0
        self.locked         = False

    def add_user(self, uid):        self.users.add(uid)
    def get_user_count(self):       return len(self.users)
    def increment_reactions(self):  self.reaction_count += 1
    def increment_views(self):      self.view_count += 1
    def set_lock(self, v):          self.locked = v
    def is_locked(self):            return self.locked

db = SimpleDB()

# ==================== OPTIONAL PYROGRAM VIEW BOT ====================
view_client = None
view_loop   = None

def setup_view_bot():
    """Start Pyrogram userbot for view incrementing (optional)."""
    global view_client, view_loop

    api_id      = getattr(config, 'API_ID', 0)
    api_hash    = getattr(config, 'API_HASH', '')
    user_session = getattr(config, 'USER_SESSION', '')

    if not (api_id and api_hash and user_session):
        print("ℹ️  Views disabled (USER_SESSION not set)")
        return

    try:
        import asyncio
        from pyrogram import Client

        view_loop = asyncio.new_event_loop()

        async def _start():
            global view_client
            view_client = Client(
                "view_session",
                api_id=api_id,
                api_hash=api_hash,
                session_string=user_session,
                no_updates=True          # we don't need updates from userbot
            )
            await view_client.start()
            me = await view_client.get_me()
            print(f"✅ View bot started as: {me.first_name} (@{me.username})")

        view_loop.run_until_complete(_start())

        # Keep event loop alive in background thread
        threading.Thread(target=view_loop.run_forever, daemon=True, name="ViewLoop").start()

    except ImportError:
        print("⚠️  Pyrogram not installed → Views disabled. Add 'pyrogram[fast]' to requirements.txt")
    except Exception as e:
        print(f"⚠️  View bot init failed: {e}")


async def _do_increment_views(chat_id: int, msg_id: int):
    """Pyrogram coroutine to increment message views (MTProto)."""
    try:
        from pyrogram import raw
        peer = await view_client.resolve_peer(chat_id)
        await view_client.invoke(
            raw.functions.messages.GetMessagesViews(
                peer=peer,
                id=[msg_id],
                increment=True
            )
        )
        db.increment_views()
        print(f"👁️  View added to msg {msg_id} in {chat_id}")
    except Exception as e:
        print(f"⚠️  View error: {e}")


def increment_views(chat_id: int, msg_id: int):
    """Thread-safe call into the Pyrogram event loop."""
    if not view_client or not view_loop:
        return
    import asyncio
    future = asyncio.run_coroutine_threadsafe(
        _do_increment_views(chat_id, msg_id), view_loop
    )
    try:
        future.result(timeout=15)
    except Exception as e:
        print(f"⚠️  View future error: {e}")


# ==================== API HELPERS ====================
def api_request(bot_token: str, method: str, data: dict = None) -> dict:
    try:
        url  = f"https://api.telegram.org/bot{bot_token}/{method}"
        resp = requests.post(url, json=data, timeout=15)
        return resp.json()
    except Exception as e:
        print(f"❌ API Error [{method}]: {e}")
        return {"ok": False}


def send_message(chat_id: int, text: str, reply_markup=None,
                 photo_url=None, animation_url=None):
    if photo_url:
        data = {"chat_id": chat_id, "photo": photo_url,
                "caption": text, "parse_mode": "HTML"}
    elif animation_url:
        data = {"chat_id": chat_id, "animation": animation_url,
                "caption": text, "parse_mode": "HTML"}
    else:
        data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}

    if reply_markup:
        data["reply_markup"] = reply_markup

    method = "sendPhoto" if photo_url else ("sendAnimation" if animation_url else "sendMessage")
    return api_request(BOT_TOKENS[0], method, data)


def get_all_bot_usernames() -> list:
    usernames = []
    for token in BOT_TOKENS:
        info = api_request(token, "getMe")
        if info.get("ok"):
            usernames.append(f"@{info['result']['username']}")
        else:
            usernames.append("Unknown")
    return usernames


# ==================== REACTION LOGIC ====================
EMOJI_POOL = {
    "text":     ["❤️","🔥","👍","👏","🎉","🤔","😮","🤝","💯","⚡","🥰","😍","🤩","✨","🌟"],
    "photo":    ["❤️","🔥","👍","👏","😍","🤩","✨","🌟","🎯","🏆","💖","🎨","📸","🌅","🖼️"],
    "video":    ["🔥","🎬","👍","👏","😎","💯","⚡","🚀","🎉","🏅","📹","🎥","🌟","🎞️","🎬"],
    "sticker":  ["😄","😂","🤣","😍","😎","🤩","🎭","✨","👍","👌","🥴","😇","🫶","🎉","💫"],
    "document": ["📄","👍","👌","✅","💾","📎","🔗","📊","📑","📁","🗂️","📃","📜","📰","📘"],
}


def send_reaction_with_retry(token: str, chat_id: int, msg_id: int,
                              emoji: str, is_big: bool, max_retries: int = 3) -> bool:
    """Send one reaction. On 429 waits and retries. Falls back to small if big fails."""
    for attempt in range(max_retries):
        data = {
            "chat_id":    chat_id,
            "message_id": msg_id,
            "reaction":   [{"type": "emoji", "emoji": emoji}],
            "is_big":     is_big
        }
        result = api_request(token, "setMessageReaction", data)

        if result.get("ok"):
            return True

        error_code  = result.get("error_code", 0)
        description = result.get("description", "").lower()

        # --- 429: Flood wait ---
        if error_code == 429:
            retry_after = result.get("parameters", {}).get("retry_after", 5)
            print(f"⏳ Flood wait {retry_after}s (msg {msg_id})")
            time.sleep(retry_after + 1)
            continue

        # --- Big reaction not supported → retry as small ---
        if is_big and ("big" in description or "not supported" in description):
            data["is_big"] = False
            r2 = api_request(token, "setMessageReaction", data)
            if r2.get("ok"):
                return True

        # --- Other transient errors: short sleep then retry ---
        if attempt < max_retries - 1:
            time.sleep(2)

    return False


def send_multiple_reactions(chat_id: int, msg_id: int, msg_type: str = "text"):
    if db.is_locked():
        return

    available = BOT_TOKENS
    num = min(len(available), MAX_REACTIONS)
    if num < 1:
        return

    emojis   = EMOJI_POOL.get(msg_type, EMOJI_POOL["text"])
    selected = random.sample(emojis, min(num, len(emojis)))

    print(f"🎯 Sending {num} reactions to msg {msg_id} (chat {chat_id})")
    success = 0

    for i in range(num):
        token  = available[i % len(available)]
        emoji  = selected[i]
        is_big = (i < BIG_REACTIONS_COUNT)

        ok = send_reaction_with_retry(token, chat_id, msg_id, emoji, is_big)
        if ok:
            success += 1
            db.increment_reactions()

        # Delay between each reaction to stay under rate limits
        time.sleep(random.uniform(0.5, 1.2))

    print(f"✅ {success}/{num} reactions done (msg {msg_id})")


# ==================== TASK QUEUE (NO MESSAGE MISSED) ====================
reaction_queue   = queue.Queue()
REACTION_WORKERS = 4   # parallel workers


def reaction_worker():
    """Persistent worker — pulls tasks from queue and processes them."""
    while True:
        try:
            chat_id, msg_id, msg_type = reaction_queue.get(timeout=2)
        except queue.Empty:
            continue
        try:
            send_multiple_reactions(chat_id, msg_id, msg_type)
        except Exception as e:
            print(f"⚠️  Worker error (msg {msg_id}): {e}")
        finally:
            reaction_queue.task_done()


def start_reaction_workers():
    for i in range(REACTION_WORKERS):
        threading.Thread(
            target=reaction_worker,
            daemon=True,
            name=f"ReactionWorker-{i}"
        ).start()
    print(f"✅ {REACTION_WORKERS} reaction workers started")


# ==================== MESSAGE PROCESSOR ====================
def detect_msg_type(msg: dict) -> str:
    if "photo" in msg:    return "photo"
    if "video" in msg:    return "video"
    if "sticker" in msg:  return "sticker"
    if "document" in msg: return "document"
    return "text"


def process_message(msg: dict):
    """
    Queue reaction task + optional view increment.
    Called for both 'message' (groups/private) and 'channel_post'.
    """
    chat_id  = msg["chat"]["id"]
    msg_id   = msg["message_id"]
    msg_type = detect_msg_type(msg)

    # Push to queue → guaranteed delivery even under load
    reaction_queue.put((chat_id, msg_id, msg_type))
    print(f"📥 Queued msg {msg_id} ({msg_type}) | Queue size: {reaction_queue.qsize()}")

    # Views — only for channel posts (optional Pyrogram feature)
    if view_client and msg.get("chat", {}).get("type") == "channel":
        threading.Thread(
            target=increment_views,
            args=(chat_id, msg_id),
            daemon=True
        ).start()


# ==================== KEYBOARDS ====================
def get_main_keyboard():
    return {"inline_keyboard": [
        [{"text": "📢 Update Channel",  "url": config.UPDATE_CHANNEL_URL}],
        [{"text": "👨‍💻 Developer", "url": f"https://t.me/{config.DEVELOPER_USERNAME}"},
         {"text": "❓ Help",            "callback_data": "help"}],
        [{"text": "⚠️ Report Error",    "url": config.ERROR_REPORT_BOT}]
    ]}


def get_force_sub_keyboard():
    if not FORCE_SUB_CHANNEL:
        return None
    channel = FORCE_SUB_CHANNEL.lstrip('@')
    return {"inline_keyboard": [
        [{"text": "📢 Join Channel", "url": f"https://t.me/{channel}"}],
        [{"text": "✅ I've Joined",  "callback_data": "check_sub"}]
    ]}


def check_subscription(user_id: int) -> bool:
    try:
        resp = api_request(BOT_TOKENS[0], "getChatMember",
                           {"chat_id": FORCE_SUB_CHANNEL, "user_id": user_id})
        return resp.get("ok") and resp["result"]["status"] in ["member","administrator","creator"]
    except:
        return False


# ==================== COMMAND HANDLERS ====================
def handle_command(command: str, chat_id: int, user_id: int, username: str = ""):
    # Strip @botname suffix (e.g. /start@MyBot)
    cmd = command.split()[0].split('@')[0].lower()
    is_owner = (user_id == OWNER_ID)

    if cmd == '/start':
        db.add_user(user_id)

        if FORCE_SUB_CHANNEL and not is_owner:
            if not check_subscription(user_id):
                text = (f"🔒 <b>Channel Membership Required</b>\n\n"
                        f"Please join our channel first:\n{FORCE_SUB_CHANNEL}\n\n"
                        f"After joining, click '✅ I've Joined'.")
                send_message(chat_id, text, get_force_sub_keyboard())
                return

        views_status = "✅ Active" if view_client else "❌ Disabled (set USER_SESSION)"
        welcome_text = (
            f"🌸 <b>Welcome {username or 'User'}!</b>\n\n"
            f"✨ I add <b>multiple animated reactions</b> to your messages using all my bot tokens.\n\n"
            f"<b>Stats:</b>\n"
            f"• Active Bots: {len(BOT_TOKENS)}\n"
            f"• Reactions sent: {db.reaction_count:,}\n"
            f"• Views added: {db.view_count:,}\n"
            f"• Users: {db.get_user_count():,}\n"
            f"• Views Feature: {views_status}\n\n"
            f"<b>Owner:</b> @technicalSerena\n\n"
            f"👉 Click <b>Help</b> below to learn how to use me."
        )

        if WELCOME_GIF_URL:
            send_message(chat_id, welcome_text, get_main_keyboard(), animation_url=WELCOME_GIF_URL)
        elif START_PIC_URL:
            send_message(chat_id, welcome_text, get_main_keyboard(), photo_url=START_PIC_URL)
        else:
            send_message(chat_id, welcome_text, get_main_keyboard())

    elif cmd == '/help':
        views_line = (
            "• <b>Views</b> bhi add hote hain channel posts pe (Pyrogram userbot active)"
            if view_client else
            "• Views: Disabled — USER_SESSION, API_ID, API_HASH set karo enable karne ke liye"
        )
        help_text = (
            f"❓ <b>Help Center</b>\n\n"
            f"<b>How it works:</b>\n"
            f"• Each bot token adds one reaction\n"
            f"• First {BIG_REACTIONS_COUNT} reactions are <b>BIG & ANIMATED</b>\n"
            f"• Works in channels, groups, and private chats\n"
            f"• Queue system ensures <b>no message is ever missed</b>\n"
            f"• Auto retry on rate limits\n"
            f"{views_line}\n\n"
            f"<b>Setup for channels/groups:</b>\n"
            f"1. Use /bots to see all bot usernames\n"
            f"2. Add each bot as admin in your channel/group\n"
            f"3. Enable <b>Add Reactions</b> permission\n"
            f"4. Post any message – reactions aayenge automatically!\n\n"
            f"<b>Commands:</b>\n"
            f"/start – Show this menu\n"
            f"/help – Show this help\n"
            f"/stats – Bot statistics (owner)\n"
            f"/lock – Disable reactions (owner)\n"
            f"/unlock – Enable reactions (owner)\n"
            f"/bots – List all bot usernames\n"
            f"/broadcast – Send to all users (owner)\n"
            f"/premium – Premium plan info\n\n"
            f"<b>Owner:</b> @technicalSerena"
        )
        send_message(chat_id, help_text)

    elif cmd == '/bots':
        usernames = get_all_bot_usernames()
        text = ("🤖 <b>All Bot Usernames</b>\n\n"
                "Add these as admins and enable <b>Add Reactions</b> permission:\n\n")
        for idx, uname in enumerate(usernames, 1):
            text += f"{idx}. {uname}\n"
        text += "\n💡 After adding, every message gets multiple animated reactions!"
        send_message(chat_id, text)

    elif cmd == '/stats' and is_owner:
        text = (
            f"📊 <b>Bot Statistics</b>\n"
            f"• Users: {db.get_user_count():,}\n"
            f"• Reactions: {db.reaction_count:,}\n"
            f"• Views Added: {db.view_count:,}\n"
            f"• Bots: {len(BOT_TOKENS)}\n"
            f"• Queue: {reaction_queue.qsize()} pending\n"
            f"• Status: {'🔒 Locked' if db.is_locked() else '✅ Active'}\n"
            f"• Views Bot: {'✅ Active' if view_client else '❌ Disabled'}\n"
            f"• Force Sub: {'✅' if FORCE_SUB_CHANNEL else '❌'}"
        )
        send_message(chat_id, text)

    elif cmd == '/lock' and is_owner:
        db.set_lock(True)
        send_message(chat_id, "🔒 Bot locked. Reactions disabled.")

    elif cmd == '/unlock' and is_owner:
        db.set_lock(False)
        send_message(chat_id, "🔓 Bot unlocked. Reactions enabled.")

    elif cmd == '/broadcast' and is_owner:
        send_message(chat_id, "📢 Reply to a message with /broadcast to send to all users.")

    elif cmd == '/premium':
        text = ("💎 <b>Premium Plan</b>\n\n"
                "• Unlimited reactions\n• Priority support\n• Custom reaction sets\n\n"
                "Contact @technicalSerena to upgrade.")
        send_message(chat_id, text)

    else:
        if is_owner:
            send_message(chat_id, "❓ Unknown command. Send /start for help.")


# ==================== CALLBACK HANDLER ====================
def handle_callback(callback_data: str, chat_id: int, message_id: int, user_id: int):
    if callback_data == "help":
        handle_command('/help', chat_id, user_id)

    elif callback_data == "check_sub":
        if FORCE_SUB_CHANNEL:
            if check_subscription(user_id):
                send_message(chat_id, "✅ Verified! Send /start again.")
            else:
                send_message(chat_id, "❌ Still not subscribed. Please join first.")
    else:
        pass  # Silently ignore unknown callbacks


# ==================== POLLING ====================
def start_polling():
    print("🔄 Starting long polling...")
    offset     = 0
    main_token = BOT_TOKENS[0]

    while True:
        try:
            resp = api_request(main_token, "getUpdates",
                               {"offset": offset, "timeout": 30})
            if not resp.get("ok"):
                print(f"⚠️  getUpdates failed: {resp.get('description')}")
                time.sleep(5)
                continue

            updates = resp.get("result", [])
            for upd in updates:
                offset = upd["update_id"] + 1

                # ── Callback query ─────────────────────────────────────────
                if "callback_query" in upd:
                    cb      = upd["callback_query"]
                    chat_id = cb["message"]["chat"]["id"]
                    msg_id  = cb["message"]["message_id"]
                    user_id = cb["from"]["id"]
                    handle_callback(cb.get("data"), chat_id, msg_id, user_id)
                    api_request(main_token, "answerCallbackQuery",
                                {"callback_query_id": cb["id"]})
                    continue

                # ── Group / private message ────────────────────────────────
                if "message" in upd:
                    msg     = upd["message"]
                    chat_id = msg["chat"]["id"]

                    # Commands
                    if "text" in msg and msg["text"].startswith('/'):
                        user_id  = msg.get("from", {}).get("id", 0)
                        username = msg.get("from", {}).get("username", "")
                        handle_command(msg["text"], chat_id, user_id, username)
                        continue

                    # Track user
                    if "from" in msg:
                        db.add_user(msg["from"]["id"])

                    process_message(msg)

                # ── ✅ FIX: Channel post (was MISSING — root cause of bug) ──
                elif "channel_post" in upd:
                    post = upd["channel_post"]

                    # Skip commands in channel posts
                    if "text" in post and post["text"].startswith('/'):
                        continue

                    process_message(post)

        except Exception as e:
            print(f"⚠️  Polling error: {e}")
            time.sleep(10)


# ==================== HEALTH SERVER ====================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        stats = (
            f"🤖 ANIMATED REACTION BOT\n\n"
            f"✅ Status: ACTIVE\n"
            f"👥 Users: {db.get_user_count():,}\n"
            f"🎭 Reactions: {db.reaction_count:,}\n"
            f"👁️  Views: {db.view_count:,}\n"
            f"🤖 Tokens: {len(BOT_TOKENS)}\n"
            f"📬 Queue: {reaction_queue.qsize()} pending\n"
            f"🔒 Locked: {db.is_locked()}\n"
            f"👁️  Views Bot: {'Active' if view_client else 'Disabled'}\n"
            f"📢 Force Sub: {FORCE_SUB_CHANNEL or 'Disabled'}\n\n"
            f"👑 Owner: @technicalSerena\n"
            f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        self.wfile.write(stats.encode())

    def log_message(self, format, *args):
        pass


def run_health_server():
    try:
        server = HTTPServer(('0.0.0.0', PORT), HealthHandler)
        print(f"✅ Health server on port {PORT}")
        server.serve_forever()
    except Exception as e:
        print(f"⚠️  Health error: {e}")


# ==================== MAIN ====================
def main():
    print("\n" + "=" * 60)
    print("🚀 BOT STARTING...")
    print("=" * 60)

    # Clear pending updates
    for t in BOT_TOKENS[:3]:
        api_request(t, "deleteWebhook", {"drop_pending_updates": True})

    # Optional: Pyrogram view bot
    setup_view_bot()

    # Start reaction queue workers
    start_reaction_workers()

    # Health server
    threading.Thread(target=run_health_server, daemon=True).start()

    # Print bot info
    bot_info = api_request(BOT_TOKENS[0], "getMe")
    if bot_info.get("ok"):
        print(f"🤖 Main Bot: @{bot_info['result']['username']}")
    print(f"📊 Users: {db.get_user_count()}")
    print(f"🤖 Tokens: {len(BOT_TOKENS)}")
    print(f"👁️  Views: {'Pyrogram active' if view_client else 'Disabled'}")
    print("\n💡 Send /start in Telegram")
    print("=" * 60)

    start_polling()


if __name__ == '__main__':
    main()
