"""Synthetic stand-ins for a news feed and an official press release (no network in tests).

The wording imitates the shape of the real demo material (a quote hinging on "net", an offsetting
pair of numbers, a startling-but-true official number) but these are test fixtures, not real articles.
"""

from __future__ import annotations

FEED_URL = "https://example-news.test/feed/"
STORY_URL = "https://example-news.test/2026/09/24/board-votes-rates/"
STORY2_URL = "https://example-news.test/2026/11/12/grid-programs/"
PRESS_URL = "https://nj.gov/bpu/newsroom/2026/approved/20260813.html"
BLOCKED_URL = "https://example-news.test/2026/10/01/blocked-page/"

STORY_HTML = (
    "<p>The utilities board approved a set of rate changes Thursday that keep residential electric rates "
    "roughly level.</p>"
    "<p>&#8220;Taken together with the items on the agenda earlier this month, these actions will result in no "
    "net increase in electricity rates and a slight decrease in gas rates,&#8221; said Dana Example, the "
    "board&#8217;s president.</p>"
    "<p>Some customers will see individual components of their bills increase, but those will be offset by drops "
    "to other components.</p>"
    "<p>Shore Electric&#8217;s average monthly bills, for example, will rise by $4.09 because of changes to "
    "transmission charges. But those same bills will fall by $4.14 due to changes to other charges, leaving the "
    "average monthly bill 5 cents cheaper than before.</p>"
    "<p>The post Board votes appeared first on Example News.</p>"
)
STORY2_HTML = (
    "<p>The board approved programs Thursday aimed at lowering peak demand.</p>"
    "<p>&#8220;I don&#8217;t know if everyone understands, but it is the most expensive hours of the year that are "
    "driving the really unsustainable price hikes in the utility and electricity bills that we saw in the last "
    "few years,&#8221; Commissioner Riley Sample said Thursday.</p>"
)

FEED_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel><title>Example News</title><link>https://example-news.test</link><description>test</description>
<item><title>Board votes to keep electricity rates level</title><link>{STORY_URL}</link>
<pubDate>Fri, 25 Sep 2026 00:48:02 +0000</pubDate><description>Rates stay level.</description>
<content:encoded><![CDATA[{STORY_HTML}]]></content:encoded></item>
<item><title>Board approves grid programs to cut electricity bills</title><link>{STORY2_URL}</link>
<pubDate>Thu, 12 Nov 2026 20:18:21 +0000</pubDate><description>Peak demand.</description>
<content:encoded><![CDATA[{STORY2_HTML}]]></content:encoded></item>
<item><title>High school football scores</title><link>https://example-news.test/2026/11/13/football/</link>
<pubDate>Fri, 13 Nov 2026 10:00:00 +0000</pubDate><description>Sports.</description>
<content:encoded><![CDATA[<p>Scores from Friday night.</p>]]></content:encoded></item>
</channel></rss>"""

PRESS_HTML = """<html><head><title>Board of Public Utilities | Newsroom</title>
<meta name="description" content="Press release"></head><body>
<ul id="navigation"><li><a href="/bpu/">Home</a></li><li><a href="/bpu/about/">About BPU</a></li></ul>
<div class="content"><h2>New Report Outlines Market Reforms</h2>
<table><tr><td><strong>Date:</strong> 08/13/2026</td></tr></table>
<p>TRENTON, N.J. &ndash; The Board released a study on the regional capacity market.<br><br>The report comes as
New Jersey electricity bills jumped roughly 20 percent last year, driven in large part by rising costs in the
capacity market.<br><br>While capacity charges currently account for approximately 15 to 20 percent of a typical
customer's electric bill, they represent the single largest cost component that the board cannot directly set.</p>
<script>var x = "do not include me";</script>
</div></body></html>"""

FEED2_URL = "https://example-news.test/feed2/"
STORY3_URL = "https://example-news.test/2026/11/10/home-batteries/"
HEADLINE3 = "Trenton board approves $4 million for home batteries on Thursday"
FEED2_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel><title>Example News</title><link>https://example-news.test</link><description>test</description>
<item><title>{HEADLINE3}</title><link>{STORY3_URL}</link>
<pubDate>Tue, 10 Nov 2026 15:00:00 +0000</pubDate><description>Batteries.</description>
<content:encoded><![CDATA[<p>The board approved $4 million on Thursday for a pilot that pays homeowners to share battery power at \
peak hours.</p><p>Officials said the pilot could shave peak demand by 20 megawatts.</p>]]></content:encoded></item>
</channel></rss>"""

ROUTES: dict[str, tuple[int, bytes, str]] = {
    FEED_URL: (200, FEED_XML.encode("utf-8"), "application/rss+xml; charset=UTF-8"),
    FEED2_URL: (200, FEED2_XML.encode("utf-8"), "application/rss+xml; charset=UTF-8"),
    PRESS_URL: (200, PRESS_HTML.encode("utf-8"), "text/html"),
    BLOCKED_URL: (403, b"<html>Forbidden</html>", "text/html"),
}


class FakeFetcher:
    def __init__(self, routes: dict[str, tuple[int, bytes, str]] | None = None) -> None:
        self.routes = dict(ROUTES if routes is None else routes)
        self.calls: list[str] = []

    def __call__(self, url: str) -> tuple[int, bytes, str]:
        self.calls.append(url)
        return self.routes.get(url, (404, b"", "text/html"))


QUOTE_NET = ("Taken together with the items on the agenda earlier this month, these actions will result in no net "
             "increase in electricity rates and a slight decrease in gas rates")
SPEAKER_NET = "Dana Example, Board President"
ACE_RISE = ("Shore Electric's average monthly bills, for example, will rise by $4.09 because of changes to "
            "transmission charges.")
ACE_FALL = "will fall by $4.14"
QUOTE_PEAK = ("it is the most expensive hours of the year that are driving the really unsustainable price hikes in "
              "the utility and electricity bills that we saw in the last few years")
SPEAKER_PEAK = "Riley Sample, Board Commissioner"
BPU_20 = ("New Jersey electricity bills jumped roughly 20 percent last year, driven in large part by rising costs in "
          "the capacity market.")
