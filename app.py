"""
app.py — GitSentry AI · Web Dashboard (Sprint 3+)
==================================================
Ultra-modern Cyberpunk Security SaaS Operations Center.
Built with Streamlit, Plotly, and full core_engine.py integration.

Author  : GitSentry AI Team
Version : 2.0.0
"""

import os
import sys
import json
import time
import base64
import io
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from dotenv import load_dotenv

# ── Path bootstrap so Streamlit finds our modules ─────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
load_dotenv()

from schemas import ReviewReport, CodeIssue
from core_engine import review_code

# ══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG  (must be first Streamlit call)
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="GitSentry AI — Security Operations Center",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTS & PALETTE
# ══════════════════════════════════════════════════════════════════════════════

PALETTE = {
    "bg":       "#0B0E14",
    "surface":  "#111520",
    "surface2": "#161B27",
    "border":   "#1E2A3A",
    "cyan":     "#00F0FF",
    "green":    "#00E676",
    "crimson":  "#FF2A6D",
    "amber":    "#FFB800",
    "orange":   "#FF6B35",
    "purple":   "#9D4EDD",
    "text":     "#C9D1E0",
    "muted":    "#5A6A80",
}

SEVERITY_CONFIG = {
    "Critical": {"color": PALETTE["crimson"],  "glow": "rgba(255,42,109,0.4)",  "emoji": "🔴", "rank": 4},
    "High":     {"color": PALETTE["orange"],   "glow": "rgba(255,107,53,0.4)",  "emoji": "🟠", "rank": 3},
    "Medium":   {"color": PALETTE["amber"],    "glow": "rgba(255,184,0,0.4)",   "emoji": "🟡", "rank": 2},
    "Low":      {"color": PALETTE["cyan"],     "glow": "rgba(0,240,255,0.4)",   "emoji": "🔵", "rank": 1},
}

SAMPLE_CODE = '''\
import sqlite3
import hashlib

# --- Database helper ---
def get_user(username: str):
    """Fetch user record from the database."""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    # BUG 1: SQL Injection — username injected directly
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
    # BUG 3: N+1 — new DB connection per user
    for uid in user_ids:
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usage WHERE user_id = ?", (uid,))
        results.append(cursor.fetchall())
        # BUG 4: Connection never closed — resource leak

    return results


# --- Hardcoded secret ---
SECRET_KEY = "s3cr3t_4dm1n_k3y_d0_n0t_sh4r3"   # BUG 5: CWE-798
'''

# ══════════════════════════════════════════════════════════════════════════════
# GLOBAL CSS  — Cyberpunk Dark Skin + Glassmorphism
# ══════════════════════════════════════════════════════════════════════════════

