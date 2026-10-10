"""Parsing of the three news sources. The inputs are trimmed copies of the real formats."""

import datetime

import pytest

from integrations.news.sources import (
    BRECORDER,
    METTIS,
    PROFIT,
    BusinessRecorderClient,
    MettisClient,
    ParseError,
    ProfitClient,
)

UTC = datetime.timezone.utc

PROFIT_PAGE = """<html><head>
<title>ignored</title>
<meta property="og:title"
 content="PSO cuts trade receivables to Rs414.8 billion in FY26 - Profit by Pakistan Today">
<script type="application/ld+json">
{"@type":"NewsArticle","datePublished":"2026-10-07T08:19:52.141Z"}</script>
</head><body><p>Article text that must never be stored.</p></body></html>"""

SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://profit.pakistantoday.com.pk/2026/10/07/pso-cuts-trade-receivables</loc></url>
<url><loc>https://profit.pakistantoday.com.pk/category/headlines</loc></url>
</urlset>"""

METTIS_SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<?xml-stylesheet type="text/xsl" href="main-sitemap.XSL"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://mettisglobal.news/author/MG%20News</loc><lastmod>2026-10-10T01:27:14+00:00</lastmod></url>
<url><loc>https://mettisglobal.news/ogdc-begins-production</loc><lastmod>2025-01-31T10:51:42+00:00</lastmod></url>
</urlset>"""

METTIS_JSON = [
    {
        "rowid": 63802,
        "link": "PSO-signs-agreement-with-OQT-64109",
        "headings": {"heading": ["PSO signs agreement with OQT"]},
        "contents": {"content": ["<p>Article text that must never be stored.</p>"]},
        "publishedTime": "2026-10-09T15:51:46.193",
    }
]

RSS = b"""<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>
<item><title>OGDC profit rises 12pc</title>
<link>https://www.brecorder.com/news/40443557/ogdc-profit-rises-12pc</link>
<description>Article text</description>
<pubDate>Sat, 10 Oct 2026 05:02:24 +0500</pubDate></item>
</channel></rss>"""


class StubFetcher:
    def __init__(self, pages):
        self.pages = pages

    def get(self, url, params=None):
        page = self.pages[url]

        class Response:
            text = page if isinstance(page, str) else ""
            content = page if isinstance(page, bytes) else b""

            def json(self):
                return page

        return Response()


def test_profit_article_gives_headline_and_utc_time_only():
    url = "https://profit.pakistantoday.com.pk/2026/10/07/pso-cuts-trade-receivables"
    article = ProfitClient(StubFetcher({url: PROFIT_PAGE})).article(url)
    assert article.source == PROFIT
    assert article.headline == "PSO cuts trade receivables to Rs414.8 billion in FY26"
    assert article.published_at == datetime.datetime(2026, 10, 7, 8, 19, 52, 141000, UTC)
    assert "never be stored" not in repr(article)


def test_profit_sitemap_keeps_dated_article_links():
    stub = StubFetcher({"https://p/sitemap-articles-1.xml": SITEMAP})
    links = ProfitClient(stub).article_links("https://p/sitemap-articles-1.xml")
    assert [(link.url.rsplit("/", 1)[-1], link.published_on) for link in links] == [
        ("pso-cuts-trade-receivables", datetime.date(2026, 10, 7))
    ]


def test_mettis_sitemap_skips_author_pages_and_reads_lastmod():
    stub = StubFetcher({"https://m/post-sitemap.xml": METTIS_SITEMAP})
    links = MettisClient(stub).article_links("https://m/post-sitemap.xml")
    assert [link.published_on for link in links] == [datetime.date(2025, 1, 31)]


def test_mettis_load_more_reads_headline_link_and_utc_time():
    stub = StubFetcher({"https://mettisglobal.news/Home/LoadMore": METTIS_JSON})
    ((row_id, article),) = MettisClient(stub).load_more()
    assert row_id == 63802
    assert article.source == METTIS
    assert article.url == "https://mettisglobal.news/PSO-signs-agreement-with-OQT-64109"
    assert article.headline == "PSO signs agreement with OQT"
    assert article.published_at == datetime.datetime(2026, 10, 9, 15, 51, 46, 193000, UTC)


def test_mettis_unexpected_json_is_a_parse_error():
    stub = StubFetcher({"https://mettisglobal.news/Home/LoadMore": [{"rowid": 1}]})
    with pytest.raises(ParseError):
        MettisClient(stub).load_more()


def test_business_recorder_rss():
    stub = StubFetcher({feed: RSS for feed in BusinessRecorderClient.FEEDS})
    (article,) = BusinessRecorderClient(stub).latest()  # the same item in both feeds: once
    assert article.source == BRECORDER
    assert article.headline == "OGDC profit rises 12pc"
    assert article.published_at == datetime.datetime(2026, 10, 10, 0, 2, 24, tzinfo=UTC)
