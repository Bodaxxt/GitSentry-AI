"""
gitsentry_analyzer.py — GitSentry AI Security Gate Analyzer (v1.0.0)
====================================================================
Production-grade CI/CD DevSecOps security scanner powered by Groq & LangChain.
Performs semantic SAST analysis, renders rich interactive CLI output with spinners,
color-coded vulnerability tables, and enforces configurable gate pass/fail policies.
"""

import os
import sys
import argparse
from pathlib import Path
from typing import List, Tuple

# Ensure UTF-8 output on Windows terminals
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.rule import Rule
from rich.syntax import Syntax
from rich.padding import Padding
from rich import box

from core_engine import review_code
from schemas import ReviewReport, CodeIssue

load_dotenv()
console = Console(force_terminal=True, legacy_windows=False)

# Strict Severity Map (Color, Emoji, Rank)
SEVERITY_CONFIG = {
    "Critical": {"color": "bold red",    "emoji": "🔴", "rank": 4, "badge": "CRITICAL"},
    "High":     {"color": "orange1",     "emoji": "🟠", "rank": 3, "badge": "HIGH"},
    "Medium":   {"color": "yellow",      "emoji": "🟡", "rank": 2, "badge": "MEDIUM"},
    "Low":      {"color": "bright_cyan", "emoji": "🔵", "rank": 1, "badge": "LOW"},
}


def print_banner() -> None:
    """Renders the GitSentry AI branded terminal banner."""
    console.print()
    console.print(Panel(
        "[bold bright_white]🛡️  GitSentry AI — DevSecOps Security Gate v1.0.0[/bold bright_white]\n"
        "[dim]Automated Semantic Code Security & SAST Engine · Powered by Groq & LangChain[/dim]",
        border_style="bright_blue",
        padding=(1, 4),
    ))
    console.print()


def render_vulnerability_table(report: ReviewReport, file_name: str) -> None:
    """
    Renders a color-coded Rich table summarizing all detected vulnerabilities.
    """
    table = Table(
        title=f"[bold]Detected Vulnerabilities in [cyan]{file_name}[/cyan][/bold]",
        title_style="bold bright_white",
        box=box.ROUNDED,
        header_style="bold bright_white on grey19",
        border_style="bright_blue",
        show_lines=True,
    )

    table.add_column("#", justify="center", style="bold", width=4)
    table.add_column("Severity", justify="center", width=14)
    table.add_column("Issue Summary", justify="left")
    table.add_column("Impact / Remediation", justify="left")

    for idx, issue in enumerate(report.issues, start=1):
        cfg = SEVERITY_CONFIG.get(issue.severity, {"color": "white", "emoji": "⚪"})
        sev_text = Text(f"{cfg['emoji']} {issue.severity}", style=cfg["color"])

        # Truncate explanation for compact table view
        short_exp = issue.explanation.split(". ")[0] + "." if "." in issue.explanation else issue.explanation
        if len(short_exp) > 110:
            short_exp = short_exp[:107] + "..."

        table.add_row(
            str(idx),
            sev_text,
            f"[bold]{issue.issue}[/bold]",
            short_exp,
        )

    console.print(table)
    console.print()


def render_issue_cards(issues: List[CodeIssue], show_fixes: bool = True) -> None:
    """
    Renders detailed breakdown cards with syntax-highlighted fix snippets.
    """
    for idx, issue in enumerate(issues, start=1):
        cfg = SEVERITY_CONFIG.get(issue.severity, {"color": "white", "emoji": "⚪"})

        header = Text()
        header.append(f"  #{idx}  ", style="bold bright_white")
        header.append(f"{cfg['emoji']} [{issue.severity.upper()}] ", style=f"bold {cfg['color']}")
        header.append(issue.issue, style=f"bold {cfg['color']}")

        body = (
            f"[bold bright_white]📁 Target File:[/bold bright_white] [cyan]{issue.file}[/cyan]\n\n"
            f"[bold bright_white]🔎 Technical Analysis:[/bold bright_white]\n{issue.explanation}"
        )

        console.print(Panel(
            body,
            title=header,
            title_align="left",
            border_style=cfg["color"],
            padding=(1, 2),
        ))

        if show_fixes and issue.suggested_fix:
            console.print("[bold bright_white]   ✅ Suggested Remediation Code:[/bold bright_white]")
            syntax = Syntax(
                issue.suggested_fix,
                "python",
                theme="monokai",
                line_numbers=True,
                word_wrap=True,
            )
            console.print(Padding(syntax, (0, 3, 1, 3)))


