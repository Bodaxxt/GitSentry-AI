"""
core_engine.py — GitSentry AI · Sprint 1
==========================================
AI-powered Code Review Assistant using LangChain + Pydantic structured output.

Author  : GitSentry AI Team
Version : 1.0.0 (Sprint 1)
"""

import os
import sys
import json
import re

# Ensure UTF-8 output on Windows terminals
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dotenv import load_dotenv

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.exceptions import OutputParserException

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.rule import Rule
from rich import box
from rich.syntax import Syntax
from rich.padding import Padding

from schemas import CodeIssue, ReviewReport

# ─────────────────────────────────────────────
# Initialisation
# ─────────────────────────────────────────────

load_dotenv()
console = Console(force_terminal=True, legacy_windows=False)

# Severity → (rich color, emoji)
SEVERITY_STYLE: dict[str, tuple[str, str]] = {
    "Low":      ("bright_cyan",   "🔵"),
    "Medium":   ("yellow",        "🟡"),
    "High":     ("orange1",       "🟠"),
    "Critical": ("bold red",      "🔴"),
}

# ─────────────────────────────────────────────
# LLM Factory
# ─────────────────────────────────────────────

def _build_llm():
    """
    Instantiate the LLM based on the LLM_PROVIDER env variable.
    Supports 'openai' and 'groq'. Defaults to 'groq'.
    """
    provider = os.getenv("LLM_PROVIDER", "groq").lower().strip()

    if provider == "openai":
        from langchain_openai import ChatOpenAI  # type: ignore
        api_key = os.getenv("OPENAI_API_KEY")
        model   = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        if not api_key:
            raise EnvironmentError("OPENAI_API_KEY is not set in your .env file.")
        console.log(f"[dim]🤖 LLM Provider: OpenAI ({model})[/dim]")
        return ChatOpenAI(model=model, api_key=api_key, temperature=0, max_tokens=4096)

    elif provider == "groq":
        from langchain_groq import ChatGroq  # type: ignore
        api_key = os.getenv("GROQ_API_KEY")
        model   = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        if not api_key:
            raise EnvironmentError("GROQ_API_KEY is not set in your .env file.")
        console.log(f"[dim]🤖 LLM Provider: Groq ({model})[/dim]")
        return ChatGroq(model=model, api_key=api_key, temperature=0, max_tokens=4096)

    else:
        raise ValueError(
            f"Unsupported LLM_PROVIDER '{provider}'. Choose 'openai' or 'groq'."
        )


# ─────────────────────────────────────────────
# System Prompt
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are GitSentry AI, an elite Senior Code Reviewer and Security Engineer with 15+ years of experience.
Your job is to perform a rigorous, production-grade code review on the provided source code.

## Your Mission
Analyze the code for ALL of the following categories:
1. **Security Vulnerabilities** — SQL Injection, XSS, SSRF, Insecure Deserialization, Hardcoded Secrets,
   Broken Access Control, Cryptographic Failures (OWASP Top 10).
2. **Critical Bugs** — Logic errors, off-by-one errors, unhandled exceptions, race conditions, null dereferences.
3. **Performance Issues** — N+1 queries, inefficient loops, memory leaks, blocking I/O in async contexts.
4. **Code Quality** — Bad practices, deprecated APIs, missing input validation, poor error handling.

## Rules
- Be thorough, objective, and precise.
- Focus on the most critical, genuine issues (at most **top 3 findings** — quality over quantity).
- Order issues from most critical (Critical) to least (Low).
- Base severity strictly on real-world exploitability and impact.
- Reference standards where applicable: OWASP, CWE, PEP 8, etc.
- For every issue, provide a `suggested_fix` with the corrected code snippet only — **maximum 10 lines**, no prose.
- Keep `explanation` concise — 2-3 sentences maximum.
- If the code is secure, return an empty issues list with an approving summary.
- CRITICAL: Your JSON output MUST be completely valid and fully closed — every brace and bracket must be closed.

## Output Format
{format_instructions}
"""

USER_PROMPT = """\
Please review the following code from file `{file_name}`:

