"""
Reply language for the chatbot (PRD.md FR37, decided 2026-10-13): the language toggle decides
between English and Urdu, except that a message written in Roman Urdu (Urdu in Latin letters)
is answered in Roman Urdu whatever the toggle says.

Pakistani users mix Roman Urdu with English words ("mai abhi long term invest kar sakta hoon"),
so detection counts Urdu marker words, with their common spellings, as a share of the message
(fixed 2026-10-15 after a live message was answered in English). Two lists:

- STRONG words are never English (mujhe, sakta, hoon, kya, kar, abhi ...).
- WEAK words are also English words or letters ("main", "he", "k", "to", "ho", "sa"); they
  count only next to strong ones, so "He said the main stock is up" stays English.
"""

import re

ENGLISH, URDU, ROMAN_URDU = "en", "ur", "ur-latn"
LANGUAGES = (ENGLISH, URDU, ROMAN_URDU)

STRONG_WORDS = frozenset("""
    mujhe mujhay mughay mujhy mujhko mjhe mjhy hamein humein
    mera meri mere mery hamara hamari hamare tumhara tera teri apna apni apne
    aap hum tum woh wo yeh ye isko usko iska uska inka unka kisi koi kuch
    bata batao batayen bataen bataiye btao btayen samjhao samjhayen samjha
    sakta saktay sakti sakte skta sakoon
    hoon hun hu hain hai hy tha thi thay hoga hogi hota hoti hote raha rahi rahe
    kya kia kiya kyun kyon kiun kab kahan kaise kaisa kaisi kesa kese kitna kitni kitne
    kon kaun konsa konsi kaunsa kaunsi kis
    mai mein mujh ka ki ke ko se ne liye wala wali wale
    kar karna karun karo karein karen kro krna kiya
    yar yaar thora thoda thori thodi abhi phir bhi sirf sab aur lekin magar agar toh
    nahi nahin nai acha accha achha theek thik bilkul zyada ziada kam
    chahiye chahye chahiay lena lene lun loon dena dekh dekho dekhna
    paisa paise paison rupay munafa nuqsan faida kamai khareedna kharidna bechna
    """.split())
WEAK_WORDS = frozenset("main he k ho to sa par ya ap me hi na do mat hay zara".split())

_LATIN_WORD = re.compile(r"[A-Za-z]+")
# The Arabic block (U+0600-U+06FF), which holds every Urdu letter
_URDU_LETTER = re.compile(f"[{chr(0x0600)}-{chr(0x06FF)}]")
# Marker words as a share of all words for a longer message to count as Roman Urdu
MIN_SHARE = 0.3


def is_roman_urdu(text: str) -> bool:
    if _URDU_LETTER.search(text):
        return False
    words = [w.lower() for w in _LATIN_WORD.findall(text)]
    if not words:
        return False
    strong = sum(1 for w in words if w in STRONG_WORDS)
    weak = sum(1 for w in words if w in WEAK_WORDS)
    if strong == 0:
        return False
    # A very short message: one Urdu word is enough ("portfolio kaisa?")
    if len(words) <= 3:
        return True
    return strong >= 2 and (strong + weak) / len(words) >= MIN_SHARE


def reply_language(text: str, toggle: str) -> str:
    """The language a reply is written in: Roman Urdu if the user wrote it, else the toggle."""
    return ROMAN_URDU if is_roman_urdu(text) else toggle
