"""
reports/terminal_report.py — Rich-based terminal output for all audit results.
Color coding: Red=Critical, Amber/Yellow=Warning, Blue/Cyan=OK/Info.
Windows-safe: no raw emoji characters, uses Rich markup only.
"""
from __future__ import annotations

import re
from typing import Any, Optional

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

console = Console(force_terminal=True)

_URL_RE = re.compile(r'https?://[^\s<>"\')\]]+')


def _linkify(value: str, base_style: str = "") -> Text:
    """Render a string as Rich Text with any http(s) URLs turned into clickable
    terminal hyperlinks (OSC 8), for terminals that support it (Windows Terminal,
    VS Code, iTerm2, etc.)."""
    text = Text(style=base_style)
    pos = 0
    for m in _URL_RE.finditer(value):
        if m.start() > pos:
            text.append(value[pos:m.start()])
        url = m.group(0)
        link_style = f"{base_style} link {url}".strip()
        text.append(url, style=link_style)
        pos = m.end()
    if pos < len(value):
        text.append(value[pos:])
    return text

# ── Status helpers ────────────────────────────────────────────────────────────

STATUS_COLORS = {
    "ok": "bright_blue",
    "warn": "bright_yellow",
    "critical": "bright_red",
}

# ASCII-safe status markers (no emoji)
STATUS_ICONS = {
    "ok":       "[bright_blue][ OK ][/bright_blue]",
    "warn":     "[bright_yellow][WARN][/bright_yellow]",
    "critical": "[bright_red][CRIT][/bright_red]",
}

STATUS_DOT = {
    "ok":       "[bright_blue](*)[/bright_blue]",
    "warn":     "[bright_yellow](!)[/bright_yellow]",
    "critical": "[bright_red][X][/bright_red]",
}


def _status_text(status: str, label: str = "") -> Text:
    color = STATUS_COLORS.get(status, "white")
    markers = {"ok": "[ OK ]", "warn": "[WARN]", "critical": "[CRIT]"}
    marker = markers.get(status, "[????]")
    return Text(f"{marker} {label}", style=color)


# ── Header banner ─────────────────────────────────────────────────────────────

def print_banner() -> None:
    console.print()
    console.print(Panel.fit(
        "[bold bright_cyan]>> SEO Audit Tool <<[/bold bright_cyan]\n"
        "[dim]Powered by Anthropic AI  |  Firebase  |  Rich[/dim]",
        border_style="bright_cyan",
        padding=(1, 4),
    ))
    console.print()


# ── Previous scans list ───────────────────────────────────────────────────────

def print_scans_list(scans: list[dict]) -> None:
    if not scans:
        console.print("[dim]No previous scans found in Firebase.[/dim]")
        return

    table = Table(
        title="Previous Scan Sessions",
        box=box.ROUNDED,
        border_style="bright_cyan",
        header_style="bold bright_cyan",
        show_lines=True,
    )
    table.add_column("#", style="dim", width=4)
    table.add_column("Scan Name", style="bold white")
    table.add_column("URL", style="cyan")
    table.add_column("Date", style="dim")

    for i, scan in enumerate(scans, 1):
        table.add_row(
            str(i),
            scan.get("scan_name", ""),
            _linkify(scan.get("url", ""), "cyan"),
            scan.get("created_at", "")[:19].replace("T", " "),
        )

    console.print(table)
    console.print()


# ── Section header ────────────────────────────────────────────────────────────

def print_section(title: str, icon: str = ">>") -> None:
    console.print()
    console.print(Rule(f"{icon}  {title}", style="bright_cyan"))
    console.print()


# ── Generic check results table ───────────────────────────────────────────────

def print_check_results(results: list, title: str) -> None:
    table = Table(
        title=title,
        box=box.SIMPLE_HEAVY,
        border_style="bright_cyan",
        header_style="bold white",
        show_lines=True,
        expand=True,
    )
    table.add_column("Status", width=10)
    table.add_column("Check", style="bold white", min_width=30)
    table.add_column("Detail", style="dim white")

    for r in results:
        status = getattr(r, "status", "ok")
        name = getattr(r, "name", str(r))
        detail = getattr(r, "detail", "")
        found = getattr(r, "found", True)

        status_cell = _status_text(status, status.upper())
        table.add_row(status_cell, name, _linkify(detail or ("Found" if found else "Not found"), "white"))

    console.print(table)


