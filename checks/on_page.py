"""
checks/on_page.py — Canonical, noindex, H1, sitemap.xml, robots.txt checks.
H1 vs keyword cluster matching is delegated to ai_analysis.py.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse
from typing import Optional

import requests
from bs4 import BeautifulSoup


@dataclass
class OnPageResult:
    name: str
    found: bool
    detail: str = ""
    status: str = "ok"  # "ok" | "warn" | "critical"
    items: list = field(default_factory=list)


def check_canonical(html: str, page_url: str) -> OnPageResult:
    soup = BeautifulSoup(html, "lxml")
    canonical = soup.find("link", rel=lambda r: r and "canonical" in r)
    if not canonical:
        return OnPageResult(
            name="Canonical Tag",
            found=False,
            detail="No canonical tag found",
            status="critical",
        )
    href = canonical.get("href", "")
    if not href:
        return OnPageResult(
            name="Canonical Tag",
            found=True,
            detail="Canonical tag present but href is empty",
            status="warn",
        )
    # Check self-referencing
    norm_page = page_url.rstrip("/")
    norm_canonical = href.rstrip("/")
    if norm_page == norm_canonical:
        return OnPageResult(
            name="Canonical Tag",
            found=True,
            detail=f"Self-referencing canonical: {href}",
            status="ok",
        )
    return OnPageResult(
        name="Canonical Tag",
        found=True,
        detail=f"Canonical points to: {href} (not self-referencing)",
        status="warn",
    )


def check_noindex(html: str) -> OnPageResult:
    soup = BeautifulSoup(html, "lxml")
    robots_meta = soup.find("meta", attrs={"name": re.compile(r"^robots$", re.I)})
    if robots_meta:
        content = robots_meta.get("content", "").lower()
        if "noindex" in content:
            return OnPageResult(
                name="Noindex Tag",
                found=True,
                detail=f"Page has noindex: {robots_meta.get('content', '')}",
                status="warn",
            )
        return OnPageResult(
            name="Noindex Tag",
            found=True,
            detail=f"Robots meta present but indexable: {robots_meta.get('content', '')}",
            status="ok",
        )
    return OnPageResult(
        name="Noindex Tag",
        found=False,
        detail="No robots meta tag — page is indexable",
        status="ok",
    )


def check_h1(html: str) -> OnPageResult:
    soup = BeautifulSoup(html, "lxml")
    h1_tags = soup.find_all("h1")
    count = len(h1_tags)
    texts = [h.get_text(strip=True) for h in h1_tags]

    if count == 0:
        return OnPageResult(
            name="H1 Tag",
            found=False,
            detail="No H1 tag found on this page",
            status="critical",
            items=[],
        )
    if count == 1:
        return OnPageResult(
            name="H1 Tag",
            found=True,
            detail=f'H1: "{texts[0]}"',
            status="ok",
            items=texts,
        )
    return OnPageResult(
        name="H1 Tag",
        found=True,
        detail=f"Multiple H1 tags ({count}): {texts}",
        status="warn",
        items=texts,
    )


def check_sitemap(base_url: str) -> OnPageResult:
    """Fetch and validate sitemap.xml."""
    sitemap_url = urljoin(base_url, "/sitemap.xml")
    try:
        resp = requests.get(sitemap_url, timeout=15)
        if resp.status_code == 404:
            return OnPageResult(
                name="sitemap.xml",
                found=False,
                detail=f"sitemap.xml not found at {sitemap_url}",
                status="critical",
            )
        if resp.status_code != 200:
            return OnPageResult(
                name="sitemap.xml",
                found=False,
                detail=f"HTTP {resp.status_code} fetching {sitemap_url}",
                status="critical",
            )
        content = resp.text
        # Basic XML validation
        if "<urlset" not in content and "<sitemapindex" not in content:
            return OnPageResult(
                name="sitemap.xml",
                found=True,
                detail="sitemap.xml found but does not appear to be valid XML",
                status="warn",
            )
        # Count URLs
        url_count = content.count("<loc>")
        return OnPageResult(
            name="sitemap.xml",
            found=True,
            detail=f"Valid sitemap.xml found with {url_count} URL(s)",
            status="ok",
        )
    except requests.RequestException as e:
        return OnPageResult(
            name="sitemap.xml",
            found=False,
            detail=f"Error fetching sitemap: {e}",
            status="critical",
        )


def check_robots_txt(base_url: str) -> OnPageResult:
    """Fetch and validate robots.txt."""
    robots_url = urljoin(base_url, "/robots.txt")
    try:
        resp = requests.get(robots_url, timeout=15)
        if resp.status_code == 404:
            return OnPageResult(
                name="robots.txt",
                found=False,
                detail=f"robots.txt not found at {robots_url}",
                status="critical",
            )
        if resp.status_code != 200:
            return OnPageResult(
                name="robots.txt",
                found=False,
                detail=f"HTTP {resp.status_code} fetching {robots_url}",
                status="critical",
            )
        content = resp.text
        has_user_agent = "user-agent" in content.lower()
        if not has_user_agent:
            return OnPageResult(
                name="robots.txt",
                found=True,
                detail="robots.txt found but missing User-agent directive",
                status="warn",
            )
        # Check if sitemap is referenced
        has_sitemap_ref = "sitemap:" in content.lower()
        detail = "Valid robots.txt found"
        if has_sitemap_ref:
            detail += " (includes Sitemap reference)"
        return OnPageResult(
            name="robots.txt",
            found=True,
            detail=detail,
            status="ok",
        )
    except requests.RequestException as e:
        return OnPageResult(
            name="robots.txt",
            found=False,
            detail=f"Error fetching robots.txt: {e}",
            status="critical",
        )


def run_all_on_page_checks(
    html: str,
    page_url: str,
    base_url: str,
    run_site_checks: bool = False,
) -> list[OnPageResult]:
    """
    Run all on-page checks for a single page.
    site_checks (sitemap, robots) are only run once for the whole site.
    """
    results: list[OnPageResult] = [
        check_canonical(html, page_url),
        check_noindex(html),
        check_h1(html),
    ]
    if run_site_checks:
        results.append(check_sitemap(base_url))
        results.append(check_robots_txt(base_url))
    return results
