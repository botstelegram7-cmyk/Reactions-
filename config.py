# config.py – All your settings in one place

# ==================== REQUIRED ====================
# List of bot tokens (comma separated in Render env, but here we read from env)
# We'll read from environment variable BOT_TOKENS
import os

BOT_TOKENS = [t.strip() for t in os.getenv("BOT_TOKENS", "").split(",") if t.strip()]

# Your Telegram user ID (owner)
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# ==================== OPTIONAL ====================
# Force subscription channel (e.g., "@serenaunzipbot")
FORCE_SUB_CHANNEL = os.getenv("FORCE_SUB_CHANNEL", "")

# Port for health server (Render uses PORT env)
PORT = int(os.getenv("PORT", "10000"))

# Reaction settings
MAX_REACTIONS = 8          # Max reactions per message (limited by number of tokens)
MIN_REACTIONS = 3          # Min reactions (will be at least number of tokens)
BIG_REACTIONS_COUNT = 3    # First N reactions will be big/animated

# Inline button URLs
UPDATE_CHANNEL_URL = "https://t.me/serenaunzipbot"
ERROR_REPORT_BOT = "https://t.me/Technical_serenabot"   # error report bot link
DEVELOPER_USERNAME = "technicalSerena"                  # without @
