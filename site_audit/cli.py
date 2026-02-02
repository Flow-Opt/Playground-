from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from rich.console import Console
from rich.table import Table

from .audit import audit_url


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="site-audit",
        description="Audit a website's automation potential (heuristic triage).",
    )
    p.add_argument("url", help="Website URL, e.g. https://example.com")
    p.add_argument("--json", action="store_true", help="Print JSON to stdout")
    p.add_argument("--out", help="Write JSON report to a file")
    p.add_argument(
        "--timeout",
        type=float,
        default=12.0,
        help="Per-request timeout in seconds (default: 12)",
    )
    p.add_argument(
        "--user-agent",
        default="FlowOptSiteAudit/0.1 (+https://www.flowopt.nl)",
        help="User-Agent header",
    )
    return p.parse_args(argv)


def _print_human(report) -> None:
    c = Console()

    c.print(f"[bold]Automation Potential Audit[/bold] — {report.input_url}")
    c.print(f"Final URL: {report.final_url}")
    c.print(f"HTTP: {report.http_status}  |  Redirects: {report.redirect_count}")
    c.print("")

    score = report.score
    if score >= 75:
        label = "HIGH"
        color = "green"
    elif score >= 50:
        label = "MEDIUM"
        color = "yellow"
    else:
        label = "LOW"
        color = "red"

    c.print(f"[bold]Score:[/bold] [{color}]{score}[/] / 100  ([{color}]{label}[/])")
    c.print(f"[bold]Suggested approach:[/bold] {report.recommendation}")
    c.print("")

    t = Table(title="Signals")
    t.add_column("Signal")
    t.add_column("Value")

    t.add_row("robots.txt", "present" if report.robots.present else "missing")
    if report.robots.present:
        t.add_row("robots disallow", "yes" if report.robots.any_disallow else "no")
    t.add_row("sitemap", "present" if report.sitemap_present else "missing")
    t.add_row("login form", "yes" if report.login_form_detected else "no")
    t.add_row("captcha hints", "yes" if report.captcha_hints_detected else "no")
    t.add_row("structured data", "yes" if report.structured_data_detected else "no")
    t.add_row("RSS/Atom", "yes" if report.feed_detected else "no")
    t.add_row("API hints", "yes" if report.api_hints_detected else "no")
    t.add_row("platform hints", ", ".join(report.platform_hints) if report.platform_hints else "-")

    c.print(t)
    c.print("")

    if report.reasons:
        c.print("[bold]Reasons[/bold]")
        for r in report.reasons:
            c.print(f"- {r}")

    if report.warnings:
        c.print("")
        c.print("[bold]Warnings[/bold]")
        for w in report.warnings:
            c.print(f"- {w}")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    report = audit_url(args.url, timeout=args.timeout, user_agent=args.user_agent)

    payload = asdict(report)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        _print_human(report)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