def scan_file(file_path: str, fail_on: str = "High", summary_only: bool = False) -> Tuple[int, int, ReviewReport]:
    """
    Executes security analysis on a single file with a Rich progress spinner.

    Returns:
        Tuple of (blocking_count, total_count, report)
    """
    path = Path(file_path)
    if not path.is_file():
        console.print(f"[bold red]❌ Error: File not found: {file_path}[/bold red]")
        return 1, 0, ReviewReport(summary="File not found", issues=[])

    code_content = path.read_text(encoding="utf-8")
    provider = os.getenv("LLM_PROVIDER", "groq")
    model = os.getenv("GROQ_MODEL" if provider == "groq" else "OPENAI_MODEL", "auto")

    # Spinner animation during LLM API call
    with console.status(
        f"[bold cyan]🔍 Scanning [bold white]{path.name}[/bold white] via {provider.upper()} ({model})...[/bold cyan]",
        spinner="dots",
    ):
        try:
            report: ReviewReport = review_code(path.name, code_content)
        except Exception as e:
            console.print(f"[bold red]❌ Analyzer Error during review of {path.name}: {e}[/bold red]")
            return 1, 0, ReviewReport(summary=f"Analysis failed: {e}", issues=[])

    # Display Executive Summary
    console.print(Panel(
        f"[bold bright_white]📄 Target File:[/bold bright_white] [cyan]{path.name}[/cyan]\n\n"
        f"[bold bright_white]📋 Executive Summary:[/bold bright_white]\n{report.summary}",
        title="[bold bright_blue]AI Code Review Summary[/bold bright_blue]",
        border_style="bright_blue",
        padding=(1, 3),
    ))
    console.print()

    if not report.issues:
        console.print(Panel(
            "[bold green]✨ Clean Code: Zero vulnerabilities or security risks detected![/bold green]",
            border_style="green",
            padding=(1, 2),
        ))
        return 0, 0, report

    # Render summary table
    render_vulnerability_table(report, path.name)

    # Render detail cards if not summary-only
    if not summary_only:
        render_issue_cards(report.issues)

    # Threshold evaluation
    threshold_rank = SEVERITY_CONFIG.get(fail_on, {}).get("rank", 3)
    blocking_issues = [
        iss for iss in report.issues
        if SEVERITY_CONFIG.get(iss.severity, {}).get("rank", 0) >= threshold_rank
    ]

    return len(blocking_issues), len(report.issues), report


def main():
    parser = argparse.ArgumentParser(
        description="GitSentry AI — Automated DevSecOps Security Gate Scanner"
    )
    parser.add_argument(
        "files",
        nargs="*",
        default=["user_service.py"],
        help="One or more Python files to review (default: user_service.py)",
    )
    parser.add_argument(
        "--fail-on",
        choices=["Critical", "High", "Medium", "Low"],
        default="High",
        help="Minimum severity level that fails the CI pipeline (default: High)",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Render compact vulnerability tables without full suggested code cards",
    )
    args = parser.parse_args()

    print_banner()

    total_blocking = 0
    total_found = 0
    scanned_results = []

    for file_path in args.files:
        blocking, total, report = scan_file(
            file_path,
            fail_on=args.fail_on,
            summary_only=args.summary_only,
        )
        total_blocking += blocking
        total_found += total
        scanned_results.append((file_path, blocking, total))

    # Aggregate CI/CD Gate Decision
    console.print(Rule(style="bright_blue"))
    console.print()

    if total_blocking > 0:
        gate_text = (
            f"[bold red]🚨 SECURITY GATE FAILED: {total_blocking} blocking issue(s) "
            f"met or exceeded severity threshold '{args.fail_on}'.[/bold red]\n\n"
            f"[bright_white]Total Vulnerabilities Found :[/bright_white] [bold red]{total_found}[/bold red]\n"
            f"[bright_white]Blocking Issues (>= {args.fail_on}) :[/bright_white] [bold red]{total_blocking}[/bold red]\n\n"
            f"[yellow]Action Required: Remediate the flagged vulnerabilities before merging this pull request.[/yellow]"
        )
        console.print(Panel(
            gate_text,
            title="[bold red]❌ CI Gate: BLOCKED[/bold red]",
            border_style="red",
            padding=(1, 3),
        ))
        console.print()
        sys.exit(1)

    pass_text = (
        f"[bold green]✅ SECURITY GATE PASSED: Zero blocking issues detected (threshold: {args.fail_on}).[/bold green]\n\n"
        f"[bright_white]Files Analyzed           :[/bright_white] [cyan]{len(args.files)}[/cyan]\n"
        f"[bright_white]Non-blocking Minor Issues:[/bright_white] [yellow]{total_found}[/yellow]\n"
        f"[bright_white]Pull Request Status      :[/bright_white] [bold green]APPROVED FOR MERGE 🚀[/bold green]"
    )
    console.print(Panel(
        pass_text,
        title="[bold green]🛡️ CI Gate: APPROVED[/bold green]",
        border_style="green",
        padding=(1, 3),
    ))
    console.print()
    sys.exit(0)


if __name__ == "__main__":
    main()
