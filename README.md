# 🔍 SEO Audit Tool

A full-featured Python SEO auditing tool that crawls a website, runs a comprehensive checklist of SEO and tracking checks, performs AI-powered content analysis via **Anthropic Claude**, stores results in **Firebase Firestore**, and exports a rich **HTML report** — all driven from the PowerShell terminal.

---

## Features

- 🕷️ **Full site crawler** — BFS crawl, respects `robots.txt`, configurable page limit
- 📡 **Tracking detection** — Google Analytics (GA4/UA), Bing Webmaster Tools, Microsoft Clarity, Facebook Pixel, Meta Ads, Google Ads, + any other trackers
- 🏷️ **Structured data** — JSON-LD schema, Open Graph, Twitter/X Card checks
- 📄 **On-page SEO** — Canonical tags, noindex, H1 check, `sitemap.xml`, `robots.txt`
- 📝 **Metadata audit** — Meta title/description length, image alt text for every image
- 🤖 **AI analysis** — Anthropic Claude evaluates H1 vs keyword cluster relevance and content SEO-friendliness, with improvement suggestions
- 🔥 **Firebase storage** — Every scan stored; compare before/after SEO changes
- 📊 **Beautiful terminal output** — Rich color-coded tables, trees, progress bars (oh-my-posh compatible)
- 🌐 **HTML report** — Dark-themed, fully self-contained, editable meta fields, Excel export, clickable site tree

---

## Installation

### 1. Prerequisites

- Python 3.9+
- PowerShell (Windows) or any terminal

### 2. Clone & Install

```powershell
cd c:\Users\BLVS\SEO\python_SEO_Tools\all_in_one_SEO
pip install -r requirements.txt
```

### 3. Set Up `.env`

```powershell
Copy-Item .env.example .env
# Edit .env and add your Anthropic API key
notepad .env
```

`.env` contents:
```
ANTHROPIC_API_KEY=sk-ant-...your-key...
```

### 4. Firebase Setup

1. Go to [Firebase Console](https://console.firebase.google.com/) → your project
2. Project Settings → Service Accounts → Generate new private key
3. Download the JSON file (e.g. `firebase-service-account.json`)
4. When the tool starts, enter the path to this file

---

## Usage

```powershell
python main.py
```

On launch the tool will:
1. Ask for your Firebase service-account JSON path
2. Show a list of previous scan sessions
3. Present options: **New scan**, **View report**, **Re-crawl**, **Compare two scans**

### New Scan

When starting a new scan you'll be prompted for:
- Target website URL
- Max pages to crawl (default: 200)
- 5 target keywords
- A unique scan name

### Comparison

Select any two previously saved scans (before/after) to generate a diff report showing:
- ✅ Issues that were **fixed**
- 🔴 **New issues** introduced
- 🟠 Issues that are **still outstanding**

---

## Output

### Terminal

Rich, color-coded output:
- 🔴 **Red** = Critical issue
- 🟠 **Amber** = Warning
- 🔵 **Blue** = OK / Passed

### HTML Report

Saved to `reports_output/seo_report_<name>_<timestamp>.html`

Features:
- Summary scoreboard
- All check results (tracking, structured data, on-page, metadata)
- AI analysis per page
- **Editable meta title/description fields** — edit directly in browser
- **Export to Excel** button — saves all (edited) meta data as `.xlsx`
- **Interactive site tree** — URLs colored by status; click red links to expand issues

---

## Project Structure

```
all_in_one_SEO/
├── main.py                    # Entry point & CLI menus
├── crawler.py                 # BFS site crawler
├── checks/
│   ├── tracking.py            # Analytics/pixel detection
│   ├── structured_data.py     # Schema, OG, Twitter Card
│   ├── on_page.py             # Canonical, noindex, H1, sitemap, robots
│   ├── metadata.py            # Meta title/desc, alt text
│   └── ai_analysis.py         # Anthropic Claude API
├── storage/
│   └── firebase_store.py      # Firestore read/write/compare
├── reports/
│   ├── terminal_report.py     # Rich terminal output
│   └── html_report.py         # HTML generator
├── templates/
│   └── report.html            # Jinja2 template
├── reports_output/            # Generated HTML reports (auto-created)
├── requirements.txt
├── .env.example
└── README.md
```

---

## Configuration

| Setting | Where | Default |
|---|---|---|
| Anthropic API key | `.env` | — |
| Firebase credentials | Runtime prompt | — |
| Max crawl pages | Runtime prompt | 200 |
| Respect robots.txt | Hardcoded (main.py) | Yes |
| Crawl delay | `main.py` → `_run_audit()` | 0.3s |

---

## Color Codes

| Color | Meaning |
|---|---|
| 🔵 Blue | OK / Passed |
| 🟠 Amber | Warning |
| 🔴 Red | Critical issue |
