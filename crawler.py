"""
crawler.py — BFS site crawler.
Crawls all pages within the same domain, tracks depth, builds a site tree.
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn


@dataclass
class PageData:
    url: str
    depth: int
    status_code: int
    title: str
    html: str
    links_out: list[str] = field(default_factory=list)
    parent: Optional[str] = None
    error: Optional[str] = None


def _normalize(url: str, base: str) -> Optional[str]:
    """Resolve relative URL and strip fragment/query for deduplication."""
    try:
        full = urljoin(base, url)
        parsed = urlparse(full)
        # Keep query strings but drop fragments
        return parsed._replace(fragment="").geturl()
    except Exception:
        return None


def _same_domain(url: str, base_netloc: str) -> bool:
    try:
        return urlparse(url).netloc == base_netloc
    except Exception:
        return False


def crawl(
    start_url: str,
    max_pages: int = 200,
    respect_robots: bool = True,
    crawl_delay: float = 0.5,
    progress: Optional[Progress] = None,
) -> dict[str, PageData]:
    """
    BFS crawl starting from start_url.
    Returns a dict of url -> PageData.
    """
    parsed_start = urlparse(start_url)
    base_netloc = parsed_start.netloc
    base_url = f"{parsed_start.scheme}://{parsed_start.netloc}"

    # Robots.txt
    disallowed: list[str] = []
    if respect_robots:
        disallowed = _load_robots(base_url)

    visited: dict[str, PageData] = {}
    queue: deque[tuple[str, int, Optional[str]]] = deque()
    queue.append((start_url, 0, None))
    queued_urls: set[str] = {start_url}

    session = requests.Session()
    session.headers.update({"User-Agent": "SEOAuditBot/1.0 (+https://github.com/seo-audit)"})

    task_id = None
    if progress:
        task_id = progress.add_task("[cyan]Crawling pages…", total=max_pages)

    while queue and len(visited) < max_pages:
        url, depth, parent = queue.popleft()

        # Robots check
        if respect_robots and _is_disallowed(url, disallowed, base_url):
            continue

        try:
            resp = session.get(url, timeout=15, allow_redirects=True)
            status_code = resp.status_code
            content_type = resp.headers.get("Content-Type", "")

            if "text/html" not in content_type:
                continue

            html = resp.text
            soup = BeautifulSoup(html, "lxml")

            title_tag = soup.find("title")
            title = title_tag.get_text(strip=True) if title_tag else ""

            # Extract internal links
            links_out: list[str] = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                norm = _normalize(href, url)
                if norm and _same_domain(norm, base_netloc):
                    links_out.append(norm)
                    if norm not in queued_urls and len(visited) + len(queue) < max_pages:
                        queued_urls.add(norm)
                        queue.append((norm, depth + 1, url))

            page = PageData(
                url=url,
                depth=depth,
                status_code=status_code,
                title=title,
                html=html,
                links_out=list(set(links_out)),
                parent=parent,
            )

        except requests.RequestException as exc:
            page = PageData(
                url=url,
                depth=depth,
                status_code=0,
                title="",
                html="",
                links_out=[],
                parent=parent,
                error=str(exc),
            )

        visited[url] = page
        if progress and task_id is not None:
            progress.update(task_id, advance=1, description=f"[cyan]Crawled {len(visited)} pages…")

        time.sleep(crawl_delay)

    if progress and task_id is not None:
        progress.update(task_id, completed=len(visited))

    return visited


def build_tree(pages: dict[str, PageData]) -> dict:
    """Build a nested dict tree from crawl results for display."""
    children: dict[str, list[str]] = {url: [] for url in pages}
    root = None
    for url, page in pages.items():
        if page.parent and page.parent in children:
            children[page.parent].append(url)
        elif page.parent is None:
            root = url

    def _node(url: str) -> dict:
        return {"url": url, "children": [_node(c) for c in children.get(url, [])]}

    return _node(root) if root else {}


# ── Robots.txt helpers ──────────────────────────────────────────────────────

def _load_robots(base_url: str) -> list[str]:
    disallowed: list[str] = []
    try:
        resp = requests.get(f"{base_url}/robots.txt", timeout=10)
        if resp.status_code == 200:
            user_agent_match = False
            for line in resp.text.splitlines():
                line = line.strip()
                if line.lower().startswith("user-agent:"):
                    agent = line.split(":", 1)[1].strip()
                    user_agent_match = agent in ("*", "SEOAuditBot")
                elif user_agent_match and line.lower().startswith("disallow:"):
                    path = line.split(":", 1)[1].strip()
                    if path:
                        disallowed.append(path)
    except Exception:
        pass
    return disallowed


def _is_disallowed(url: str, disallowed: list[str], base_url: str) -> bool:
    path = urlparse(url).path
    for rule in disallowed:
        if path.startswith(rule):
            return True
    return False
