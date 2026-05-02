#!/usr/bin/env python3
"""
ANIMATED REACTION BOT — FINAL v4
Channel Fix:
  ✅ is_big=False for channels (channels never support animated/big reactions)
  ✅ Each token reacts independently — one fail does NOT stop others
  ✅ Strictly confirmed Telegram emoji list (no invalid emojis)
  ✅ Full error logging per token
"""

import os, sys, random, time, threading, queue
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
import config

print("=" * 60)
print("🤖 ANIMATED REACTION BOT v4")
print("=" * 60)

# ── CONFIG ────────────────────────────────────────────────────
BOT_TOKENS          = config.BOT_TOKENS
OWNER_ID            = config.OWNER_ID
PORT                = config.PORT
FORCE_SUB_CHANNEL   = config.FORCE_SUB_CHANNEL
MAX_REACTIONS       = config.MAX_REACTIONS
BIG_REACTIONS_COUNT = config.BIG_REACTIONS_COUNT
START_PIC_URL       = config.START_PIC_URL
WELCOME_GIF_URL     = config.WELCOME_GIF_URL

if not BOT_TOKENS:
    print("ERROR: No BOT_TOKENS!"); sys.exit(1)

LONG_POLL_TIMEOUT = 30
API_TIMEOUT       = 15
POLL_READ_TIMEOUT = LONG_POLL_TIMEOUT + 10

OWN_USERNAMES = set()
print(f"Tokens={len(BOT_TOKENS)} Owner={OWNER_ID} ForceSub={FORCE_SUB_CHANNEL or 'Off'}")

# ── DATABASE ──────────────────────────────────────────────────
class DB:
    def __init__(self):
        self.users = set(); self.reactions = 0; self.locked = False
    def add_user(self, uid):      self.users.add(uid)
    def user_count(self):         return len(self.users)
    def inc(self):                self.reactions += 1
    def lock(self, v):            self.locked = v
    def is_locked(self):          return self.locked

db = SimpleDB = DB()

_rcache = {}; _rcache_lock = threading.Lock()

# ── API ───────────────────────────────────────────────────────
def api(token, method, data=None, read_timeout=API_TIMEOUT):
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/{method}",
                          json=data, timeout=(10, read_timeout))
        return r.json()
    except Exception as e:
        print(f"API[{method}] ERR: {e}"); return {"ok": False}

def send_msg(chat_id, text, markup=None, photo=None, anim=None):
    if photo:
        d, m = {"chat_id": chat_id, "photo": photo, "caption": text,
                "parse_mode": "HTML"}, "sendPhoto"
    elif anim:
        d, m = {"chat_id": chat_id, "animation": anim, "caption": text,
                "parse_mode": "HTML"}, "sendAnimation"
    else:
        d, m = {"chat_id": chat_id, "text": text,
                "parse_mode": "HTML"}, "sendMessage"
    if markup: d["reply_markup"] = markup
    return api(BOT_TOKENS[0], m, d)

def fetch_own_usernames():
    for t in BOT_TOKENS:
        r = api(t, "getMe")
        if r.get("ok"): OWN_USERNAMES.add(r["result"]["username"].lower())
    print(f"Own bots: {OWN_USERNAMES}")

def get_all_usernames():
    out = []
    for t in BOT_TOKENS:
        r = api(t, "getMe")
        if r.get("ok"):
            u = r["result"]["username"]
            OWN_USERNAMES.add(u.lower()); out.append(f"@{u}")
        else: out.append("Unknown")
    return out

# ── STRICTLY CONFIRMED TELEGRAM REACTION EMOJIS ───────────────
# These are the ONLY emojis that Telegram Bot API accepts for
# setMessageReaction. Any other emoji silently returns ok:false.
# Source: Telegram Bot API official docs (2024)
# ❤ = U+2764 plain (NO FE0F variation selector — very important!)

