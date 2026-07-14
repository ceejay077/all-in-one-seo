"""
checks/ai_analysis.py — Anthropic Claude API calls for:
  1. H1 vs keyword cluster matching (per page)
  2. Content SEO-friendliness + keyword cluster coverage (per page)
  3. Alternative content suggestions when content is weak
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

import anthropic
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

_client: Optional[anthropic.Anthropic] = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY not found. Add it to your .env file."
            )
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def _extract_text(html: str) -> str:
    """Extract visible text from page HTML."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()
    return soup.get_text(separator=" ", strip=True)[:6000]  # Cap to avoid huge prompts


# ── H1 keyword match ─────────────────────────────────────────────────────────

@dataclass
class H1KeywordResult:
    h1_text: str
    keywords: list[str]
    is_relevant: bool
    explanation: str
    status: str  # "ok" | "warn" | "critical"


def check_h1_keyword_match(h1_text: str, keywords: list[str]) -> H1KeywordResult:
    if not h1_text.strip():
        return H1KeywordResult(
            h1_text="",
            keywords=keywords,
            is_relevant=False,
            explanation="Page has no H1 text to evaluate.",
            status="critical",
        )

    client = _get_client()
    prompt = (
        f"You are an SEO expert. Evaluate whether the following H1 heading is relevant "
        f"to the keyword cluster.\n\n"
        f"H1: {h1_text}\n\n"
        f"Keywords: {', '.join(keywords)}\n\n"
        f"Reply with a JSON object with keys:\n"
        f'  "relevant": true or false\n'
        f'  "explanation": one sentence explanation\n'
        f"Do not include any other text."
    )

    try:
        message = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        import json
        text = message.content[0].text.strip()
        # Strip markdown code fences if present
        text = text.strip("`").strip()
        if text.startswith("json"):
            text = text[4:].strip()
        data = json.loads(text)
        relevant = bool(data.get("relevant", False))
        explanation = data.get("explanation", "")
        return H1KeywordResult(
            h1_text=h1_text,
            keywords=keywords,
            is_relevant=relevant,
            explanation=explanation,
            status="ok" if relevant else "warn",
        )
    except Exception as e:
        return H1KeywordResult(
            h1_text=h1_text,
            keywords=keywords,
            is_relevant=False,
            explanation=f"AI check failed: {e}",
            status="warn",
        )


# ── Content SEO analysis ──────────────────────────────────────────────────────

@dataclass
class ContentAnalysisResult:
    url: str
    keywords: list[str]
    is_seo_friendly: bool
    keyword_cluster_score: str  # "good" | "partial" | "poor"
    summary: str
    suggestions: list[str] = field(default_factory=list)
    status: str = "ok"
    h1_keyword_result: Optional[H1KeywordResult] = None


def analyze_content(url: str, html: str, keywords: list[str]) -> ContentAnalysisResult:
    client = _get_client()
    text = _extract_text(html)

    prompt = (
        f"You are an expert SEO content analyst.\n\n"
        f"Page URL: {url}\n"
        f"Target keywords: {', '.join(keywords)}\n\n"
        f"Page content (truncated):\n{text}\n\n"
        f"Evaluate the content and reply ONLY with a JSON object with these keys:\n"
        f'  "seo_friendly": true or false\n'
        f'  "keyword_cluster_score": "good", "partial", or "poor"\n'
        f'  "summary": 2-3 sentence analysis\n'
        f'  "suggestions": array of up to 3 specific actionable content improvement suggestions '
        f'(empty array if content is good)\n'
        f"Do not include any other text."
    )

    try:
        message = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        import json
        text_resp = message.content[0].text.strip()
        text_resp = text_resp.strip("`").strip()
        if text_resp.startswith("json"):
            text_resp = text_resp[4:].strip()
        data = json.loads(text_resp)

        seo_friendly = bool(data.get("seo_friendly", False))
        cluster_score = data.get("keyword_cluster_score", "poor")
        summary = data.get("summary", "")
        suggestions = data.get("suggestions", [])

        if seo_friendly and cluster_score == "good":
            status = "ok"
        elif seo_friendly or cluster_score == "partial":
            status = "warn"
        else:
            status = "critical"

        return ContentAnalysisResult(
            url=url,
            keywords=keywords,
            is_seo_friendly=seo_friendly,
            keyword_cluster_score=cluster_score,
            summary=summary,
            suggestions=suggestions,
            status=status,
        )
    except Exception as e:
        return ContentAnalysisResult(
            url=url,
            keywords=keywords,
            is_seo_friendly=False,
            keyword_cluster_score="poor",
            summary=f"AI analysis failed: {e}",
            suggestions=[],
            status="warn",
        )
