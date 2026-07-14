"""
checks/tracking.py — Detect analytics and advertising tracking pixels.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup


@dataclass
class TrackingResult:
    name: str
    found: bool
    detail: str = ""
    status: str = "ok"  # "ok" | "warn" | "critical"


# Patterns: (name, search_fn) — each fn takes (html: str, soup: BeautifulSoup) -> (found, detail)

def _bing_webmaster(html: str, soup: BeautifulSoup) -> tuple[bool, str]:
    meta = soup.find("meta", attrs={"name": re.compile(r"msvalidate\.01", re.I)})
    if meta:
        return True, f"Content: {meta.get('content', '')}"
    return False, ""


def _clarity(html: str, soup: BeautifulSoup) -> tuple[bool, str]:
    if "clarity.ms" in html or "microsoft clarity" in html.lower():
        return True, "Microsoft Clarity script detected"
    return False, ""


def _google_analytics(html: str, soup: BeautifulSoup) -> tuple[bool, str]:
    ga4 = bool(re.search(r"G-[A-Z0-9]+", html))
    ua = bool(re.search(r"UA-\d+-\d+", html))
    gtag = "gtag" in html
    if ga4:
        return True, "GA4 (G-XXXX) detected"
    if ua and gtag:
        return True, "Universal Analytics + gtag.js detected"
    if ua:
        return True, "Universal Analytics (UA-XXXX) detected"
    if gtag:
        return True, "gtag.js detected (type unclear)"
    return False, ""


def _search_console(html: str, soup: BeautifulSoup) -> tuple[bool, str]:
    meta = soup.find("meta", attrs={"name": re.compile(r"google-site-verification", re.I)})
    if meta:
        return True, f"Verification content: {meta.get('content', '')}"
    return False, ""


def _facebook_pixel(html: str, soup: BeautifulSoup) -> tuple[bool, str]:
    if "fbq(" in html or "facebook.net/en_US/fbevents.js" in html:
        match = re.search(r"fbq\('init',\s*'(\d+)'", html)
        detail = f"Pixel ID: {match.group(1)}" if match else "Facebook Pixel script detected"
        return True, detail
    return False, ""


def _meta_ads(html: str, soup: BeautifulSoup) -> tuple[bool, str]:
    # Meta Ads conversion tracking is served via the Pixel but may also use meta.com/tr
    if "meta.com/tr" in html or "connect.facebook.net" in html:
        return True, "Meta Ads tracking pixel found"
    return False, ""


def _google_ads(html: str, soup: BeautifulSoup) -> tuple[bool, str]:
    if re.search(r"AW-\d+", html) or "googleadservices.com" in html or "google_conversion" in html:
        match = re.search(r"AW-\d+", html)
        detail = f"Google Ads tag: {match.group(0)}" if match else "Google Ads conversion script detected"
        return True, detail
    return False, ""


# Known third-party tracker fingerprints (name, pattern)
_THIRD_PARTY_TRACKERS = [
    ("HubSpot", r"js\.hs-scripts\.com|hubspot\.com"),
    ("Hotjar", r"hotjar\.com"),
    ("Mixpanel", r"mixpanel\.com"),
    ("Segment", r"segment\.com|cdn\.segment\.com"),
    ("Intercom", r"intercom\.com"),
    ("LinkedIn Insight", r"snap\.licdn\.com|linkedin\.com/px"),
    ("Twitter/X Pixel", r"static\.ads-twitter\.com"),
    ("Pinterest Tag", r"pintrk\(|ct\.pinterest\.com"),
    ("TikTok Pixel", r"analytics\.tiktok\.com"),
    ("Quora Pixel", r"qss\.quora\.com"),
    ("Crazy Egg", r"crazyegg\.com"),
    ("FullStory", r"fullstory\.com"),
    ("Heap", r"heapanalytics\.com"),
    ("Amplitude", r"amplitude\.com"),
    ("Mouseflow", r"mouseflow\.com"),
    ("VWO", r"vwo\.com|visualwebsiteoptimizer\.com"),
    ("Optimizely", r"optimizely\.com"),
]


def _detect_other_trackers(html: str) -> list[TrackingResult]:
    others: list[TrackingResult] = []
    for name, pattern in _THIRD_PARTY_TRACKERS:
        if re.search(pattern, html, re.I):
            others.append(TrackingResult(
                name=f"Other Tracker: {name}",
                found=True,
                detail=f"{name} tracking script detected",
                status="warn",
            ))
    return others


def check_tracking(html: str) -> list[TrackingResult]:
    """Run all tracking checks on a page's HTML. Returns list of TrackingResult."""
    soup = BeautifulSoup(html, "lxml")
    results: list[TrackingResult] = []

    checks = [
        ("Bing Webmaster Tools", _bing_webmaster),
        ("Microsoft Clarity", _clarity),
        ("Google Analytics", _google_analytics),
        ("Google Search Console", _search_console),
        ("Facebook Pixel", _facebook_pixel),
        ("Meta Ads", _meta_ads),
        ("Google Ads", _google_ads),
    ]

    for name, fn in checks:
        found, detail = fn(html, soup)
        results.append(TrackingResult(
            name=name,
            found=found,
            detail=detail,
            status="ok" if found else "critical",
        ))

    results.extend(_detect_other_trackers(html))
    return results
