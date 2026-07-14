"""
main.py — Entry point for the SEO Audit Tool.
All interaction is terminal-driven (PowerShell / oh-my-posh compatible via Rich).
"""
from __future__ import annotations

import datetime
import os
import sys
from pathlib import Path
from typing import Optional

# ── Windows UTF-8 fix ────────────────────────────────────────────────
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    # reconfigure() safely changes encoding without replacing the stream object
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeElapsedColumn,
    TaskProgressColumn,
)

load_dotenv()

console = Console(force_terminal=True)

# ── Lazy imports (to give fast startup even if optional deps missing) ──────────

def _import_checks():
    from checks.tracking import check_tracking
    from checks.structured_data import check_structured_data
    from checks.on_page import run_all_on_page_checks, check_sitemap, check_robots_txt
    from checks.metadata import check_metadata
    from checks.ai_analysis import check_h1_keyword_match, analyze_content
    return (
        check_tracking,
        check_structured_data,
        run_all_on_page_checks,
        check_sitemap,
        check_robots_txt,
        check_metadata,
        check_h1_keyword_match,
        analyze_content,
    )


def _import_storage():
    from storage.firebase_store import (
        init_firebase,
        init_firebase_from_env,
        save_scan,
        list_scans,
        load_scan,
        compare_scans,
    )
    return init_firebase, init_firebase_from_env, save_scan, list_scans, load_scan, compare_scans


def _import_reports():
    from reports.terminal_report import (
        print_banner,
        print_scans_list,
        print_section,
        print_check_results,
        print_metadata_results,
        print_ai_results,
        print_site_tree,
        print_comparison_report,
        print_summary,
    )
    from reports.html_report import generate_html_report
    return (
        print_banner,
        print_scans_list,
        print_section,
        print_check_results,
        print_metadata_results,
        print_ai_results,
        print_site_tree,
        print_comparison_report,
        print_summary,
        generate_html_report,
    )


# ── Firebase setup ────────────────────────────────────────────────────────────

def _init_firebase_interactive() -> bool:
    """
    Initialise Firebase.  Tries FIREBASE_SERVICE_ACCOUNT from .env first.
    Falls back to an interactive prompt only when the env var is absent/invalid.
    """
    init_firebase, init_firebase_from_env, *_ = _import_storage()

    # ── 1. Try .env auto-init ─────────────────────────────────────────────────
    import os
    sa_env = os.getenv("FIREBASE_SERVICE_ACCOUNT", "").strip()
    if sa_env:
        try:
            init_firebase(sa_env)
            console.print(
                f"[bright_blue]✔ Firebase connected[/bright_blue] "
                f"[dim](via .env → {sa_env})[/dim]\n"
            )
            return True
        except Exception as e:
            console.print(
                f"[bright_yellow]⚠ FIREBASE_SERVICE_ACCOUNT in .env failed: {e}[/bright_yellow]\n"
                "  Falling back to manual entry…\n"
            )

    # ── 2. Interactive fallback ───────────────────────────────────────────────
    console.print("\n[bold bright_cyan]🔥 Firebase Setup[/bold bright_cyan]")
    console.print(
        "[dim]Add [bold]FIREBASE_SERVICE_ACCOUNT[/bold] to your [bold].env[/bold] file "
        "to skip this prompt in future.\n"
        "Download key: Firebase Console → Project Settings → Service Accounts.[/dim]\n"
    )
    path = Prompt.ask(
        "  Path to service-account JSON",
        default=str(Path.home() / "firebase-service-account.json"),
    )
    path = path.strip('"').strip("'")
    if not Path(path).exists():
        console.print(f"[bright_red]✘ File not found: {path}[/bright_red]")
        return False
    try:
        init_firebase(path)
        console.print("[bright_blue]✔ Firebase connected[/bright_blue]\n")
        # Offer to save path into .env for next time
        if Confirm.ask("  Save this path to .env so you won't be asked again?", default=True):
            _save_firebase_path_to_env(path)
        return True
    except Exception as e:
        console.print(f"[bright_red]✘ Firebase error: {e}[/bright_red]")
        return False


def _save_firebase_path_to_env(path: str) -> None:
    """Append or update FIREBASE_SERVICE_ACCOUNT in the local .env file."""
    env_file = Path(".env")
    lines: list[str] = []
    if env_file.exists():
        lines = env_file.read_text(encoding="utf-8").splitlines()

    updated = False
    for i, line in enumerate(lines):
        if line.startswith("FIREBASE_SERVICE_ACCOUNT"):
            lines[i] = f"FIREBASE_SERVICE_ACCOUNT={path}"
            updated = True
            break
    if not updated:
        lines.append(f"FIREBASE_SERVICE_ACCOUNT={path}")

    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    console.print(f"[bright_blue]✔ Saved to .env[/bright_blue] [dim]({env_file.resolve()})[/dim]\n")


