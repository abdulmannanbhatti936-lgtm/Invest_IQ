"""
Figure check for chatbot replies (Phases.md Phase 8 exit: "never states a figure that doesn't
match the database"; rules decided 2026-10-13).

Every number in a reply must be one of the figures injected into its grounding context
(services/chat_context.py), at the precision written there: "Rs. 99,887" for Rs. 99,887.21 is a
rounding and fails. Formatting is ignored: commas (thousands or lakh style), "Rs."/"PKR", "%",
Urdu and Arabic-Indic digits, bidi marks. A sign may be carried by words ("fell 20.25%" for
-20.25%).

Exempt, and nothing else:
  (a) numbers that appear in the user's own message;
  (b) list numbering at the start of a line ("1." or "2)");
  (c) the index name "KSE-100".
Dates must be dates in the context.

The digits-only rule is enforced too: a number written in words next to a unit or a magnitude
("twenty percent", "بیس فیصد", "das hazaar") fails, in English, Urdu script and Roman Urdu.

Known limitation (documented): a wrong direction stated in words ("rose" for a fall) is not
caught; only the magnitude is checked.
"""

import datetime
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

# Arabic-Indic and Extended Arabic-Indic (Urdu) digits, the Arabic decimal and thousands
# separators and the minus sign, mapped to their ASCII forms
_DIGITS = str.maketrans(
    {
        **{chr(0x0660 + i): str(i) for i in range(10)},
        **{chr(0x06F0 + i): str(i) for i in range(10)},
        chr(0x066B): ".",
        chr(0x066C): ",",
        chr(0x2212): "-",
    }
)
# Zero-width characters, bidi marks, embeddings and isolates
_INVISIBLE = re.compile(
    "[" + "".join(f"{chr(a)}-{chr(b)}" for a, b in ((0x200B, 0x200F), (0x202A, 0x202E))) + "]"
    + "|[" + chr(0x2066) + "-" + chr(0x2069) + "]"
)  # fmt: skip

_LIST_NUMBER = re.compile(r"(?m)^[ \t]*\d{1,2}[.)](?=\s)")
_KSE100 = re.compile(r"\bKSE[\s-]?100\b", re.IGNORECASE)
# A number not glued to a letter before it (TPLRF1) or to more digits after it. Commas may group
# in thousands or in the lakh style ("1,00,000"), as Pakistani text often does
_NUMBER = re.compile(r"(?<![^\W\d_])(?<![\d,])(?<!\d\.)[-+]?\d+(?:,\d{2,3})*(?:\.\d+)?(?!\d)")
_PCT_AFTER = re.compile(r"\s?(?:%|percent\b|per cent\b|فیصد|feesad\b|fisad\b)", re.IGNORECASE)
_MONEY_BEFORE = re.compile(r"(?:rs\.?|pkr|روپے)\s?$", re.IGNORECASE)
_MONEY_AFTER = re.compile(r"\s?(?:rupees?\b|روپے|روپیہ|rupay\b|rupaye\b)", re.IGNORECASE)

_EN_MONTHS = "january february march april may june july august september october november december"
_EN_SHORT = "jan feb mar apr may jun jul aug sep oct nov dec"
_UR_MONTHS = "جنوری فروری مارچ اپریل مئی جون جولائی اگست ستمبر اکتوبر نومبر دسمبر"
MONTHS = {
    **{m: i for i, m in enumerate(_EN_MONTHS.split(), 1)},
    **{m: i for i, m in enumerate(_EN_SHORT.split(), 1)},
    "sept": 9,
    **{m: i for i, m in enumerate(_UR_MONTHS.split(), 1)},
}


def _alternation(names) -> str:
    return "|".join(sorted(map(re.escape, names), key=len, reverse=True))


