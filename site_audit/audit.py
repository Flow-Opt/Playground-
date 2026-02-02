from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


@dataclass
class RobotsInfo:
    url: str
    present: bool
    any_disallow: bool
    disallow_lines: list[str]


@dataclass
class AuditReport:
    input_url: str
    final_url: str
    http_status: int | None
    redirect_count: int

    score: int
    recommendation: str

    robots: RobotsInfo
    sitemap_present: bool

    login_form_detected: bool
    captcha_hints_detected: bool

    structured_data_detected: bool
    feed_detected: bool
    api_hints_detected: bool

    platform_hints: list[str]

    reasons: list[str]
    warnings: list[str]


def _normalize_url(url: str) -> str:
    url = url.strip()
    if not url:
        raise ValueError("URL is empty")
    if not re.match(r"^https?://", url, flags=re.I):
        url = "https://" + url
    return url


def _fetch(session: requests.Session, url: str, timeout: float) -> requests.Response:
    # allow redirects for main page
    return session.get(url, timeout=timeout, allow_redirects=True)


def _robots(session: requests.Session, base_url: str, timeout: float) -> RobotsInfo:
    robots_url = urljoin(base_url, "/robots.txt")
    try:
        r = session.get(robots_url, timeout=timeout, allow_redirects=True)
    except Exception:
        return RobotsInfo(url=robots_url, present=False, any_disallow=False, disallow_lines=[])

    if r.status_code != 200 or not r.text:
        return RobotsInfo(url=robots_url, present=False, any_disallow=False, disallow_lines=[])

    disallow_lines: list[str] = []
    for line in r.text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("disallow:"):
            disallow_lines.append(line)

    any_disallow = len(disallow_lines) > 0
    return RobotsInfo(url=robots_url, present=True, any_disallow=any_disallow, disallow_lines=disallow_lines[:50])


def _sitemap_present(session: requests.Session, base_url: str, timeout: float) -> bool:
    # Fast heuristic: check /sitemap.xml and (if robots.txt exists) optionally parse it.
    sitemap_url = urljoin(base_url, "/sitemap.xml")
    try:
        r = session.get(sitemap_url, timeout=timeout, allow_redirects=True)
        if r.status_code == 200 and (r.text or "").strip():
            return True
    except Exception:
        pass
    return False


def _detect_login_form(soup: BeautifulSoup) -> bool:
    # If there's a password input anywhere, assume login/auth wall possibility.
    return soup.select_one("input[type='password']") is not None


def _detect_captcha_hints(html: str, soup: BeautifulSoup) -> bool:
    # Heuristic keywords + common providers.
    text = (html or "").lower()
    if any(k in text for k in ["captcha", "recaptcha", "hcaptcha", "cloudflare turnstile", "turnstile"]):
        return True
    if soup.select_one("iframe[src*='recaptcha']"):
        return True
    if soup.select_one("script[src*='recaptcha']"):
        return True
    if soup.select_one("script[src*='hcaptcha']"):
        return True
    if soup.select_one("iframe[src*='hcaptcha']"):
        return True
    if soup.select_one("script[src*='turnstile']"):
        return True
    return False


def _detect_structured_data(soup: BeautifulSoup) -> bool:
    # JSON-LD is the best quick signal.
    scripts = soup.select("script[type='application/ld+json']")
    if scripts:
        return True
    # Light microdata hint: itemscope / itemtype.
    return soup.select_one("[itemscope]") is not None


def _detect_feed(soup: BeautifulSoup) -> bool:
    # RSS/Atom via <link rel="alternate" type="application/rss+xml"> etc.
    for link in soup.select("link[rel~='alternate']"):
        t = (link.get("type") or "").lower()
        if t in ("application/rss+xml", "application/atom+xml"):
            return True
    return False


def _detect_api_hints(html: str, soup: BeautifulSoup, base_url: str) -> bool:
    text = (html or "").lower()
    # common API doc endpoints/hints
    api_keywords = [
        "openapi",
        "swagger",
        "api/docs",
        "api-docs",
        "/graphql",
        "rest api",
    ]
    if any(k in text for k in api_keywords):
        return True

    # explicit links to swagger/openapi
    for a in soup.select("a[href]"):
        href = a.get("href") or ""
        abs_url = urljoin(base_url, href)
        p = urlparse(abs_url)
        path = (p.path or "").lower()
        if any(x in path for x in ["swagger", "openapi", "api-docs", "graphql"]):
            return True

    # JSON endpoints mentioned in scripts
    if re.search(r"https?://[^\s'\"]+\.json", html or "", flags=re.I):
        return True

    return False


