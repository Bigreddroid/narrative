"""Tests for Google News redirect resolution.

Network is never touched: the transport is injected, so these assert the parsing,
the caching, the budget and — most importantly — that every failure mode degrades to
"keep the URL we already had" rather than losing the article.
"""

import asyncio

from backend.feeds import gnews_resolve as gr

GNEWS = ("https://news.google.com/rss/articles/"
         "CBMiiwFBVV95cUxPYmhpZEhkN2tSYXdOd1dZTzk0VEQteXNCYThKMlVt?oc=5")
GNEWS2 = ("https://news.google.com/rss/articles/"
          "CBMipgFBVV95cUxQNFlzTDhEZnA4czZwRGFoWDhrZ2JJQlpWd3BKN1lo?oc=5")
DIRECT = "https://www.theguardian.com/world/2026/jul/26/some-story"

# Shape of a real batchexecute response, prefix and length-chunking included.
BATCH_OK = (
    ")]}'\n\n3405\n"
    '[["wrb.fr","Fbv4je","[\\"garturlres\\",'
    '\\"https://www.nytimes.com/2026/07/26/us/man-convicted-arson.html\\",1]",'
    'null,null,null,""],["di",44],["af.httprm",43,"1234",7]]\n26\n'
    '[["e",4,null,null,131]]\n'
)
INTERSTITIAL = '<c-wiz data-n-a-ts="1753500000" data-n-a-sg="abc123sig">' + "x" * 500


class _FakeResponse:
    def __init__(self, text, status=200):
        self.text = text
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeClient:
    """Records calls so we can assert the cache and budget actually bite."""

    def __init__(self, get_text=INTERSTITIAL, post_text=BATCH_OK,
                 get_status=200, post_status=200, raise_on_get=False):
        self.get_text, self.post_text = get_text, post_text
        self.get_status, self.post_status = get_status, post_status
        self.raise_on_get = raise_on_get
        self.gets, self.posts = [], []

    async def get(self, url, **kw):
        self.gets.append(url)
        if self.raise_on_get:
            raise RuntimeError("connection reset")
        return _FakeResponse(self.get_text, self.get_status)

    async def post(self, url, **kw):
        self.posts.append(url)
        return _FakeResponse(self.post_text, self.post_status)


def _run(coro):
    return asyncio.run(coro)


def test_recognises_only_google_news_article_urls():
    assert gr.is_gnews_article(GNEWS)
    assert not gr.is_gnews_article(DIRECT)
    assert not gr.is_gnews_article("")
    assert not gr.is_gnews_article(None)
    # A Google News *search* or section URL carries no article id to resolve.
    assert not gr.is_gnews_article("https://news.google.com/rss/search?q=osint")


def test_extracts_the_article_id():
    assert gr.article_id(GNEWS) == ("CBMiiwFBVV95cUxPYmhpZEhkN2tSYXdOd1dZTzk0VEQteXNCYThKMlVt")
    assert gr.article_id(DIRECT) is None


def test_parses_the_publisher_url_out_of_a_real_batchexecute_body():
    assert gr.parse_batch_response(BATCH_OK) == (
        "https://www.nytimes.com/2026/07/26/us/man-convicted-arson.html")


def test_parse_returns_none_rather_than_guessing_when_the_body_is_not_what_we_expect():
    assert gr.parse_batch_response("") is None
    assert gr.parse_batch_response(")]}'\n\n[[\"wrb.fr\",\"Other\",\"[]\"]]") is None
    # Google answering with its own domain is not a resolution.
    assert gr.parse_batch_response(
        ')]}\'\n[["wrb.fr","Fbv4je","[\\"garturlres\\",\\"https://news.google.com/x\\",1]"]]'
    ) is None


def test_resolves_a_url_end_to_end_through_the_injected_transport():
    gr.reset_cache()
    c = _FakeClient()
    out = _run(gr.resolve_urls([GNEWS], client=c))
    assert out == {GNEWS: "https://www.nytimes.com/2026/07/26/us/man-convicted-arson.html"}
    assert len(c.gets) == 1 and len(c.posts) == 1


