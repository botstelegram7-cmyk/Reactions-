<!-- markdownlint-disable MD033 -->
<p align="center">
  <img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=700&size=32&duration=3500&pause=500&color=F75C7E&center=true&vCenter=true&width=600&height=70&lines=✨+Animated+Reaction+Bot+✨;🌸+Multi‑Token+Reactions+🌸;⚡+BIG+Long‑Press+Effect+⚡" alt="Typing SVG" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Telegram%20Bot-API-blue?style=for-the-badge&logo=telegram&logoColor=white" />
  <img src="https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python&logoColor=yellow" />
  <img src="https://img.shields.io/badge/Deploy%20on-Render-46E3B7?style=for-the-badge&logo=render&logoColor=white" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" />
</p>

<p align="center">
  <a href="https://t.me/technicalSerena">
    <img src="https://img.shields.io/badge/Developer-@technicalSerena-2CA5E0?style=flat-square&logo=telegram&logoColor=white" />
  </a>
  <a href="https://t.me/serenaunzipbot">
    <img src="https://img.shields.io/badge/Join%20Channel-2CA5E0?style=flat-square&logo=telegram&logoColor=white" />
  </a>
  <a href="https://github.com/yourusername/reaction-bot">
    <img src="https://img.shields.io/github/stars/yourusername/reaction-bot?style=social" />
  </a>
</p>

---

## 🌸 About the Bot

**Animated Reaction Bot** adds **multiple big, animated reactions** to any message – exactly like a user long‑pressing an emoji.

- 🚀 Uses **several bot tokens** → one token = one reaction (up to 10 reactions per message)
- 🎯 First **3 reactions are BIG & ANIMATED** (`is_big=True`) – lasts 2‑3 seconds
- 📢 Works in **channels, groups, and private chats**
- 💡 **No 409 errors** – only one bot polls, others only send reactions
- 🔧 Built with **pure Python + requests** – no heavy libraries

---

## ✨ Features at a Glance

| Feature | Description |
|---------|-------------|
| **Animated Reactions** | `is_big=True` → Telegram’s native long‑press effect |
| **Multi‑Token Support** | Add as many bot tokens as you want (max 10 recommended) |
| **Channel / Group Ready** | Works perfectly in channels, groups, and private chats |
| **Force Subscription** | Optional – users must join your channel before using the bot |
| **Inline Keyboard** | Buttons: Update Channel, Support Group, Developer, Help |
| **Admin Commands** | `/lock`, `/unlock`, `/stats`, `/broadcast`, `/bots` |
| **Health Check** | Built‑in HTTP server for Render monitoring |
| **User Database** | Stores user IDs and reaction counts (simple JSON) |

---

## 🎬 Demo (Animated Preview)

<p align="center">
  <img src="https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExN3h2eGJ4aGpkNWt1bnN6dGZydWYycHNpYzZ1Y2JhZ2V4dnV0NXF5dyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/3o7abB06u9bNzA8LC8/giphy.gif" width="400" />
  <br />
  <i>Example: first 3 reactions are BIG & animated</i>
</p>

*(Replace with your own screen recording or GIF)*

---

## 📋 Commands

| Command | Who | Description |
|---------|-----|-------------|
| `/start` | Everyone | Welcome message + inline keyboard |
| `/stats` | Owner | Show bot statistics |
| `/lock` | Owner | Disable all reactions |
| `/unlock` | Owner | Enable reactions |
| `/bots` | Owner | List all bot usernames (to add as admins) |
| `/broadcast` | Owner | Send a message to all users |
| `/premium` | Everyone | Info about premium plan (optional) |

---

## 🚀 Deploy to Render – Step by Step

### 1. Create Bot Tokens
- Go to [@BotFather](https://t.me/BotFather) on Telegram.
- Send `/newbot` and follow instructions.
- **Repeat** to create **at least 2 bots** (more tokens = more reactions).
- Copy each token (looks like `1234567890:ABCdef...`).

### 2. Prepare GitHub Repository
Create a new repo and upload these 5 files (provided in this repo):

### 3. Deploy on Render
1. Go to [render.com](https://render.com) and sign in.
2. Click **New +** → **Web Service**.
3. Connect your GitHub repository.
4. Fill the details:

   | Field | Value |
   |-------|-------|
   | **Name** | `reaction-bot` (or your choice) |
   | **Environment** | `Python 3` |
   | **Build Command** | `pip install -r requirements.txt` |
   | **Start Command** | `python bot.py` |
   | **Instance Type** | Free |

5. Scroll down to **Environment Variables** and add:

   | Key | Value |
   |-----|-------|
   | `BOT_TOKENS` | `token1,token2,token3` (comma‑separated, no spaces) |
   | `OWNER_ID` | Your numeric Telegram user ID (get from [@userinfobot](https://t.me/userinfobot)) |
   | `FORCE_SUB_CHANNEL` | Optional – e.g. `@serenaunzipbot` (leave empty to disable) |
   | `PORT` | `10000` |

6. Click **Create Web Service**.
7. Wait for the build (~1‑2 minutes).  
   You’ll see a URL like `https://reaction-bot.onrender.com`.

### 4. Add All Bot Usernames as Admins
- After deployment, send `/bots` to your main bot (owner only).
- You will get a list of **all bot usernames** (e.g., `@bot1`, `@bot2`, ...).
- Go to your channel/group → **Add Administrators** → search and add **each** bot username.
- **Important:** Enable the permission **“Add Reactions”** for each bot.

### 5. Test the Bot
- In your channel/group, send any message (text, photo, video, sticker).
- The bot will add **3–8 reactions** – the first 3 will be **BIG & ANIMATED**.
- In private chat, send `/start` to see the welcome message.

---

## 🤖 Owner & Developer

<p align="center">
  <img src="https://img.shields.io/badge/Created%20by-TECHNICAL%20SERENA-ff69b4?style=for-the-badge&logo=telegram&logoColor=white" />
</p>

<p align="center">
  <a href="https://t.me/technicalSerena">
    <img src="https://img.shields.io/badge/Contact%20Owner-2CA5E0?style=flat-square&logo=telegram&logoColor=white" />
  </a>
  <a href="https://t.me/serenaunzipbot">
    <img src="https://img.shields.io/badge/Join%20Channel-2CA5E0?style=flat-square&logo=telegram&logoColor=white" />
  </a>
</p>

**💖 Support the project** – Star this repo, share with friends, and upgrade to Premium for unlimited reactions!

---

## 📜 License

MIT License – feel free to use, modify, and distribute.

---

## ❓ Troubleshooting

| Issue | Solution |
|-------|----------|
| **Bot doesn’t react** | Make sure all bot tokens are added as admins with **“Add Reactions”** permission. |
| **Reactions are not animated** | Check that you used `runtime.txt` with `python-3.11.0`. Also ensure the bot tokens are **not** restricted. |
| **409 error** | Wait 1‑2 minutes after deployment – the old webhook will expire. This code uses **polling** only on one bot. |
| **Force subscription not working** | Verify `FORCE_SUB_CHANNEL` is exactly like `@username` and the bot is **admin** of that channel. |
| **Bot stops after a few hours** | Render free tier may spin down. Use **UptimeRobot** or similar to ping `https://your-app.onrender.com` every 5 minutes. |

---

<p align="center">
  Made with ❤️ by <b>Technical Serena</b> – <i>“React beautifully, automate everything.”</i>
</p>

