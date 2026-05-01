# config.py – All settings

import os

# ==================== REQUIRED ====================
# Bot tokens (comma separated in Render env)
BOT_TOKENS = [t.strip() for t in os.getenv("BOT_TOKENS", "").split(",") if t.strip()]

# Your Telegram user ID (owner)
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# ==================== OPTIONAL ====================
# Force subscription channel (e.g., "@serenaunzipbot")
FORCE_SUB_CHANNEL = os.getenv("FORCE_SUB_CHANNEL", "")

# Port for health server
PORT = int(os.getenv("PORT", "10000"))

# Reaction settings — uses ALL tokens
MAX_REACTIONS       = len(BOT_TOKENS)
BIG_REACTIONS_COUNT = 3   # first N reactions are big/animated

# Inline button URLs
UPDATE_CHANNEL_URL  = "https://t.me/serenaunzipbot"
ERROR_REPORT_BOT    = "https://t.me/Technical_serenabot"
DEVELOPER_USERNAME  = "technicalSerena"

# Start picture (optional)
START_PIC_URL   = ""
WELCOME_GIF_URL = "https://media4.giphy.com/media/v1.Y2lkPTZjMDliOTUyeTgzeXBsNXdmbGo2YmRkd3dtcDY3aWtuNWU1azYyNGt0c2JzZ21rdSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/Ed7grcEsfruMYR8QRh/giphy.gif"

# ==================== VIEWS (OPTIONAL) ====================
# Ye feature channel posts pe views add karta hai via Pyrogram userbot.
#
# Enable karne ke steps:
#   1. https://my.telegram.org → jaake API_ID aur API_HASH lo
#   2. Session string generate karo:
#        python3 -c "
#        from pyrogram import Client
#        Client('x', api_id=YOUR_ID, api_hash='YOUR_HASH').run()
#        "
#      (ek baar run karo, login karo, Ctrl+C maaro — session string milegi)
#   3. Render.com pe teen env vars add karo:
#        API_ID       → integer
#        API_HASH     → string
#        USER_SESSION → session string
#   4. requirements.txt me add karo:  pyrogram[fast]
#
# Agar ye set nahi ho to views feature silently disable rahega.
# ─────────────────────────────────────────────────────────
API_ID       = int(os.getenv("API_ID", "0"))
API_HASH     = os.getenv("API_HASH", "")
USER_SESSION = os.getenv("USER_SESSION", "")
