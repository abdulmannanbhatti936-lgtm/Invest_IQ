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
