"""Headline-to-ticker matching (Memory.md §3, 2026-10-11)."""

from integrations.news.matching import default_matcher, url_slug

matcher = default_matcher()


def test_matches_names_as_whole_words_ignoring_case_and_punctuation():
    assert matcher.match("Mari Petroleum's gas discovery in Sindh") == {"MARI"}
    assert matcher.match("OGDCL begins production from Bettani-2") == {"OGDC"}
    assert matcher.match("D.G. Khan Cement posts profit") == {"DGKC"}
    # 'pso' inside another word is not PSO
    assert matcher.match("Psoriasis drug launched") == set()


def test_one_headline_can_name_several_stocks():
    assert matcher.match("Lucky Cement, Hub Power consortium shortlisted") == {"LUCK", "HUBC"}


def test_routine_items_carrying_a_bank_name_are_excluded():
    assert matcher.match("NBP issues foreign exchange rates") == set()
    assert matcher.match("HBL PMI: manufacturing activity rises") == set()
    assert matcher.match("NBP posts record profit") == {"NBP"}


def test_an_article_needs_a_tracked_stock_in_its_url_slug():
    url = "https://profit.pakistantoday.com.pk/2026/10/07/lucky-cement-consortium-shortlisted"
    assert matcher.match_article(url) == {"LUCK"}
    assert matcher.match_article(url, "Lucky Cement and Hub Power shortlisted") == {
        "LUCK",
        "HUBC",
    }
    # The headline alone is not enough: history is discovered by slug, so live news is too
    other = "https://profit.pakistantoday.com.pk/2026/10/07/consortium-shortlisted-for-gepco"
    assert matcher.match_article(other, "Lucky Cement consortium shortlisted") == set()


def test_mettis_article_ids_are_not_part_of_the_slug():
    assert url_slug("https://mettisglobal.news/PSO-signs-agreement-64110") == "PSO-signs-agreement"
