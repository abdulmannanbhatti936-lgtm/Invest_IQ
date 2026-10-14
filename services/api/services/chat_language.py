"""
Reply language for the chatbot (PRD.md FR37, decided 2026-10-13): the language toggle decides
between English and Urdu, except that a message written in Roman Urdu (Urdu in Latin letters)
is answered in Roman Urdu whatever the toggle says.

Detection is deliberately simple: a message counts as Roman Urdu when it is written in Latin
letters and uses common Urdu words. The list leaves out words that are also everyday English
("main", "to", "do", "me", "is", "so"), so an English question is never mistaken for Urdu.
"""

import re

ENGLISH, URDU, ROMAN_URDU = "en", "ur", "ur-latn"
LANGUAGES = (ENGLISH, URDU, ROMAN_URDU)

ROMAN_URDU_WORDS = frozenset("""
    mera meri mere mujhe mujh hum hamara hamari aap ap apna apni apne
    kya kaisa kaisi kaise kyun kyon kab kahan kitna kitni kitne kaun konsa konsi
    hai hain tha thi thay hoga hogi hota hoti raha rahi rahe
    aur ya lekin magar agar toh phir bhi sirf abhi sab
    ka ki ke ko se mein par liye wala wali wale
    nahi nahin batao bataen bataiye samjhao samjhaen chahiye karna karun karein
    yeh ye woh wo isko usko iska uska
    paisa paise munafa nuqsan faida khareedna bechna
    """.split())

_LATIN_WORD = re.compile(r"[A-Za-z]+")
# The Arabic block (U+0600-U+06FF), which holds every Urdu letter
_URDU_LETTER = re.compile(f"[{chr(0x0600)}-{chr(0x06FF)}]")


def is_roman_urdu(text: str) -> bool:
    if _URDU_LETTER.search(text):
        return False
    words = [w.lower() for w in _LATIN_WORD.findall(text)]
    if not words:
        return False
    hits = sum(1 for w in words if w in ROMAN_URDU_WORDS)
    distinct = len({w for w in words if w in ROMAN_URDU_WORDS})
    # Two different Urdu words, or one in a very short message ("portfolio kaisa?")
    return distinct >= 2 or (hits >= 1 and len(words) <= 3)


def reply_language(text: str, toggle: str) -> str:
    """The language a reply is written in: Roman Urdu if the user wrote it, else the toggle."""
    return ROMAN_URDU if is_roman_urdu(text) else toggle