def test_leaves_non_google_urls_completely_alone_and_makes_no_requests():
    gr.reset_cache()
    c = _FakeClient()
    assert _run(gr.resolve_urls([DIRECT], client=c)) == {}
    assert c.gets == [] and c.posts == []


def test_a_second_pass_is_served_from_cache_and_issues_no_new_requests():
    gr.reset_cache()
    c = _FakeClient()
    _run(gr.resolve_urls([GNEWS], client=c))
    before = len(c.gets)
    out = _run(gr.resolve_urls([GNEWS], client=c))
    assert out[GNEWS].startswith("https://www.nytimes.com")
    assert len(c.gets) == before, "cached resolution must not refetch a 600KB interstitial"


def test_per_cycle_budget_caps_how_many_are_attempted():
    gr.reset_cache()
    c = _FakeClient()
    urls = [GNEWS.replace("CBMi", f"CBMi{i}") for i in range(10)]
    out = _run(gr.resolve_urls(urls, client=c, budget=3))
    assert len(c.gets) == 3, "budget must bound the bandwidth spent per cycle"
    assert len(out) == 3


def test_an_interstitial_without_a_signature_degrades_to_no_resolution():
    gr.reset_cache()
    c = _FakeClient(get_text="<html>no signature here</html>")
    assert _run(gr.resolve_urls([GNEWS], client=c)) == {}
    assert c.posts == [], "must not POST without the signature pair"


def test_a_transport_failure_degrades_to_no_resolution_and_never_raises():
    gr.reset_cache()
    c = _FakeClient(raise_on_get=True)
    assert _run(gr.resolve_urls([GNEWS], client=c)) == {}


def test_repeated_failures_stop_being_retried_so_one_dead_id_cannot_burn_the_budget():
    gr.reset_cache()
    c = _FakeClient(raise_on_get=True)
    for _ in range(gr.MAX_ATTEMPTS + 2):
        _run(gr.resolve_urls([GNEWS], client=c))
    assert len(c.gets) == gr.MAX_ATTEMPTS, (
        "a permanently unresolvable id must be abandoned, not retried every cycle")


def test_apply_rewrites_the_url_in_place_and_leaves_unresolved_items_untouched():
    items = [
        {"url": GNEWS, "title": "resolved one"},
        {"url": GNEWS2, "title": "unresolved one"},
        {"url": DIRECT, "title": "direct one"},
    ]
    resolved = {GNEWS: "https://www.nytimes.com/a.html"}
    n = gr.apply_resolutions(items, resolved)
    assert n == 1
    assert items[0]["url"] == "https://www.nytimes.com/a.html"
    assert items[1]["url"] == GNEWS2, "no resolution means keep the only address we have"
    assert items[2]["url"] == DIRECT


def test_external_id_is_not_disturbed_by_resolution():
    """external_id keys dedupe. Rewriting it would re-ingest every already-stored
    Google item as brand new, so resolution must only touch the url."""
    items = [{"url": GNEWS, "external_id": "rss-deadbeefdeadbeef"}]
    gr.apply_resolutions(items, {GNEWS: "https://www.nytimes.com/a.html"})
    assert items[0]["external_id"] == "rss-deadbeefdeadbeef"


def test_publisher_name_comes_from_the_resolved_domain():
    assert gr.publisher_from_url("https://www.nytimes.com/2026/07/26/x.html") == "nytimes.com"
    assert gr.publisher_from_url("https://wpbf.com/article/y/732") == "wpbf.com"
    assert gr.publisher_from_url("http://news.bbc.co.uk/2/hi/x.stm") == "news.bbc.co.uk"
    assert gr.publisher_from_url("not a url") is None
    assert gr.publisher_from_url("") is None


TESTS = [v for k, v in sorted(globals().items()) if k.startswith("test_")]


def run() -> None:
    for t in TESTS:
        t()
    print(f"gnews_resolve_test: {len(TESTS)} passed")


if __name__ == "__main__":
    run()