# ── Metadata table ─────────────────────────────────────────────────────────────

def print_metadata_results(meta_results: list) -> None:
    print_section("Metadata -- Titles, Descriptions & Images", ">>")

    for meta in meta_results:
        url = getattr(meta, "url", "")
        title_status = getattr(meta, "title_status", "ok")
        desc_status = getattr(meta, "description_status", "ok")
        meta_title = getattr(meta, "meta_title", None) or "[dim]Missing[/dim]"
        meta_desc = getattr(meta, "meta_description", None) or "[dim]Missing[/dim]"
        images = getattr(meta, "images", [])
        missing_alt = getattr(meta, "missing_alt_count", 0)

        t_dot = STATUS_DOT.get(title_status, "(?)")
        d_dot = STATUS_DOT.get(desc_status, "(?)")

        panel_content = (
            f"[bold]Title[/bold] {t_dot}  {meta_title}\n"
            f"[bold]Desc [/bold] {d_dot}  {meta_desc}\n"
            f"[bold]Images[/bold]  {len(images)} total, "
            f"[bright_red]{missing_alt} missing alt[/bright_red]"
        )
        worst = (
            "critical" if (title_status == "critical" or desc_status == "critical" or missing_alt > 0)
            else "warn" if (title_status == "warn" or desc_status == "warn")
            else "ok"
        )
        console.print(Panel(
            panel_content,
            title=_linkify(url[:80], "cyan"),
            border_style=STATUS_COLORS.get(worst, "bright_blue"),
            padding=(0, 1),
        ))

        # Image detail table
        if images:
            img_table = Table(box=box.MINIMAL, show_header=True, header_style="dim")
            img_table.add_column("St", width=6)
            img_table.add_column("Image src")
            img_table.add_column("Alt text")
            for img in images[:20]:
                img_table.add_row(
                    "OK" if img.has_alt else "[bright_red]MISS[/bright_red]",
                    img.src[:60],
                    img.alt[:80] if img.has_alt else "[bright_red]MISSING ALT[/bright_red]",
                )
            if len(images) > 20:
                img_table.add_row("...", f"...and {len(images)-20} more", "")
            console.print(img_table)

    console.print()


# ── AI analysis results ───────────────────────────────────────────────────────

def print_ai_results(ai_results: list) -> None:
    print_section("AI Content Analysis (Anthropic Claude)", "AI")

    for r in ai_results:
        url = getattr(r, "url", "")
        is_seo = getattr(r, "is_seo_friendly", False)
        score = getattr(r, "keyword_cluster_score", "poor")
        summary = getattr(r, "summary", "")
        suggestions = getattr(r, "suggestions", [])
        status = getattr(r, "status", "warn")

        seo_label = "[bright_blue]SEO-Friendly: YES[/bright_blue]" if is_seo else "[bright_red]SEO-Friendly: NO[/bright_red]"
        score_color = {"good": "bright_blue", "partial": "bright_yellow", "poor": "bright_red"}.get(score, "white")

        content = (
            f"{seo_label}    "
            f"[bold]Keyword Cluster:[/bold] [{score_color}]{score.upper()}[/{score_color}]\n\n"
            f"[dim]{summary}[/dim]"
        )
        if suggestions:
            content += "\n\n[bold yellow]Suggestions:[/bold yellow]"
            for s in suggestions:
                content += f"\n  - {s}"

        console.print(Panel(
            content,
            title=_linkify(url[:80], "cyan"),
            border_style=STATUS_COLORS.get(status, "bright_blue"),
            padding=(0, 1),
        ))


# ── Site structure tree ───────────────────────────────────────────────────────

