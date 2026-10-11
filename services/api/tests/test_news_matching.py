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
    # PSO also means an SBP payment system operator licence
    assert matcher.match("Fintech secures PSO/PSP approval") == set()
    assert matcher.match("PSO, OQ Trading sign petroleum supply agreement") == {"PSO"}


def test_an_article_needs_a_tracked_stock_in_its_url_slug():
    url = "https://profit.pakistantoday.com.pk/2026/10/07/lucky-cement-consortium-shortlisted"
    assert matcher.match_article(url) == {"LUCK"}
    # A stock named only in the headline is not attached: history is discovered by slug
    assert matcher.match_article(url, "Lucky Cement and Hub Power shortlisted") == {"LUCK"}
    other = "https://profit.pakistantoday.com.pk/2026/10/07/consortium-shortlisted-for-gepco"
    assert matcher.match_article(other, "Lucky Cement consortium shortlisted") == set()


def test_industry_wording_in_a_headline_never_adds_a_stock():
    # 'Pakistan petroleum sales' is industry data, not Pakistan Petroleum Limited
    url = "https://profit.pakistantoday.com.pk/2026/08/03/pakistans-petroleum-sales-pso-leads"
    assert matcher.match_article(url, "Pakistan petroleum sales jump 23.3% YoY; PSO leads") == {
        "PSO"
    }


def test_exclusions_apply_to_the_headline_and_slug_together():
    # The slug of a daily exchange-rate notice does not carry the excluded wording
    url = (
        "https://mettisglobal.news/treasury-management-division-of-the-national-bank-of-"
        "pakistan-nbp-on-monday-issued-the-following-rates"
    )
    assert matcher.match_article(url) == {"NBP"}
    assert matcher.match_article(url, "NBP issues foreign exchange rates") == set()


def test_universal_network_systems_is_not_systems_limited():
    url = "https://mettisglobal.news/universal-network-systems-limited-has-received-an-offer"
    assert matcher.match_article(url, "Universal Network receives offer") == set()
    assert matcher.match("Systems Limited posts record profit") == {"SYS"}


def test_a_title_that_describes_another_article_is_flagged():
    url = "https://profit.pakistantoday.com.pk/2025/07/07/ogdcl-boosts-output-at-rajian-05-well"
    assert not matcher.title_matches_slug("FBR launches customs system to boost efficiency", url)
    assert matcher.title_matches_slug("OGDCL raises output at Rajian-05", url)
    # Different wording, same stock named in both
    nbp = "https://profit.pakistantoday.com.pk/2026/09/03/govt-appoints-imran-sarwar-as-nbp-ceo"
    assert matcher.title_matches_slug("Imran Sarwar appointed NBP president", nbp)


def test_mettis_article_ids_are_not_part_of_the_slug():
    assert url_slug("https://mettisglobal.news/PSO-signs-agreement-64110") == "PSO-signs-agreement"
