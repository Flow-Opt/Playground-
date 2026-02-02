# FlowOpt Site Automation Potential Audit (MVP)

CLI tool that takes a URL and produces an **automation potential** score (0–100) plus a short, actionable report.

This is an **opinionated heuristic** audit intended for triage ("is this a good candidate for automation and what approach?").

## Install

```bash
python -m venv .venv
# Windows
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

```bash
python -m site_audit https://example.com
# or
site-audit https://example.com
```

Outputs:
- Human-readable summary
- `--json` to print JSON
- `--out report.json` to write JSON to a file

## What it checks (MVP)

- Reachability / status code / redirects
- `robots.txt` and whether it disallows broad scraping
- `sitemap.xml` presence
- Structured data (`application/ld+json`, microdata-ish hints)
- RSS/Atom feeds
- Presence of login/password forms
- Common anti-bot/CAPTCHA hints
- Tech hints (WordPress/Shopify/Wix/etc., basic SPA hints)
- API discovery hints (OpenAPI/Swagger endpoints, JSON endpoints)

## Notes

- This tool performs **lightweight HTTP requests** and HTML parsing only.
- It does **not** attempt to bypass access controls, rate limits, or anti-bot systems.
