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

# Reaction settings – use ALL tokens
MAX_REACTIONS = len(BOT_TOKENS)   # uses every bot token you add
BIG_REACTIONS_COUNT = 3           # first N reactions are big/animated

# Inline button URLs
UPDATE_CHANNEL_URL = "https://t.me/serenaunzipbot"
ERROR_REPORT_BOT = "https://t.me/Technical_serenabot"
DEVELOPER_USERNAME = "technicalSerena"

# Start picture (optional) – direct image URL
START_PIC_URL = ""   # leave empty if you don't want an image

# Welcome animation GIF (fire effect)
WELCOME_GIF_URL = "https://media.giphy.com/media/3o7abB06u9bNzA8LC8/giphy.gif"