# ── Full audit pipeline ───────────────────────────────────────────────────────

def _run_audit(url: str, keywords: list[str], scan_name: str, max_pages: int = 200) -> dict:
    """
    Full audit pipeline. Returns scan_data dict.
    """
    from crawler import crawl, build_tree
    (
        check_tracking,
        check_structured_data,
        run_all_on_page_checks,
        check_sitemap,
        check_robots_txt,
        check_metadata,
        check_h1_keyword_match,
        analyze_content,
    ) = _import_checks()

    from urllib.parse import urlparse
    base_url = "{0}://{1}".format(*urlparse(url)[:2])

    pages_data: dict = {}
    site_tree: dict = {}

    # ── Step 1: Crawl ────────────────────────────────────────────────────────
    console.print()
    console.print("[bold bright_cyan]Step 1/5 — Crawling site…[/bold bright_cyan]")
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        crawled = crawl(
            start_url=url,
            max_pages=max_pages,
            respect_robots=True,
            crawl_delay=0.3,
            progress=progress,
        )

    site_tree = build_tree(crawled)
    console.print(f"[bright_blue]✔ Crawled {len(crawled)} pages[/bright_blue]\n")

    # ── Step 2: Tracking (homepage only) ─────────────────────────────────────
    console.print("[bold bright_cyan]Step 2/5 — Checking tracking & analytics…[/bold bright_cyan]")
    homepage_html = crawled[url].html if url in crawled else ""
    tracking_results = []
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as progress:
        task = progress.add_task("Detecting trackers…", total=None)
        tracking_results = check_tracking(homepage_html)
        progress.update(task, completed=True)
    console.print(f"[bright_blue]✔ {len(tracking_results)} tracking checks completed[/bright_blue]\n")

    # ── Step 3: Site-level checks (sitemap + robots) ──────────────────────────
    console.print("[bold bright_cyan]Step 3/5 — Site-level checks (sitemap, robots.txt)…[/bold bright_cyan]")
    site_checks = []
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as progress:
        task = progress.add_task("Checking sitemap & robots…", total=None)
        site_checks = [check_sitemap(base_url), check_robots_txt(base_url)]
        progress.update(task, completed=True)
    console.print("[bright_blue]✔ Site-level checks done[/bright_blue]\n")

    # ── Step 4: Per-page checks ───────────────────────────────────────────────
    console.print("[bold bright_cyan]Step 4/5 — Per-page SEO checks…[/bold bright_cyan]")
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Checking pages…", total=len(crawled))

        structured_data_results = []  # Aggregate from homepage for summary

        for page_url, page in crawled.items():
            page_dict: dict = {"url": page_url}

            # Structured data
            sd_results = check_structured_data(page.html) if page.html else []
            page_dict["structured_data"] = sd_results
            if page_url == url:
                structured_data_results = sd_results

            # On-page
            op_results = run_all_on_page_checks(page.html, page_url, base_url)
            page_dict["on_page"] = op_results

            # Metadata
            meta_result = check_metadata(page.html, page_url) if page.html else None
            page_dict["metadata_result"] = meta_result

            # AI: H1 keyword match
            h1_result_obj = None
            if op_results:
                h1_check = next((r for r in op_results if r.name == "H1 Tag"), None)
                if h1_check and h1_check.items:
                    h1_text = h1_check.items[0]
                    h1_result_obj = check_h1_keyword_match(h1_text, keywords)

            # AI: Content analysis
            ai_result = None
            if page.html:
                ai_result = analyze_content(page_url, page.html, keywords)
                if ai_result:
                    ai_result.h1_keyword_result = h1_result_obj

            page_dict["ai_result"] = ai_result
            pages_data[page_url] = page_dict
            progress.advance(task)

    console.print(f"[bright_blue]✔ Per-page checks complete ({len(crawled)} pages)[/bright_blue]\n")

    scan_data = {
        "scan_name": scan_name,
        "url": url,
        "keywords": keywords,
        "created_at": datetime.datetime.utcnow().isoformat(),
        "total_pages": len(crawled),
        "tracking": tracking_results,
        "structured_data": structured_data_results,
        "site_checks": site_checks,
        "pages": pages_data,
        "site_tree": site_tree,
    }

    return scan_data