def _platform_hints(headers: dict[str, str], html: str, soup: BeautifulSoup) -> list[str]:
    hints: list[str] = []

    h = {k.lower(): v for k, v in (headers or {}).items()}
    server = (h.get("server") or "").lower()
    powered = (h.get("x-powered-by") or "").lower()

    generator = (soup.select_one("meta[name='generator']") or {}).get("content", "")
    generator_l = (generator or "").lower()

    if "wordpress" in generator_l or "wp-content" in (html or "").lower():
        hints.append("WordPress")
    if "shopify" in (html or "").lower() or "x-shopify" in powered or "shopify" in server:
        hints.append("Shopify")
    if "wix" in (html or "").lower():
        hints.append("Wix")
    if "squarespace" in (html or "").lower():
        hints.append("Squarespace")

    # SPA-ish hint: lots of script + minimal body text
    scripts = len(soup.select("script"))
    text_len = len(soup.get_text(" ", strip=True))
    if scripts >= 25 and text_len < 600:
        hints.append("Likely SPA/heavy JS")

    if "cloudflare" in server or "cloudflare" in (html or "").lower():
        hints.append("Cloudflare")

    return sorted(set(hints))


def _clamp(n: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, n))


def audit_url(url: str, timeout: float = 12.0, user_agent: str | None = None) -> AuditReport:
    input_url = _normalize_url(url)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": user_agent or "FlowOptSiteAudit/0.1 (+https://www.flowopt.nl)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )

    warnings: list[str] = []
    reasons: list[str] = []

    http_status: int | None = None
    final_url = input_url
    redirect_count = 0

    try:
        resp = _fetch(session, input_url, timeout=timeout)
        http_status = resp.status_code
        final_url = resp.url
        redirect_count = len(resp.history)
    except requests.RequestException as e:
        # Unreachable => very low automation potential.
        robots = RobotsInfo(url=urljoin(input_url, "/robots.txt"), present=False, any_disallow=False, disallow_lines=[])
        return AuditReport(
            input_url=input_url,
            final_url=input_url,
            http_status=None,
            redirect_count=0,
            score=0,
            recommendation="Manual review (site unreachable from audit tool)",
            robots=robots,
            sitemap_present=False,
            login_form_detected=False,
            captcha_hints_detected=False,
            structured_data_detected=False,
            feed_detected=False,
            api_hints_detected=False,
            platform_hints=[],
            reasons=[f"Request failed: {type(e).__name__}"],
            warnings=["Site could not be reached from this environment."],
        )

    html = resp.text or ""
    soup = BeautifulSoup(html, "html.parser")

    robots = _robots(session, final_url, timeout=timeout)
    sitemap_present = _sitemap_present(session, final_url, timeout=timeout)

    login_form = _detect_login_form(soup)
    captcha_hints = _detect_captcha_hints(html, soup)

    structured = _detect_structured_data(soup)
    feed = _detect_feed(soup)
    api_hints = _detect_api_hints(html, soup, final_url)
    platform = _platform_hints(dict(resp.headers), html, soup)

    # --- scoring heuristic ---
    score = 60  # neutral starting point

    if http_status and 200 <= http_status < 300:
        score += 10
        reasons.append("Homepage reachable (2xx)")
    elif http_status and 300 <= http_status < 400:
        score += 5
        reasons.append("Homepage reachable with redirect")
    else:
        score -= 15
        reasons.append(f"Homepage status {http_status}")

    if redirect_count >= 3:
        score -= 3
        warnings.append("Many redirects; may complicate automation.")

    if robots.present:
        reasons.append("robots.txt present")
        if robots.any_disallow:
            score -= 6
            warnings.append("robots.txt contains Disallow rules; review legality/ToS before scraping.")
    else:
        reasons.append("robots.txt missing")

    if sitemap_present:
        score += 6
        reasons.append("sitemap.xml present (good for discovery)")

    if structured:
        score += 8
        reasons.append("Structured data detected (JSON-LD/microdata)")

    if feed:
        score += 4
        reasons.append("RSS/Atom feed detected")

    if api_hints:
        score += 10
        reasons.append("API/OpenAPI/Swagger hints detected")

    if login_form:
        score -= 12
        warnings.append("Login/password form detected; automation may require authenticated flows.")

    if captcha_hints:
        score -= 20
        warnings.append("CAPTCHA/anti-bot hints detected; browser automation may be blocked.")

    if "Likely SPA/heavy JS" in platform:
        score -= 6
        reasons.append("Likely SPA/heavy JS (browser automation more likely than scraping)")

    if "Cloudflare" in platform and captcha_hints:
        score -= 6

    # clamp
    score = _clamp(score, 0, 100)

    # recommendation
    if captcha_hints:
        recommendation = "Prefer official API / partnership; if browser automation needed, expect anti-bot friction"
    elif api_hints:
        recommendation = "Prefer API integration (or reverse-proxy internal automation); fallback to scraping if allowed"
    elif "Likely SPA/heavy JS" in platform:
        recommendation = "Browser automation (Playwright) likely; scraping may be brittle"
    else:
        recommendation = "Scraping + light automation likely feasible (validate robots/ToS)"

    return AuditReport(
        input_url=input_url,
        final_url=final_url,
        http_status=http_status,
        redirect_count=redirect_count,
        score=score,
        recommendation=recommendation,
        robots=robots,
        sitemap_present=sitemap_present,
        login_form_detected=login_form,
        captcha_hints_detected=captcha_hints,
        structured_data_detected=structured,
        feed_detected=feed,
        api_hints_detected=api_hints,
        platform_hints=platform,
        reasons=reasons,
        warnings=warnings,
    )