# "may" is also a verb ("forecasts may be wrong"), so May counts as a month only with a year
_MONTH = _alternation(m for m in MONTHS if m != "may")
_ANY_MONTH = _alternation(MONTHS)
_ORDINAL = r"(?:st|nd|rd|th)?"
_ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DAY_MAY_YEAR = re.compile(rf"\b(\d{{1,2}}){_ORDINAL}\s+(may)\b,?\s+(\d{{4}})\b", re.I)
_MAY_DAY_YEAR = re.compile(rf"\b(may)\s+(\d{{1,2}}){_ORDINAL}\b,?\s+(\d{{4}})\b", re.I)
_DAY_MONTH = re.compile(rf"\b(\d{{1,2}}){_ORDINAL}\s+({_MONTH})\b,?(?:\s+(\d{{4}})\b)?", re.I)
_MONTH_DAY = re.compile(rf"\b({_MONTH})\s+(\d{{1,2}}){_ORDINAL}\b,?(?:\s+(\d{{4}})\b)?", re.I)
_MONTH_YEAR = re.compile(rf"\b({_ANY_MONTH})\s+(\d{{4}})\b", re.I)
_YEAR = re.compile(r"(?<![\w.,])(?:19|20)\d{2}(?![\w%])")

# Numbers in words (kept small and explicit; tests/test_chat_figure_check.py)
NUMBER_WORDS = frozenset("""
    zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen
    fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty
    ninety hundred half
    ایک دو تین چار پانچ چھ سات آٹھ نو دس گیارہ بارہ بیس تیس چالیس پچاس ساٹھ ستر اسی نوے سو آدھا
    ek teen chaar char paanch panch chay chhe saat aath nau das gyarah barah bees tees chalees
    pachaas pachas saath sattar assi nabbay sau aadha
    """.split())
MAGNITUDE_WORDS = frozenset("""
    thousand lakh lac lakhs million crore crores billion bn mn
    ہزار لاکھ کروڑ ارب
    hazaar hazar karor arab
    """.split())
UNIT_WORDS = frozenset("""
    percent percentage rupee rupees shares
    فیصد روپے روپیہ حصص
    feesad fisad rupay rupaye
    """.split())
# Roman Urdu "do" (two) is also English "do", so it counts only right before a magnitude
ROMAN_TWO = "do"
_WORD = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*")
_DIGITS_THEN_WORD = re.compile(r"\d+(?:[.,]\d+)*\s?([^\W\d_]+)")


@dataclass
class CheckResult:
    unmatched: list[str] = field(default_factory=list)
    number_words: list[str] = field(default_factory=list)
    matched_sources: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.unmatched and not self.number_words

    def detail(self) -> dict:
        return {"unmatched": self.unmatched, "number_words": self.number_words}


def normalize(text: str) -> str:
    """Western digits and plain separators; invisible bidi and spacing characters removed."""
    text = _INVISIBLE.sub("", text.translate(_DIGITS))
    return text.replace(chr(0x00A0), " ").replace(chr(0x202F), " ")


@dataclass(frozen=True)
class Number:
    value: Decimal
    kind: str  # "pct", "money" or "number"
    text: str


def extract_numbers(text: str) -> list[Number]:
    """Every number written in digits, with its unit when one is next to it."""
    text = normalize(text)
    numbers = []
    for match in _NUMBER.finditer(text):
        try:
            value = Decimal(match.group().replace(",", "").lstrip("+"))
        except InvalidOperation:
            continue
        before, after = text[max(0, match.start() - 5) : match.start()], text[match.end() :]
        if _PCT_AFTER.match(after):
            kind = "pct"
        elif _MONEY_BEFORE.search(before) or _MONEY_AFTER.match(after):
            kind = "money"
        else:
            kind = "number"
        numbers.append(Number(value, kind, match.group()))
    return numbers


def _blank(pattern: re.Pattern, text: str) -> str:
    return pattern.sub(lambda m: " " * len(m.group()), text)


