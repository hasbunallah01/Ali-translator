"""
Ali Translator — a multilingual Telegram bot. 🔁
Main pair: Arabic (ar) ⇄ English (en). Supports 100+ languages via Google Translator.
Plus: English synonyms (/syn) and antonyms (/ant) via the free Dictionary API.
"""

import asyncio
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import List, Optional, Tuple

# Force unbuffered stdout/stderr so Railway logs stream live.
try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

# Configure logging FIRST so health-server logs (which start very early) are captured.
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
    force=True,
)
logger = logging.getLogger("ali-translator")

# Startup banner — visible immediately in Railway logs.
logger.info("=" * 60)
logger.info("Ali Translator — bot.py loaded")
logger.info("Python: %s", sys.version.split()[0])
logger.info("PORT env (Railway-provided): %r", os.environ.get("PORT"))
logger.info("HEALTHCHECK_PORT env: %r", os.environ.get("HEALTHCHECK_PORT"))
logger.info("TELEGRAM_BOT_TOKEN present: %s", bool(os.environ.get("TELEGRAM_BOT_TOKEN")))
logger.info("=" * 60)

import requests
from deep_translator import GoogleTranslator, exceptions as dt_exceptions
from deep_translator.detection import single_detection
from flags import flag_for
from telegram import BotCommand, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)


# ---------- Healthcheck HTTP server ----------
# Railway (and similar platforms) probe a web endpoint after deploy to confirm
# the container is alive. A pure Telegram bot never answers HTTP, so the probe
# fails and the deploy rolls back. This tiny server answers 200 OK on every GET
# so the platform thinks we're alive, while the bot keeps polling Telegram.
#
# We use HEALTHCHECK_PORT (default 8080) so there's zero chance of colliding
# with PTB's `port` parameter, which is reserved for webhook mode.
class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 (BaseHTTPRequestHandler API)
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Ali Translator bot is alive")

    def log_message(self, *_args, **_kwargs):  # silence default access log
        return


def _start_health_server() -> None:
    # Prefer HEALTHCHECK_PORT if set; otherwise bind to Railway's PORT (which
    # is what the platform's healthcheck probe targets by default); otherwise
    # fall back to 8080. Falling back to PORT is the correct behavior for
    # Railway so the probe can actually reach us.
    port_str = (
        os.environ.get("HEALTHCHECK_PORT")
        or os.environ.get("PORT")
        or "8080"
    )
    try:
        port = int(port_str)
    except ValueError:
        logger.error("Health port %r is not an int, falling back to 8080", port_str)
        port = 8080
    try:
        server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    except OSError as e:
        logger.error("Failed to bind health server on port %s: %s", port, e)
        return
    Thread(target=server.serve_forever, name="health-http", daemon=True).start()
    logger.info("Healthcheck HTTP server listening on 0.0.0.0:%s", port)


# ---------- Config ----------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
BOT_LOGO = "🔁"
BOT_SHORT_DESCRIPTION = "🔁 Multilingual translator (Arabic ⇄ English + 100 more) with synonyms & antonyms."
BOT_DESCRIPTION = (
    "🔁 Ali Translator — translate between 100+ languages, with Arabic ⇄ English "
    "as the headline pair.\n\n"
    "Commands:\n"
    "• /start — welcome\n"
    "• /langs — list all supported languages with flags\n"
    "• /to <lang> <text> — translate into a specific language\n"
    "• /from <lang> <text> — translate from a specific language\n"
    "• /syn <word> — English synonyms\n"
    "• /ant <word> — English antonyms\n\n"
    "Just send any text to auto-translate it (Arabic ⇄ English by default)."
)

MAIN_LANGUAGES = {"ar": "Arabic", "en": "English"}
WELCOME = (
    f"{BOT_LOGO} *Welcome to Ali Translator!* {BOT_LOGO}\n\n"
    "I translate between *100+ languages*. My main pair is 🇸🇦 Arabic ⇄ 🇬🇧 English.\n\n"
    "Just send me any text and I'll auto-detect the language and translate it "
    "into the *other main language*.\n\n"
    "*Commands*\n"
    "/start — show this welcome\n"
    "/help — usage help\n"
    "/langs — list supported languages with flags\n"
    "/to \\<lang\\> \\<text\\> — translate text into a specific language\n"
    "/from \\<lang\\> \\<text\\> — translate text from a specific language\n"
    "/syn \\<word\\> — get English synonyms\n"
    "/ant \\<word\\> — get English antonyms\n\n"
    "Tip: in `/to` and `/from`, language can be a code (`ar`, `en`, `fr`, …) or a full name (`arabic`, `french`)."
)


