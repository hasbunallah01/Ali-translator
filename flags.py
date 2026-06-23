"""
Map ISO 639-1 language codes (as used by deep-translator/Google) to a
representative country flag emoji. Built from country code + manual curation
for the languages most likely to be requested.

Falls back to a globe emoji for unmapped languages.
"""

from typing import Dict

# Format: 'lang_code' -> ISO 3166-1 alpha-2 country code
# Sources: ISO 639-1 ↔ ISO 3166-1 conventions, plus manual picks for languages
# spoken across multiple countries (we pick the most associated flag).
LANG_TO_COUNTRY: Dict[str, str] = {
    # Main pair
    "ar": "sa",   # Arabic → Saudi Arabia
    "en": "gb",   # English → United Kingdom (also US, but UK is the origin)
    # Top Google Translate languages
    "af": "za",   # Afrikaans → South Africa
    "sq": "al",   # Albanian
    "am": "et",   # Amharic
    "hy": "am",   # Armenian
    "az": "az",   # Azerbaijani
    "eu": "es",   # Basque
    "be": "by",   # Belarusian
    "bn": "bd",   # Bengali → Bangladesh
    "bs": "ba",   # Bosnian
    "bg": "bg",   # Bulgarian
    "ca": "es",   # Catalan
    "ceb": "ph",  # Cebuano
    "zh": "cn",   # Chinese → China
    "zh-cn": "cn",
    "zh-tw": "tw",
    "co": "fr",   # Corsican
    "hr": "hr",   # Croatian
    "cs": "cz",   # Czech
    "da": "dk",   # Danish
    "nl": "nl",   # Dutch
    "eo": "eu",   # Esperanto
    "et": "ee",   # Estonian
    "fi": "fi",   # Finnish
    "fr": "fr",   # French
    "fy": "nl",   # Frisian
    "gl": "es",   # Galician
    "ka": "ge",   # Georgian
    "de": "de",   # German
    "el": "gr",   # Greek
    "gu": "in",   # Gujarati
    "ht": "ht",   # Haitian Creole
    "ha": "ng",   # Hausa
    "haw": "us",  # Hawaiian
    "he": "il",   # Hebrew
    "iw": "il",   # Hebrew (alt code)
    "hi": "in",   # Hindi
    "hmn": "cn",  # Hmong
    "hu": "hu",   # Hungarian
    "is": "is",   # Icelandic
    "ig": "ng",   # Igbo
    "id": "id",   # Indonesian
    "ga": "ie",   # Irish
    "it": "it",   # Italian
    "ja": "jp",   # Japanese
    "jv": "id",   # Javanese
    "kn": "in",   # Kannada
    "kk": "kz",   # Kazakh
    "km": "kh",   # Khmer
    "rw": "rw",   # Kinyarwanda
    "ko": "kr",   # Korean
    "ku": "iq",   # Kurdish
    "ky": "kg",   # Kyrgyz
    "lo": "la",   # Lao
    "la": "va",   # Latin
    "lv": "lv",   # Latvian
    "lt": "lt",   # Lithuanian
    "lb": "lu",   # Luxembourgish
    "mk": "mk",   # Macedonian
    "mg": "mg",   # Malagasy
    "ms": "my",   # Malay
    "ml": "in",   # Malayalam
    "mt": "mt",   # Maltese
    "mi": "nz",   # Maori
    "mr": "in",   # Marathi
    "mn": "mn",   # Mongolian
    "my": "mm",   # Myanmar (Burmese)
    "ne": "np",   # Nepali
    "no": "no",   # Norwegian
    "ny": "mw",   # Nyanja (Chichewa)
    "or": "in",   # Odia
    "ps": "af",   # Pashto
    "fa": "ir",   # Persian
    "pl": "pl",   # Polish
    "pt": "pt",   # Portuguese
    "pa": "in",   # Punjabi
    "ro": "ro",   # Romanian
    "ru": "ru",   # Russian
    "sm": "ws",   # Samoan
    "gd": "gb",   # Scottish Gaelic
    "sr": "rs",   # Serbian
    "st": "ls",   # Sesotho
    "sn": "zw",   # Shona
    "sd": "pk",   # Sindhi
    "si": "lk",   # Sinhala
    "sk": "sk",   # Slovak
    "sl": "si",   # Slovenian
    "so": "so",   # Somali
    "es": "es",   # Spanish
    "su": "id",   # Sundanese
    "sw": "tz",   # Swahili
    "sv": "se",   # Swedish
    "tl": "ph",   # Tagalog
    "tg": "tj",   # Tajik
    "ta": "in",   # Tamil
    "tt": "ru",   # Tatar
    "te": "in",   # Telugu
    "th": "th",   # Thai
    "tr": "tr",   # Turkish
    "tk": "tm",   # Turkmen
    "uk": "ua",   # Ukrainian
    "ur": "pk",   # Urdu
    "ug": "cn",   # Uyghur
    "uz": "uz",   # Uzbek
    "vi": "vn",   # Vietnamese
    "cy": "gb",   # Welsh
    "xh": "za",   # Xhosa
    "yi": "il",   # Yiddish
    "yo": "ng",   # Yoruba
    "zu": "za",   # Zulu
}


def flag_for(lang_code: str) -> str:
    """Return a flag emoji for a language code, or a globe if unmapped."""
    code = (lang_code or "").lower()
    country = LANG_TO_COUNTRY.get(code)
    if not country:
        return "🌐"
    # Regional indicator symbols: each letter A-Z maps to U+1F1E6..U+1F1FF
    a = ord(country[0].upper()) - ord("A") + 0x1F1E6
    b = ord(country[1].upper()) - ord("A") + 0x1F1E6
    return chr(a) + chr(b)
