"""
reports/html_report.py — Generate a self-contained HTML report from scan data.
"""
from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def _status_for_page(page_data: dict) -> str:
    """Determine the worst status across all checks for a page dict."""
    worst = "ok"
    for cat in ["on_page", "structured_data", "metadata"]:
        for item in page_data.get(cat, []):
            if isinstance(item, dict):
                s = item.get("status", "ok")
            else:
                s = getattr(item, "status", "ok")
            if s == "critical":
                return "critical"
            if s == "warn":
                worst = "warn"
    return worst


def _issues_for_page(page_data: dict) -> list[str]:
    """Collect all critical issue names for a page."""
    issues: list[str] = []
    for cat in ["on_page", "structured_data"]:
        for item in page_data.get(cat, []):
            if isinstance(item, dict):
                if item.get("status") == "critical":
                    issues.append(item.get("name", "Unknown issue"))
            else:
                if getattr(item, "status", "") == "critical":
                    issues.append(getattr(item, "name", "Unknown issue"))
    return issues


def _count_statuses(scan_data: dict) -> tuple[int, int, int]:
    """Return (critical, warn, ok) counts across all per-page checks."""
    critical = warn = ok = 0
    for page in scan_data.get("pages", {}).values():
        for cat in ["on_page", "structured_data"]:
            for item in page.get(cat, []):
                s = item.get("status", "ok") if isinstance(item, dict) else getattr(item, "status", "ok")
                if s == "critical":
                    critical += 1
                elif s == "warn":
                    warn += 1
                else:
                    ok += 1
    return critical, warn, ok


def _to_template_obj(obj: Any) -> Any:
    """Convert dataclasses to attribute-accessible objects for Jinja2."""
    if hasattr(obj, "__dataclass_fields__"):
        # Return a simple namespace that Jinja2 can access by attribute
        class _Obj:
            pass
        o = _Obj()
        for k, v in obj.__dict__.items():
            setattr(o, k, _to_template_obj(v))
        return o
    if isinstance(obj, list):
        return [_to_template_obj(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _to_template_obj(v) for k, v in obj.items()}
    return obj


def generate_html_report(
    scan_data: dict,
    output_path: str,
    comparison=None,
) -> str:
    """
    Render the HTML report from scan_data and write to output_path.
    Returns the output path.
    """
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template("report.html")

    pages = scan_data.get("pages", {})
    critical_count, warn_count, ok_count = _count_statuses(scan_data)

    # Build per-page status and issue maps for the JS tree
    page_statuses: dict[str, str] = {}
    page_issues: dict[str, list[str]] = {}
    for url, page in pages.items():
        page_statuses[url] = _status_for_page(page)
        page_issues[url] = _issues_for_page(page)

    # Convert to template-friendly objects
    def _get_list(data: dict, key: str) -> list:
        raw = data.get(key, [])
        return _to_template_obj(raw) if raw else []

    tracking_results = _get_list(scan_data, "tracking")
    structured_data_results = _get_list(scan_data, "structured_data")
    site_checks = _get_list(scan_data, "site_checks")  # sitemap + robots
    per_page_on_page = {
        url: _to_template_obj(page.get("on_page", []))
        for url, page in pages.items()
    }
    metadata_results = _to_template_obj([
        page.get("metadata_result") for page in pages.values()
        if page.get("metadata_result")
    ])
    ai_results = _to_template_obj([
        page.get("ai_result") for page in pages.values()
        if page.get("ai_result")
    ])

    context = dict(
        scan_name=scan_data.get("scan_name", "Audit"),
        url=scan_data.get("url", ""),
        created_at=scan_data.get("created_at", datetime.datetime.utcnow().isoformat()[:19]),
        keywords=scan_data.get("keywords", []),
        total_pages=len(pages),
        critical_count=critical_count,
        warn_count=warn_count,
        ok_count=ok_count,
        tracking_results=tracking_results,
        structured_data_results=structured_data_results,
        site_checks=site_checks,
        per_page_on_page=per_page_on_page,
        metadata_results=metadata_results,
        ai_results=ai_results,
        site_tree_json=json.dumps(scan_data.get("site_tree", {})),
        page_statuses_json=json.dumps(page_statuses),
        page_issues_json=json.dumps(page_issues),
        comparison=_to_template_obj(comparison) if comparison else None,
    )

    html = template.render(**context)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")

    return str(out)