# ---------- Helpers ----------
def _resolve_lang(user_input: str) -> Optional[str]:
    """Accept 'ar', 'AR', 'arabic', 'Arabic', 'french', etc. → ISO 639-1 code."""
    if not user_input:
        return None
    key = user_input.strip().lower()
    if key in GoogleTranslator().get_supported_languages(as_dict=True):
        return key
    code_map = GoogleTranslator().get_supported_languages(as_dict=True)
    for code, name in code_map.items():
        if name.lower() == key:
            return code
    return None


def _partner(code: str) -> str:
    code = (code or "").lower()
    if code == "ar":
        return "en"
    if code == "en":
        return "ar"
    return "en"


def _truncate(text: str, limit: int = 3800) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


async def _translate_text(text: str, target: str, source_hint: Optional[str] = None) -> Tuple[str, str]:
    try:
        if source_hint and source_hint != "auto":
            detected = source_hint
        else:
            try:
                detected = single_detection(text, api="google") or "auto"
            except Exception:
                detected = "auto"
        translated = GoogleTranslator(source=detected, target=target).translate(text)
        return translated or "", detected
    except dt_exceptions.NotValidPayload:
        return "❗ Empty or invalid input.", "unknown"
    except dt_exceptions.LanguageNotSupportedException:
        return "❗ That language is not supported.", "unknown"
    except dt_exceptions.TranslationNotFound:
        return "❗ Could not translate that. Try rephrasing.", "unknown"
    except Exception as e:  # pragma: no cover
        logger.exception("translate failed: %s", e)
        return f"❗ Translation failed: {e}", "unknown"


def _lookup_word_en(word: str) -> List[dict]:
    """
    Look up an English word in the free dictionary API.
    Returns a list of meaning dicts: [{"pos": "noun", "synonyms": [...], "antonyms": [...]}]
    """
    try:
        r = requests.get(
            f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}",
            timeout=10,
        )
        if r.status_code != 200:
            return []
        data = r.json()
        if not isinstance(data, list):
            return []
    except Exception as e:
        logger.warning("dictionary lookup failed: %s", e)
        return []

    out: List[dict] = []
    for entry in data:
        for meaning in entry.get("meanings", []):
            pos = meaning.get("partOfSpeech", "")
            syns = list(dict.fromkeys(meaning.get("synonyms", []) or []))
            ants = list(dict.fromkeys(meaning.get("antonyms", []) or []))
            for d in meaning.get("definitions", []):
                for s in d.get("synonyms", []) or []:
                    if s not in syns:
                        syns.append(s)
                for a in d.get("antonyms", []) or []:
                    if a not in ants:
                        ants.append(a)
            if syns or ants:
                out.append({"pos": pos, "synonyms": syns, "antonyms": ants})
    return out


