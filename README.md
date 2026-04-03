<!-- markdownlint-disable MD033 -->
<p align="center">
  <img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=28&duration=3000&pause=500&color=F75C7E&center=true&vCenter=true&width=500&lines=✨+Save+Restricted+Bot+✨;🌸+Animated+Reactions+Bot+🌸;⚡+Multiple+Bots+%3D+Multiple+Reactions+⚡" alt="Typing SVG" />
</p>

<p align="center">
  <a href="https://t.me/technicalSerena">
    <img src="https://img.shields.io/badge/Developer-@technicalSerena-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white" />
  </a>
  <a href="https://t.me/serenaunzipbot">
    <img src="https://img.shields.io/badge/Join-Channel-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white" />
  </a>
  <a href="https://render.com">
    <img src="https://img.shields.io/badge/Deployed%20on-Render-46E3B7?style=for-the-badge&logo=render&logoColor=white" />
  </a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-blue?style=flat-square&logo=python" />
  <img src="https://img.shields.io/badge/Telegram%20Bot-API-blue?style=flat-square&logo=telegram" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" />
  <img src="https://img.shields.io/badge/Status-Online-brightgreen?style=flat-square" />
</p>

---

## 🌸 About the Bot

**Save Restricted Bot** is a powerful Telegram bot that:

- ✅ Adds **multiple animated reactions** to any message (text, photo, video, sticker, document)
- ✅ Uses **several bot tokens** → one token = one reaction (up to 10 reactions per message)
- ✅ First **3 reactions are BIG & ANIMATED** (like a user long‑pressing the emoji)
- ✅ Beautiful **inline keyboard** with buttons: *Update Channel*, *Support Group*, *Developer*, *Help*
- ✅ Optional **force subscription** to your channel
- ✅ **Admin commands**: `/lock`, `/unlock`, `/stats`, `/broadcast`
- ✅ **No 409 errors** – only one bot polls, others only send reactions
- ✅ **100% free** – works on Render free tier

---

## 🎯 Features in Detail

| Feature | Description |
|---------|-------------|
| **Animated Reactions** | `is_big=True` – Telegram’s native long‑press effect |
| **Multi‑Token Support** | Add as many bot tokens as you want (max 10 recommended) |
| **Channel & Group Ready** | Works perfectly in channels, groups, and private chats |
| **Force Subscription** | Users must join your channel before using the bot |
| **Rich Keyboard** | Inline buttons with custom callbacks |
| **Health Check** | Built‑in HTTP server for Render monitoring |
| **User Database** | Stores user IDs and reaction counts (simple JSON) |

---

## 🚀 Deploy to Render (Step‑by‑Step)

### 1. Create Bot Tokens
- Open Telegram → [@BotFather](https://t.me/BotFather)
- Send `/newbot` and follow instructions
- **Repeat** to create **at least 2 bots** (more tokens = more reactions)
- Copy each token (looks like `1234567890:ABCdef...`)

### 2. Prepare GitHub Repository
Create a new repository and upload the following files (already provided above):

### 3. Deploy on Render

1. Go to [render.com](https://render.com) and sign in.
2. Click **New +** → **Web Service**.
3. Connect your GitHub repository.
4. Fill in the details:

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
7. Wait for the build (approx. 1‑2 minutes).  
   Once deployed, you will see a URL like `https://reaction-bot.onrender.com`.

### 4. Set Up Webhook (Optional – Not Needed for Polling)

The bot uses **long polling**, so **no webhook setup** is required.  
It will start listening automatically after deployment.

### 5. Test Your Bot

- Open Telegram and find your bot (the **first** token’s username).
- Send `/start` – you should see the welcome message with buttons.
- Send a normal message – the bot will reply with **multiple animated reactions**.
- Add **all your bot tokens** as administrators to your channel/group (enable “Add Reactions” permission).  
  Now every new post will automatically get reactions.

---

## 📸 Preview (as in your screenshots)

<p align="center">
  <img src="https://via.placeholder.com/400x800?text=Bot+Screenshot+1" width="250" />
  <img src="https://via.placeholder.com/400x800?text=Bot+Screenshot+2" width="250" />
</p>

*(Replace with actual screenshots after deployment)*

---

## 👑 Owner & Developer

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

## ⚡ Quick Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message + inline menu |
| `/stats` | Show bot statistics (owner only) |
| `/lock` | Disable reactions (owner only) |
| `/unlock` | Enable reactions (owner only) |
| `/broadcast` | Send a message to all users (owner only) |
| `/premium` | Information about premium plan |

---

## ❓ Troubleshooting

- **Bot doesn’t react** → Make sure you added all bot tokens as admins and enabled “Add Reactions” permission.
- **409 error** → Already fixed in this code (only one bot polls). If you still see it, wait 1‑2 minutes – the old webhook will expire.
- **Reactions are not animated** → Check that you used at least **Python 3.11** (runtime.txt) and the bot token has permission.
- **Force subscription not working** → Ensure `FORCE_SUB_CHANNEL` is set exactly as `@username` (including `@`) and the bot is **admin** of that channel.

---

<p align="center">
  Made with ❤️ by <b>Technical Serena</b> – <i>“Automate everything, react beautifully.”</i>
</p>
