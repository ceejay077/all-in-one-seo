"""
checks/metadata.py — Meta title, meta description, image alt text checks per page.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from bs4 import BeautifulSoup


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
