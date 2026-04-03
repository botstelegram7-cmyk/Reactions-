# config.py – All your settings in one place

import os

# ==================== REQUIRED ====================
# List of bot tokens (comma separated in Render env)
BOT_TOKENS = [t.strip() for t in os.getenv("BOT_TOKENS", "").split(",") if t.strip()]

# Your Telegram user ID (owner)
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# ==================== OPTIONAL ====================
# Force subscription channel (e.g., "@serenaunzipbot")
FORCE_SUB_CHANNEL = os.getenv("FORCE_SUB_CHANNEL", "")

# Port for health server (Render uses PORT env)
PORT = int(os.getenv("PORT", "10000"))

# Reaction settings
# Set MAX_REACTIONS = len(BOT_TOKENS) to use all tokens (even if it takes longer)
MAX_REACTIONS = len(BOT_TOKENS)   # ← now uses ALL your tokens
BIG_REACTIONS_COUNT = 3           # First N reactions will be big/animated

# Inline button URLs
UPDATE_CHANNEL_URL = "https://t.me/serenaunzipbot"
ERROR_REPORT_BOT = "https://t.me/Technical_serenabot"
DEVELOPER_USERNAME = "technicalSerena"

# Start picture (optional) – add a direct image URL (JPG/PNG)
# If empty, no image will be sent.
START_PIC_URL = "https://graph.org/file/your_image.jpg"   # 👈 replace with your own image URL

# Welcome animation (GIF) – appears with the start message
WELCOME_GIF_URL = "https://media.giphy.com/media/3o7abB06u9bNzA8LC8/giphy.gif"  # 🔥 fire animation