def print_site_tree(pages: dict, tree_data: dict, max_depth: int = 4) -> None:
    print_section("Site Structure", ">>")

    def _add_branch(tree_node: Tree, node: dict, depth: int = 0) -> None:
        if depth > max_depth:
            return
        url = node.get("url", "")
        page = pages.get(url, None)
        status = "ok"
        if page:
            for attr in ["on_page_results", "structured_data_results"]:
                for r in getattr(page, attr, []) or []:
                    if getattr(r, "status", "ok") == "critical":
                        status = "critical"
                        break
                    elif getattr(r, "status", "ok") == "warn" and status == "ok":
                        status = "warn"

        color = STATUS_COLORS.get(status, "white")
        markers = {"ok": "[OK]", "warn": "[!]", "critical": "[X]"}
        marker = markers.get(status, "")
        if page and hasattr(page, "status_code") and page.status_code not in (0, 200):
            label = Text(f"[ERR {page.status_code}] ", style="bright_red")
            label.append_text(_linkify(url, "bright_red"))
        else:
            label = Text(f"{marker} ", style=color)
            label.append_text(_linkify(url, color))

        branch = tree_node.add(label)
        for child in node.get("children", []):
            _add_branch(branch, child, depth + 1)

    if tree_data:
        root_label = _linkify(tree_data.get("url", "Root"), "bold bright_cyan")
        tree = Tree(root_label, guide_style="bright_cyan")
        for child in tree_data.get("children", []):
            _add_branch(tree, child, depth=1)
        console.print(tree)
    else:
        console.print("[dim]Site tree not available.[/dim]")
    console.print()


# ── Comparison report ─────────────────────────────────────────────────────────

def print_comparison_report(report) -> None:
    print_section(
        f"Comparison: {report.scan_a_name} -> {report.scan_b_name}",
        ">>"
    )
    console.print(
        f"  [dim]Before:[/dim] {report.scan_a_name} ({report.scan_a_date[:19]})\n"
        f"  [dim]After: [/dim] {report.scan_b_name} ({report.scan_b_date[:19]})"
    )
    console.print()

    def _section(title: str, items: list[str], color: str) -> None:
        if not items:
            console.print(f"[{color}]{title}:[/{color}] [dim]None[/dim]")
            return
        console.print(f"[{color}]{title} ({len(items)}):[/{color}]")
        for item in items[:30]:
            parts = item.split("|")
            console.print(f"  - [dim]{parts[0][:50]}[/dim] -- {parts[1] if len(parts) > 1 else ''}")
        if len(items) > 30:
            console.print(f"  [dim]...and {len(items)-30} more[/dim]")
        console.print()

    _section("[bright_blue]FIXED Issues[/bright_blue]", report.fixed, "bright_blue")
    _section("[bright_red]NEW Issues[/bright_red]", report.new_issues, "bright_red")
    _section("[bright_yellow]OUTSTANDING Issues[/bright_yellow]", report.still_outstanding, "bright_yellow")

    if report.improved_pages:
        console.print("[bright_blue]Improved Pages:[/bright_blue]")
        for p in report.improved_pages[:10]:
            console.print(f"  + {p}")
    if report.regressed_pages:
        console.print("[bright_red]Regressed Pages:[/bright_red]")
        for p in report.regressed_pages[:10]:
            console.print(f"  - {p}")
    console.print()


# ── Summary scoreboard ─────────────────────────────────────────────────────────

def print_summary(scan_data: dict) -> None:
    print_section("Audit Summary", ">>")

    pages = scan_data.get("pages", {})
    total = len(pages)
    critical_pages = sum(
        1 for p in pages.values()
        if any(
            getattr(r, "status", "") == "critical"
            for attr in ["on_page_results", "structured_data_results"]
            for r in (getattr(p, attr, None) or [])
        )
    )

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Metric", style="bold white")
    table.add_column("Value", style="bold bright_cyan")
    table.add_row("Total pages crawled", str(total))
    table.add_row("Pages with critical issues", f"[bright_red]{critical_pages}[/bright_red]")
    table.add_row("Target URL", _linkify(scan_data.get("url", ""), "bright_cyan"))
    table.add_row("Keywords", ", ".join(scan_data.get("keywords", [])))
    console.print(table)
    console.print()