# ── Report output ─────────────────────────────────────────────────────────────

def _output_reports(scan_data: dict, comparison=None) -> None:
    (
        print_banner,
        print_scans_list,
        print_section,
        print_check_results,
        print_metadata_results,
        print_ai_results,
        print_site_tree,
        print_comparison_report,
        print_summary,
        generate_html_report,
    ) = _import_reports()

    # Terminal report
    print_summary(scan_data)
    print_section("Tracking & Analytics", "📡")
    print_check_results(scan_data.get("tracking", []), "Tracking Checks")

    print_section("Structured Data", "🏷️")
    print_check_results(scan_data.get("structured_data", []), "Structured Data Checks")

    print_section("Site-Level Checks", "🌐")
    print_check_results(scan_data.get("site_checks", []), "Sitemap & Robots.txt")

    # Metadata
    meta_results = [
        page.get("metadata_result")
        for page in scan_data.get("pages", {}).values()
        if page.get("metadata_result")
    ]
    print_metadata_results(meta_results)

    # AI
    ai_results = [
        page.get("ai_result")
        for page in scan_data.get("pages", {}).values()
        if page.get("ai_result")
    ]
    print_ai_results(ai_results)

    # Site tree (pass empty dict for pages — terminal_report uses page objects)
    print_site_tree({}, scan_data.get("site_tree", {}))

    if comparison:
        print_comparison_report(comparison)

    # HTML report
    console.print()
    report_dir = Path.cwd() / "reports_output"
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = report_dir / f"seo_report_{scan_data['scan_name']}_{timestamp}.html"

    console.print("[bold bright_cyan]Step 5/5 — Generating HTML report…[/bold bright_cyan]")
    out_path = generate_html_report(scan_data, str(report_path), comparison=comparison)
    console.print(f"[bright_blue]✔ HTML report saved:[/bright_blue] [link={out_path}]{out_path}[/link]\n")


# ── Main menu ─────────────────────────────────────────────────────────────────

def main() -> None:
    (
        print_banner,
        print_scans_list,
        *_rest,
    ) = _import_reports()

    print_banner()

    # Firebase init
    firebase_ok = _init_firebase_interactive()
    storage = _import_storage() if firebase_ok else None

    previous_scans: list[dict] = []
    if firebase_ok and storage:
        _, _, _, list_scans, *_ = storage
        try:
            previous_scans = list_scans()
        except Exception as e:
            console.print(f"[bright_yellow]⚠ Could not load previous scans: {e}[/bright_yellow]")

    print_scans_list(previous_scans)

    # Menu
    while True:
        console.print("[bold white]What would you like to do?[/bold white]")
        console.print("  [bright_cyan]1[/bright_cyan] — New scan")
        if previous_scans:
            console.print("  [bright_cyan]2[/bright_cyan] — View a previous report")
            console.print("  [bright_cyan]3[/bright_cyan] — Re-crawl a previous site")
            console.print("  [bright_cyan]4[/bright_cyan] — Compare two scans")
        console.print("  [bright_cyan]0[/bright_cyan] — Exit")
        console.print()

        choice = Prompt.ask("  Choice", choices=["0","1","2","3","4"] if previous_scans else ["0","1"])

        if choice == "0":
            console.print("[dim]Goodbye.[/dim]")
            sys.exit(0)

        elif choice == "1":
            _new_scan_flow(firebase_ok, storage)

        elif choice == "2":
            _view_report_flow(previous_scans, storage)

        elif choice == "3":
            _recrawl_flow(previous_scans, firebase_ok, storage)

        elif choice == "4":
            _compare_flow(previous_scans, storage)

        console.print()


# ── Flows ─────────────────────────────────────────────────────────────────────

def _new_scan_flow(firebase_ok: bool, storage) -> None:
    console.print("\n[bold bright_cyan]🆕 New Scan[/bold bright_cyan]\n")

    url = Prompt.ask("  Target website URL (e.g. https://example.com)")
    if not url.startswith("http"):
        url = "https://" + url

    max_pages = int(Prompt.ask("  Max pages to crawl", default="200"))

    console.print("\n  Enter 5 target keywords (press Enter after each):")
    keywords: list[str] = []
    for i in range(1, 6):
        kw = Prompt.ask(f"    Keyword {i}")
        keywords.append(kw.strip())

    scan_name = Prompt.ask(
        "\n  Unique scan name",
        default=f"scan_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}",
    )

    scan_data = _run_audit(url, keywords, scan_name, max_pages=max_pages)

    if firebase_ok and storage:
        _, _, save_scan, *_ = storage
        try:
            save_scan(scan_name, scan_data)
            console.print(f"[bright_blue]✔ Scan saved to Firebase as '{scan_name}'[/bright_blue]")
        except Exception as e:
            console.print(f"[bright_yellow]⚠ Could not save to Firebase: {e}[/bright_yellow]")

    _output_reports(scan_data)