def _dates(text: str, known: set[datetime.date]) -> tuple[str, list[str]]:
    """Blanks out every date in the text; returns the text and the dates not in the context."""
    unmatched: list[str] = []

    def keep_if_unknown(phrase: str, day: int | None, month: int, year: int | None) -> None:
        if not any(
            d.month == month and day in (None, d.day) and year in (None, d.year) for d in known
        ):
            unmatched.append(phrase.strip())

    for match in _ISO_DATE.finditer(text):
        year, month, day = map(int, match.groups())
        keep_if_unknown(match.group(), day, month, year)
    text = _blank(_ISO_DATE, text)
    patterns = (
        (_DAY_MAY_YEAR, True),
        (_MAY_DAY_YEAR, False),
        (_DAY_MONTH, True),
        (_MONTH_DAY, False),
    )
    for pattern, day_first in patterns:
        for match in pattern.finditer(text):
            a, b, year = match.groups()
            day, month = (a, b) if day_first else (b, a)
            keep_if_unknown(match.group(), int(day), MONTHS[month.lower()], year and int(year))
        text = _blank(pattern, text)
    for match in _MONTH_YEAR.finditer(text):
        month, year = match.groups()
        keep_if_unknown(match.group(), None, MONTHS[month.lower()], int(year))
    text = _blank(_MONTH_YEAR, text)
    # A year on its own ("in 2026") must be the year of a date in the context
    years = {d.year for d in known}
    unmatched += [m.group() for m in _YEAR.finditer(text) if int(m.group()) not in years]
    return _blank(_YEAR, text), unmatched


def number_words(text: str) -> list[str]:
    """
    Numbers written in words where they state a figure: number words followed by a unit
    ("twenty percent", "بیس فیصد") or a magnitude ("das hazaar"), a magnitude followed by a
    unit ("thousand rupees"), or digits followed by a magnitude ("10 thousand").
    "one of your stocks" is not a figure.
    """
    found: list[str] = []
    tokens = [(m.group().lower(), m.start(), m.end()) for m in _WORD.finditer(text)]

    def is_number_word(word: str) -> bool:
        return all(part in NUMBER_WORDS for part in word.split("-"))

    def flag(start: int, end: int) -> None:
        if text[start:end] not in found:
            found.append(text[start:end])

    for i, (word, start, _end) in enumerate(tokens):
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        if word in MAGNITUDE_WORDS and nxt and nxt[0] in UNIT_WORDS:
            flag(start, nxt[2])
        if not (is_number_word(word) or word == ROMAN_TWO):
            continue
        j = i + 1
        while j < len(tokens) and is_number_word(tokens[j][0]):
            j += 1
        if j == len(tokens):
            continue
        follower = tokens[j][0]
        only_do = word == ROMAN_TWO and j == i + 1
        if follower in MAGNITUDE_WORDS or (follower in UNIT_WORDS and not only_do):
            flag(start, tokens[j][2])
    for match in _DIGITS_THEN_WORD.finditer(text):
        if match.group(1).lower() in MAGNITUDE_WORDS:
            flag(*match.span())
    return found


def _tags_a_source(number: Number) -> bool:
    """
    A small whole number ("3 years", "2 stocks") matches too many figures to say where it came
    from, so only rupee amounts, percentages, decimals and large numbers tag a source.
    """
    size = abs(number.value)
    return number.kind != "number" or size != size.to_integral_value() or size >= 100


def check_reply(reply: str, context, user_message: str) -> CheckResult:
    """Checks a reply against a ChatContext's `figures`, `dates` and `json`."""
    result = CheckResult()
    text = _blank(_LIST_NUMBER, _blank(_KSE100, normalize(reply)))
    text, result.unmatched = _dates(text, context.dates)

    context_text = normalize(context.json)
    result.number_words = [p for p in number_words(text) if normalize(p) not in context_text]

    exempt = {abs(n.value) for n in extract_numbers(user_message)}
    named = set(re.findall(r"\b[A-Z][A-Z0-9]{1,9}\b", reply))
    for number in extract_numbers(text):
        size = abs(number.value)
        sources = [
            f.source
            for f in context.figures
            if abs(f.value) == size and number.kind in ("number", f.kind)
        ]
        if not sources:
            if size not in exempt:
                result.unmatched.append(number.text)
            continue
        if _tags_a_source(number):
            chosen = _attributed(sources, named)
            result.matched_sources += [s for s in chosen if s not in result.matched_sources]
    return result


def _attributed(sources: list[str], named: set[str]) -> list[str]:
    """
    The sources a matched figure is credited to. Several stocks can share a figure (every
    forecast at 49% confidence), so a stock's source counts only if the reply names that stock,
    or if it is the only stock the figure could have come from.
    """
    general = [s for s in sources if ":" not in s]
    per_stock = [s for s in sources if ":" in s]
    mentioned = [s for s in per_stock if s.split(":", 1)[1] in named]
    return general + (mentioned or (per_stock if len(per_stock) == 1 else []))
