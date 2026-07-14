"""
storage/firebase_store.py — Firestore-backed scan storage and comparison.
"""
from __future__ import annotations

import datetime
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

load_dotenv()

COLLECTION = "seo_scans"

_db: Optional[Any] = None


def init_firebase(service_account_path: str) -> None:
    """Initialize Firebase with a service-account JSON file path."""
    global _db
    path = Path(service_account_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Firebase service-account file not found: {service_account_path}\n"
            "Set FIREBASE_SERVICE_ACCOUNT in your .env file."
        )
    if not firebase_admin._apps:
        cred = credentials.Certificate(str(path))
        firebase_admin.initialize_app(cred)
    _db = firestore.client()


def init_firebase_from_env() -> bool:
    """
    Try to initialise Firebase automatically from the FIREBASE_SERVICE_ACCOUNT
    environment variable (set in .env).  Returns True on success, False if the
    variable is missing or the file doesn't exist.
    """
    sa_path = os.getenv("FIREBASE_SERVICE_ACCOUNT", "").strip()
    if not sa_path:
        return False
    try:
        init_firebase(sa_path)
        return True
    except Exception:
        return False


def _get_db():
    if _db is None:
        raise RuntimeError("Firebase not initialized. Call init_firebase() first.")
    return _db


# ── Serialization helpers ────────────────────────────────────────────────────

def _to_dict(obj: Any) -> Any:
    """Recursively convert dataclasses/lists/dicts to JSON-serializable dicts."""
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _to_dict(v) for k, v in asdict(obj).items()}
    if isinstance(obj, list):
        return [_to_dict(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    return obj


# ── Save scan ────────────────────────────────────────────────────────────────

def save_scan(scan_name: str, scan_data: dict) -> str:
    """
    Save a complete scan to Firestore.
    Returns the document ID.
    """
    db = _get_db()
    doc_ref = db.collection(COLLECTION).document(scan_name)

    payload = {
        "scan_name": scan_name,
        "created_at": datetime.datetime.utcnow().isoformat(),
        "data": _to_dict(scan_data),
    }
    doc_ref.set(payload)
    return scan_name


# ── List scans ───────────────────────────────────────────────────────────────

def list_scans() -> list[dict]:
    """Return all scans, sorted newest first."""
    db = _get_db()
    docs = db.collection(COLLECTION).stream()
    scans = []
    for doc in docs:
        d = doc.to_dict()
        scans.append({
            "id": doc.id,
            "scan_name": d.get("scan_name", doc.id),
            "created_at": d.get("created_at", ""),
            "url": d.get("data", {}).get("url", ""),
        })
    scans.sort(key=lambda x: x["created_at"], reverse=True)
    return scans


# ── Load scan ────────────────────────────────────────────────────────────────

def load_scan(scan_name: str) -> Optional[dict]:
    """Load a scan by name. Returns None if not found."""
    db = _get_db()
    doc = db.collection(COLLECTION).document(scan_name).get()
    if doc.exists:
        return doc.to_dict()
    return None


# ── Compare scans ─────────────────────────────────────────────────────────────

@dataclass
class ComparisonReport:
    scan_a_name: str
    scan_b_name: str
    scan_a_date: str
    scan_b_date: str
    fixed: list[str]        # Issues in A that are gone in B
    new_issues: list[str]   # Issues in B not in A
    still_outstanding: list[str]  # Issues in both
    improved_pages: list[str]
    regressed_pages: list[str]


def compare_scans(scan_name_a: str, scan_name_b: str) -> ComparisonReport:
    """
    Compare two scans and return a diff report.
    A = older/before, B = newer/after.
    """
    doc_a = load_scan(scan_name_a)
    doc_b = load_scan(scan_name_b)

    if not doc_a or not doc_b:
        missing = scan_name_a if not doc_a else scan_name_b
        raise ValueError(f"Scan '{missing}' not found in Firebase.")

    data_a = doc_a.get("data", {})
    data_b = doc_b.get("data", {})

    def _issues_from_scan(data: dict) -> set[str]:
        """Extract a flat set of issue strings from a scan."""
        issues: set[str] = set()
        pages_a = data.get("pages", {})
        for url, page in pages_a.items():
            for check_category in ["on_page", "metadata", "structured_data"]:
                for item in page.get(check_category, []):
                    if isinstance(item, dict) and item.get("status") in ("critical", "warn"):
                        issues.add(f"{url}|{item.get('name', '')}|{item.get('status', '')}")
        return issues

    issues_a = _issues_from_scan(data_a)
    issues_b = _issues_from_scan(data_b)

    fixed = sorted(issues_a - issues_b)
    new_issues = sorted(issues_b - issues_a)
    still_outstanding = sorted(issues_a & issues_b)

    # Page-level score comparison
    def _page_scores(data: dict) -> dict[str, int]:
        scores: dict[str, int] = {}
        for url, page in data.get("pages", {}).items():
            critical = sum(
                1 for cat in ["on_page", "metadata", "structured_data"]
                for item in page.get(cat, [])
                if isinstance(item, dict) and item.get("status") == "critical"
            )
            scores[url] = critical
        return scores

    scores_a = _page_scores(data_a)
    scores_b = _page_scores(data_b)

    improved_pages = [
        url for url in scores_b
        if url in scores_a and scores_b[url] < scores_a[url]
    ]
    regressed_pages = [
        url for url in scores_b
        if url in scores_a and scores_b[url] > scores_a[url]
    ]

    return ComparisonReport(
        scan_a_name=scan_name_a,
        scan_b_name=scan_name_b,
        scan_a_date=doc_a.get("created_at", ""),
        scan_b_date=doc_b.get("created_at", ""),
        fixed=fixed,
        new_issues=new_issues,
        still_outstanding=still_outstanding,
        improved_pages=improved_pages,
        regressed_pages=regressed_pages,
    )
