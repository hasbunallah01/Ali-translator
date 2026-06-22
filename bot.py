"""
Ali Translator — a multilingual Telegram bot.
Main languages: Arabic (ar) and English (en).
Supports translation between 100+ languages via Google Translator.
"""

import logging
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Optional, Tuple

from deep_translator import GoogleTranslator, exceptions as dt_exceptions
from deep_translator.detection import single_detection
from telegram import Update
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
class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 (BaseHTTPRequestHandler API)
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"All-translator bot is alive")

    def log_message(self, *_args, **_kwargs):  # silence default access log
        return


def _start_health_server() -> None:
    port = int(os.environ.get("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    Thread(target=server.serve_forever, name="health-http", daemon=True).start()
    logger.info("Healthcheck HTTP server listening on 0.0.0.0:%s", port)

# ---------- Config ----------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
MAIN_LANGUAGES = {"ar": "Arabic", "en": "English"}
WELCOME = (
    "👋 *Welcome to Ali Translator!*\n\n"
    "I translate between *100+ languages*. My main pair is 🇸🇦 Arabic ⇄ 🇬🇧 English.\n\n"
    "Just send me any text and I'll auto-detect the language and translate it "
    "into the *other main language*.\n\n"
    "*Commands*\n"
    "/start — show this welcome\n"
    "/help — usage help\n"
    "/langs — list supported languages\n"
    "/to \\<lang\\> \\<text\\> — translate text into a specific language\n"
    "/from \\<lang\\> \\<text\\> — translate text from a specific language\n\n"
    "Tip: in `/to` and `/from`, language can be a code (`ar`, `en`, `fr`, …) or a full name (`arabic`, `french`)."
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("ali-translator")


# ---------- Helpers ----------
def _resolve_lang(user_input: str) -> Optional[str]:
    """Accept 'ar', 'AR', 'arabic', 'Arabic', 'french', etc. → ISO 639-1 code."""
    if not user_input:
        return None
    key = user_input.strip().lower()
    # Already a code?
    if key in GoogleTranslator().get_supported_languages(as_dict=True):
        return key
    # Try matching against the full name list
    code_map = GoogleTranslator().get_supported_languages(as_dict=True)  # {code: name}
    for code, name in code_map.items():
        if name.lower() == key:
            return code
    return None


def _partner(code: str) -> str:
    """Pick the 'other' main language for the auto-translate flow."""
    code = (code or "").lower()
    if code == "ar":
        return "en"
    if code == "en":
        return "ar"
    # If neither main, default to English so user always gets a useful reply.
    return "en"


def _truncate(text: str, limit: int = 3800) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


async def _translate_text(text: str, target: str, source_hint: Optional[str] = None) -> Tuple[str, str]:
    """
    Translate `text` into `target`. Returns (translated_text, source_code).
    Detects source via deep_translator's single_detection when not supplied.
    """
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


# ---------- Handlers ----------
async def cmd_start(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(WELCOME, parse_mode=ParseMode.MARKDOWN)


async def cmd_help(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_start(update, _)


async def cmd_langs(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    code_map = GoogleTranslator().get_supported_languages(as_dict=True)
    main_block = "\n".join(f"• `{c}` — {n}" for c, n in MAIN_LANGUAGES.items())
    other_codes = sorted(c for c in code_map.keys() if c not in MAIN_LANGUAGES)
    msg = (
        "*Supported languages*\n\n"
        "*Main pair:*\n" + main_block + "\n\n"
        f"_All {len(code_map)} languages are supported via Google Translator._\n"
        "Send `/to <code> <text>` to pick a target explicitly."
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


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
    flag = f"`{source}` → `{target}`"
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
        f"{translated}\n\n`{source}` → `{target}`",
        parse_mode=ParseMode.MARKDOWN,
    )


async def on_text(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()
    if not text:
        return
    # Detect → flip between main languages (ar ⇄ en). If neither, fall back to en.
    try:
        source = single_detection(text, api="google") or "auto"
    except Exception:
        source = "auto"
    target = _partner(source)
    translated, _src = await _translate_text(text, target, source_hint=source)
    await update.message.reply_text(_truncate(translated))


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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    logger.info("Ali Translator is starting…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()