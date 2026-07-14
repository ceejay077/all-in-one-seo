"""
checks/structured_data.py — Schema.org JSON-LD and Open Graph / Twitter Card checks.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from bs4 import BeautifulSoup


@dataclass
class StructuredDataResult:
    name: str
    found: bool
    detail: str = ""
    status: str = "ok"  # "ok" | "warn" | "critical"
    items: list[Any] = field(default_factory=list)


def _extract_json_ld(soup: BeautifulSoup) -> list[dict]:
    """Return all parsed JSON-LD blocks."""
    schemas = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, list):
                schemas.extend(data)
            else:
                schemas.append(data)
        except (json.JSONDecodeError, TypeError):
            pass
    return schemas


def _extract_microdata(soup: BeautifulSoup) -> list[str]:
    """Return itemtype values (Microdata)."""
    return [
        el.get("itemtype", "")
        for el in soup.find_all(itemtype=True)
    ]


def check_structured_data(html: str) -> list[StructuredDataResult]:
    soup = BeautifulSoup(html, "lxml")
    results: list[StructuredDataResult] = []

    # ── JSON-LD ──────────────────────────────────────────────────────────────
    json_ld_blocks = _extract_json_ld(soup)
    if json_ld_blocks:
        schema_types = [b.get("@type", "Unknown") for b in json_ld_blocks]
        results.append(StructuredDataResult(
            name="Schema Markup (JSON-LD)",
            found=True,
            detail=f"Types: {', '.join(schema_types)}",
            status="ok",
            items=json_ld_blocks,
        ))
    else:
        results.append(StructuredDataResult(
            name="Schema Markup (JSON-LD)",
            found=False,
            detail="No JSON-LD schema blocks found",
            status="critical",
        ))

    # ── Microdata (non-JSON-LD) ───────────────────────────────────────────────
    microdata_types = _extract_microdata(soup)
    if microdata_types:
        results.append(StructuredDataResult(
            name="Schema Markup (Microdata)",
            found=True,
            detail=f"Microdata types: {', '.join(set(microdata_types))}",
            status="warn",  # Warn because JSON-LD is preferred
            items=microdata_types,
        ))
    else:
        results.append(StructuredDataResult(
            name="Schema Markup (Microdata)",
            found=False,
            detail="No Microdata found (JSON-LD is preferred anyway)",
            status="ok",
        ))

    # ── Schema context checks (Google / Bing / Yandex) ──────────────────────
    schema_html = str(soup)
    for engine, pattern in [
        ("Google", r"schema\.org"),
        ("Bing", r"schema\.org"),  # Bing also uses schema.org
        ("Yandex", r"schema\.org"),
    ]:
        found = bool(re.search(pattern, schema_html, re.I))
        results.append(StructuredDataResult(
            name=f"Schema Context — {engine}",
            found=found,
            detail="schema.org context detected" if found else "No schema.org context found",
            status="ok" if found else "critical",
        ))

    # ── Open Graph ───────────────────────────────────────────────────────────
    og_tags: dict[str, str] = {}
    for meta in soup.find_all("meta", property=re.compile(r"^og:", re.I)):
        og_tags[meta.get("property", "")] = meta.get("content", "")

    required_og = ["og:title", "og:description", "og:image", "og:url", "og:type"]
    missing_og = [t for t in required_og if t not in og_tags]

    if not missing_og:
        results.append(StructuredDataResult(
            name="Open Graph Tags",
            found=True,
            detail=f"All required OG tags present: {', '.join(required_og)}",
            status="ok",
            items=list(og_tags.items()),
        ))
    elif og_tags:
        results.append(StructuredDataResult(
            name="Open Graph Tags",
            found=True,
            detail=f"Partial OG tags. Missing: {', '.join(missing_og)}",
            status="warn",
            items=list(og_tags.items()),
        ))
    else:
        results.append(StructuredDataResult(
            name="Open Graph Tags",
            found=False,
            detail="No Open Graph tags found",
            status="critical",
        ))

    # ── Twitter Card ─────────────────────────────────────────────────────────
    twitter_tags: dict[str, str] = {}
    for meta in soup.find_all("meta", attrs={"name": re.compile(r"^twitter:", re.I)}):
        twitter_tags[meta.get("name", "")] = meta.get("content", "")

    if twitter_tags:
        results.append(StructuredDataResult(
            name="Twitter / X Card Tags",
            found=True,
            detail=f"Card type: {twitter_tags.get('twitter:card', 'unknown')}",
            status="ok",
            items=list(twitter_tags.items()),
        ))
    else:
        results.append(StructuredDataResult(
            name="Twitter / X Card Tags",
            found=False,
            detail="No Twitter Card meta tags found",
            status="warn",
        ))

    return results