def inject_css():
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;900&family=JetBrains+Mono:wght@400;500;700&display=swap');

    /* ── Root reset ─────────────────────────────────────────────────────── */
    html, body, [data-testid="stAppViewContainer"] {{
        background: {PALETTE['bg']} !important;
        color: {PALETTE['text']} !important;
        font-family: 'Inter', sans-serif !important;
    }}

    [data-testid="stAppViewContainer"] > .main {{
        background: {PALETTE['bg']} !important;
    }}

    [data-testid="stHeader"] {{
        background: transparent !important;
        border-bottom: 1px solid {PALETTE['border']} !important;
    }}

    /* Hide default Streamlit elements */
    #MainMenu, footer, [data-testid="stToolbar"] {{ visibility: hidden; }}
    [data-testid="stSidebar"] {{ display: none; }}

    /* ── Scrollbar ───────────────────────────────────────────────────────── */
    ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
    ::-webkit-scrollbar-track {{ background: {PALETTE['surface']}; }}
    ::-webkit-scrollbar-thumb {{ background: {PALETTE['border']}; border-radius: 3px; }}
    ::-webkit-scrollbar-thumb:hover {{ background: {PALETTE['cyan']}44; }}

    /* ── Glassmorphism Card ──────────────────────────────────────────────── */
    .gs-card {{
        background: linear-gradient(135deg, {PALETTE['surface']}ee, {PALETTE['surface2']}cc);
        border: 1px solid {PALETTE['border']};
        border-radius: 16px;
        padding: 20px 24px;
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        transition: border-color 0.3s ease, box-shadow 0.3s ease;
        position: relative;
        overflow: hidden;
    }}

    .gs-card::before {{
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 1px;
        background: linear-gradient(90deg, transparent, {PALETTE['cyan']}44, transparent);
    }}

    .gs-card:hover {{
        border-color: {PALETTE['cyan']}44;
        box-shadow: 0 0 30px {PALETTE['cyan']}11;
    }}

    /* ── KPI Cards ───────────────────────────────────────────────────────── */
    .kpi-card {{
        background: linear-gradient(135deg, {PALETTE['surface']}f0, {PALETTE['surface2']}e0);
        border: 1px solid;
        border-radius: 16px;
        padding: 18px 20px;
        text-align: center;
        position: relative;
        overflow: hidden;
        transition: all 0.3s ease;
        cursor: default;
    }}

    .kpi-card::after {{
        content: '';
        position: absolute;
        top: -50%; left: -50%;
        width: 200%; height: 200%;
        background: radial-gradient(circle at center, currentColor 0%, transparent 60%);
        opacity: 0.03;
        pointer-events: none;
    }}

    .kpi-value {{
        font-size: 3rem;
        font-weight: 900;
        line-height: 1;
        font-family: 'JetBrains Mono', monospace;
        letter-spacing: -2px;
    }}

    .kpi-label {{
        font-size: 0.7rem;
        font-weight: 600;
        letter-spacing: 2px;
        text-transform: uppercase;
        margin-top: 6px;
        opacity: 0.7;
    }}

    /* ── Neon Button ─────────────────────────────────────────────────────── */
    .stButton > button {{
        width: 100% !important;
        background: linear-gradient(135deg, {PALETTE['cyan']}22, {PALETTE['cyan']}11) !important;
        color: {PALETTE['cyan']} !important;
        border: 1px solid {PALETTE['cyan']}88 !important;
        border-radius: 12px !important;
        padding: 14px 28px !important;
        font-family: 'Inter', sans-serif !important;
        font-weight: 700 !important;
        font-size: 0.95rem !important;
        letter-spacing: 1.5px !important;
        text-transform: uppercase !important;
        cursor: pointer !important;
        transition: all 0.25s ease !important;
        box-shadow: 0 0 20px {PALETTE['cyan']}22 !important;
        position: relative !important;
        overflow: hidden !important;
    }}

    .stButton > button:hover {{
        background: linear-gradient(135deg, {PALETTE['cyan']}44, {PALETTE['cyan']}22) !important;
        border-color: {PALETTE['cyan']} !important;
        box-shadow: 0 0 40px {PALETTE['cyan']}44, inset 0 0 20px {PALETTE['cyan']}11 !important;
        transform: translateY(-1px) !important;
        color: #ffffff !important;
    }}

    .stButton > button:active {{
        transform: translateY(0) !important;
    }}

    /* ── Scan button (special) ───────────────────────────────────────────── */
    .scan-btn > div > button {{
        background: linear-gradient(135deg, {PALETTE['cyan']}33, {PALETTE['green']}22) !important;
        border-color: {PALETTE['cyan']} !important;
        font-size: 1.05rem !important;
        padding: 18px 32px !important;
        box-shadow: 0 0 30px {PALETTE['cyan']}33, 0 4px 20px rgba(0,0,0,0.4) !important;
    }}

    /* ── Text Inputs / Text Areas ────────────────────────────────────────── */
    .stTextArea textarea, .stTextInput input, .stSelectbox select {{
        background: {PALETTE['surface2']} !important;
        border: 1px solid {PALETTE['border']} !important;
        border-radius: 10px !important;
        color: {PALETTE['text']} !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.82rem !important;
        line-height: 1.6 !important;
    }}

    .stTextArea textarea:focus, .stTextInput input:focus {{
        border-color: {PALETTE['cyan']}88 !important;
        box-shadow: 0 0 15px {PALETTE['cyan']}22 !important;
    }}

    /* ── Select boxes ────────────────────────────────────────────────────── */
    [data-baseweb="select"] > div {{
        background: {PALETTE['surface2']} !important;
        border-color: {PALETTE['border']} !important;
        border-radius: 10px !important;
        color: {PALETTE['text']} !important;
    }}

    [data-baseweb="select"] > div:hover {{
        border-color: {PALETTE['cyan']}66 !important;
    }}

    /* ── File uploader ───────────────────────────────────────────────────── */
    [data-testid="stFileUploader"] {{
        background: {PALETTE['surface2']} !important;
        border: 2px dashed {PALETTE['border']} !important;
        border-radius: 14px !important;
        transition: all 0.3s ease !important;
    }}

    [data-testid="stFileUploader"]:hover {{
        border-color: {PALETTE['cyan']}88 !important;
        background: {PALETTE['surface']} !important;
    }}

    [data-testid="stFileUploader"] label {{
        color: {PALETTE['muted']} !important;
    }}

    /* ── Tabs ────────────────────────────────────────────────────────────── */
    .stTabs [data-baseweb="tab-list"] {{
        background: {PALETTE['surface2']} !important;
        border-radius: 12px !important;
        padding: 4px !important;
        gap: 4px !important;
        border: 1px solid {PALETTE['border']} !important;
    }}

    .stTabs [data-baseweb="tab"] {{
        background: transparent !important;
        border-radius: 8px !important;
        color: {PALETTE['muted']} !important;
        font-weight: 500 !important;
        font-size: 0.82rem !important;
        letter-spacing: 0.5px !important;
        padding: 8px 18px !important;
        transition: all 0.2s ease !important;
    }}

    .stTabs [aria-selected="true"] {{
        background: {PALETTE['cyan']}22 !important;
        color: {PALETTE['cyan']} !important;
        box-shadow: 0 0 15px {PALETTE['cyan']}22 !important;
    }}

    /* ── Progress bar ────────────────────────────────────────────────────── */
    .stProgress > div > div > div {{
        background: linear-gradient(90deg, {PALETTE['cyan']}, {PALETTE['green']}) !important;
        border-radius: 4px !important;
        box-shadow: 0 0 10px {PALETTE['cyan']}66 !important;
    }}

    .stProgress > div > div {{
        background: {PALETTE['surface2']} !important;
        border-radius: 4px !important;
    }}

    /* ── Dividers ────────────────────────────────────────────────────────── */
    hr {{
        border-color: {PALETTE['border']} !important;
        margin: 20px 0 !important;
    }}

    /* ── Radio buttons ───────────────────────────────────────────────────── */
    .stRadio > div {{
        background: {PALETTE['surface2']} !important;
        border: 1px solid {PALETTE['border']} !important;
        border-radius: 12px !important;
        padding: 12px 16px !important;
        gap: 8px !important;
    }}

    .stRadio label {{
        color: {PALETTE['text']} !important;
        font-size: 0.85rem !important;
    }}

    /* ── Metric widgets ──────────────────────────────────────────────────── */
    [data-testid="stMetric"] {{
        background: {PALETTE['surface2']} !important;
        border: 1px solid {PALETTE['border']} !important;
        border-radius: 12px !important;
        padding: 12px 16px !important;
    }}

    /* ── Expander (accordion) ────────────────────────────────────────────── */
    .streamlit-expanderHeader {{
        background: {PALETTE['surface']} !important;
        border: 1px solid {PALETTE['border']} !important;
        border-radius: 10px !important;
        color: {PALETTE['text']} !important;
        font-weight: 600 !important;
        font-size: 0.88rem !important;
        transition: all 0.2s ease !important;
    }}

    .streamlit-expanderHeader:hover {{
        border-color: {PALETTE['cyan']}66 !important;
        background: {PALETTE['surface2']} !important;
    }}

    .streamlit-expanderContent {{
        background: {PALETTE['surface2']} !important;
        border: 1px solid {PALETTE['border']} !important;
        border-top: none !important;
        border-radius: 0 0 10px 10px !important;
    }}

    /* ── Spinner ─────────────────────────────────────────────────────────── */
    .stSpinner > div {{
        border-top-color: {PALETTE['cyan']} !important;
    }}

    /* ── Custom elements ─────────────────────────────────────────────────── */
    .gs-header {{
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px 0 20px;
        border-bottom: 1px solid {PALETTE['border']};
        margin-bottom: 24px;
    }}

    .gs-logo {{
        font-size: 1.8rem;
        filter: drop-shadow(0 0 12px {PALETTE['cyan']});
    }}

    .gs-title {{
        font-size: 1.4rem;
        font-weight: 700;
        color: #ffffff;
        letter-spacing: -0.5px;
    }}

    .gs-subtitle {{
        font-size: 0.75rem;
        color: {PALETTE['muted']};
        letter-spacing: 1px;
        text-transform: uppercase;
    }}

    .gs-badge {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.5px;
        border: 1px solid;
    }}

    .gs-badge-online {{
        background: {PALETTE['green']}22;
        border-color: {PALETTE['green']}66;
        color: {PALETTE['green']};
    }}

    .gs-badge-model {{
        background: {PALETTE['cyan']}15;
        border-color: {PALETTE['cyan']}44;
        color: {PALETTE['cyan']};
    }}

    .gs-section-label {{
        font-size: 0.68rem;
        font-weight: 700;
        letter-spacing: 2px;
        text-transform: uppercase;
        color: {PALETTE['muted']};
        margin-bottom: 10px;
    }}

    /* Gate verdict banners */
    .gate-approved {{
        background: linear-gradient(135deg, {PALETTE['green']}22, {PALETTE['green']}11);
        border: 2px solid {PALETTE['green']}88;
        border-radius: 16px;
        padding: 28px 32px;
        text-align: center;
        animation: pulse-green 2s ease-in-out infinite;
        box-shadow: 0 0 40px {PALETTE['green']}22, inset 0 0 40px {PALETTE['green']}08;
    }}

    .gate-rejected {{
        background: linear-gradient(135deg, {PALETTE['crimson']}22, {PALETTE['crimson']}11);
        border: 2px solid {PALETTE['crimson']}88;
        border-radius: 16px;
        padding: 28px 32px;
        text-align: center;
        animation: pulse-red 2s ease-in-out infinite;
        box-shadow: 0 0 40px {PALETTE['crimson']}22, inset 0 0 40px {PALETTE['crimson']}08;
    }}

    .gate-title {{
        font-size: 2.2rem;
        font-weight: 900;
        letter-spacing: -1px;
        line-height: 1;
    }}

    .gate-subtitle {{
        font-size: 0.85rem;
        opacity: 0.75;
        margin-top: 8px;
        letter-spacing: 0.5px;
    }}

    @keyframes pulse-green {{
        0%, 100% {{ box-shadow: 0 0 30px {PALETTE['green']}22; }}
        50% {{ box-shadow: 0 0 60px {PALETTE['green']}44; }}
    }}

    @keyframes pulse-red {{
        0%, 100% {{ box-shadow: 0 0 30px {PALETTE['crimson']}22; }}
        50% {{ box-shadow: 0 0 60px {PALETTE['crimson']}44; }}
    }}

    /* Issue cards */
    .issue-header {{
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 12px;
    }}

    .issue-tag {{
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 0.68rem;
        font-weight: 700;
        letter-spacing: 1px;
        text-transform: uppercase;
        border: 1px solid;
    }}

    .diff-container {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 12px;
        margin-top: 12px;
    }}

    .diff-panel {{
        background: {PALETTE['bg']};
        border-radius: 10px;
        padding: 14px;
        border: 1px solid;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.78rem;
        line-height: 1.6;
        overflow-x: auto;
    }}

    .diff-panel-label {{
        font-size: 0.65rem;
        font-weight: 700;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        margin-bottom: 10px;
        padding-bottom: 8px;
        border-bottom: 1px solid;
        opacity: 0.7;
    }}

    .diff-line-bad  {{ color: {PALETTE['crimson']}; background: {PALETTE['crimson']}11; display: block; padding: 0 4px; border-radius: 3px; margin: 1px 0; }}
    .diff-line-good {{ color: {PALETTE['green']};   background: {PALETTE['green']}11;   display: block; padding: 0 4px; border-radius: 3px; margin: 1px 0; }}

    /* Scan progress laser */
    .laser-bar {{
        height: 3px;
        background: linear-gradient(90deg, transparent, {PALETTE['cyan']}, {PALETTE['green']}, transparent);
        border-radius: 2px;
        animation: laser-sweep 1.5s linear infinite;
        box-shadow: 0 0 12px {PALETTE['cyan']};
    }}

    @keyframes laser-sweep {{
        0%   {{ transform: translateX(-100%); opacity: 1; }}
        100% {{ transform: translateX(200%);  opacity: 0.3; }}
    }}

    /* Copy button override */
    .copy-btn > div > button {{
        background: {PALETTE['surface']} !important;
        border-color: {PALETTE['border']} !important;
        color: {PALETTE['muted']} !important;
        font-size: 0.75rem !important;
        padding: 6px 14px !important;
        border-radius: 8px !important;
        letter-spacing: 0.5px !important;
        width: auto !important;
    }}

    .copy-btn > div > button:hover {{
        border-color: {PALETTE['cyan']}66 !important;
        color: {PALETTE['cyan']} !important;
        box-shadow: 0 0 10px {PALETTE['cyan']}22 !important;
    }}

    /* Tooltip-style info */
    .info-pill {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: {PALETTE['surface2']};
        border: 1px solid {PALETTE['border']};
        border-radius: 20px;
        padding: 4px 12px;
        font-size: 0.72rem;
        color: {PALETTE['muted']};
        margin: 2px;
    }}

    /* Plotly chart backgrounds */
    .js-plotly-plot .plotly .bg {{
        fill: transparent !important;
    }}

    /* Column containers */
    [data-testid="column"] > div {{
        height: 100%;
    }}

    /* Remove Streamlit default padding */
    .block-container {{
        padding-top: 1rem !important;
        padding-bottom: 1rem !important;
        max-width: 100% !important;
    }}

    /* Animated scan line overlay */
    .scan-overlay {{
        position: relative;
        overflow: hidden;
    }}

    .scan-overlay::after {{
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 2px;
        background: linear-gradient(90deg, transparent, {PALETTE['cyan']}cc, transparent);
        animation: scan-line 3s ease-in-out infinite;
    }}

    @keyframes scan-line {{
        0%   {{ top: 0;    opacity: 1; }}
        100% {{ top: 100%; opacity: 0; }}
    }}

    /* Theme for stCode */
    [data-testid="stCode"] {{
        background: {PALETTE['bg']} !important;
        border: 1px solid {PALETTE['border']} !important;
        border-radius: 10px !important;
    }}
    </style>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def severity_counts(issues: list[CodeIssue]) -> dict:
    counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    for iss in issues:
        if iss.severity in counts:
            counts[iss.severity] += 1
    return counts


