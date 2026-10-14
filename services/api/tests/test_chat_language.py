import pytest

from services.chat_language import ENGLISH, ROMAN_URDU, URDU, is_roman_urdu, reply_language


@pytest.mark.parametrize(
    "text",
    [
        "mera portfolio kaisa hai?",
        "HBL ka forecast kya hai",
        "Mujhe batao ke backtest mein kitna munafa hua",
        "portfolio kaisa?",
        "Kya mujhe Bitcoin lena chahiye?",
        "aur dusra wala?",
    ],
)
def test_roman_urdu_is_recognised(text):
    assert is_roman_urdu(text)


@pytest.mark.parametrize(
    "text",
    [
        "What does my portfolio look like?",
        "Why is HBL in my portfolio and what is the main reason?",
        "Do I have to pay CGT on this?",
        "Tell me about the KSE-100 so I can compare",
        "and the second one?",
        "Is it safe to buy PSO?",
        "میرا پورٹ فولیو کیسا ہے؟",
        "1234",
        "",
    ],
)
def test_english_urdu_script_and_empty_text_are_not_roman_urdu(text):
    assert not is_roman_urdu(text)


def test_the_toggle_decides_unless_the_user_wrote_roman_urdu():
    assert reply_language("What is my portfolio?", ENGLISH) == ENGLISH
    assert reply_language("What is my portfolio?", URDU) == URDU
    assert reply_language("میرا پورٹ فولیو کیسا ہے؟", ENGLISH) == ENGLISH
    assert reply_language("mera portfolio kaisa hai?", ENGLISH) == ROMAN_URDU
    assert reply_language("mera portfolio kaisa hai?", URDU) == ROMAN_URDU


# Live message that was answered in English before the 2026-10-15 fix
LIVE_MESSAGE = (
    "Hey yar mughay thora bata saktay ho k mai kon sa stock mai abhi currently invest kar "
    "sakta hoon for long time"
)


@pytest.mark.parametrize(
    "text",
    [
        LIVE_MESSAGE,
        "mujhay batao mera portfolio kaisa perform kar raha hai",
        "kia mai HBL mai invest kar sakta hun?",
        "yaar mere portfolio ka total cost kitna hai",
        "OGDC ka forecast kya hai next day ke liye",
        "mujhy samjhao ye low confidence kyun hai",
        "kon sa stock best hai long term ke liye?",
        "backtest ka result kaisa tha? thoda detail mai batayen",
        "Mai abhi 50000 rupay invest karna chahta hoon, kya karun?",
        "bhai sirf top 3 holdings bata do",
        "kya mera risk profile moderate hai?",
        "dividend kitna milega mujhe FFC se",
        "acha theek hai, aur second lowest wala konsa hai?",
    ],
)
def test_mixed_roman_urdu_and_english_is_roman_urdu(text):
    assert is_roman_urdu(text), text
    assert reply_language(text, ENGLISH) == ROMAN_URDU


@pytest.mark.parametrize(
    "text",
    [
        "Which stock should I buy for the long term?",
        "What is the main reason my forecast is low confidence?",
        "He said the main holding is up today, is that right?",
        "Can you explain the Sharpe ratio in simple words?",
        "Show me my portfolio and the total cost please",
        "Is it a good time to invest in HBL or OGDC?",
        "What does break-even price mean for me?",
        "How do I read the backtest chart?",
        "Tell me about the KSE-100 and how it compares",
        "Do I pay CGT when I sell my shares?",
        "I am new to investing, where should I start?",
        "Ok so what is the second lowest one then?",
    ],
)
def test_plain_english_stays_english(text):
    assert not is_roman_urdu(text), text
    assert reply_language(text, ENGLISH) == ENGLISH