# ---------- Handlers ----------
async def cmd_start(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(WELCOME, parse_mode=ParseMode.MARKDOWN)


async def cmd_help(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_start(update, _)


async def cmd_langs(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    code_map = GoogleTranslator().get_supported_languages(as_dict=True)
    main_block = "\n".join(
        f"• {flag_for(c)} `{c}` — {n}" for c, n in MAIN_LANGUAGES.items()
    )
    other_codes = sorted(c for c in code_map.keys() if c not in MAIN_LANGUAGES)
    other_lines = [f"• {flag_for(c)} `{c}` — {code_map[c]}" for c in other_codes]

    header = (
        f"{BOT_LOGO} *Supported languages* {BOT_LOGO}\n\n"
        f"*Main pair:*\n{main_block}\n\n"
        f"_All {len(code_map)} languages are supported via Google Translator._\n\n"
    )
    await update.message.reply_text(header, parse_mode=ParseMode.MARKDOWN)

    chunk, size = [], 0
    for line in other_lines:
        size += len(line) + 1
        chunk.append(line)
        if size > 3000:
            await update.message.reply_text("\n".join(chunk), parse_mode=ParseMode.MARKDOWN)
            chunk, size = [], 0
    if chunk:
        await update.message.reply_text("\n".join(chunk), parse_mode=ParseMode.MARKDOWN)

    await update.message.reply_text(
        f"Send `/to <code> <text>` to translate into any of these. Example:\n"
        f"`/to fr Hello world`",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_to(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.message.reply_text("Usage: `/to <lang> <text>`", parse_mode=ParseMode.MARKDOWN)
        return
    target = _resolve_lang(context.args[0])
    if not target:
        await update.message.reply_text(
            f"❗ Unknown language `{context.args[0]}`. Try `/langs`.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    text = " ".join(context.args[1:])
    translated, source = await _translate_text(text, target)
    flag = f"`{source}` {flag_for(source)} → `{target}` {flag_for(target)}"
    await update.message.reply_text(f"{translated}\n\n{flag}", parse_mode=ParseMode.MARKDOWN)


async def cmd_from(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: `/from <lang> <text>`", parse_mode=ParseMode.MARKDOWN
        )
        return
    source = _resolve_lang(context.args[0])
    if not source:
        await update.message.reply_text(
            f"❗ Unknown language `{context.args[0]}`. Try `/langs`.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    target = _partner(source)
    text = " ".join(context.args[1:])
    try:
        translated = GoogleTranslator(source=source, target=target).translate(text)
    except Exception as e:
        logger.exception("translate failed: %s", e)
        translated = f"❗ Translation failed: {e}"
    await update.message.reply_text(
        f"{translated}\n\n`{source}` {flag_for(source)} → `{target}` {flag_for(target)}",
        parse_mode=ParseMode.MARKDOWN,
    )


async def _render_word_relations(word: str, kind: str, update: Update) -> None:
    """kind: 'syn' or 'ant'"""
    word = (word or "").strip()
    if not word:
        await update.message.reply_text(
            f"Usage: `/{kind} <word>`", parse_mode=ParseMode.MARKDOWN
        )
        return

    lookup_word = word
    translated_from = None
    try:
        detected = single_detection(word, api="google")
    except Exception:
        detected = "auto"
    if detected and detected not in ("en", "auto"):
        try:
            lookup_word = GoogleTranslator(source=detected, target="en").translate(word)
            translated_from = detected
        except Exception:
            lookup_word = word

    meanings = await asyncio.to_thread(_lookup_word_en, lookup_word)
    if not meanings:
        msg = f"❗ No `{kind}` found for *{word}*."
        if translated_from:
            msg += f"\n(I looked up the English form: *{lookup_word}*)"
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        return

    title_kind = "Synonyms" if kind == "syn" else "Antonyms"
    lines = [f"📖 *{title_kind} for* _{word}_"]
    if translated_from:
        lines.append(f"_looked up in English as:_ *{lookup_word}*")
    lines.append("")

    for m in meanings:
        pos = m["pos"] or "—"
        rels = m["synonyms"] if kind == "syn" else m["antonyms"]
        if not rels:
            continue
        rels = rels[:25]
        lines.append(f"*{pos}*")
        lines.append(", ".join(f"`{r}`" for r in rels))
        lines.append("")

    if len(lines) <= 2:
        await update.message.reply_text(
            f"❗ No `{kind}` found for *{word}*.", parse_mode=ParseMode.MARKDOWN
        )
        return

    await update.message.reply_text(_truncate("\n".join(lines)), parse_mode=ParseMode.MARKDOWN)


async def cmd_syn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    word = " ".join(context.args) if context.args else ""
    await _render_word_relations(word, "syn", update)


async def cmd_ant(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    word = " ".join(context.args) if context.args else ""
    await _render_word_relations(word, "ant", update)


async def on_text(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()
    if not text:
        return
    try:
        source = single_detection(text, api="google") or "auto"
    except Exception:
        source = "auto"
    target = _partner(source)
    translated, _src = await _translate_text(text, target, source_hint=source)
    await update.message.reply_text(_truncate(translated))


# ---------- Bot branding ----------
async def _register_bot_profile(app: Application) -> None:
    """Set bot commands list, short description, and full description on startup."""
    commands = [
        BotCommand("start", "Show welcome message"),
        BotCommand("help", "Show usage help"),
        BotCommand("langs", "List all supported languages with flags"),
        BotCommand("to", "Translate to a language: /to <lang> <text>"),
        BotCommand("from", "Translate from a language: /from <lang> <text>"),
        BotCommand("syn", "Get English synonyms: /syn <word>"),
        BotCommand("ant", "Get English antonyms: /ant <word>"),
    ]
    try:
        await app.bot.set_my_commands(commands)
        await app.bot.set_my_short_description(BOT_SHORT_DESCRIPTION)
        await app.bot.set_my_description(BOT_DESCRIPTION)
        logger.info("Bot profile (commands, descriptions) registered.")
    except Exception as e:
        logger.warning("Failed to register bot profile: %s", e)


# ---------- Main ----------
def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

    # Start the healthcheck HTTP server BEFORE the bot so Railway can reach us
    # as soon as the container is up. The bot's polling loop runs after this.
    _start_health_server()

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("langs", cmd_langs))
    app.add_handler(CommandHandler("to", cmd_to))
    app.add_handler(CommandHandler("from", cmd_from))
    app.add_handler(CommandHandler("syn", cmd_syn))
    app.add_handler(CommandHandler("ant", cmd_ant))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    # Register bot branding before polling starts.
    app.post_init = _register_bot_profile

    logger.info("Ali Translator is starting…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()