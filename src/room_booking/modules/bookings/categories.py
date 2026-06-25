import re
import unicodedata

MAX_EXCHANGE_CATEGORY_LEN = 255
_INVALID_CATEGORY_CHARS_RE = re.compile(r"[,;]")
_TRAILING_SLASH_RE = re.compile(r"\s*/\s*$")


def sanitize_exchange_category(value: str) -> str:
    text = _INVALID_CATEGORY_CHARS_RE.sub(" ", value)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"\s+", " ", text).strip()
    text = _TRAILING_SLASH_RE.sub("", text).strip()
    if len(text) > MAX_EXCHANGE_CATEGORY_LEN:
        text = text[:MAX_EXCHANGE_CATEGORY_LEN].rstrip()
    return text


def sanitize_exchange_categories(categories: list[str] | None) -> list[str] | None:
    if not categories:
        return categories
    cleaned = [sanitized for category in categories if (sanitized := sanitize_exchange_category(str(category)))]
    return cleaned or None
