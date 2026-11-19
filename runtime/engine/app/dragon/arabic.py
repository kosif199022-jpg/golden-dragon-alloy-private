"""Arabic-aware text normalisation for search: the same word in any spelling maps to one form."""
import re

_TASHKEEL = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭ]")
_MAP = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
    "ى": "ي", "ئ": "ي", "ؤ": "و", "ة": "ه",
    "ـ": "",  # tatweel
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4", "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
    "٬": "", "،": " ", "؛": " ", "؟": " ",
})
_NON_WORD = re.compile(r"[^\w]+", re.UNICODE)
# very common words that carry no meaning for routing (Arabic + Egyptian + English)
STOP = set("""
في من على الى عن مع او و ان ما لا هذا هذه ذلك التي الذي كل اي عايز عاوز ايه اللي ده دي بتاع يا لو
the a an of to in on for and or with is are be by from this that it as at my me i you
""".split())
# Arabic definite article and attached conjunction/preposition prefixes, removed for matching
_PREFIX = re.compile(r"^(وال|بال|كال|فال|لل|ال)(?=\w{2,})")


def normalize(text: str) -> str:
    """Lowercase, strip diacritics/tatweel, unify alef/ya/ta-marbuta, Arabic digits -> ASCII."""
    t = _TASHKEEL.sub("", (text or "").lower()).translate(_MAP)
    return _NON_WORD.sub(" ", t).strip()


def tokens(text: str, drop_stop: bool = True) -> list:
    """Search tokens: normalised words with the article prefix removed; stop words dropped."""
    out = []
    for w in normalize(text).split():
        w = _PREFIX.sub("", w)
        if len(w) < 2 or (drop_stop and w in STOP):
            continue
        out.append(w)
    return out
