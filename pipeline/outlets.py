"""Known publishers: how a real source is shown (plain-text name, no logos; SPEC §8.3)."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class Outlet:
    name: str
    kind: str  # "outlet" | "official"
    handle: str
    bio: str
    label: str  # used in source_label, e.g. "NJBPU press release"
    avatar_color: str


_OUTLETS: list[tuple[str, str, Outlet]] = [
    # (domain suffix, path prefix, outlet)
    ("newjerseymonitor.com", "", Outlet("New Jersey Monitor", "outlet", "@NJMonitor",
                                        "News outlet · newjerseymonitor.com", "New Jersey Monitor", "#2F9E6A")),
    ("nj.gov", "/bpu", Outlet("NJ Board of Public Utilities", "official", "@NJBPU",
                              "State utility regulator · nj.gov/bpu", "NJBPU press release", "#1F5FD1")),
    ("eia.gov", "", Outlet("U.S. Energy Information Administration", "official", "@EIAgov",
                           "Federal energy statistics agency · eia.gov", "EIA", "#0E7490")),
    ("njspotlightnews.org", "", Outlet("NJ Spotlight News", "outlet", "@NJSpotlightNews",
                                       "News outlet · njspotlightnews.org", "NJ Spotlight News", "#B45309")),
    ("whyy.org", "", Outlet("WHYY", "outlet", "@WHYY", "Public media · whyy.org", "WHYY", "#7C3AED")),
    ("nj1015.com", "", Outlet("New Jersey 101.5", "outlet", "@nj1015", "Radio news · nj1015.com",
                              "New Jersey 101.5", "#DC2626")),
    ("nj.com", "", Outlet("NJ.com", "outlet", "@njdotcom", "News outlet · nj.com", "NJ.com", "#2563EB")),
    ("npr.org", "", Outlet("NPR", "outlet", "@NPR", "News outlet · npr.org", "NPR", "#1D4ED8")),
    ("bbc.co.uk", "", Outlet("BBC", "outlet", "@BBC", "News outlet · bbc.co.uk", "BBC", "#991B1B")),
    ("bbc.com", "", Outlet("BBC", "outlet", "@BBC", "News outlet · bbc.com", "BBC", "#991B1B")),
    ("nj.gov", "", Outlet("State of New Jersey", "official", "@NewJersey", "State government · nj.gov",
                          "nj.gov", "#1F5FD1")),
]


def outlet_for(url: str) -> Outlet:
    p = urlparse(url)
    host = (p.hostname or "").lower().removeprefix("www.")
    path = p.path or "/"
    for domain, prefix, outlet in _OUTLETS:
        if (host == domain or host.endswith("." + domain)) and path.startswith(prefix):
            return outlet
    name = host or "Unknown source"
    kind = "official" if host.endswith(".gov") else "outlet"
    handle = "@" + "".join(ch for ch in name.split(".")[0].title() if ch.isalnum())[:15]
    return Outlet(name, kind, handle, f"{'Government source' if kind == 'official' else 'News outlet'} · {name}",
                  name, "#475569")
