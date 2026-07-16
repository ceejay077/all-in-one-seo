"""
checks/metadata.py — Meta title, meta description, image alt text checks per page.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from bs4 import BeautifulSoup

# Analytics/ad tracking pixels (Facebook Pixel, GA, GTM, LinkedIn Insight, etc.) are
# 1x1 <img> tags used for tracking, not content — they don't need alt text and
# shouldn't be flagged in the image accessibility audit.
_TRACKING_PIXEL_DOMAINS = re.compile(
    r"(facebook\.com/tr|google-analytics\.com|googletagmanager\.com|doubleclick\.net|"
    r"linkedin\.com/(px|li/track)|px\.ads\.linkedin\.com|"
    r"ads-twitter\.com|analytics\.tiktok\.com|bat\.bing\.com|pinterest\.com/v3)",
    re.I,
)


def _is_tracking_pixel(img) -> bool:
    """True if an <img> tag is a tracking pixel rather than real content."""
    if img.find_parent("noscript") is not None:
        return True
    width = (img.get("width") or "").strip()
    height = (img.get("height") or "").strip()
    if width in ("0", "1") and height in ("0", "1"):
        return True
    if _TRACKING_PIXEL_DOMAINS.search(img.get("src", "")):
        return True
    return False


@dataclass
class ImageInfo:
    src: str
    alt: str
    has_alt: bool
    status: str  # "ok" | "critical"


@dataclass
class MetadataResult:
    url: str
    meta_title: Optional[str]
    meta_description: Optional[str]
    title_status: str  # "ok" | "warn" | "critical"
    description_status: str
    images: list[ImageInfo] = field(default_factory=list)
    missing_alt_count: int = 0


def check_metadata(html: str, url: str) -> MetadataResult:
    soup = BeautifulSoup(html, "lxml")

    # ── Meta title ────────────────────────────────────────────────────────────
    title_tag = soup.find("title")
    meta_title = title_tag.get_text(strip=True) if title_tag else None

    if not meta_title:
        title_status = "critical"
    elif len(meta_title) < 30:
        title_status = "warn"  # Too short
    elif len(meta_title) > 60:
        title_status = "warn"  # Too long
    else:
        title_status = "ok"

    # ── Meta description ──────────────────────────────────────────────────────
    desc_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    meta_description = desc_tag.get("content", "").strip() if desc_tag else None

    if not meta_description:
        description_status = "critical"
    elif len(meta_description) < 70:
        description_status = "warn"
    elif len(meta_description) > 160:
        description_status = "warn"
    else:
        description_status = "ok"

    # ── Images ────────────────────────────────────────────────────────────────
    images: list[ImageInfo] = []
    for img in soup.find_all("img"):
        if _is_tracking_pixel(img):
            continue
        src = img.get("src", "")
        alt = img.get("alt", None)
        has_alt = alt is not None and alt.strip() != ""
        images.append(ImageInfo(
            src=src,
            alt=alt if alt is not None else "",
            has_alt=has_alt,
            status="ok" if has_alt else "critical",
        ))

    missing_alt_count = sum(1 for i in images if not i.has_alt)

    return MetadataResult(
        url=url,
        meta_title=meta_title,
        meta_description=meta_description,
        title_status=title_status,
        description_status=description_status,
        images=images,
        missing_alt_count=missing_alt_count,
    )
