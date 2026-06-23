# 🤖 Ali Translator

A multilingual Telegram translation bot. Main pair: 🇸🇦 **Arabic** ⇄ 🇬🇧 **English**. Supports **100+ languages** via Google Translator (no API key required).

## ✨ Features

- **Auto-detect** source language and flip between Arabic and English.
- **`/to <lang> <text>`** — translate into any supported language.
- **`/from <lang> <text>`** — translate *from* a specific language to its main partner.
- **`/langs`** — list **all** supported languages with country flags.
- **`/syn <word>`** — get English **synonyms** (uses the free Dictionary API).
- **`/ant <word>`** — get English **antonyms**.
- 🔁 **Logo & branding** — bot short description, full description, and command list are registered on startup.
- Lightweight: pure Python, single process, runs anywhere.

## 🚀 Setup

### 1. Clone & install

```bash
git clone https://github.com/hasbunallah01/Ali-translator.git
cd Ali-translator
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env and put your Telegram bot token from @BotFather
```

### 3. Run

```bash
python bot.py
```

## 🐳 Run with Docker (optional)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot.py .
ENV TELEGRAM_BOT_TOKEN=""
CMD ["python", "bot.py"]
```

```bash
docker build -t ali-translator .
docker run -e TELEGRAM_BOT_TOKEN=xxx --restart unless-stopped ali-translator
```

## ☁️ Run on a free VPS (recommended for 24/7 uptime)

The bot needs a host that stays online. Cheap/free options:

- **Railway.app** — one-click deploy from GitHub (see below)
- **Fly.io** — free tier with `fly launch`
- **Oracle Cloud free tier VM** — always-free ARM VM, run with `systemd`
- **A small Hetzner/DigitalOcean droplet** — €4/mo

### 🚂 Deploy on Railway

1. Go to https://railway.app → **New Project → Deploy from GitHub repo**
2. Select `hasbunallah01/Ali-translator`
3. Railway will detect the `Dockerfile` automatically. The included `railway.toml` pins the start command.
4. In your service → **Variables**, add:
   - `TELEGRAM_BOT_TOKEN` = your bot token from @BotFather
5. **Settings → Networking → Generate Domain** (optional, not needed for a polling bot)
6. Hit **Deploy**. Watch the logs — you should see `Ali Translator is starting…`

Free tier gives you $5/month of usage, which is plenty for a low-traffic bot.

### Example: Oracle Cloud / generic Linux VM with systemd

```ini
# /etc/systemd/system/ali-translator.service
[Unit]
Description=Ali Translator Bot
After=network.target

[Service]
WorkingDirectory=/opt/ali-translator
EnvironmentFile=/opt/ali-translator/.env
ExecStart=/opt/ali-translator/.venv/bin/python bot.py
Restart=always
User=ubuntu

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ali-translator
sudo journalctl -u ali-translator -f
```

## 💬 Bot commands

| Command | What it does |
|---|---|
| `/start` | Welcome message |
| `/help` | Usage help |
| `/langs` | Show **all** supported languages with country flags |
| `/to <lang> <text>` | Translate text into `<lang>` (code or name) |
| `/from <lang> <text>` | Translate text *from* `<lang>` to its main partner |
| `/syn <word>` | English **synonyms** of `<word>` |
| `/ant <word>` | English **antonyms** of `<word>` |
| *any text* | Auto-detect and flip Arabic ⇄ English (fallback: → English) |

> `/syn` and `/ant` work best with English words. For non-English words, the bot will translate to English first and then look it up.

## 🔐 Security

- Your `.env` is **gitignored** — never commit the bot token.
- The repo uses `python-dotenv` to load it at runtime.

## 📜 License

MIT