CONFIRMED_REACTIONS = [
    "👍", "👎", "❤",  "🔥", "🥰", "👏", "😁", "🤔",
    "🤯", "😱", "🤬", "😢", "🎉", "🤩", "🤮", "💩",
    "🙏", "👌", "🕊",  "🤡", "🥱", "🥴", "😍", "🐳",
    "❤‍🔥", "🌚", "🌭", "💯", "🤣", "⚡", "🍌", "🏆",
    "💔", "🤨", "😐", "🍓", "🍾", "💋", "🖕", "😈",
    "😴", "😭", "🤓", "👻", "👨‍💻", "👀", "🎃", "🙈",
    "😡",
]
print(f"Valid reactions: {len(CONFIRMED_REACTIONS)}")

# ── ALLOWED REACTIONS PER CHAT ────────────────────────────────
def get_allowed(chat_id, chat_type="group"):
    """
    Channels → always full list (skip getChat — bot may not be admin).
    Groups   → call getChat to get admin-configured allowed reactions.
    """
    if chat_type == "channel":
        return CONFIRMED_REACTIONS          # bypass getChat for channels

    with _rcache_lock:
        if chat_id in _rcache:
            return _rcache[chat_id]

    allowed = CONFIRMED_REACTIONS           # safe default
    r = api(BOT_TOKENS[0], "getChat", {"chat_id": chat_id})
    if r.get("ok"):
        avail = r["result"].get("available_reactions")
        if isinstance(avail, dict):
            if avail.get("type") == "some":
                s = {x["emoji"] for x in avail.get("reactions", [])
                     if x.get("type") == "emoji"}
                f = [e for e in CONFIRMED_REACTIONS if e in s]
                if f: allowed = f
                print(f"Group {chat_id}: {len(allowed)}/{len(CONFIRMED_REACTIONS)} reactions allowed")
        elif isinstance(avail, list):
            s = {x["emoji"] for x in avail
                 if isinstance(x, dict) and x.get("type") == "emoji"}
            f = [e for e in CONFIRMED_REACTIONS if e in s]
            if f: allowed = f

    with _rcache_lock:
        _rcache[chat_id] = allowed
    return allowed

def _cache_loop():
    while True:
        time.sleep(30 * 60)
        with _rcache_lock: _rcache.clear()
        print("Reaction cache refreshed")

threading.Thread(target=_cache_loop, daemon=True).start()

# ── REACT: ONE TOKEN, ONE EMOJI ───────────────────────────────
def react_one(token, chat_id, msg_id, emoji, is_big):
    """
    Send a single reaction. Returns True on success.
    is_big is ALWAYS False for channels.
    On 429: sleep and retry.
    On 400/403: skip this emoji (don't retry).
    """
    for attempt in range(3):
        r = api(token, "setMessageReaction", {
            "chat_id":    chat_id,
            "message_id": msg_id,
            "reaction":   [{"type": "emoji", "emoji": emoji}],
            "is_big":     is_big,
        })
        if r.get("ok"):
            return True

        code = r.get("error_code", "?")
        desc = r.get("description", "?")
        print(f"  ❌ [{emoji}] msg={msg_id} code={code}: {desc}")

        if code == 429:
            wait = r.get("parameters", {}).get("retry_after", 5)
            print(f"  ⏳ Flood wait {wait}s"); time.sleep(wait + 1); continue

        # Bad emoji or no permission — skip immediately
        if code in (400, 403): break

        if attempt < 2: time.sleep(2)

    return False

