#!/usr/bin/env python3
"""
ANIMATED REACTION BOT — v5 ULTIMATE
New: Settings Panel, Broadcast, User List, Workable Help, Channel Fix
"""

import os, sys, random, time, threading, queue
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
import config

VERSION = "v5"
print("=" * 60)
print(f"  ANIMATED REACTION BOT {VERSION}")
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

LONG_POLL   = 30
API_TO      = 15
POLL_TO     = LONG_POLL + 10
PAGE_SIZE   = 10

OWN_USERNAMES = set()
print(f"Tokens={len(BOT_TOKENS)} | Owner={OWNER_ID} | ForceSub={FORCE_SUB_CHANNEL or 'Off'}")

# ═══════════════════════════════════════════════════════════════
# DATABASE
# ═══════════════════════════════════════════════════════════════
class DB:
    def __init__(self):
        # uid → {name, username, joined}
        self.users     = {}
        self.reactions = 0
        self.cfg = {
            "locked":        False,
            "react_dm":      True,
            "react_group":   True,
            "react_channel": True,
            "big_anim":      True,
            "force_sub_on":  bool(FORCE_SUB_CHANNEL),
        }

    def add_user(self, uid, name="", username=""):
        if uid not in self.users:
            self.users[uid] = {
                "name":     name or "Unknown",
                "username": username or "",
                "joined":   time.time(),
            }
        else:
            if name:     self.users[uid]["name"]     = name
            if username: self.users[uid]["username"] = username

    def user_count(self): return len(self.users)
    def user_list(self):  return list(self.users.items())
    def inc(self):        self.reactions += 1
    def get(self, k):     return self.cfg.get(k, False)
    def toggle(self, k):
        self.cfg[k] = not self.cfg.get(k, False)
        return self.cfg[k]
    def is_locked(self):  return self.cfg["locked"]

db = DB()

# Broadcast: owner's chat_id → waiting for next message
_bcast_state = {}
# Per-chat reaction allow-list cache
_rcache = {}; _rl = threading.Lock()

# ═══════════════════════════════════════════════════════════════
# API
# ═══════════════════════════════════════════════════════════════
def api(token, method, data=None, rt=API_TO):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/{method}",
            json=data, timeout=(10, rt))
        return r.json()
    except Exception as e:
        print(f"  API[{method}]: {e}"); return {"ok": False}