def _view_report_flow(previous_scans: list[dict], storage) -> None:
    if not storage:
        console.print("[bright_red]Firebase not available.[/bright_red]")
        return

    _, _, _, list_scans, load_scan, _ = storage
    idx = int(Prompt.ask("  Enter scan # to view", default="1")) - 1
    if idx < 0 or idx >= len(previous_scans):
        console.print("[bright_red]Invalid selection.[/bright_red]")
        return

    scan_name = previous_scans[idx]["scan_name"]
    doc = load_scan(scan_name)
    if not doc:
        console.print("[bright_red]Scan not found.[/bright_red]")
        return

    scan_data = doc.get("data", {})
    scan_data["scan_name"] = scan_name
    scan_data["created_at"] = doc.get("created_at", "")
    _output_reports(scan_data)


def _recrawl_flow(previous_scans: list[dict], firebase_ok: bool, storage) -> None:
    idx = int(Prompt.ask("  Enter scan # to re-crawl", default="1")) - 1
    if idx < 0 or idx >= len(previous_scans):
        console.print("[bright_red]Invalid selection.[/bright_red]")
        return

    old_scan = previous_scans[idx]
    url = old_scan.get("url", "")
    old_name = old_scan.get("scan_name", "")

    if not url:
        url = Prompt.ask("  URL not found in previous scan. Enter URL")

    keywords: list[str] = []
    if storage:
        _, _, _, load_scan, *_ = storage
        doc = load_scan(old_name)
        if doc:
            keywords = doc.get("data", {}).get("keywords", [])

    if not keywords:
        console.print("  Enter 5 target keywords:")
        for i in range(1, 6):
            kw = Prompt.ask(f"    Keyword {i}")
            keywords.append(kw.strip())

    max_pages = int(Prompt.ask("  Max pages to crawl", default="200"))
    new_name = Prompt.ask(
        "  New scan name",
        default=f"{old_name}_recrawl_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}",
    )

    scan_data = _run_audit(url, keywords, new_name, max_pages=max_pages)

    comparison = None
    if firebase_ok and storage:
        _, _, save_scan, _, _, compare_scans = storage
        try:
            save_scan(new_name, scan_data)
            console.print(f"[bright_blue]✔ New scan saved as '{new_name}'[/bright_blue]")
        except Exception as e:
            console.print(f"[bright_yellow]⚠ Could not save: {e}[/bright_yellow]")

        # Offer comparison
        if Confirm.ask(f"\n  Generate before/after comparison ({old_name} → {new_name})?"):
            try:
                comparison = compare_scans(old_name, new_name)
            except Exception as e:
                console.print(f"[bright_yellow]⚠ Comparison failed: {e}[/bright_yellow]")

    _output_reports(scan_data, comparison=comparison)


def _compare_flow(previous_scans: list[dict], storage) -> None:
    if not storage:
        console.print("[bright_red]Firebase not available.[/bright_red]")
        return

    _, _, _, _, _, compare_scans = storage
    console.print("\n  Select two scans to compare:")
    idx_a = int(Prompt.ask("  Scan A (#, older/before)", default="1")) - 1
    idx_b = int(Prompt.ask("  Scan B (#, newer/after)", default="2")) - 1

    if not (0 <= idx_a < len(previous_scans) and 0 <= idx_b < len(previous_scans)):
        console.print("[bright_red]Invalid selections.[/bright_red]")
        return

    name_a = previous_scans[idx_a]["scan_name"]
    name_b = previous_scans[idx_b]["scan_name"]

    try:
        comparison = compare_scans(name_a, name_b)
    except Exception as e:
        console.print(f"[bright_red]Comparison failed: {e}[/bright_red]")
        return

    (
        *_,
        print_comparison_report,
        print_summary,
        generate_html_report,
    ) = _import_reports()

    # Load scan B data for HTML report
    _, _, _, _, load_scan, _ = storage
    doc_b = load_scan(name_b)
    scan_data_b = doc_b.get("data", {}) if doc_b else {}
    scan_data_b["scan_name"] = name_b
    scan_data_b["created_at"] = doc_b.get("created_at", "") if doc_b else ""

    _output_reports(scan_data_b, comparison=comparison)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    main()