# ── REACT: ALL TOKENS ─────────────────────────────────────────
def react_all(chat_id, msg_id, chat_type="group", forced=None):
    if db.is_locked(): return

    num = min(len(BOT_TOKENS), MAX_REACTIONS)
    if num < 1: return

    # Channels NEVER support is_big — always False
    allow_big = (chat_type != "channel")

    if forced:
        selected = [forced] * num
    else:
        pool     = get_allowed(chat_id, chat_type)
        selected = random.sample(pool, min(num, len(pool)))
        while len(selected) < num:
            selected.append(random.choice(pool))

    print(f"{'💩 Forced' if forced else '🎯 Reacting'}: {num} reactions "
          f"msg={msg_id} chat={chat_id} type={chat_type}")

    ok_count = 0
    for i, (token, emoji) in enumerate(zip(BOT_TOKENS[:num], selected)):
        # ✅ KEY FIX: is_big=False for channels, normal logic for groups
        is_big = allow_big and (i < BIG_REACTIONS_COUNT)
        if react_one(token, chat_id, msg_id, emoji, is_big):
            ok_count += 1; db.inc()
        time.sleep(random.uniform(0.5, 1.2))

    print(f"  ✅ {ok_count}/{num} done msg={msg_id}")

# ── QUEUE ─────────────────────────────────────────────────────
rq = queue.Queue()

def _worker():
    while True:
        try: item = rq.get(timeout=2)
        except queue.Empty: continue
        try:    react_all(*item)
        except Exception as e: print(f"Worker err: {e}")
        finally: rq.task_done()

def start_workers():
    for i in range(4):
        threading.Thread(target=_worker, daemon=True, name=f"W{i}").start()
    print("4 workers started")

def enqueue(chat_id, msg_id, chat_type="group", forced=None):
    rq.put((chat_id, msg_id, chat_type, forced))
    print(f"📥 msg={msg_id} type={chat_type} forced={forced or 'random'} q={rq.qsize()}")

# ── COMMAND FILTER ────────────────────────────────────────────
def should_handle(cmd_text, chat_type):
    if chat_type == "private": return True
    parts = cmd_text.split()[0]
    if '@' in parts:
        return parts.split('@', 1)[1].lower() in OWN_USERNAMES
    return parts.lower() in ('/lock', '/unlock', '/stats', '/bots', '/broadcast')

# ── KEYBOARDS ─────────────────────────────────────────────────
def main_kb():
    return {"inline_keyboard": [
        [{"text": "📢 Updates",   "url": config.UPDATE_CHANNEL_URL}],
        [{"text": "👨‍💻 Dev",   "url": f"https://t.me/{config.DEVELOPER_USERNAME}"},
         {"text": "❓ Help",      "callback_data": "help"}],
        [{"text": "⚠️ Report",   "url": config.ERROR_REPORT_BOT}],
    ]}

def fsub_kb():
    if not FORCE_SUB_CHANNEL: return None
    return {"inline_keyboard": [
        [{"text": "📢 Join Channel",
          "url": f"https://t.me/{FORCE_SUB_CHANNEL.lstrip('@')}"}],
        [{"text": "✅ I've Joined", "callback_data": "check_sub"}],
    ]}

def check_sub(user_id):
    if not FORCE_SUB_CHANNEL: return True
    try:
        r = api(BOT_TOKENS[0], "getChatMember",
                {"chat_id": FORCE_SUB_CHANNEL, "user_id": user_id})
        return r.get("ok") and r["result"]["status"] in \
               ["member", "administrator", "creator"]
    except: return False