```python
{code_content}
```
"""

# ─────────────────────────────────────────────
# JSON Recovery Helpers
# ─────────────────────────────────────────────

def _repair_truncated_json(raw: str) -> ReviewReport | None:
    """
    Attempt to salvage a ReviewReport from a truncated / malformed LLM response.

    Strategy:
    1. Extract the JSON blob from the raw string (strip markdown fences).
    2. Try to parse it as-is.
    3. If that fails, extract every complete CodeIssue object using a regex
       and rebuild a minimal valid ReviewReport from those.

    Returns a ReviewReport on success, None if recovery is impossible.
    """
    # Strip markdown code fences if present
    text = re.sub(r"```(?:json)?\s*", "", raw, flags=re.IGNORECASE).strip()

    # --- Attempt 1: direct parse ---
    try:
        data = json.loads(text)
        return ReviewReport(**data)
    except Exception:
        pass

    # --- Attempt 2: find the outermost JSON object and close it ---
    # Locate where the JSON object starts
    start = text.find("{")
    if start == -1:
        return None

    blob = text[start:]

    # Try progressively trimming trailing garbage and re-closing the JSON
    for trim in range(len(blob), max(len(blob) - 200, 0), -1):
        candidate = blob[:trim]
        # Count unclosed braces / brackets and close them
        opens_brace   = candidate.count("{") - candidate.count("}")
        opens_bracket = candidate.count("[") - candidate.count("]")
        if opens_brace < 0 or opens_bracket < 0:
            continue
        closed = candidate + "]" * opens_bracket + "}" * opens_brace
        try:
            data = json.loads(closed)
            if isinstance(data, dict):
                # Sanitise: keep only fully-formed issues
                issues_raw = data.get("issues", [])
                valid_issues = []
                required = {"file", "issue", "severity", "explanation", "suggested_fix"}
                for item in issues_raw:
                    if isinstance(item, dict) and required.issubset(item.keys()):
                        try:
                            valid_issues.append(CodeIssue(**item))
                        except Exception:
                            pass  # skip malformed issue
                summary = data.get("summary", "Partial review — output was truncated by the LLM.")
                console.print(
                    f"[bold yellow]⚠️  Recovered {len(valid_issues)} issue(s) from truncated LLM output.[/bold yellow]"
                )
                return ReviewReport(summary=summary, issues=valid_issues)
        except Exception:
            continue

    return None


# ─────────────────────────────────────────────
# Core Review Function
# ─────────────────────────────────────────────

MAX_RETRIES = 3

def review_code(file_name: str, code_content: str) -> ReviewReport:
    """
    Performs an AI-powered code review on the given source code.

    Retries up to MAX_RETRIES times on parse failures and falls back to
    partial-JSON recovery before giving up.

    Args:
        file_name    : The name of the file being reviewed (e.g., "app.py").
        code_content : The raw source code string to analyze.

    Returns:
        A fully structured ReviewReport Pydantic model.

    Raises:
        RuntimeError : If all retries and recovery attempts fail.
    """
    llm    = _build_llm()
    parser = PydanticOutputParser(pydantic_object=ReviewReport)

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human",  USER_PROMPT),
    ]).partial(format_instructions=parser.get_format_instructions())

    # Raw LLM chain — we grab the string output for recovery fallback
    raw_chain    = prompt | llm
    parsed_chain = raw_chain | parser

    console.log(f"[dim]🔍 Reviewing [bold]{file_name}[/bold] ...[/dim]")

    last_raw: str = ""
    for attempt in range(1, MAX_RETRIES + 1):
        if attempt > 1:
            console.log(f"[dim yellow]↩️  Retry {attempt}/{MAX_RETRIES} ...[/dim yellow]")
        try:
            report: ReviewReport = parsed_chain.invoke({
                "file_name":    file_name,
                "code_content": code_content,
            })
            return report  # ✅ clean parse
        except OutputParserException as exc:
            # Extract the raw LLM text from the exception for recovery
            raw_msg = str(exc)
            # LangChain embeds the raw output in the exception message
            raw_start = raw_msg.find("```")
            if raw_start != -1:
                last_raw = raw_msg[raw_start:]
            else:
                # Try to get it from exc.llm_output if available
                last_raw = getattr(exc, "llm_output", raw_msg)
            console.log(
                f"[dim red]Parse error on attempt {attempt}: "
                f"{str(exc)[:120]}…[/dim red]"
            )
        except Exception as exc:
            console.log(f"[dim red]Unexpected error on attempt {attempt}: {exc}[/dim red]")
            last_raw = ""

    # ── All retries exhausted — try partial recovery ──────────────────────────
    if last_raw:
        console.log("[dim yellow]🔧 Attempting partial JSON recovery...[/dim yellow]")
        recovered = _repair_truncated_json(last_raw)
        if recovered is not None:
            return recovered

    raise RuntimeError(
        f"GitSentry AI failed to produce a valid review for '{file_name}' "
        f"after {MAX_RETRIES} attempts. Check your API key and model availability."
    )


# ─────────────────────────────────────────────
# Rich Display Helpers
# ─────────────────────────────────────────────

def _severity_badge(severity: str) -> Text:
    color, emoji = SEVERITY_STYLE.get(severity, ("white", "⚪"))
    badge = Text()
    badge.append(f" {emoji} {severity.upper()} ", style=f"bold {color} on grey19")
    return badge


def display_report(report: ReviewReport, file_name: str) -> None:
    """Renders a ReviewReport to the console using Rich formatting."""

    console.print()
    console.print(Rule(
        f"[bold bright_white] 🛡️  GitSentry AI — Code Review Report [/bold bright_white]",
        style="bright_blue",
    ))
    console.print()

    # ── Header Panel ──────────────────────────────────────────────────────────
    console.print(Panel(
        f"[bold bright_white]📄 File:[/bold bright_white] [cyan]{file_name}[/cyan]\n\n"
        f"[bold bright_white]📋 Summary:[/bold bright_white]\n{report.summary}",
        title="[bold bright_blue]Executive Summary[/bold bright_blue]",
        border_style="bright_blue",
        padding=(1, 3),
    ))
    console.print()

    if not report.issues:
        console.print(Panel(
            "[bold green]✅  No issues found. The code looks clean![/bold green]",
            border_style="green",
            padding=(1, 2),
        ))
        return

    # ── Severity Stats Table ──────────────────────────────────────────────────
    counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    for issue in report.issues:
        if issue.severity in counts:
            counts[issue.severity] += 1

    stats = Table(box=box.ROUNDED, show_header=True, header_style="bold bright_white",
                  title="[bold]Issue Distribution[/bold]", title_style="bright_yellow",
                  border_style="bright_yellow")
    stats.add_column("Severity",  style="bold", justify="center")
    stats.add_column("Count",     justify="center")
    stats.add_column("Risk",      justify="left")

    risk_map = {
        "Critical": "[bold red]Exploitable — Fix Immediately[/bold red]",
        "High":     "[orange1]Serious Risk — Fix This Sprint[/orange1]",
        "Medium":   "[yellow]Moderate Risk — Fix Soon[/yellow]",
        "Low":      "[cyan]Minor Issue — Fix When Possible[/cyan]",
    }
    for sev in ["Critical", "High", "Medium", "Low"]:
        color, emoji = SEVERITY_STYLE[sev]
        stats.add_row(
            Text(f"{emoji} {sev}", style=f"bold {color}"),
            str(counts[sev]),
            risk_map[sev],
        )
    console.print(stats)
    console.print()

    # ── Individual Issue Cards ────────────────────────────────────────────────
    for idx, issue in enumerate(report.issues, start=1):
        color, emoji = SEVERITY_STYLE.get(issue.severity, ("white", "⚪"))

        # Issue header
        header = Text()
        header.append(f"  #{idx}  ", style="bold bright_white")
        header.append(f"{emoji} {issue.issue}", style=f"bold {color}")

        # Body content
        body = (
            f"[bold bright_white]📁 File:[/bold bright_white] [cyan]{issue.file}[/cyan]\n\n"
            f"[bold bright_white]🔎 Explanation:[/bold bright_white]\n{issue.explanation}\n\n"
            f"[bold bright_white]✅ Suggested Fix:[/bold bright_white]"
        )

        console.print(Panel(
            body,
            title=header,
            title_align="left",
            border_style=color,
            padding=(1, 2),
        ))

        # Syntax-highlighted fix
        fix_syntax = Syntax(
            issue.suggested_fix,
            "python",
            theme="monokai",
            line_numbers=True,
            word_wrap=True,
        )
        console.print(Padding(fix_syntax, (0, 3, 1, 3)))

    console.print(Rule(style="bright_blue"))
    console.print(
        f"[dim]  🏁 Review complete — [bold]{len(report.issues)}[/bold] issue(s) found in [bold]{file_name}[/bold][/dim]\n"
    )


# ─────────────────────────────────────────────
# Entry Point — Demo / Testing
# ─────────────────────────────────────────────

if __name__ == "__main__":

    # ── Sample vulnerable code for testing ────────────────────────────────────
    SAMPLE_FILE = "user_service.py"

    SAMPLE_CODE = '''\
import sqlite3
import hashlib

# --- Database helper ---
def get_user(username: str):
    """Fetch user record from the database."""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    # BUG 1: SQL Injection — username is injected directly into the query
    query = f"SELECT * FROM users WHERE username = \'{username}\'"
    cursor.execute(query)
    return cursor.fetchone()


# --- Password helper ---
def hash_password(password: str) -> str:
    """Hash a user password before storing."""
    # BUG 2: MD5 is cryptographically broken (CWE-327)
    return hashlib.md5(password.encode()).hexdigest()


# --- Report generator ---
def generate_monthly_report(user_ids: list) -> list:
    """Generate usage stats for a list of user IDs."""
    results = []

    # BUG 3: Inefficient loop — opens a new DB connection per user (N+1 problem)
    for uid in user_ids:
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usage WHERE user_id = ?", (uid,))
        results.append(cursor.fetchall())
        # BUG 4: Connection is never closed — resource leak

    return results


# --- Hardcoded secret ---
SECRET_KEY = "s3cr3t_4dm1n_k3y_d0_n0t_sh4r3"   # BUG 5: Hardcoded credential (CWE-798)
'''

    # ── Run the review ────────────────────────────────────────────────────────
    console.print(Panel(
        "[bold bright_white]🚀 GitSentry AI — Sprint 1[/bold bright_white]\n"
        "[dim]AI-powered Code Security Review Assistant[/dim]",
        border_style="bright_blue",
        padding=(1, 4),
    ))
    console.print()

    report = review_code(SAMPLE_FILE, SAMPLE_CODE)
    display_report(report, SAMPLE_FILE)
