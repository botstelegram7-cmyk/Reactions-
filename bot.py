#!/usr/bin/env python3
"""
ANIMATED REACTION BOT — v6 FIXED
Fixes:
  ✅ answer_cb FIRST before any edit (buttons work now)
  ✅ allowed_updates includes channel_post (channels work now)
  ✅ Settings panel all toggles working
  ✅ Help all buttons working
  ✅ Channel: is_big=False, independent per-token
"""

import os, sys, random, time, threading, queue
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
import config

print("=" * 60)
print("  ANIMATED REACTION BOT v6")
print("=" * 60)

# ═══════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════
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

LONG_POLL = 30
API_TO    = 15
POLL_TO   = LONG_POLL + 10
PAGE_SIZE = 10

# ✅ FIX: Explicitly request channel_post + all needed update types
ALLOWED_UPDATES = [
    "message", "callback_query", "channel_post",
    "edited_channel_post", "my_chat_member"
]

OWN_USERNAMES = set()
print(f"Tokens={len(BOT_TOKENS)} | Owner={OWNER_ID} | ForceSub={FORCE_SUB_CHANNEL or 'Off'}")

# ═══════════════════════════════════════════════════════════════
# DATABASE
# ═══════════════════════════════════════════════════════════════
class DB:
    def __init__(self):
        self.users     = {}   # uid -> {name, username, joined}
        self.reactions = 0
        self.cfg = {
            "locked":        False,
            "react_dm":      True,
            "react_group":   True,
            "react_channel": True,
            "big_anim":      True,
            "force_sub_on":  bool(FORCE_SUB_CHANNEL),
        }

    def add_user(self, uid, first="", username=""):
        if uid not in self.users:
            self.users[uid] = {"name": first or "User",
                               "username": username or "",
                               "joined": time.time()}
        else:
            if first:    self.users[uid]["name"]     = first
            if username: self.users[uid]["username"] = username

    def count(self):      return len(self.users)
    def all(self):        return list(self.users.items())
    def inc(self):        self.reactions += 1
    def get(self, k):     return self.cfg.get(k, False)
    def toggle(self, k):
        self.cfg[k] = not self.cfg.get(k, False)
        return self.cfg[k]
    def is_locked(self):  return self.cfg["locked"]

db = DB()

_bcast_wait  = set()   # owner uids waiting to type broadcast msg
_rcache      = {}
_rl          = threading.Lock()

# ═══════════════════════════════════════════════════════════════
# API HELPERS
# ═══════════════════════════════════════════════════════════════
def api(token, method, data=None, rt=API_TO):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/{method}",
            json=data, timeout=(10, rt))
        return r.json()
    except Exception as e:
        print(f"  API[{method}]: {e}")
        return {"ok": False}