# ── COMMANDS ──────────────────────────────────────────────────
def handle_cmd(text, chat_id, msg_id, user_id, uname="", chat_type="private"):
    cmd = text.split()[0].split('@')[0].lower()
    own = (user_id == OWNER_ID)

    if cmd == '/start':
        db.add_user(user_id)
        if FORCE_SUB_CHANNEL and not own:
            if not check_sub(user_id):
                enqueue(chat_id, msg_id, chat_type, forced="💩")
                send_msg(chat_id,
                    "🔒 <b>Channel Membership Required</b>\n\n"
                    f"Please join: {FORCE_SUB_CHANNEL}\n\n"
                    "Then click '✅ I've Joined'.", fsub_kb())
                return
        enqueue(chat_id, msg_id, chat_type)
        txt = (
            f"🌸 <b>Welcome {uname or 'User'}!</b>\n\n"
            "✨ I add <b>multiple animated reactions</b> to every message!\n\n"
            f"<b>📊 Stats:</b>\n"
            f"• Active Bots: {len(BOT_TOKENS)}\n"
            f"• Reactions Sent: {db.reactions:,}\n"
            f"• Total Users: {db.user_count():,}\n\n"
            "<b>Owner:</b> @technicalSerena\n\n"
            "👇 Use buttons below for help & info."
        )
        if WELCOME_GIF_URL:   send_msg(chat_id, txt, main_kb(), anim=WELCOME_GIF_URL)
        elif START_PIC_URL:   send_msg(chat_id, txt, main_kb(), photo=START_PIC_URL)
        else:                 send_msg(chat_id, txt, main_kb())

    elif cmd == '/help':
        send_msg(chat_id,
            "❓ <b>Help Center</b>\n\n"
            "<b>⚙️ How It Works:</b>\n"
            "• Each bot token = 1 reaction\n"
            f"• First {BIG_REACTIONS_COUNT} group reactions → BIG & ANIMATED\n"
            "• Channels → small reactions (Telegram limitation)\n"
            "• Groups → auto detects allowed emojis\n"
            "• Queue system → zero messages missed\n"
            "• Rate limit auto retry (flood wait handled)\n\n"
            "<b>🚀 Setup (Channel/Group):</b>\n"
            "1️⃣ /bots → copy all usernames\n"
            "2️⃣ Add every bot as Admin\n"
            "3️⃣ Give <b>Add Reactions</b> permission\n"
            "4️⃣ Post anything → reactions appear!\n\n"
            "<b>📋 Commands:</b>\n"
            "• /start — Welcome & stats\n"
            "• /help — This menu\n"
            "• /bots — List all bot usernames\n"
            "• /stats — Bot statistics (owner)\n"
            "• /lock — Pause reactions (owner)\n"
            "• /unlock — Resume reactions (owner)\n"
            "• /premium — Premium info\n\n"
            "<b>👑 Owner:</b> @technicalSerena"
        )

    elif cmd == '/bots':
        names = get_all_usernames()
        t = ("🤖 <b>All Bot Usernames</b>\n\n"
             "Add each as Admin → enable <b>Add Reactions</b>:\n\n")
        for i, n in enumerate(names, 1): t += f"{i}. {n}\n"
        t += "\n💡 Every message gets animated reactions automatically!"
        send_msg(chat_id, t)

    elif cmd == '/stats' and own:
        send_msg(chat_id,
            "📊 <b>Bot Statistics</b>\n\n"
            f"👥 Users:        {db.user_count():,}\n"
            f"🎭 Reactions:    {db.reactions:,}\n"
            f"🤖 Bot Tokens:   {len(BOT_TOKENS)}\n"
            f"😂 Valid Emojis: {len(CONFIRMED_REACTIONS)}\n"
            f"📬 Queue:        {rq.qsize()} pending\n"
            f"📋 Cached chats: {len(_rcache)}\n"
            f"🔒 Status:       {'Locked' if db.is_locked() else 'Active'}\n"
            f"📢 Force Sub:    {'On' if FORCE_SUB_CHANNEL else 'Off'}"
        )

    elif cmd == '/lock'   and own: db.lock(True);  send_msg(chat_id, "🔒 Reactions paused.")
    elif cmd == '/unlock' and own: db.lock(False); send_msg(chat_id, "🔓 Reactions resumed.")
    elif cmd == '/broadcast' and own:
        send_msg(chat_id, "📢 Broadcast: reply to a message with /broadcast.")
    elif cmd == '/premium':
        send_msg(chat_id,
            "💎 <b>Premium Plan</b>\n\nContact @technicalSerena to upgrade.")
    else:
        # Only reply in private — NEVER spam groups/channels
        if chat_type == "private":
            send_msg(chat_id, "❓ Unknown command. Try /start or /help.")

