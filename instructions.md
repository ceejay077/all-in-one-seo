# SEO Audit Tool — Project Specification

## 1. Overview

Build a Python application that performs a full SEO audit of a website and
reports the results as a **richly formatted PowerShell terminal report**
(styled to match an `oh-my-posh` setup), with an **optional HTML export**.

**Core principle:** every operation (crawling, checking, AI analysis, saving,
comparing) runs and is controlled from the terminal. The **only** thing that
leaves the terminal is the *output* — i.e. the generated HTML report(s).
Nothing about running or configuring the tool should require anything other
than the terminal.

If any requirement below is ambiguous, ask the user for clarification before
starting implementation.

---

## 2. Terminal Experience (PowerShell)

- Colorized output, compatible with an `oh-my-posh` prompt/theme.
- Color code (used consistently in both terminal and HTML output):
  - 🔴 **Red** — Critical issue
  - 🟠 **Amber** — Warning
  - 🔵 **Blue** — OK / passed
- A **progress bar** for each check while it runs.
- On launch, the app must:
  1. Show a list of **previous scan sessions** (loaded from Firebase) with the
     option to view a past report, trigger a **re-crawl**, or **compare** it
     against another previous scan.
  2. If starting a new scan, prompt the user for:
     - Target website URL
     - 5 target keywords
  3. Prompt for **Firebase credentials** (for storing/reading scan data).
- Every scan is saved under a **unique scan name** for later comparison.

---

## 3. Site Crawling

- Crawl every page of the target website.
- Build the full site structure and represent it as a **tree graph** in the
  report (both terminal and HTML).
- Detect crawl depth per page.

---

## 4. SEO / Tracking Checklist

For each item below, run a check, show a progress bar, and report status
using the red/amber/blue color scheme. Even if an item is **not found at
all** on the site, it must still be explicitly listed in the report (not
omitted).

### Tracking & Analytics
- Bing Webmaster Tools installed
- Microsoft Clarity installed
- Google Analytics installed (specify if GA4)
- Google Search Console installed
- Facebook Pixel snippet
- Meta Ads snippet
- Google Ads snippet
- Any **other** tracking tools detected — list separately and identify what
  each one is for

### Structured Data & Markup
- Schema markup presence for Google, Bing, and Yandex
- Confirm schema is implemented as **JSON-LD**
- Open Graph tags present for every social platform

### On-Page / Technical SEO
- Canonical tags used correctly
- Noindex tag check
- Every page has exactly **one `<h1>`**, and it contains at least one term
  from the main keyword cluster (use the Anthropic API to judge whether the
  H1 matches/relates to the keyword cluster, not just an exact string match)
- `sitemap.xml` present and free of errors
- `robots.txt` present and free of errors
- Any sitemap/robots issues are highlighted in **red**

### Metadata & Accessibility
- Every indexable page has: meta title, meta description, image alt text
- Report every image filename with its alt text (terminal + HTML)
- Report meta title/description for every page (terminal + HTML)
- Missing alt texts are highlighted

---

## 5. AI-Powered Content Analysis (Anthropic API)

- Use an Anthropic API key stored in a local `.env` file.
- For the 5 user-provided keywords, use the API to:
  - Evaluate whether page content is SEO-friendly for those keywords
  - Evaluate whether the content covers a good keyword cluster
  - If it doesn't, generate alternative content suggestions that better
    incorporate the keyword cluster

---

## 6. HTML Report

The HTML report is the one exportable artifact. It must include:

- Full meta details (title, description) for every page
- Full image list with alt text, missing ones highlighted
- All checklist results, color-coded red/amber/blue
- **Editable fields** to rewrite meta titles/descriptions directly in the
  report
- Export button to **save the edited meta data as an Excel file**
- A separate **site-structure / sitemap view**, showing crawl depth as a
  tree/graph, where:
  - Each page URL is colored per its status (red/amber/blue)
  - Clicking a **red** link expands/shows the specific SEO issues for that
    page in the same view

---

## 7. Data Storage & Comparison (Firebase)

- Every scan is stored in Firebase under a unique scan name.
- New feature: **Compare** — select two scans (e.g. before/after an SEO
  update) and generate a comparison report showing:
  - What changed
  - What was fixed
  - What is still outstanding
- Re-crawling an existing site from the session list should automatically
  offer a before/after comparison report.

---

## 8. Configuration

- `.env` file for the Anthropic API key (and any other secrets).
- Firebase credentials requested at runtime (not hardcoded).

---

## 9. Open Questions to Resolve Before Building

1. Preferred Python libraries for the terminal UI (e.g. `rich` pairs very
   well with PowerShell + oh-my-posh) — confirm or leave to implementer's
   discretion?
2. Crawl scope/limits — max pages, respect `robots.txt` disallow rules?
3. Firebase product choice — Firestore vs Realtime Database?
4. Authentication approach for Firebase (service account JSON vs interactive
   login)?
5. Any page-count or rate-limit constraints for the Anthropic API calls
   during content analysis?