def send(chat_id, text, markup=None, photo=None, anim=None):
    if photo:
        d, m = {"chat_id": chat_id, "photo": photo,
                "caption": text, "parse_mode": "HTML"}, "sendPhoto"
    elif anim:
        d, m = {"chat_id": chat_id, "animation": anim,
                "caption": text, "parse_mode": "HTML"}, "sendAnimation"
    else:
        d, m = {"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                "disable_web_page_preview": True}, "sendMessage"
    if markup: d["reply_markup"] = markup
    return api(BOT_TOKENS[0], m, d)

def edit(chat_id, msg_id, text, markup=None):
    d = {"chat_id": chat_id, "message_id": msg_id,
         "text": text, "parse_mode": "HTML",
         "disable_web_page_preview": True}
    if markup: d["reply_markup"] = markup
    r = api(BOT_TOKENS[0], "editMessageText", d)
    if not r.get("ok"):
        print(f"  edit fail: {r.get('description')}")
    return r

# ✅ FIX: answer_cb must be called BEFORE edit/send
def answer_cb(cb_id, text="", alert=False):
    api(BOT_TOKENS[0], "answerCallbackQuery",
        {"callback_query_id": cb_id, "text": text, "show_alert": alert})

def fetch_own():
    for t in BOT_TOKENS:
        r = api(t, "getMe")
        if r.get("ok"): OWN_USERNAMES.add(r["result"]["username"].lower())
    print(f"Own bots: {OWN_USERNAMES}")

def all_unames():
    out = []
    for t in BOT_TOKENS:
        r = api(t, "getMe")
        if r.get("ok"):
            u = r["result"]["username"]
            OWN_USERNAMES.add(u.lower())
            out.append(f"@{u}")
        else:
            out.append("Unknown")
    return out

# ═══════════════════════════════════════════════════════════════
# CONFIRMED TELEGRAM REACTION EMOJIS
# ❤ = U+2764 plain (no FE0F!)
# ═══════════════════════════════════════════════════════════════
EMOJIS = [
    "👍","👎","❤","🔥","🥰","👏","😁","🤔","🤯","😱",
    "🤬","😢","🎉","🤩","🤮","💩","🙏","👌","🕊","🤡",
    "🥱","🥴","😍","🐳","🌚","🌭","💯","🤣","⚡","🍌",
    "🏆","💔","🤨","😐","🍓","🍾","💋","😈","😴","😭",
    "🤓","👻","👀","🎃","🙈","😡","👨‍💻","🖕",
]
print(f"Valid emojis: {len(EMOJIS)}")

# ═══════════════════════════════════════════════════════════════
# ALLOWED REACTIONS PER CHAT
# ═══════════════════════════════════════════════════════════════
def get_allowed(chat_id, chat_type):
    if chat_type == "channel":
        return EMOJIS          # skip getChat for channels

    with _rl:
        if chat_id in _rcache: return _rcache[chat_id]

    allowed = EMOJIS
    r = api(BOT_TOKENS[0], "getChat", {"chat_id": chat_id})
    if r.get("ok"):
        avail = r["result"].get("available_reactions")
        if isinstance(avail, dict) and avail.get("type") == "some":
            s = {x["emoji"] for x in avail.get("reactions", [])
                 if x.get("type") == "emoji"}
            f = [e for e in EMOJIS if e in s]
            if f:
                allowed = f
                print(f"  Group {chat_id}: {len(f)} reactions allowed")
        elif isinstance(avail, list):
            s = {x["emoji"] for x in avail
                 if isinstance(x, dict) and x.get("type") == "emoji"}
            f = [e for e in EMOJIS if e in s]
            if f: allowed = f

    with _rl: _rcache[chat_id] = allowed
    return allowed

def _cache_loop():
    while True:
        time.sleep(30 * 60)
        with _rl: _rcache.clear()
        print("Reaction cache refreshed")
threading.Thread(target=_cache_loop, daemon=True).start()

# ═══════════════════════════════════════════════════════════════
# REACTION — ONE TOKEN
# ═══════════════════════════════════════════════════════════════
def react_one(token, chat_id, msg_id, emoji, is_big):
    """Fully independent — returns True/False, never affects other tokens."""
    for attempt in range(3):
        r = api(token, "setMessageReaction", {
            "chat_id":    chat_id,
            "message_id": msg_id,
            "reaction":   [{"type": "emoji", "emoji": emoji}],
            "is_big":     is_big,
        })
        if r.get("ok"):
            print(f"  ✅ [{emoji}] big={is_big} msg={msg_id}")
            return True

        code = r.get("error_code", "?")
        desc = r.get("description", "?")
        print(f"  ❌ [{emoji}] code={code} msg={msg_id}: {desc}")

        if code == 429:
            w = r.get("parameters", {}).get("retry_after", 5)
            print(f"  ⏳ Flood wait {w}s")
            time.sleep(w + 1)
            continue

        # 400/403 = bad emoji or not admin — skip, no retry
        if code in (400, 403):
            return False

        if attempt < 2: time.sleep(1.5)

    return False

# ═══════════════════════════════════════════════════════════════
# REACTION — ALL TOKENS
# ═══════════════════════════════════════════════════════════════
def react_all(chat_id, msg_id, chat_type, forced=None):
    if db.is_locked(): return
    if chat_type == "private"             and not db.get("react_dm"):      return
    if chat_type in ("group","supergroup") and not db.get("react_group"):  return
    if chat_type == "channel"             and not db.get("react_channel"): return

    num = min(len(BOT_TOKENS), MAX_REACTIONS)
    if num < 1: return

    # ✅ Channels: is_big ALWAYS False (Telegram doesn't support big in channels)
    allow_big = (chat_type != "channel") and db.get("big_anim")

    if forced:
        selected = [forced] * num
    else:
        pool     = get_allowed(chat_id, chat_type)
        selected = random.sample(pool, min(num, len(pool)))
        while len(selected) < num:
            selected.append(random.choice(pool))

    print(f"{'💩' if forced else '🎯'} {num} reactions "
          f"msg={msg_id} chat={chat_id} type={chat_type}")

    ok = 0
    for i, (tok, emoji) in enumerate(zip(BOT_TOKENS[:num], selected)):
        big = allow_big and (i < BIG_REACTIONS_COUNT)
        if react_one(tok, chat_id, msg_id, emoji, big):
            ok += 1; db.inc()
        time.sleep(random.uniform(0.5, 1.1))

    print(f"  Done {ok}/{num} msg={msg_id}")

# ═══════════════════════════════════════════════════════════════
# QUEUE
# ═══════════════════════════════════════════════════════════════
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

def enqueue(chat_id, msg_id, chat_type, forced=None):
    rq.put((chat_id, msg_id, chat_type, forced))
    print(f"📥 msg={msg_id} type={chat_type} q={rq.qsize()}")

# ═══════════════════════════════════════════════════════════════
# SETTINGS PANEL
# ═══════════════════════════════════════════════════════════════
def _on(k): return "✅" if db.get(k) else "❌"

def settings_text():
    st = "🔴 PAUSED" if db.is_locked() else "🟢 ACTIVE"
    return (
        f"⚙️ <b>Settings Panel</b>\n\n"
        f"Status:          <b>{st}</b>\n"
        f"💬 DM Reactions:      {_on('react_dm')}\n"
        f"👥 Group Reactions:   {_on('react_group')}\n"
        f"📢 Channel Reactions: {_on('react_channel')}\n"
        f"⚡ Big Animations:    {_on('big_anim')}\n"
        f"🔐 Force Subscribe:   {_on('force_sub_on')}\n\n"
        f"<i>Tap any button to toggle instantly</i>"
    )

def settings_kb():
    lbl = "🔓 Resume" if db.is_locked() else "🔒 Pause All"
    def btn(txt, key):
        return {"text": f"{_on(key)} {txt}", "callback_data": f"s|{key}"}
    return {"inline_keyboard": [
        [{"text": lbl, "callback_data": "s|locked"}],
        [btn("DM React",      "react_dm"),
         btn("Group React",   "react_group")],
        [btn("Channel React", "react_channel"),
         btn("Big Anim",      "big_anim")],
        [btn("Force Sub",     "force_sub_on")],
        [{"text": "👥 User List",  "callback_data": "u|0"},
         {"text": "📊 Live Stats", "callback_data": "live"}],
        [{"text": "❌ Close",      "callback_data": "close"}],
    ]}

# ═══════════════════════════════════════════════════════════════
# USER LIST (paginated, clickable profile links)
# ═══════════════════════════════════════════════════════════════
def users_page(page=0):
    items = db.all()
    total = len(items)
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page  = max(0, min(page, pages - 1))
    chunk = items[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]

    lines = [f"👥 <b>User List</b> — Total: <b>{total:,}</b>\n"]
    for i, (uid, info) in enumerate(chunk, page * PAGE_SIZE + 1):
        name  = info.get("name", "User")
        uname = info.get("username", "")
        d     = datetime.fromtimestamp(info.get("joined", 0)).strftime("%d/%m/%y")
        u_str = f" @{uname}" if uname else ""
        lines.append(
            f"{i}. <a href='tg://user?id={uid}'>{name}</a>"
            f"{u_str} <code>{uid}</code> 📅{d}"
        )
    lines.append(f"\n📄 Page {page+1}/{pages}")

    nav = []
    if page > 0:
        nav.append({"text": "◀", "callback_data": f"u|{page-1}"})
    nav.append({"text": f"{page+1}/{pages}", "callback_data": "noop"})
    if page < pages - 1:
        nav.append({"text": "▶", "callback_data": f"u|{page+1}"})

    return "\n".join(lines), {"inline_keyboard": [
        nav,
        [{"text": "🔙 Settings", "callback_data": "back_settings"},
         {"text": "❌ Close",    "callback_data": "close"}],
    ]}

# ═══════════════════════════════════════════════════════════════
# BROADCAST
# ═══════════════════════════════════════════════════════════════
def do_broadcast(owner_cid, text):
    uids = list(db.users.keys())
    send(owner_cid, f"📤 Broadcasting to <b>{len(uids):,}</b> users...")
    sent = fail = 0
    for uid in uids:
        try:
            if send(uid, text).get("ok"): sent += 1
            else: fail += 1
        except: fail += 1
        time.sleep(0.05)
    send(owner_cid,
         f"✅ <b>Broadcast Done!</b>\n"
         f"• Sent:   {sent:,}\n"
         f"• Failed: {fail:,}")

# ═══════════════════════════════════════════════════════════════
# HELP SYSTEM
# ═══════════════════════════════════════════════════════════════
def help_main_kb():
    return {"inline_keyboard": [
        [{"text": "📢 Channel Setup",  "callback_data": "h|ch"},
         {"text": "👥 Group Setup",    "callback_data": "h|grp"}],
        [{"text": "🤖 Commands",       "callback_data": "h|cmds"},
         {"text": "😂 Emoji List",     "callback_data": "h|emojis"}],
        [{"text": "⚙️ Settings Guide", "callback_data": "h|settings"},
         {"text": "📢 Broadcast Help", "callback_data": "h|bcast"}],
        [{"text": "🔑 BotFather Menu", "callback_data": "h|botfather"}],
        [{"text": "❌ Close",          "callback_data": "close"}],
    ]}

BACK_KB = {"inline_keyboard": [[
    {"text": "🔙 Back to Help", "callback_data": "h|main"},
    {"text": "❌ Close",        "callback_data": "close"},
]]}

HELP = {
    "main": (
        "❓ <b>Help Center</b>\n\n"
        "Choose any topic below to learn how it works.\n"
        "All examples are real use cases 👇"
    ),
    "ch": (
        "📢 <b>Channel Setup Guide</b>\n\n"
        "<b>⚠️ MOST IMPORTANT:</b>\n"
        "BOT_TOKENS[0] (your first/main bot) MUST be\n"
        "admin in the channel. Without this, the bot\n"
        "never receives channel posts at all.\n\n"
        "<b>Steps:</b>\n"
        "1️⃣ Send /bots → copy all usernames\n\n"
        "2️⃣ Channel → Edit → Admins → Add Admin\n"
        "   Add EVERY bot, give permission:\n"
        "   ✅ Add Reactions  ← This is required\n\n"
        "3️⃣ Post any message → reactions in ~2s\n\n"
        "<b>Channel limits (Telegram rules):</b>\n"
        "• No big/animated reactions in channels\n"
        "• Each admin bot = 1 reaction\n"
        "• 1 bot admin = 1 reaction only\n"
        "• 5 bots admin = 5 reactions\n\n"
        "<b>Troubleshoot:</b>\n"
        "❌ No reactions at all?\n"
        "→ Main bot (BOT_TOKENS[0]) not admin!\n\n"
        "❌ Only 1 reaction?\n"
        "→ Only 1 bot is admin. Add more bots."
    ),
    "grp": (
        "👥 <b>Group Setup Guide</b>\n\n"
        "<b>Steps:</b>\n"
        "1️⃣ /bots → copy all bot usernames\n\n"
        "2️⃣ Group → Edit → Admins → Add\n"
        "   Add each bot → permission:\n"
        "   ✅ Add Reactions  ← Required\n\n"
        "3️⃣ Anyone sends a message:\n"
        "<code>Rahul: Hello everyone! 👋</code>\n"
        "Bot1 → ❤  ← BIG animated\n"
        "Bot2 → 🔥 ← BIG animated\n"
        "Bot3 → 🎉 ← BIG animated\n"
        "Bot4 → 👏 ← normal\n"
        "Bot5 → 😍 ← normal\n"
        "All within 5-8 seconds\n\n"
        "<b>Limited emoji groups:</b>\n"
        "If admin restricted emojis → bot auto detects\n"
        "and only uses those. No manual setup needed!"
    ),
    "cmds": (
        "🤖 <b>All Commands</b>\n\n"
        "<b>👤 Everyone:</b>\n"
        "/start — Welcome + stats\n"
        "/help  — This help center\n"
        "/bots  — List all bot usernames\n"
        "/premium — Premium info\n\n"
        "<b>👑 Owner Only:</b>\n"
        "/settings  — Toggle panel (inline buttons)\n"
        "/stats     — Detailed statistics\n"
        "/users     — All users with profile links\n"
        "/broadcast — Send msg to all users\n"
        "  <code>/broadcast Hello!</code>\n"
        "  or reply to a message with /broadcast\n"
        "/lock      — Pause all reactions\n"
        "/unlock    — Resume reactions"
    ),
    "emojis": (
        f"😂 <b>Reaction Emojis</b> ({len(EMOJIS)} total)\n\n"
        + " ".join(EMOJIS[:16]) + "\n"
        + " ".join(EMOJIS[16:32]) + "\n"
        + " ".join(EMOJIS[32:]) + "\n\n"
        "<b>Rules:</b>\n"
        "• Random pick each time\n"
        "• Groups: respects admin emoji limit\n"
        "• Channels: random from full list\n"
        "• Force sub fail → always 💩\n\n"
        "⚠️ Uses ❤ (U+2764), not ❤️\n"
        "Telegram Bot API is strict about this"
    ),
    "settings": (
        "⚙️ <b>Settings Guide</b>\n\n"
        "Open with /settings (owner only)\n\n"
        "🔒 <b>Pause/Resume</b>\n"
        "→ Stops ALL reactions globally\n\n"
        "💬 <b>DM Reactions</b>\n"
        "→ React when users DM the bot\n\n"
        "👥 <b>Group Reactions</b>\n"
        "→ React in groups (with big anim)\n\n"
        "📢 <b>Channel Reactions</b>\n"
        "→ React to channel posts (small only)\n\n"
        "⚡ <b>Big Animations</b>\n"
        "→ First 3 group reactions = animated\n"
        "→ Only works in groups, not channels\n\n"
        "🔐 <b>Force Subscribe</b>\n"
        "→ Users must join your channel first\n"
        "→ Non-subscribers get 💩 on /start\n\n"
        "👥 <b>User List</b>\n"
        "→ Paginated, 10 per page\n"
        "→ Tap name = opens Telegram profile\n"
        "→ Shows: name, @username, ID, join date"
    ),
    "bcast": (
        "📢 <b>Broadcast Guide</b>\n\n"
        "<b>3 ways to broadcast:</b>\n\n"
        "1️⃣ Text in command:\n"
        "<code>/broadcast Update aaya!</code>\n\n"
        "2️⃣ Reply to a message:\n"
        "→ Reply to any msg with /broadcast\n"
        "→ That text gets sent to all users\n\n"
        "3️⃣ Two-step:\n"
        "→ Send /broadcast (alone)\n"
        "→ Bot says: send your message\n"
        "→ Type your message → sent!\n\n"
        "<b>After sending you'll see:</b>\n"
        "📤 Broadcasting to 1,234 users...\n"
        "✅ Broadcast Done!\n"
        "   Sent: 1,200  Failed: 34\n\n"
        "Failed = user blocked the bot\n"
        "Rate: 1 msg per 0.05s (safe)"
    ),
    "botfather": (
        "🤖 <b>BotFather Menu Button Setup</b>\n\n"
        "Ye steps follow karo to add menu button:\n\n"
        "1️⃣ Open @BotFather in Telegram\n\n"
        "2️⃣ Send: /mybots\n"
        "   → Apna bot select karo\n\n"
        "3️⃣ Click: <b>Bot Settings</b>\n\n"
        "4️⃣ Click: <b>Menu Button</b>\n\n"
        "5️⃣ Click: <b>Configure menu button</b>\n\n"
        "6️⃣ Button text bhejo:\n"
        "   <code>⚙️ Settings</code>\n\n"
        "7️⃣ Button URL bhejo:\n"
        "   <code>https://t.me/YourBotUsername</code>\n\n"
        "✅ Done! Ab bot ke niche ek button\n"
        "dikhega jo direct /start pe le jayega.\n\n"
        "<b>Commands menu ke liye:</b>\n"
        "1️⃣ BotFather → /setcommands\n"
        "2️⃣ Bot select karo\n"
        "3️⃣ Ye bhejo:\n\n"
        "<code>start - Welcome aur stats\n"
        "help - Help center\n"
        "bots - All bot usernames\n"
        "settings - Settings panel (owner)\n"
        "stats - Statistics (owner)\n"
        "users - User list (owner)\n"
        "broadcast - Broadcast (owner)\n"
        "lock - Pause reactions (owner)\n"
        "unlock - Resume reactions (owner)\n"
        "premium - Premium info</code>\n\n"
        "✅ Ab / daalne par commands dikhenge!"
    ),
}

# ═══════════════════════════════════════════════════════════════
# KEYBOARDS
# ═══════════════════════════════════════════════════════════════
def main_kb():
    return {"inline_keyboard": [
        [{"text": "📢 Updates",     "url": config.UPDATE_CHANNEL_URL}],
        [{"text": "👨‍💻 Developer","url": f"https://t.me/{config.DEVELOPER_USERNAME}"},
         {"text": "❓ Help",        "callback_data": "h|main"}],
        [{"text": "⚠️ Report",     "url": config.ERROR_REPORT_BOT}],
    ]}

def fsub_kb():
    if not FORCE_SUB_CHANNEL: return None
    return {"inline_keyboard": [
        [{"text": "📢 Join Channel",
          "url": f"https://t.me/{FORCE_SUB_CHANNEL.lstrip('@')}"}],
        [{"text": "✅ I've Joined", "callback_data": "check_sub"}],
    ]}

def check_sub(uid):
    if not FORCE_SUB_CHANNEL: return True
    try:
        r = api(BOT_TOKENS[0], "getChatMember",
                {"chat_id": FORCE_SUB_CHANNEL, "user_id": uid})
        return r.get("ok") and r["result"]["status"] in \
               ["member","administrator","creator"]
    except: return False

# ═══════════════════════════════════════════════════════════════
# COMMAND FILTER
# ═══════════════════════════════════════════════════════════════
def should_handle(cmd_text, chat_type):
    if chat_type == "private": return True
    parts = cmd_text.split()[0]
    if '@' in parts:
        return parts.split('@', 1)[1].lower() in OWN_USERNAMES
    return parts.lower() in (
        '/lock','/unlock','/stats','/bots',
        '/broadcast','/settings','/users','/cancel'
    )

# ═══════════════════════════════════════════════════════════════
# COMMANDS
# ═══════════════════════════════════════════════════════════════
def handle_cmd(text, chat_id, msg_id, uid, first="", username="",
               chat_type="private", reply_to=None):
    parts = text.strip().split(None, 1)
    cmd   = parts[0].split('@')[0].lower()
    arg   = parts[1].strip() if len(parts) > 1 else ""
    own   = (uid == OWNER_ID)

    if cmd == '/start':
        db.add_user(uid, first, username)
        if FORCE_SUB_CHANNEL and db.get("force_sub_on") and not own:
            if not check_sub(uid):
                enqueue(chat_id, msg_id, chat_type, forced="💩")
                send(chat_id,
                     "🔒 <b>Access Required</b>\n\n"
                     f"Join our channel first: {FORCE_SUB_CHANNEL}\n\n"
                     "Then tap <b>I've Joined</b>.", fsub_kb())
                return
        enqueue(chat_id, msg_id, chat_type)
        txt = (
            f"🌸 <b>Welcome, {first or 'User'}!</b>\n\n"
            "✨ I add <b>animated reactions</b> to every message!\n\n"
            "📊 <b>Live Stats:</b>\n"
            f"  🤖 Active Bots:    {len(BOT_TOKENS)}\n"
            f"  🎭 Reactions Sent: {db.reactions:,}\n"
            f"  👥 Total Users:    {db.count():,}\n\n"
            "👑 <b>Owner:</b> @technicalSerena\n\n"
            "👇 Tap Help to get started!"
        )
        if WELCOME_GIF_URL:   send(chat_id, txt, main_kb(), anim=WELCOME_GIF_URL)
        elif START_PIC_URL:   send(chat_id, txt, main_kb(), photo=START_PIC_URL)
        else:                 send(chat_id, txt, main_kb())

    elif cmd == '/help':
        send(chat_id, HELP["main"], help_main_kb())

    elif cmd == '/bots':
        names = all_unames()
        t = "🤖 <b>Bot Usernames</b>\n\nAdd each as Admin → ✅ Add Reactions:\n\n"
        for i, n in enumerate(names, 1): t += f"  {i}. {n}\n"
        t += ("\n<b>Channel:</b> Settings → Admins → Add → ✅ Add Reactions\n"
              "<b>Group:</b>   Edit → Admins → Add → ✅ Add Reactions")
        send(chat_id, t)

    elif cmd == '/settings' and own:
        send(chat_id, settings_text(), settings_kb())

    elif cmd == '/stats' and own:
        send(chat_id,
             "📊 <b>Statistics</b>\n\n"
             f"  👥 Users:        {db.count():,}\n"
             f"  🎭 Reactions:    {db.reactions:,}\n"
             f"  🤖 Tokens:       {len(BOT_TOKENS)}\n"
             f"  😂 Emojis:       {len(EMOJIS)}\n"
             f"  📬 Queue:        {rq.qsize()} pending\n"
             f"  📋 Cached chats: {len(_rcache)}\n"
             f"  🔒 Status:       {'Paused' if db.is_locked() else 'Active'}\n"
             f"  ⚡ Big Anim:     {'ON' if db.get('big_anim') else 'OFF'}\n"
             f"  📢 Force Sub:    {'ON' if db.get('force_sub_on') else 'OFF'}")

    elif cmd == '/users' and own:
        txt, kb = users_page(0)
        send(chat_id, txt, kb)

    elif cmd == '/broadcast' and own:
        if arg:
            threading.Thread(target=do_broadcast, args=(chat_id, arg), daemon=True).start()
        elif reply_to and reply_to.get("text"):
            threading.Thread(
                target=do_broadcast, args=(chat_id, reply_to["text"]), daemon=True
            ).start()
        else:
            _bcast_wait.add(uid)
            send(chat_id,
                 "📢 <b>Broadcast Mode</b>\n\n"
                 "Next message you send will be broadcasted.\n"
                 "Send /cancel to cancel.")

    elif cmd == '/cancel' and own:
        _bcast_wait.discard(uid)
        send(chat_id, "❌ Cancelled.")

    elif cmd == '/lock' and own:
        db.cfg["locked"] = True
        send(chat_id, "🔒 All reactions paused.")

    elif cmd == '/unlock' and own:
        db.cfg["locked"] = False
        send(chat_id, "🔓 Reactions resumed.")

    elif cmd == '/premium':
        send(chat_id,
             "💎 <b>Premium Plan</b>\n\n"
             "• Unlimited bot tokens\n"
             "• Priority support\n"
             "• Custom emojis per chat\n\n"
             "Contact @technicalSerena")

    else:
        if chat_type == "private":
            send(chat_id, "❓ Unknown command. Try /help")

# ═══════════════════════════════════════════════════════════════
# CALLBACKS — answer_cb ALWAYS FIRST
# ═══════════════════════════════════════════════════════════════
def handle_cb(cb_id, data, chat_id, msg_id, uid):
    # ✅ ALWAYS answer callback FIRST — prevents spinning button
    answer_cb(cb_id)
    own = (uid == OWNER_ID)

    # ── Settings toggles ──────────────────────────────────────
    if data.startswith("s|") and own:
        key = data[2:]
        db.toggle(key)
        edit(chat_id, msg_id, settings_text(), settings_kb())
        return

    if data == "back_settings" and own:
        edit(chat_id, msg_id, settings_text(), settings_kb())
        return

    if data == "live" and own:
        edit(chat_id, msg_id,
             "📊 <b>Live Stats</b>\n\n"
             f"  👥 Users:     {db.count():,}\n"
             f"  🎭 Reactions: {db.reactions:,}\n"
             f"  📬 Queue:     {rq.qsize()} pending\n"
             f"  🕒 {datetime.now().strftime('%H:%M:%S')}",
             {"inline_keyboard": [[
                 {"text": "🔄 Refresh",  "callback_data": "live"},
                 {"text": "🔙 Settings", "callback_data": "back_settings"},
             ]]})
        return

    # ── User list pagination ──────────────────────────────────
    if data.startswith("u|") and own:
        try:
            page = int(data.split("|")[1])
            txt, kb = users_page(page)
            edit(chat_id, msg_id, txt, kb)
        except: pass
        return

    # ── Help topics ───────────────────────────────────────────
    if data == "h|main":
        edit(chat_id, msg_id, HELP["main"], help_main_kb())
        return

    topics = {
        "h|ch":        "ch",
        "h|grp":       "grp",
        "h|cmds":      "cmds",
        "h|emojis":    "emojis",
        "h|settings":  "settings",
        "h|bcast":     "bcast",
        "h|botfather": "botfather",
    }
    if data in topics:
        edit(chat_id, msg_id, HELP[topics[data]], BACK_KB)
        return

    # ── Force sub check ───────────────────────────────────────
    if data == "check_sub":
        if check_sub(uid):
            send(chat_id, "✅ Verified! Now send /start 🎉")
        else:
            send(chat_id, "❌ Still not joined. Please join the channel first!")
        return

    # ── Close ─────────────────────────────────────────────────
    if data == "close":
        api(BOT_TOKENS[0], "deleteMessage",
            {"chat_id": chat_id, "message_id": msg_id})
        return

    # noop = do nothing (page counter buttons etc)

# ═══════════════════════════════════════════════════════════════
# POLLING
# ═══════════════════════════════════════════════════════════════
def poll():
    print("Long polling started...")
    offset = 0
    mt     = BOT_TOKENS[0]

    while True:
        try:
            resp = api(mt, "getUpdates", {
                "offset":          offset,
                "timeout":         LONG_POLL,
                "allowed_updates": ALLOWED_UPDATES,   # ✅ includes channel_post
            }, rt=POLL_TO)

            if not resp.get("ok"):
                print(f"getUpdates: {resp.get('description')}")
                time.sleep(5)
                continue

            for upd in resp.get("result", []):
                offset = upd["update_id"] + 1

                # ── Callback ──────────────────────────────────
                if "callback_query" in upd:
                    cb  = upd["callback_query"]
                    msg = cb.get("message", {})
                    handle_cb(
                        cb["id"],
                        cb.get("data", ""),
                        msg.get("chat", {}).get("id", 0),
                        msg.get("message_id", 0),
                        cb["from"]["id"]
                    )
                    continue

                # ── Private / Group message ────────────────────
                if "message" in upd:
                    msg    = upd["message"]
                    cid    = msg["chat"]["id"]
                    mid    = msg["message_id"]
                    ctype  = msg["chat"].get("type", "private")
                    frm    = msg.get("from", {})
                    uid    = frm.get("id", 0)
                    first  = frm.get("first_name", "")
                    uname  = frm.get("username", "")

                    if uid: db.add_user(uid, first, uname)

                    # Owner in broadcast wait?
                    if uid == OWNER_ID and uid in _bcast_wait:
                        _bcast_wait.discard(uid)
                        txt = msg.get("text","") or msg.get("caption","")
                        if txt:
                            threading.Thread(
                                target=do_broadcast, args=(cid, txt), daemon=True
                            ).start()
                        else:
                            send(cid, "❌ Only text supported. Cancelled.")
                        continue

                    # Command?
                    if "text" in msg and msg["text"].startswith('/'):
                        if not should_handle(msg["text"], ctype): continue
                        handle_cmd(msg["text"], cid, mid, uid,
                                   first, uname, ctype,
                                   reply_to=msg.get("reply_to_message"))
                        continue

                    # Normal message → react
                    enqueue(cid, mid, ctype)

                # ── Channel Post ──────────────────────────────
                elif "channel_post" in upd:
                    post  = upd["channel_post"]
                    cid   = post["chat"]["id"]
                    mid   = post["message_id"]
                    # Skip commands in channels
                    if "text" in post and post["text"].startswith('/'):
                        continue
                    print(f"📢 Channel post: {mid} in {cid}")
                    # ✅ chat_type="channel" → is_big=False in react_all
                    enqueue(cid, mid, "channel")

        except Exception as e:
            print(f"Poll error: {e}")
            time.sleep(10)

# ═══════════════════════════════════════════════════════════════
# HEALTH
# ═══════════════════════════════════════════════════════════════
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write((
            f"REACTION BOT v6 — ACTIVE\n\n"
            f"Users:     {db.count():,}\n"
            f"Reactions: {db.reactions:,}\n"
            f"Tokens:    {len(BOT_TOKENS)}\n"
            f"Emojis:    {len(EMOJIS)}\n"
            f"Queue:     {rq.qsize()}\n"
            f"Cached:    {len(_rcache)}\n"
            f"Locked:    {db.is_locked()}\n\n"
            f"Time: {datetime.now():%Y-%m-%d %H:%M:%S}"
        ).encode())
    def log_message(self, *a): pass

def health():
    try: HTTPServer(("0.0.0.0", PORT), H).serve_forever()
    except Exception as e: print(f"Health: {e}")

# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════
def main():
    print("=" * 60)
    # Clear webhook + pending updates
    for t in BOT_TOKENS[:3]:
        api(t, "deleteWebhook", {"drop_pending_updates": True})
    fetch_own()
    start_workers()
    threading.Thread(target=health, daemon=True).start()
    r = api(BOT_TOKENS[0], "getMe")
    if r.get("ok"):
        print(f"Main Bot: @{r['result']['username']}")
    print(f"Tokens={len(BOT_TOKENS)} | Emojis={len(EMOJIS)}")
    print("=" * 60)
    poll()

if __name__ == "__main__":
    main()