# ── CALLBACK ──────────────────────────────────────────────────
def handle_cb(data, chat_id, msg_id, user_id):
    if data == "help":
        handle_cmd('/help', chat_id, msg_id, user_id, chat_type="private")
    elif data == "check_sub" and FORCE_SUB_CHANNEL:
        if check_sub(user_id): send_msg(chat_id, "✅ Verified! Send /start again.")
        else:                  send_msg(chat_id, "❌ Still not subscribed. Join first!")

# ── POLLING ───────────────────────────────────────────────────
def poll():
    print("Long polling started...")
    offset = 0; mt = BOT_TOKENS[0]
    while True:
        try:
            resp = api(mt, "getUpdates",
                       {"offset": offset, "timeout": LONG_POLL_TIMEOUT},
                       read_timeout=POLL_READ_TIMEOUT)

            if not resp.get("ok"):
                print(f"getUpdates fail: {resp.get('description')}"); time.sleep(5); continue

            for upd in resp.get("result", []):
                offset = upd["update_id"] + 1

                # Callback
                if "callback_query" in upd:
                    cb = upd["callback_query"]
                    handle_cb(cb.get("data"),
                              cb["message"]["chat"]["id"],
                              cb["message"]["message_id"],
                              cb["from"]["id"])
                    api(mt, "answerCallbackQuery", {"callback_query_id": cb["id"]})
                    continue

                # Private / Group message
                if "message" in upd:
                    msg = upd["message"]
                    cid = msg["chat"]["id"]
                    mid = msg["message_id"]
                    ctype = msg["chat"].get("type", "private")

                    if "from" in msg: db.add_user(msg["from"]["id"])

                    if "text" in msg and msg["text"].startswith('/'):
                        if not should_handle(msg["text"], ctype): continue
                        handle_cmd(msg["text"], cid, mid,
                                   msg.get("from", {}).get("id", 0),
                                   msg.get("from", {}).get("username", ""),
                                   chat_type=ctype)
                        continue

                    enqueue(cid, mid, ctype)

                # ✅ CHANNEL POST — is_big=False enforced inside react_all
                elif "channel_post" in upd:
                    post  = upd["channel_post"]
                    cid   = post["chat"]["id"]
                    mid   = post["message_id"]
                    if "text" in post and post["text"].startswith('/'): continue
                    enqueue(cid, mid, "channel")   # chat_type="channel" is the fix

        except Exception as e:
            print(f"Poll error: {e}"); time.sleep(10)

# ── HEALTH ────────────────────────────────────────────────────
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write((
            f"ANIMATED REACTION BOT v4 — ACTIVE\n\n"
            f"Users:      {db.user_count():,}\n"
            f"Reactions:  {db.reactions:,}\n"
            f"Tokens:     {len(BOT_TOKENS)}\n"
            f"Emojis:     {len(CONFIRMED_REACTIONS)}\n"
            f"Queue:      {rq.qsize()} pending\n"
            f"Cached:     {len(_rcache)} chats\n"
            f"Locked:     {db.is_locked()}\n"
            f"ForceSub:   {FORCE_SUB_CHANNEL or 'Off'}\n\n"
            f"Time: {datetime.now():%Y-%m-%d %H:%M:%S}"
        ).encode())
    def log_message(self, *a): pass

def health():
    try: HTTPServer(('0.0.0.0', PORT), H).serve_forever()
    except Exception as e: print(f"Health err: {e}")

# ── MAIN ──────────────────────────────────────────────────────
def main():
    print("=" * 60 + "\nSTARTING...\n" + "=" * 60)
    for t in BOT_TOKENS[:3]:
        api(t, "deleteWebhook", {"drop_pending_updates": True})
    fetch_own_usernames()
    start_workers()
    threading.Thread(target=health, daemon=True).start()
    r = api(BOT_TOKENS[0], "getMe")
    if r.get("ok"): print(f"Main Bot: @{r['result']['username']}")
    print(f"Tokens={len(BOT_TOKENS)} Emojis={len(CONFIRMED_REACTIONS)}")
    print("=" * 60)
    poll()

if __name__ == '__main__':
    main()
