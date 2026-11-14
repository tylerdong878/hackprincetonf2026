"""Player-facing views. Whitelists, so a stray answer field can never reach the browser."""
from __future__ import annotations

CASE_KEYS = ("id", "number", "title", "topic", "briefing", "clue_budget", "trick_options", "posts")
POST_KEYS = ("id", "author", "posted_at", "body", "quote", "chart", "source_label", "tools", "card_style")
AUTHOR_KEYS = ("name", "handle", "kind", "verified", "avatar_color")


def card_style(post: dict) -> str:
    """Display hint for Daily cards (CONTRACT §7.1), derived when the post doesn't set one."""
    if post.get("chart"):
        return "chart"
    if post.get("quote"):
        return "quote"
    return "stat" if any(ch.isdigit() for ch in post.get("body") or "") else "headline"


def post_view(p: dict) -> dict:
    post = {k: p[k] for k in POST_KEYS if k in p}
    if isinstance(post.get("author"), dict):
        post["author"] = {k: post["author"][k] for k in AUTHOR_KEYS if k in post["author"]}
    post.setdefault("card_style", card_style(p))
    return post


def player_view(case: dict) -> dict:
    out = {k: case[k] for k in CASE_KEYS if k in case}
    out["posts"] = [post_view(p) for p in case.get("posts", [])]
    return out