def send(chat_id, text, markup=None, photo=None, anim=None):
    if photo:
        d, m = {"chat_id": chat_id, "photo": photo,
                "caption": text, "parse_mode": "HTML"}, "sendPhoto"
    elif anim:
        d, m = {"chat_id": chat_id, "animation": anim,
                "caption": text, "parse_mode": "HTML"}, "sendAnimation"
    else:
        d, m = {"chat_id": chat_id, "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True}, "sendMessage"
    if markup: d["reply_markup"] = markup
    return api(BOT_TOKENS[0], m, d)

def edit(chat_id, msg_id, text, markup=None):
    d = {"chat_id": chat_id, "message_id": msg_id,
         "text": text, "parse_mode": "HTML",
         "disable_web_page_preview": True}
    if markup: d["reply_markup"] = markup
    return api(BOT_TOKENS[0], "editMessageText", d)

def edit_markup(chat_id, msg_id, markup):
    return api(BOT_TOKENS[0], "editMessageReplyMarkup",
               {"chat_id": chat_id, "message_id": msg_id,
                "reply_markup": markup})

def answer_cb(cb_id, text=""):
    api(BOT_TOKENS[0], "answerCallbackQuery",
        {"callback_query_id": cb_id, "text": text})

def fetch_own():
    for t in BOT_TOKENS:
        r = api(t, "getMe")
        if r.get("ok"): OWN_USERNAMES.add(r["result"]["username"].lower())
    print(f"Own bots: {OWN_USERNAMES}")

def all_usernames():
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
# Use plain ❤ (U+2764) — NOT ❤️ (with FE0F)
# ═══════════════════════════════════════════════════════════════
EMOJIS = [
    "👍","👎","❤","🔥","🥰","👏","😁","🤔","🤯","😱",
    "🤬","😢","🎉","🤩","🤮","💩","🙏","👌","🕊","🤡",
    "🥱","🥴","😍","🐳","❤‍🔥","🌚","🌭","💯","🤣","⚡",
    "🍌","🏆","💔","🤨","😐","🍓","🍾","💋","🖕","😈",
    "😴","😭","🤓","👻","👀","🎃","🙈","😡",
]
print(f"Valid emojis: {len(EMOJIS)}")

# ═══════════════════════════════════════════════════════════════
# ALLOWED REACTIONS PER CHAT
# ═══════════════════════════════════════════════════════════════
def get_allowed(chat_id, chat_type):
    # CHANNELS: Skip getChat — use full list, rely on 403 filter
    if chat_type == "channel":
        return EMOJIS

    with _rl:
        if chat_id in _rcache:
            return _rcache[chat_id]

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
                print(f"Group {chat_id}: limited to {len(f)} reactions")
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
# REACTION — SINGLE TOKEN
# is_big is ALWAYS False for channels (channel fix)
# Each token is fully independent — one fail never stops others
# ═══════════════════════════════════════════════════════════════
def react_one(token, chat_id, msg_id, emoji, is_big):
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
            wait = r.get("parameters", {}).get("retry_after", 5)
            print(f"  ⏳ Flood {wait}s"); time.sleep(wait + 1); continue

        # 400/403 = invalid emoji or not admin → skip, no retry
        if code in (400, 403): return False

        if attempt < 2: time.sleep(1.5)

    return False


# ═══════════════════════════════════════════════════════════════
# REACTION — ALL TOKENS
# ═══════════════════════════════════════════════════════════════
def react_all(chat_id, msg_id, chat_type, forced=None):
    if db.is_locked(): return

    # Check per-type toggles
    if chat_type == "private"    and not db.get("react_dm"):      return
    if chat_type in ("group","supergroup") and not db.get("react_group"): return
    if chat_type == "channel"    and not db.get("react_channel"):  return

    num = min(len(BOT_TOKENS), MAX_REACTIONS)
    if num < 1: return

    # ✅ CHANNEL FIX: is_big always False for channels
    allow_big = (chat_type != "channel") and db.get("big_anim")

    if forced:
        selected = [forced] * num
    else:
        pool     = get_allowed(chat_id, chat_type)
        selected = random.sample(pool, min(num, len(pool)))
        while len(selected) < num:
            selected.append(random.choice(pool))

    tag = "💩 Forced" if forced else "🎯 React"
    print(f"{tag}: {num} reactions msg={msg_id} chat={chat_id} type={chat_type}")

    ok = 0
    for i, (tok, emoji) in enumerate(zip(BOT_TOKENS[:num], selected)):
        # Each token independent — is_big per-position, False for channel
        big = allow_big and (i < BIG_REACTIONS_COUNT)
        if react_one(tok, chat_id, msg_id, emoji, big):
            ok += 1; db.inc()
        time.sleep(random.uniform(0.5, 1.1))

    print(f"  Done {ok}/{num} msg={msg_id}")


# ═══════════════════════════════════════════════════════════════
# QUEUE — NO MESSAGE MISSED
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
def _st(k):
    return "✅ ON" if db.get(k) else "❌ OFF"

def settings_text():
    s = db.cfg
    status = "🔴 PAUSED" if s["locked"] else "🟢 ACTIVE"
    return (
        "⚙️ <b>Settings Panel</b>\n\n"
        f"  Status:          <b>{status}</b>\n"
        f"  💬 DM React:     <b>{_st('react_dm')}</b>\n"
        f"  👥 Group React:  <b>{_st('react_group')}</b>\n"
        f"  📢 Channel React:<b>{_st('react_channel')}</b>\n"
        f"  ⚡ Big Anim:     <b>{_st('big_anim')}</b>\n"
        f"  🔐 Force Sub:    <b>{_st('force_sub_on')}</b>"
        + (f"  ({FORCE_SUB_CHANNEL})" if FORCE_SUB_CHANNEL else "  <i>(channel not set)</i>")
        + "\n\n<i>Tap a button to toggle instantly</i>"
    )

def settings_kb():
    locked     = db.get("locked")
    lock_label = "🔓 Resume Reactions" if locked else "🔒 Pause Reactions"
    def tb(label, key):
        icon = "✅" if db.get(key) else "❌"
        return {"text": f"{icon} {label}", "callback_data": f"st_{key}"}
    return {"inline_keyboard": [
        [{"text": lock_label, "callback_data": "st_locked"}],
        [tb("DM React",      "react_dm"),
         tb("Group React",   "react_group")],
        [tb("Channel React", "react_channel"),
         tb("Big Anim",      "big_anim")],
        [tb("Force Sub",     "force_sub_on")],
        [{"text": "👥 User List",  "callback_data": "users_0"},
         {"text": "📊 Live Stats", "callback_data": "live_stats"}],
        [{"text": "❌ Close",      "callback_data": "close"}],
    ]}


# ═══════════════════════════════════════════════════════════════
# USER LIST (paginated with profile links)
# ═══════════════════════════════════════════════════════════════
def users_page(page=0):
    items = db.user_list()
    total = len(items)
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page  = max(0, min(page, pages - 1))
    chunk = items[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]

    lines = [f"👥 <b>User List</b> — Total: <b>{total:,}</b>\n"]
    for i, (uid, info) in enumerate(chunk, page * PAGE_SIZE + 1):
        name  = info.get("name",     "Unknown")
        uname = info.get("username", "")
        d     = datetime.fromtimestamp(info.get("joined", 0)).strftime("%d/%m/%y")
        u_part = f"  @{uname}" if uname else ""
        lines.append(
            f"{i}. <a href='tg://user?id={uid}'>{name}</a>"
            f"{u_part}  <code>{uid}</code>  📅{d}"
        )
    lines.append(f"\n📄 Page {page + 1} / {pages}")

    nav = []
    if page > 0:
        nav.append({"text": "◀ Prev", "callback_data": f"users_{page-1}"})
    nav.append({"text": f"{page+1}/{pages}", "callback_data": "noop"})
    if page < pages - 1:
        nav.append({"text": "Next ▶", "callback_data": f"users_{page+1}"})

    kb = {"inline_keyboard": [
        nav,
        [{"text": "🔙 Settings", "callback_data": "settings"},
         {"text": "❌ Close",    "callback_data": "close"}],
    ]}
    return "\n".join(lines), kb


# ═══════════════════════════════════════════════════════════════
# BROADCAST
# ═══════════════════════════════════════════════════════════════
def do_broadcast(owner_chat, text):
    users = list(db.users.keys())
    send(owner_chat,
         f"📤 <b>Broadcasting</b> to {len(users):,} users...\n<i>Please wait</i>")
    sent = fail = 0
    for uid in users:
        try:
            r = send(uid, text)
            if r.get("ok"): sent += 1
            else:            fail += 1
        except: fail += 1
        time.sleep(0.05)
    send(owner_chat,
         f"✅ <b>Broadcast Done!</b>\n\n"
         f"• Sent:   {sent:,}\n"
         f"• Failed: {fail:,}\n"
         f"• Total:  {len(users):,}")


# ═══════════════════════════════════════════════════════════════
# HELP SYSTEM (workable inline buttons with examples)
# ═══════════════════════════════════════════════════════════════
BACK_KB = {"inline_keyboard": [[
    {"text": "🔙 Help Menu",  "callback_data": "help_main"},
    {"text": "❌ Close",      "callback_data": "close"},
]]}

def help_main_kb():
    return {"inline_keyboard": [
        [{"text": "📢 Channel Setup",  "callback_data": "help_ch"},
         {"text": "👥 Group Setup",    "callback_data": "help_grp"}],
        [{"text": "🤖 Commands List",  "callback_data": "help_cmds"},
         {"text": "😂 Emoji List",     "callback_data": "help_emojis"}],
        [{"text": "⚙️ Settings Guide", "callback_data": "help_settings"},
         {"text": "📢 Broadcast Help", "callback_data": "help_bcast"}],
        [{"text": "❌ Close",          "callback_data": "close"}],
    ]}

HELP_TEXTS = {
    "main": (
        "❓ <b>Help Center</b>\n\n"
        "Choose a topic below to learn how each feature works.\n"
        "Every button shows real examples 👇"
    ),

    "ch": (
        "📢 <b>Channel Setup Guide</b>\n\n"
        "<b>⚠️ CRITICAL — Main bot must be Admin!</b>\n"
        "Bot only receives channel posts if BOT_TOKENS[0]\n"
        "is an admin in your channel.\n\n"
        "<b>Step-by-step:</b>\n\n"
        "1️⃣ Send <code>/bots</code> to get all usernames\n"
        "   Example: @ReactBot1, @ReactBot2...\n\n"
        "2️⃣ Open your channel → Settings\n"
        "   → Administrators → Add Admin\n"
        "   → Search each bot → Add\n\n"
        "3️⃣ Permissions to give each bot:\n"
        "   ✅ <b>Add Reactions</b>   ← Must ON\n"
        "   ❌ Others not needed\n\n"
        "4️⃣ Post any message in channel\n"
        "   → Reactions appear in 1–3 seconds\n\n"
        "<b>Channel Rules (Telegram limit):</b>\n"
        "• Only small reactions (no big/animated)\n"
        "• 1 bot = 1 reaction\n"
        "• Only admin bots will react\n\n"
        "💡 <b>Example:</b> 3 bots admin → 3 reactions\n"
        "   1 bot admin → 1 reaction\n\n"
        "🔧 <b>Troubleshoot:</b>\n"
        "If no reactions: Check that BOT_TOKENS[0]\n"
        "(your main bot) is admin in the channel!"
    ),

    "grp": (
        "👥 <b>Group Setup Guide</b>\n\n"
        "<b>Step-by-step:</b>\n\n"
        "1️⃣ Send <code>/bots</code> to get all usernames\n\n"
        "2️⃣ Open group → Edit → Administrators → Add\n"
        "   → Add each bot → Enable:\n"
        "   ✅ <b>Add Reactions</b>   ← Must ON\n\n"
        "3️⃣ Done! Every message gets reactions 🎉\n\n"
        "<b>Example reaction flow:</b>\n"
        "User: 'Hello everyone!'\n"
        "╔══════════════════╗\n"
        "║ Bot1 → ❤  (BIG)  ║\n"
        "║ Bot2 → 🔥 (BIG)  ║\n"
        "║ Bot3 → 🎉 (BIG)  ║\n"
        "║ Bot4 → 👏 (small)║\n"
        "║ Bot5 → 😍 (small)║\n"
        "╚══════════════════╝\n"
        "→ All within 5–8 seconds\n\n"
        "<b>Limited Reactions (group setting):</b>\n"
        "If admin limited emojis → bot auto-detects\n"
        "and only uses allowed ones. No setup needed!"
    ),

    "cmds": (
        "🤖 <b>All Commands</b>\n\n"
        "<b>👤 For Everyone:</b>\n"
        "• /start  →  Welcome + bot stats\n"
        "  <i>Shows: Active bots, reactions sent, users</i>\n\n"
        "• /help  →  This help center\n"
        "  <i>Tap any topic button to learn more</i>\n\n"
        "• /bots  →  All bot usernames\n"
        "  <i>Copy and add them as channel/group admins</i>\n\n"
        "• /premium  →  Premium plan info\n\n"
        "<b>👑 Owner Only:</b>\n"
        "• /settings  →  Control panel\n"
        "  <i>Toggle reactions, force sub, big anim...</i>\n\n"
        "• /stats  →  Detailed statistics\n"
        "  <i>Users, reactions, queue, cached chats</i>\n\n"
        "• /users  →  All registered users\n"
        "  <i>Paginated list with clickable profile links</i>\n\n"
        "• /broadcast &lt;text&gt;  →  Send to all users\n"
        "  <i>Example: /broadcast New update available!</i>\n\n"
        "• /lock  →  Pause all reactions\n"
        "• /unlock  →  Resume reactions"
    ),

    "emojis": (
        f"😂 <b>Reaction Emojis</b> — Total: {len(EMOJIS)}\n\n"
        + "  ".join(EMOJIS[:12]) + "\n"
        + "  ".join(EMOJIS[12:24]) + "\n"
        + "  ".join(EMOJIS[24:36]) + "\n"
        + "  ".join(EMOJIS[36:]) + "\n\n"
        "<b>How they're picked:</b>\n"
        "• Random from allowed list each time\n"
        "• Groups: filtered to admin-allowed only\n"
        "• Channels: random from full list\n"
        "• Force sub fail: always 💩\n\n"
        "⚠️ <b>Important:</b> Uses plain ❤ (not ❤️)\n"
        "Telegram Bot API requires exact Unicode"
    ),

    "settings": (
        "⚙️ <b>Settings Panel Guide</b>\n\n"
        "Open: /settings  (owner only)\n\n"
        "🔒 <b>Pause / Resume</b>\n"
        "   → Stops all reactions globally\n"
        "   → Example: Maintenance mode\n\n"
        "💬 <b>DM Reactions</b>\n"
        "   → React when users message bot in DM\n"
        "   → Toggle OFF if you don't want this\n\n"
        "👥 <b>Group Reactions</b>\n"
        "   → React in group chats\n"
        "   → Includes big animated reactions\n\n"
        "📢 <b>Channel Reactions</b>\n"
        "   → React to channel posts\n"
        "   → Small reactions only (Telegram limit)\n\n"
        "⚡ <b>Big Animations</b>\n"
        "   → First 3 group reactions = animated\n"
        "   → OFF = all reactions are small\n\n"
        "🔐 <b>Force Subscribe</b>\n"
        "   → Users must join your channel first\n"
        "   → Non-subscribers get 💩 on /start\n"
        f"   → Channel: {FORCE_SUB_CHANNEL or '(not set in env)'}\n\n"
        "👥 <b>User List Button</b>\n"
        "   → Click tapped name = opens Telegram profile\n"
        "   → 10 users per page, paginated"
    ),

    "bcast": (
        "📢 <b>Broadcast System Guide</b>\n\n"
        "<b>Method 1 — Text in command:</b>\n"
        "<code>/broadcast Hello everyone!</code>\n"
        "→ Sends that text to all users\n\n"
        "<b>Method 2 — Reply to message:</b>\n"
        "→ Reply to any message with /broadcast\n"
        "→ That message gets forwarded to all\n\n"
        "<b>What you'll see:</b>\n"
        "📤 Broadcasting to 1,234 users...\n"
        "      ↓ (after completion)\n"
        "✅ Broadcast Done!\n"
        "   • Sent:   1,200\n"
        "   • Failed: 34\n\n"
        "⚠️ <b>Notes:</b>\n"
        "• Owner only\n"
        "• Rate: 1 msg / 0.05s (Telegram safe)\n"
        "• Failed = user blocked the bot\n"
        "• Use wisely — no spam!"
    ),
}


# ═══════════════════════════════════════════════════════════════
# KEYBOARDS
# ═══════════════════════════════════════════════════════════════
def main_kb():
    return {"inline_keyboard": [
        [{"text": "📢 Updates",    "url": config.UPDATE_CHANNEL_URL}],
        [{"text": "👨‍💻 Developer","url": f"https://t.me/{config.DEVELOPER_USERNAME}"},
         {"text": "❓ Help",       "callback_data": "help_main"}],
        [{"text": "⚠️ Report",    "url": config.ERROR_REPORT_BOT}],
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
        return parts.split('@',1)[1].lower() in OWN_USERNAMES
    return parts.lower() in ('/lock','/unlock','/stats','/bots','/broadcast','/settings','/users')


# ═══════════════════════════════════════════════════════════════
# COMMANDS
# ═══════════════════════════════════════════════════════════════
def handle_cmd(text, chat_id, msg_id, uid, uname="", chat_type="private", reply_to=None):
    parts = text.split(None, 1)
    cmd   = parts[0].split('@')[0].lower()
    own   = (uid == OWNER_ID)
    arg   = parts[1].strip() if len(parts) > 1 else ""

    if cmd == '/start':
        db.add_user(uid, uname, uname)
        if FORCE_SUB_CHANNEL and db.get("force_sub_on") and not own:
            if not check_sub(uid):
                enqueue(chat_id, msg_id, chat_type, forced="💩")
                send(chat_id,
                    "🔒 <b>Access Required</b>\n\n"
                    f"Join our channel first:\n{FORCE_SUB_CHANNEL}\n\n"
                    "Then tap <b>I've Joined</b> below.", fsub_kb())
                return
        enqueue(chat_id, msg_id, chat_type)
        txt = (
            f"🌸 <b>Welcome, {uname or 'User'}!</b>\n\n"
            "✨ I add <b>animated reactions</b> to every message "
            "using multiple bot tokens simultaneously!\n\n"
            "📊 <b>Stats:</b>\n"
            f"  🤖 Active Bots:   {len(BOT_TOKENS)}\n"
            f"  🎭 Reactions Sent: {db.reactions:,}\n"
            f"  👥 Total Users:   {db.user_count():,}\n\n"
            "👑 <b>Owner:</b> @technicalSerena\n\n"
            "👇 Use the buttons below to get started!"
        )
        if WELCOME_GIF_URL: send(chat_id, txt, main_kb(), anim=WELCOME_GIF_URL)
        elif START_PIC_URL: send(chat_id, txt, main_kb(), photo=START_PIC_URL)
        else:               send(chat_id, txt, main_kb())

    elif cmd == '/help':
        send(chat_id, HELP_TEXTS["main"], help_main_kb())

    elif cmd == '/bots':
        names = all_usernames()
        t = "🤖 <b>Bot Usernames</b>\n\nAdd each as admin → enable <b>Add Reactions</b>:\n\n"
        for i, n in enumerate(names, 1): t += f"  {i}. {n}\n"
        t += ("\n<b>Channel:</b> Add → Settings → Admins → Add → ✅ Add Reactions\n"
              "<b>Group:</b>   Add → Admin → ✅ Add Reactions")
        send(chat_id, t)

    elif cmd == '/settings' and own:
        send(chat_id, settings_text(), settings_kb())

    elif cmd == '/stats' and own:
        send(chat_id,
            "📊 <b>Bot Statistics</b>\n\n"
            f"  👥 Users:        {db.user_count():,}\n"
            f"  🎭 Reactions:    {db.reactions:,}\n"
            f"  🤖 Tokens:       {len(BOT_TOKENS)}\n"
            f"  😂 Emojis:       {len(EMOJIS)}\n"
            f"  📬 Queue:        {rq.qsize()} pending\n"
            f"  📋 Cached chats: {len(_rcache)}\n"
            f"  🔒 Status:       {'Paused' if db.is_locked() else 'Active'}\n"
            f"  📢 Force Sub:    {'ON' if db.get('force_sub_on') else 'OFF'}\n"
            f"  ⚡ Big Anim:     {'ON' if db.get('big_anim') else 'OFF'}"
        )

    elif cmd == '/users' and own:
        txt, kb = users_page(0)
        send(chat_id, txt, kb)

    elif cmd == '/broadcast' and own:
        # Method 1: /broadcast <text>
        if arg:
            threading.Thread(target=do_broadcast, args=(chat_id, arg), daemon=True).start()
        # Method 2: reply to message
        elif reply_to and reply_to.get("text"):
            threading.Thread(
                target=do_broadcast,
                args=(chat_id, reply_to["text"]),
                daemon=True
            ).start()
        else:
            # Method 3: wait for next message
            _bcast_state[uid] = True
            send(chat_id,
                "📢 <b>Broadcast Mode</b>\n\n"
                "Send the message you want to broadcast.\n"
                "Or /cancel to cancel.")

    elif cmd == '/cancel' and own:
        _bcast_state.pop(uid, None)
        send(chat_id, "❌ Broadcast cancelled.")

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
            "• Custom emoji sets per chat\n"
            "• MongoDB persistent storage\n\n"
            "Contact @technicalSerena to upgrade.")

    else:
        if chat_type == "private":
            send(chat_id,
                "❓ Unknown command.\n\n"
                "Try /help for the full guide, or /start to begin.")


# ═══════════════════════════════════════════════════════════════
# CALLBACKS
# ═══════════════════════════════════════════════════════════════
def handle_cb(cb_id, data, chat_id, msg_id, uid):
    own = (uid == OWNER_ID)

    # Settings toggles (owner only)
    if data.startswith("st_") and own:
        key = data[3:]
        if key == "locked":
            new = db.toggle("locked")
            answer_cb(cb_id, "🔒 Paused" if new else "🔓 Resumed")
        elif key in db.cfg:
            new = db.toggle(key)
            answer_cb(cb_id, f"{'✅ ON' if new else '❌ OFF'}")
        else:
            answer_cb(cb_id)
        edit(chat_id, msg_id, settings_text(), settings_kb())
        return

    if data == "settings" and own:
        edit(chat_id, msg_id, settings_text(), settings_kb())
        answer_cb(cb_id)
        return

    if data == "live_stats" and own:
        edit(chat_id, msg_id,
            "📊 <b>Live Stats</b>\n\n"
            f"  👥 Users:     {db.user_count():,}\n"
            f"  🎭 Reactions: {db.reactions:,}\n"
            f"  📬 Queue:     {rq.qsize()} pending\n"
            f"  🕒 {datetime.now().strftime('%H:%M:%S')}",
            {"inline_keyboard": [[
                {"text": "🔙 Settings", "callback_data": "settings"},
                {"text": "🔄 Refresh",  "callback_data": "live_stats"},
            ]]}
        )
        answer_cb(cb_id)
        return

    # User list pagination (owner only)
    if data.startswith("users_") and own:
        page = int(data.split("_")[1])
        txt, kb = users_page(page)
        edit(chat_id, msg_id, txt, kb)
        answer_cb(cb_id)
        return

    # Help topics (anyone)
    if data == "help_main":
        edit(chat_id, msg_id, HELP_TEXTS["main"], help_main_kb())
        answer_cb(cb_id); return

    topic_map = {
        "help_ch":       "ch",
        "help_grp":      "grp",
        "help_cmds":     "cmds",
        "help_emojis":   "emojis",
        "help_settings": "settings",
        "help_bcast":    "bcast",
    }
    if data in topic_map:
        edit(chat_id, msg_id, HELP_TEXTS[topic_map[data]], BACK_KB)
        answer_cb(cb_id); return

    # Force sub check
    if data == "check_sub":
        if check_sub(uid):
            answer_cb(cb_id, "✅ Verified!")
            send(chat_id, "✅ Verified! Send /start now.")
        else:
            answer_cb(cb_id, "❌ Not joined yet")
            send(chat_id, "❌ Still not joined. Please join first!")
        return

    if data == "close":
        api(BOT_TOKENS[0], "deleteMessage",
            {"chat_id": chat_id, "message_id": msg_id})
        answer_cb(cb_id); return

    if data == "noop":
        answer_cb(cb_id); return

    answer_cb(cb_id)


# ═══════════════════════════════════════════════════════════════
# POLLING
# ═══════════════════════════════════════════════════════════════
def poll():
    print("Long polling started...")
    offset = 0; mt = BOT_TOKENS[0]
    while True:
        try:
            resp = api(mt, "getUpdates",
                       {"offset": offset, "timeout": LONG_POLL},
                       rt=POLL_TO)
            if not resp.get("ok"):
                print(f"getUpdates: {resp.get('description')}"); time.sleep(5); continue

            for upd in resp.get("result", []):
                offset = upd["update_id"] + 1

                # ── Callback ──────────────────────────────────────
                if "callback_query" in upd:
                    cb = upd["callback_query"]
                    handle_cb(cb["id"], cb.get("data",""),
                              cb["message"]["chat"]["id"],
                              cb["message"]["message_id"],
                              cb["from"]["id"])
                    continue

                # ── Message ───────────────────────────────────────
                if "message" in upd:
                    msg   = upd["message"]
                    cid   = msg["chat"]["id"]
                    mid   = msg["message_id"]
                    ctype = msg["chat"].get("type","private")
                    frm   = msg.get("from", {})
                    uid   = frm.get("id", 0)
                    uname = frm.get("username","") or frm.get("first_name","")

                    if uid: db.add_user(uid, frm.get("first_name",""), frm.get("username",""))

                    # Owner in broadcast-wait state?
                    if uid == OWNER_ID and uid in _bcast_state:
                        del _bcast_state[uid]
                        txt = msg.get("text","") or msg.get("caption","")
                        if txt:
                            threading.Thread(
                                target=do_broadcast, args=(cid, txt), daemon=True
                            ).start()
                        else:
                            send(cid, "❌ Only text broadcast supported. Cancelled.")
                        continue

                    # Command?
                    if "text" in msg and msg["text"].startswith('/'):
                        if not should_handle(msg["text"], ctype): continue
                        handle_cmd(msg["text"], cid, mid, uid, uname,
                                   chat_type=ctype,
                                   reply_to=msg.get("reply_to_message"))
                        continue

                    # Normal message → react
                    enqueue(cid, mid, ctype)

                # ── Channel Post ──────────────────────────────────
                elif "channel_post" in upd:
                    post  = upd["channel_post"]
                    cid   = post["chat"]["id"]
                    mid   = post["message_id"]
                    if "text" in post and post["text"].startswith('/'): continue
                    # ✅ chat_type="channel" → is_big=False inside react_all
                    enqueue(cid, mid, "channel")

        except Exception as e:
            print(f"Poll error: {e}"); time.sleep(10)


# ═══════════════════════════════════════════════════════════════
# HEALTH SERVER
# ═══════════════════════════════════════════════════════════════
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type','text/plain')
        self.end_headers()
        self.wfile.write((
            f"REACTION BOT {VERSION} — ACTIVE\n\n"
            f"Users:      {db.user_count():,}\n"
            f"Reactions:  {db.reactions:,}\n"
            f"Tokens:     {len(BOT_TOKENS)}\n"
            f"Emojis:     {len(EMOJIS)}\n"
            f"Queue:      {rq.qsize()}\n"
            f"Cached:     {len(_rcache)}\n"
            f"Locked:     {db.is_locked()}\n\n"
            f"Time: {datetime.now():%Y-%m-%d %H:%M:%S}"
        ).encode())
    def log_message(self,*a): pass

def health():
    try: HTTPServer(('0.0.0.0',PORT),H).serve_forever()
    except Exception as e: print(f"Health: {e}")


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════
def main():
    print("=" * 60)
    for t in BOT_TOKENS[:3]:
        api(t, "deleteWebhook", {"drop_pending_updates": True})
    fetch_own()
    start_workers()
    threading.Thread(target=health, daemon=True).start()
    r = api(BOT_TOKENS[0], "getMe")
    if r.get("ok"): print(f"Main Bot: @{r['result']['username']}")
    print(f"Tokens={len(BOT_TOKENS)} | Emojis={len(EMOJIS)}")
    print("=" * 60)
    poll()

if __name__ == '__main__':
    main()