def gate_passes(issues: list[CodeIssue], threshold: str) -> bool:
    threshold_rank = SEVERITY_CONFIG.get(threshold, {}).get("rank", 3)
    for iss in issues:
        if SEVERITY_CONFIG.get(iss.severity, {}).get("rank", 0) >= threshold_rank:
            return False
    return True


def build_json_report(report: ReviewReport, file_name: str, threshold: str) -> str:
    data = {
        "meta": {
            "tool": "GitSentry AI v2.0.0",
            "file": file_name,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "gate_threshold": threshold,
            "gate_verdict": "APPROVED" if gate_passes(report.issues, threshold) else "REJECTED",
        },
        "summary": report.summary,
        "issue_count": len(report.issues),
        "severity_distribution": severity_counts(report.issues),
        "issues": [
            {
                "file":          iss.file,
                "issue":         iss.issue,
                "severity":      iss.severity,
                "explanation":   iss.explanation,
                "suggested_fix": iss.suggested_fix,
            }
            for iss in report.issues
        ],
    }
    return json.dumps(data, indent=2)


def build_pdf_report(report: ReviewReport, file_name: str, threshold: str) -> bytes:
    """Generate an executive PDF summary using reportlab."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        )

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            leftMargin=18*mm, rightMargin=18*mm,
            topMargin=18*mm, bottomMargin=18*mm,
        )

        # Colour palette for PDF
        DARK  = colors.HexColor("#0B0E14")
        CYAN  = colors.HexColor("#00F0FF")
        GREEN = colors.HexColor("#00E676")
        RED   = colors.HexColor("#FF2A6D")
        AMBER = colors.HexColor("#FFB800")
        ORNG  = colors.HexColor("#FF6B35")
        LIGHT = colors.HexColor("#C9D1E0")
        MUTED = colors.HexColor("#5A6A80")
        SEV_COLORS = {"Critical": RED, "High": ORNG, "Medium": AMBER, "Low": CYAN}

        styles = getSampleStyleSheet()
        story  = []

        # Title block
        title_style = ParagraphStyle("title", fontSize=22, leading=28,
                                     textColor=CYAN, fontName="Helvetica-Bold",
                                     spaceAfter=4)
        sub_style   = ParagraphStyle("sub", fontSize=9, leading=13,
                                     textColor=MUTED, fontName="Helvetica")
        body_style  = ParagraphStyle("body", fontSize=9, leading=14,
                                     textColor=LIGHT, fontName="Helvetica",
                                     spaceAfter=6)
        h2_style    = ParagraphStyle("h2", fontSize=12, leading=16,
                                     textColor=CYAN, fontName="Helvetica-Bold",
                                     spaceBefore=12, spaceAfter=6)
        code_style  = ParagraphStyle("code", fontSize=7.5, leading=11,
                                     textColor=GREEN, fontName="Courier",
                                     backColor=colors.HexColor("#111520"),
                                     borderPadding=8, spaceAfter=6)

        story.append(Paragraph("🛡️  GitSentry AI", title_style))
        story.append(Paragraph("Executive Security Review Report", sub_style))
        story.append(Spacer(1, 4*mm))
        story.append(HRFlowable(width="100%", thickness=1, color=CYAN))
        story.append(Spacer(1, 4*mm))

        # Meta
        verdict = "APPROVED ✅" if gate_passes(report.issues, threshold) else "REJECTED ❌"
        verdict_color = GREEN if gate_passes(report.issues, threshold) else RED
        meta_data = [
            ["File Reviewed",    file_name],
            ["Timestamp",        datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")],
            ["Gate Threshold",   threshold],
            ["Gate Verdict",     verdict],
            ["Total Issues",     str(len(report.issues))],
        ]
        meta_table = Table(meta_data, colWidths=[45*mm, 130*mm])
        meta_table.setStyle(TableStyle([
            ("FONTNAME",    (0,0), (-1,-1), "Helvetica"),
            ("FONTSIZE",    (0,0), (-1,-1), 9),
            ("FONTNAME",    (0,0), (0,-1),  "Helvetica-Bold"),
            ("TEXTCOLOR",   (0,0), (0,-1),  MUTED),
            ("TEXTCOLOR",   (1,0), (1,-1),  LIGHT),
            ("TEXTCOLOR",   (1,3), (1,3),   verdict_color),
            ("FONTNAME",    (1,3), (1,3),   "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0,0), (-1,-1), [colors.HexColor("#111520"), colors.HexColor("#161B27")]),
            ("BOTTOMPADDING",(0,0), (-1,-1), 5),
            ("TOPPADDING",  (0,0), (-1,-1), 5),
            ("LEFTPADDING", (0,0), (-1,-1), 8),
            ("GRID",        (0,0), (-1,-1), 0.25, colors.HexColor("#1E2A3A")),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 6*mm))

        # Summary
        story.append(Paragraph("Executive Summary", h2_style))
        story.append(Paragraph(report.summary, body_style))

        # Severity table
        counts = severity_counts(report.issues)
        story.append(Paragraph("Severity Distribution", h2_style))
        sev_data  = [["Severity", "Count"]]
        sev_data += [[s, str(counts[s])] for s in ["Critical", "High", "Medium", "Low"]]
        sev_table = Table(sev_data, colWidths=[80*mm, 95*mm])
        sev_table.setStyle(TableStyle([
            ("FONTNAME",  (0,0), (-1,0),  "Helvetica-Bold"),
            ("FONTSIZE",  (0,0), (-1,-1), 9),
            ("TEXTCOLOR", (0,0), (-1,0),  CYAN),
            ("BACKGROUND",(0,0), (-1,0),  colors.HexColor("#111520")),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.HexColor("#111520"),colors.HexColor("#161B27")]),
            ("TEXTCOLOR", (0,1), (0,1),   RED),
            ("TEXTCOLOR", (0,2), (0,2),   ORNG),
            ("TEXTCOLOR", (0,3), (0,3),   AMBER),
            ("TEXTCOLOR", (0,4), (0,4),   CYAN),
            ("FONTNAME",  (0,1), (0,-1),  "Helvetica-Bold"),
            ("GRID",      (0,0), (-1,-1), 0.25, colors.HexColor("#1E2A3A")),
            ("BOTTOMPADDING",(0,0),(-1,-1),5),
            ("TOPPADDING",(0,0),(-1,-1),5),
            ("LEFTPADDING",(0,0),(-1,-1),8),
        ]))
        story.append(sev_table)
        story.append(Spacer(1, 4*mm))

        # Issues
        if report.issues:
            story.append(Paragraph("Detailed Findings", h2_style))
            for idx, iss in enumerate(report.issues, 1):
                sev_color = SEV_COLORS.get(iss.severity, LIGHT)
                issue_header = ParagraphStyle(
                    f"ih{idx}", fontSize=10, leading=14,
                    textColor=sev_color, fontName="Helvetica-Bold", spaceBefore=8
                )
                story.append(Paragraph(f"#{idx}  [{iss.severity.upper()}]  {iss.issue}", issue_header))
                story.append(Paragraph(f"<b>Analysis:</b> {iss.explanation}", body_style))
                story.append(Paragraph("<b>Suggested Fix:</b>", body_style))
                fix_lines = iss.suggested_fix.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
                story.append(Paragraph(fix_lines, code_style))
                story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#1E2A3A")))

        # Footer
        story.append(Spacer(1, 8*mm))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1E2A3A")))
        footer_style = ParagraphStyle("footer", fontSize=7.5, textColor=MUTED,
                                      fontName="Helvetica", alignment=1)
        story.append(Paragraph(
            f"Generated by GitSentry AI v2.0.0 · {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} · Powered by Groq LLM",
            footer_style
        ))

        doc.build(story)
        return buf.getvalue()

    except ImportError:
        # Fallback plain-text "PDF"
        text = build_json_report(report, file_name, threshold)
        return text.encode()


def kpi_card(value: int, label: str, color: str, glow: str, emoji: str) -> str:
    return f"""
    <div class="kpi-card" style="border-color:{color}44; box-shadow: 0 0 20px {glow}; color:{color};">
        <div class="kpi-value" style="color:{color}; text-shadow: 0 0 20px {glow};">{value}</div>
        <div class="kpi-label">{emoji} {label}</div>
    </div>
    """


def gate_verdict_html(approved: bool, blocking: int, threshold: str) -> str:
    if approved:
        return f"""
        <div class="gate-approved">
            <div class="gate-title" style="color:#00E676; text-shadow: 0 0 30px #00E67666;">
                ✅ GATE APPROVED
            </div>
            <div class="gate-subtitle" style="color:#00E676cc;">
                Zero blocking issues · Threshold: {threshold} · Safe to merge
            </div>
        </div>
        """
    return f"""
    <div class="gate-rejected">
        <div class="gate-title" style="color:#FF2A6D; text-shadow: 0 0 30px #FF2A6D66;">
            ❌ GATE REJECTED
        </div>
        <div class="gate-subtitle" style="color:#FF2A6Dcc;">
            {blocking} blocking issue(s) ≥ {threshold} · Remediation required before merge
        </div>
    </div>
    """


def donut_chart(counts: dict) -> go.Figure:
    labels  = ["Critical", "High", "Medium", "Low"]
    values  = [counts[s] for s in labels]
    colors_ = [SEVERITY_CONFIG[s]["color"] for s in labels]

    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        hole=0.62,
        marker=dict(
            colors=colors_,
            line=dict(color=PALETTE["bg"], width=3),
        ),
        textfont=dict(family="Inter", size=12, color="#ffffff"),
        hovertemplate="<b>%{label}</b><br>Count: %{value}<br>Share: %{percent}<extra></extra>",
    ))

    total = sum(values)
    fig.update_layout(
        showlegend=True,
        legend=dict(
            font=dict(color=PALETTE["text"], size=11, family="Inter"),
            bgcolor="rgba(0,0,0,0)",
            bordercolor="rgba(0,0,0,0)",
            orientation="v",
            x=1.05,
        ),
        annotations=[dict(
            text=f"<b>{total}</b><br><span style='font-size:10px'>TOTAL</span>",
            x=0.5, y=0.5,
            font=dict(size=22, color="#ffffff", family="JetBrains Mono"),
            showarrow=False,
        )],
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=10, b=10),
        height=260,
    )
    return fig


def bar_chart(counts: dict) -> go.Figure:
    labels  = ["Critical", "High", "Medium", "Low"]
    values  = [counts[s] for s in labels]
    colors_ = [SEVERITY_CONFIG[s]["color"] for s in labels]

    fig = go.Figure(go.Bar(
        x=labels,
        y=values,
        marker=dict(
            color=colors_,
            opacity=0.85,
            line=dict(color=colors_, width=1),
        ),
        text=values,
        textposition="outside",
        textfont=dict(color="#ffffff", size=13, family="JetBrains Mono"),
        hovertemplate="<b>%{x}</b><br>Count: %{y}<extra></extra>",
    ))

    fig.update_layout(
        xaxis=dict(
            showgrid=False, zeroline=False,
            tickfont=dict(color=PALETTE["text"], size=11, family="Inter"),
            title=None,
        ),
        yaxis=dict(
            showgrid=True, zeroline=False,
            gridcolor=PALETTE["border"],
            tickfont=dict(color=PALETTE["muted"], size=10),
            title=None,
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=30, b=10),
        height=240,
        bargap=0.35,
    )
    return fig


def render_issue_card(idx: int, issue: CodeIssue):
    """Render a single vulnerability accordion card with diff view."""
    cfg   = SEVERITY_CONFIG.get(issue.severity, {"color": PALETTE["text"], "glow": "transparent", "emoji": "⚪", "rank": 0})
    color = cfg["color"]
    emoji = cfg["emoji"]

    with st.expander(f"{emoji}  #{idx}  [{issue.severity.upper()}]  {issue.issue}", expanded=(idx == 1)):

        col_meta, col_copy = st.columns([8, 2])
        with col_meta:
            st.markdown(f"""
            <div style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom:14px;">
                <span class="issue-tag" style="border-color:{color}66; background:{color}15; color:{color};">
                    {emoji} {issue.severity}
                </span>
                <span class="info-pill">📁 {issue.file}</span>
            </div>
            <div style="font-size:0.85rem; color:{PALETTE['text']}; line-height:1.7; margin-bottom:14px;">
                <span style="font-weight:600; color:{PALETTE['cyan']};">🔎 Technical Analysis</span><br>
                {issue.explanation}
            </div>
            """, unsafe_allow_html=True)

        # ── Diff View ─────────────────────────────────────────────────────────
        st.markdown(f"""
        <div style="font-size:0.68rem; font-weight:700; letter-spacing:2px; text-transform:uppercase;
                    color:{PALETTE['muted']}; margin-bottom:8px;">
            ⚡ Vulnerability vs Remediation
        </div>
        """, unsafe_allow_html=True)

        diff_col1, diff_col2 = st.columns(2)

        with diff_col1:
            st.markdown(f"""
            <div style="background:{PALETTE['bg']}; border:1px solid {PALETTE['crimson']}44;
                        border-radius:10px; padding:14px;">
                <div style="font-size:0.65rem; font-weight:700; letter-spacing:1.5px;
                            text-transform:uppercase; color:{PALETTE['crimson']}; margin-bottom:10px;
                            padding-bottom:8px; border-bottom:1px solid {PALETTE['crimson']}33;">
                    ❌ Vulnerable Code
                </div>
            </div>
            """, unsafe_allow_html=True)
            # Extract relevant lines from the issue context (first 10 lines shown)
            vuln_preview = _extract_vuln_preview(issue)
            st.code(vuln_preview, language="python")

        with diff_col2:
            st.markdown(f"""
            <div style="background:{PALETTE['bg']}; border:1px solid {PALETTE['green']}44;
                        border-radius:10px; padding:14px;">
                <div style="font-size:0.65rem; font-weight:700; letter-spacing:1.5px;
                            text-transform:uppercase; color:{PALETTE['green']}; margin-bottom:10px;
                            padding-bottom:8px; border-bottom:1px solid {PALETTE['green']}33;">
                    ✅ Remediated Fix
                </div>
            </div>
            """, unsafe_allow_html=True)
            fix_lines = "\n".join(issue.suggested_fix.splitlines()[:12])
            st.code(fix_lines, language="python")

        # ── Copy Fix button ────────────────────────────────────────────────────
        st.markdown('<div class="copy-btn">', unsafe_allow_html=True)
        if st.button(f"📋  Copy Fix Code", key=f"copy_{idx}_{issue.severity}"):
            st.toast(f"✅ Fix for Issue #{idx} copied to clipboard!", icon="✅")
            st.code(issue.suggested_fix, language="python")
        st.markdown("</div>", unsafe_allow_html=True)


def _extract_vuln_preview(issue: CodeIssue) -> str:
    """Build a short vulnerable code preview from the issue title."""
    # Create a short representative snippet using the issue description as a comment
    lines = [
        f"# ⚠️  {issue.issue}",
        f"# Severity: {issue.severity}",
        "#",
        "# See explanation panel above for full technical details.",
    ]
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN APP
# ══════════════════════════════════════════════════════════════════════════════

def main():
    inject_css()

    # ── Top header bar ─────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="gs-header">
        <div class="gs-logo">🛡️</div>
        <div>
            <div class="gs-title">GitSentry <span style="color:{PALETTE['cyan']};">AI</span></div>
            <div class="gs-subtitle">Security Operations Center · DevSecOps Platform</div>
        </div>
        <div style="margin-left:auto; display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
            <span class="gs-badge gs-badge-online">● ONLINE</span>
            <span class="gs-badge gs-badge-model">🤖 openai/gpt-oss-120b</span>
            <span class="info-pill">⏱ {datetime.utcnow().strftime('%H:%M UTC')}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── State ──────────────────────────────────────────────────────────────────
    if "report"    not in st.session_state: st.session_state.report    = None
    if "file_name" not in st.session_state: st.session_state.file_name = "user_service.py"
    if "latency"   not in st.session_state: st.session_state.latency   = None
    if "scanning"  not in st.session_state: st.session_state.scanning  = False

    # ── Main 2-column layout ───────────────────────────────────────────────────
    left_col, right_col = st.columns([1, 1.05], gap="large")

    # ══════════════════════════════════════════════════════════════════════════
    # LEFT PANEL — Code Input Suite
    # ══════════════════════════════════════════════════════════════════════════
    with left_col:
        st.markdown(f'<div class="gs-section-label">⬛ Code Input Suite</div>', unsafe_allow_html=True)

        # ── Input source tabs ──────────────────────────────────────────────────
        tab_editor, tab_upload = st.tabs(["  📝  Code Editor  ", "  📂  File Upload  "])

        with tab_editor:
            st.markdown(f"""
            <div style="font-size:0.75rem; color:{PALETTE['muted']}; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;">
                <span>Paste or edit source code below</span>
            </div>
            """, unsafe_allow_html=True)

            sample_col, fname_col = st.columns([1.4, 1])
            with sample_col:
                if st.button("⚡  Load Sample Vulnerable Code", key="load_sample"):
                    st.session_state["code_buffer"] = SAMPLE_CODE
                    st.session_state.file_name      = "user_service.py"
                    st.rerun()
            with fname_col:
                file_name_input = st.text_input(
                    "Target filename",
                    value=st.session_state.file_name,
                    placeholder="e.g. app.py",
                    label_visibility="collapsed",
                    key="fname_input",
                )
                st.session_state.file_name = file_name_input or "code_review.py"

            code_input = st.text_area(
                "Code Editor",
                value=st.session_state.get("code_buffer", SAMPLE_CODE),
                height=420,
                label_visibility="collapsed",
                placeholder="# Paste your Python code here for security analysis...",
            )
            # Persist whatever the user types into code_buffer
            st.session_state["code_buffer"] = code_input

        with tab_upload:
            st.markdown(f"""
            <div style="text-align:center; padding:10px 0 6px; color:{PALETTE['muted']}; font-size:0.8rem;">
                Drag & drop or browse to upload a <b style="color:{PALETTE['cyan']};">.py</b> file
            </div>
            """, unsafe_allow_html=True)

            uploaded = st.file_uploader(
                "Upload Python file",
                type=["py"],
                label_visibility="collapsed",
                key="uploader",
            )

            if uploaded:
                content = uploaded.read().decode("utf-8", errors="replace")
                st.session_state["code_buffer"] = content
                st.session_state.file_name      = uploaded.name
                st.success(f"✅ Loaded **{uploaded.name}** ({len(content.splitlines())} lines)")
                st.code(content[:800] + ("\n# ... (truncated)" if len(content) > 800 else ""),
                        language="python")

        # ── Security Gate Config ───────────────────────────────────────────────
        st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
        st.markdown(f'<div class="gs-section-label">⚙️ Security Gate Configuration</div>', unsafe_allow_html=True)

        cfg_col1, cfg_col2 = st.columns(2)
        with cfg_col1:
            threshold = st.selectbox(
                "Fail threshold",
                ["Critical", "High", "Medium", "Low"],
                index=1,
                key="threshold",
                help="Gate FAILS when any issue has severity ≥ this level",
            )
        with cfg_col2:
            groq_key_override = st.text_input(
                "Groq API Key (optional override)",
                type="password",
                placeholder="gsk_... (uses .env if blank)",
                key="groq_key_override",
            )

        # ── Model status strip ─────────────────────────────────────────────────
        env_key = os.getenv("GROQ_API_KEY", "")
        key_status = "🟢 API Key Detected" if (groq_key_override or env_key) else "🔴 No API Key"
        st.markdown(f"""
        <div style="display:flex; gap:8px; flex-wrap:wrap; margin-top:6px; margin-bottom:16px;">
            <span class="info-pill">🤖 Model: openai/gpt-oss-120b</span>
            <span class="info-pill">{key_status}</span>
            <span class="info-pill">🌐 Provider: Groq</span>
            {"" if not st.session_state.latency else f'<span class="info-pill">⚡ Last scan: {st.session_state.latency:.1f}s</span>'}
        </div>
        """, unsafe_allow_html=True)

        # ── RUN SCAN BUTTON ────────────────────────────────────────────────────
        st.markdown('<div class="scan-btn">', unsafe_allow_html=True)
        run_scan = st.button(
            "🔬  RUN SECURITY GATE SCAN",
            key="run_scan",
            use_container_width=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # RIGHT PANEL — Metrics, Gate Verdict, Findings
    # ══════════════════════════════════════════════════════════════════════════
    with right_col:
        st.markdown(f'<div class="gs-section-label">📊 Threat Intelligence & Metrics</div>', unsafe_allow_html=True)

        report: Optional[ReviewReport] = st.session_state.report

        if report is None:
            # ── Idle state ─────────────────────────────────────────────────────
            st.markdown(f"""
            <div class="gs-card scan-overlay" style="text-align:center; padding:48px 24px;">
                <div style="font-size:3rem; margin-bottom:16px; filter:drop-shadow(0 0 20px {PALETTE['cyan']});">🛡️</div>
                <div style="font-size:1.2rem; font-weight:700; color:#ffffff; margin-bottom:8px;">
                    Security Operations Center
                </div>
                <div style="font-size:0.85rem; color:{PALETTE['muted']}; line-height:1.7;">
                    Load or paste source code on the left panel,<br>
                    then click <b style="color:{PALETTE['cyan']};">RUN SECURITY GATE SCAN</b> to begin analysis.
                </div>
                <div style="margin-top:24px; display:flex; justify-content:center; gap:12px; flex-wrap:wrap;">
                    <span class="info-pill">🔴 SQL Injection Detection</span>
                    <span class="info-pill">🟠 Crypto Weakness Analysis</span>
                    <span class="info-pill">🟡 Resource Leak Detection</span>
                    <span class="info-pill">🔵 Secret Exposure Checks</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

        else:
            # ── Gate verdict ───────────────────────────────────────────────────
            counts   = severity_counts(report.issues)
            approved = gate_passes(report.issues, threshold)
            blocking = sum(
                1 for iss in report.issues
                if SEVERITY_CONFIG.get(iss.severity, {}).get("rank", 0)
                >= SEVERITY_CONFIG.get(threshold, {}).get("rank", 3)
            )
            st.markdown(gate_verdict_html(approved, blocking, threshold), unsafe_allow_html=True)
            st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

            # ── KPI cards ──────────────────────────────────────────────────────
            k1, k2, k3, k4 = st.columns(4)
            for col, sev in zip([k1, k2, k3, k4], ["Critical", "High", "Medium", "Low"]):
                with col:
                    cfg = SEVERITY_CONFIG[sev]
                    st.markdown(
                        kpi_card(counts[sev], sev, cfg["color"], cfg["glow"], cfg["emoji"]),
                        unsafe_allow_html=True,
                    )

            st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

            # ── Charts ─────────────────────────────────────────────────────────
            if any(counts.values()):
                chart_tab1, chart_tab2 = st.tabs(["  🍩  Donut  ", "  📊  Bar Chart  "])
                with chart_tab1:
                    st.plotly_chart(donut_chart(counts), use_container_width=True, config={"displayModeBar": False})
                with chart_tab2:
                    st.plotly_chart(bar_chart(counts),   use_container_width=True, config={"displayModeBar": False})

            # ── Summary box ────────────────────────────────────────────────────
            st.markdown(f"""
            <div class="gs-card" style="margin-top:4px; margin-bottom:16px;">
                <div style="font-size:0.68rem; font-weight:700; letter-spacing:2px; text-transform:uppercase;
                            color:{PALETTE['muted']}; margin-bottom:8px;">📋 Executive Summary</div>
                <div style="font-size:0.85rem; color:{PALETTE['text']}; line-height:1.7;">
                    {report.summary}
                </div>
            </div>
            """, unsafe_allow_html=True)

            # ── Export buttons ──────────────────────────────────────────────────
            exp_col1, exp_col2 = st.columns(2)
            file_name = st.session_state.file_name

            with exp_col1:
                json_str = build_json_report(report, file_name, threshold)
                st.download_button(
                    "⬇️  Download JSON Report",
                    data=json_str,
                    file_name=f"gitsentry_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                    use_container_width=True,
                    key="dl_json",
                )

            with exp_col2:
                try:
                    import reportlab  # noqa: F401
                    pdf_bytes = build_pdf_report(report, file_name, threshold)
                    st.download_button(
                        "📄  Download PDF Report",
                        data=pdf_bytes,
                        file_name=f"gitsentry_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        key="dl_pdf",
                    )
                except ImportError:
                    st.button("📄  PDF (install reportlab)", disabled=True, use_container_width=True)

    # ══════════════════════════════════════════════════════════════════════════
    # SCAN EXECUTION — triggers after button press
    # ══════════════════════════════════════════════════════════════════════════
    if run_scan:
        code_to_scan = st.session_state.get("code_buffer", "").strip()
        file_name    = st.session_state.file_name

        if not code_to_scan:
            st.error("⚠️  Please paste or upload code before running the scan.")
            st.stop()

        # Apply optional API key override
        if groq_key_override:
            os.environ["GROQ_API_KEY"] = groq_key_override

        if not os.getenv("GROQ_API_KEY") and not os.getenv("OPENAI_API_KEY"):
            st.error("❌  No API key found. Add your Groq key in the config panel or `.env` file.")
            st.stop()

        # ── Scan animation ─────────────────────────────────────────────────────
        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
        progress_placeholder = st.empty()
        status_placeholder   = st.empty()

        messages = [
            "🔬  Initialising LLM security engine...",
            "🧬  Parsing AST and control flow...",
            "🔐  Running OWASP Top-10 checks...",
            "⚡  Groq inference in progress...",
            "📊  Structuring findings...",
            "✅  Finalising report...",
        ]

        with progress_placeholder.container():
            prog = st.progress(0)
            st.markdown(f'<div class="laser-bar"></div>', unsafe_allow_html=True)

        for i, msg in enumerate(messages[:-1]):
            status_placeholder.markdown(
                f'<div style="text-align:center; color:{PALETTE["cyan"]}; font-size:0.85rem; '
                f'letter-spacing:0.5px; padding:8px 0;">{msg}</div>',
                unsafe_allow_html=True
            )
            prog.progress(int((i + 1) / len(messages) * 80))
            time.sleep(0.4)

        # ── Actual LLM call ────────────────────────────────────────────────────
        try:
            t0 = time.time()
            with st.spinner(""):
                report = review_code(file_name, code_to_scan)
            latency = time.time() - t0

            prog.progress(100)
            status_placeholder.markdown(
                f'<div style="text-align:center; color:{PALETTE["green"]}; font-size:0.85rem; '
                f'letter-spacing:0.5px; padding:8px 0;">✅ Scan complete in {latency:.1f}s</div>',
                unsafe_allow_html=True
            )
            time.sleep(0.8)

            # Store in session
            st.session_state.report    = report
            st.session_state.file_name = file_name
            st.session_state.latency   = latency

            progress_placeholder.empty()
            status_placeholder.empty()
            st.rerun()

        except Exception as e:
            progress_placeholder.empty()
            status_placeholder.empty()
            st.error(f"❌ Scan failed: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # VULNERABILITY INSPECTOR — full width below the columns
    # ══════════════════════════════════════════════════════════════════════════
    report = st.session_state.report
    if report and report.issues:
        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
        st.markdown(f"""
        <div style="display:flex; align-items:center; gap:12px; margin-bottom:16px;">
            <div style="height:2px; flex:1; background:linear-gradient(90deg, {PALETTE['border']}, {PALETTE['cyan']}44, transparent);"></div>
            <div class="gs-section-label" style="margin-bottom:0; white-space:nowrap;">
                🔍 VULNERABILITY REMEDIATION INSPECTOR — {len(report.issues)} Finding(s)
            </div>
            <div style="height:2px; flex:1; background:linear-gradient(90deg, transparent, {PALETTE['cyan']}44, {PALETTE['border']});"></div>
        </div>
        """, unsafe_allow_html=True)

        for idx, issue in enumerate(report.issues, 1):
            render_issue_card(idx, issue)

    elif report and not report.issues:
        st.markdown(f"""
        <div class="gate-approved" style="margin-top:24px;">
            <div style="font-size:1.5rem; font-weight:900; color:#00E676; text-shadow: 0 0 20px #00E67666;">
                🎉 Clean Codebase — Zero Issues Found
            </div>
            <div style="font-size:0.85rem; color:#00E676cc; margin-top:8px;">
                No vulnerabilities detected · This file is safe to merge
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── Footer ─────────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div style="margin-top:40px; padding:20px 0 10px; border-top:1px solid {PALETTE['border']};
                display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
        <div style="font-size:0.72rem; color:{PALETTE['muted']};">
            🛡️ <b style="color:{PALETTE['cyan']};">GitSentry AI</b> v2.0.0 · Powered by Groq LLM + LangChain
        </div>
        <div style="display:flex; gap:8px; flex-wrap:wrap;">
            <span class="info-pill">🔐 SAST Engine</span>
            <span class="info-pill">🤖 Groq Inference</span>
            <span class="info-pill">📦 Pydantic v2</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
