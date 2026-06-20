"""
Fact-Check Agent — a "Truth Layer" for marketing PDFs.

Pipeline
--------
1. EXTRACT  — pull text out of an uploaded PDF (pdfplumber).
2. IDENTIFY — ask Gemini to pull out specific, checkable claims
              (stats, dates, financial/technical figures).
3. VERIFY   — ask Gemini, with Grounding with Google Search turned on,
              to check each claim against current, real-world data.
4. REPORT   — render a verdict for every claim: Verified / Inaccurate / False,
              with the correct fact and sources, so a marketer can fix it fast.

Run locally:
    export GEMINI_API_KEY=AI...
    streamlit run app.py

Deploy:
    Push this folder to GitHub, then deploy on Streamlit Community Cloud
    (share.streamlit.io) and add GEMINI_API_KEY as a secret.
    See README.md for the full walkthrough.
"""

from __future__ import annotations

import io
import json
import os
import re
from datetime import datetime

import pandas as pd
import pdfplumber
import streamlit as st
from google import genai
from google.genai import types

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

DEFAULT_MODEL = "gemini-2.5-flash"
MAX_CHARS_FROM_PDF = 14000          # keep extraction calls fast & cheap
MAX_CLAIMS = 12                     # cap claims per run (cost/time control)

INK = "#13112B"
VIOLET = "#5B4FE0"
VIOLET_DEEP = "#433A9E"
MINT = "#0E9F6E"
AMBER = "#B45309"
RED = "#DC2626"
GREY = "#6B7280"

VERDICT_STYLE = {
    "Verified":     {"color": MINT,  "bg": "#E6F8F0", "icon": "check"},
    "Inaccurate":   {"color": AMBER, "bg": "#FEF3DA", "icon": "alert"},
    "False":        {"color": RED,   "bg": "#FDE8E8", "icon": "cross"},
    "Unverifiable": {"color": GREY,  "bg": "#F1F2F4", "icon": "help"},
}

st.set_page_config(
    page_title="Fact-Check Agent — Truth Layer",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --------------------------------------------------------------------------
# Icons — small hand-rolled outline SVGs (no external icon library needed)
# --------------------------------------------------------------------------

ICONS = {
    "check": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"></circle><path d="M8 12.5l2.5 2.5L16 9"></path></svg>',
    "alert": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3.3 L21 19.5 H3 Z"></path><line x1="12" y1="9.5" x2="12" y2="14"></line><circle cx="12" cy="16.8" r="0.55" fill="currentColor" stroke="none"></circle></svg>',
    "cross": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"></circle><line x1="9" y1="9" x2="15" y2="15"></line><line x1="15" y1="9" x2="9" y2="15"></line></svg>',
    "help": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"></circle><path d="M9.3 9.2a2.7 2.7 0 1 1 3.8 2.5c-.9.4-1.1 1-1.1 1.9"></path><circle cx="12" cy="16.9" r="0.5" fill="currentColor" stroke="none"></circle></svg>',
    "search": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="10.5" cy="10.5" r="6.5"></circle><line x1="15.3" y1="15.3" x2="21" y2="21"></line></svg>',
    "zap": '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M13 2L4 14h6l-1 8 9-12h-6l1-8z"></path></svg>',
    "upload": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 18a4 4 0 0 1-1-7.9 5 5 0 0 1 9.6-1.9A4.5 4.5 0 0 1 17 18"></path><path d="M12 12v7"></path><path d="M9.3 14.3L12 11.6l2.7 2.7"></path></svg>',
    "link": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 14a3.5 3.5 0 0 0 5 0l3-3a3.5 3.5 0 0 0-5-5l-1 1"></path><path d="M14 10a3.5 3.5 0 0 0-5 0l-3 3a3.5 3.5 0 0 0 5 5l1-1"></path></svg>',
    "quote": '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M7 7h4v4c0 3-2 5-4 5v-2c1 0 2-1 2-2H7V7zm8 0h4v4c0 3-2 5-4 5v-2c1 0 2-1 2-2h-2V7z"></path></svg>',
}


def icon(name: str, size: int = 14) -> str:
    svg = ICONS.get(name, "")
    return svg.replace("<svg ", f'<svg width="{size}" height="{size}" ', 1)


# --------------------------------------------------------------------------
# Global styling — injected once
# --------------------------------------------------------------------------

def inject_css():
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Sora:wght@600;700;800&display=swap');

        html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
        h1, h2, h3 {{ font-family: 'Sora', sans-serif !important; }}

        .block-container {{ padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1120px; }}

        /* primary buttons */
        .stButton > button[kind="primary"] {{
            background: linear-gradient(135deg, {VIOLET} 0%, {VIOLET_DEEP} 100%);
            border: none; border-radius: 10px; padding: 0.55rem 1.5rem;
            font-weight: 600; box-shadow: 0 4px 14px rgba(91,79,224,0.32);
            transition: all 0.15s ease;
        }}
        .stButton > button[kind="primary"]:hover {{
            transform: translateY(-1px); box-shadow: 0 6px 18px rgba(91,79,224,0.42);
        }}
        .stButton > button[kind="secondary"], .stDownloadButton > button {{
            border-radius: 10px; font-weight: 600; border: 1px solid #E4E1F5;
        }}

        /* file uploader */
        [data-testid="stFileUploaderDropzone"] {{
            border-radius: 14px; border: 1.5px dashed #C9C5EE; background: #FAFAFD;
        }}

        /* sidebar */
        [data-testid="stSidebar"] {{ background: #FBFAFE; border-right: 1px solid #ECEAF7; }}

        /* expander */
        [data-testid="stExpander"] {{ border-radius: 12px; border: 1px solid #ECEAF7; }}

        /* tabs */
        button[data-baseweb="tab"] {{ font-weight: 600; }}

        .fc-chip {{
            display:inline-flex; align-items:center; gap:4px;
            background:#F1F0FA; color:{VIOLET_DEEP}; border-radius:999px;
            padding:2px 10px; font-size:0.70rem; font-weight:600;
            text-transform:uppercase; letter-spacing:0.4px;
        }}
        .fc-badge {{
            display:inline-flex; align-items:center; gap:5px;
            border-radius:999px; padding:4px 12px; font-weight:700; font-size:0.78rem;
            white-space:nowrap;
        }}
        .fc-card {{
            background:#fff; border:1px solid #ECEAF7; border-radius:14px;
            padding:1.15rem 1.35rem; margin-bottom:0.85rem;
            box-shadow:0 1px 4px rgba(19,17,43,0.045);
        }}
        .fc-card-head {{ display:flex; justify-content:space-between; align-items:flex-start; gap:1rem; }}
        .fc-claim-text {{ font-weight:600; font-size:1rem; color:{INK}; line-height:1.45; }}
        .fc-quote {{
            margin-top:0.55rem; font-size:0.85rem; color:#6B6985; font-style:italic;
            border-left:2.5px solid #E4E1F5; padding-left:0.6rem;
        }}
        .fc-explain {{ margin-top:0.55rem; font-size:0.92rem; color:#33304F; line-height:1.5; }}
        .fc-correct {{
            margin-top:0.6rem; background:#F1F0FA; border-radius:10px;
            padding:0.6rem 0.85rem; font-size:0.88rem; color:{VIOLET_DEEP};
        }}
        .fc-sources {{ margin-top:0.65rem; display:flex; gap:0.5rem; flex-wrap:wrap; }}
        .fc-source-chip {{
            display:inline-flex; align-items:center; gap:4px;
            background:#FAFAFD; border:1px solid #ECEAF7; border-radius:8px;
            padding:3px 9px; font-size:0.74rem; color:#5B4FE0; text-decoration:none;
        }}
        .fc-hero {{
            padding: 1.6rem 1.8rem; border-radius: 16px;
            background: linear-gradient(135deg, {INK} 0%, {VIOLET_DEEP} 100%);
            margin-bottom: 1.3rem; position: relative; overflow: hidden;
        }}
        .fc-hero-tag {{ color:{MINT}; font-weight:700; font-size:0.78rem; letter-spacing:2px; text-transform:uppercase; display:flex; align-items:center; gap:6px; }}
        .fc-hero-title {{ color:white; font-size:1.85rem; font-weight:700; margin-top:0.4rem; font-family:'Sora',sans-serif; display:flex; align-items:center; gap:10px; }}
        .fc-hero-sub {{ color:#C9C5EE; font-size:0.97rem; margin-top:0.4rem; max-width:640px; }}
        .fc-stat {{
            border-radius:12px; padding:0.95rem 1rem; text-align:left;
        }}
        .fc-stat-num {{ font-size:1.7rem; font-weight:800; font-family:'Sora',sans-serif; }}
        .fc-stat-label {{ font-size:0.78rem; font-weight:600; margin-top:2px; display:flex; align-items:center; gap:5px; }}
        .fc-proportion {{ display:flex; height:10px; border-radius:6px; overflow:hidden; margin-top:0.7rem; background:#F1F2F4; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def get_api_key() -> str | None:
    """Look for the key in Streamlit secrets first, then the environment."""
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
        if "GOOGLE_API_KEY" in st.secrets:
            return st.secrets["GOOGLE_API_KEY"]
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def get_client() -> genai.Client | None:
    key = get_api_key()
    if not key:
        return None
    return genai.Client(api_key=key)


def extract_pdf_text(file_bytes: bytes) -> tuple[str, int]:
    """Returns (text, page_count). Truncates very long documents."""
    text_parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)
    full_text = "\n".join(text_parts).strip()
    truncated = full_text[:MAX_CHARS_FROM_PDF]
    return truncated, page_count


def strip_code_fence(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def safe_json_loads(text: str, fallback):
    cleaned = strip_code_fence(text or "")
    try:
        return json.loads(cleaned)
    except Exception:
        match = re.search(r"\[.*\]", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        return fallback


# --------------------------------------------------------------------------
# Step 1 — Claim extraction (no search needed)
# --------------------------------------------------------------------------

EXTRACT_SYSTEM = """You are a precise fact-extraction engine for a marketing fact-checking tool.

Given the raw text of a document, identify the most specific, checkable factual
claims: statistics, dates, financial figures, technical specs, market-share
numbers, growth percentages, user/customer counts, awards, or comparisons to
named competitors. Skip vague opinions, marketing fluff, and anything that
cannot be checked against an external source.

Return ONLY a JSON array as your entire response — no introductory text, no
closing remarks, no markdown code fences. Schema:
[
  {"id": "c1", "claim": "<the exact claim, restated concisely>", "type": "stat|date|financial|technical|other", "quote": "<short supporting quote from the doc, under 20 words>"}
]

Return at most {max_claims} claims, prioritizing the ones most likely to be
wrong, outdated, or hallucinated (specific numbers and dates first)."""


def extract_claims(client: genai.Client, document_text: str, model: str) -> list[dict]:
    config = types.GenerateContentConfig(
        system_instruction=EXTRACT_SYSTEM.replace("{max_claims}", str(MAX_CLAIMS)),
    )
    resp = client.models.generate_content(model=model, contents=document_text, config=config)
    claims = safe_json_loads(resp.text, fallback=[])
    return claims[:MAX_CLAIMS]


# --------------------------------------------------------------------------
# Step 2 — Live verification (Grounding with Google Search)
# --------------------------------------------------------------------------

VERIFY_SYSTEM = """You are a rigorous fact-checking agent. You will be given a
JSON list of claims extracted from a marketing document, plus today's date.

For EACH claim, use Google Search to find current, authoritative information,
then decide a verdict:
- "Verified"     — the claim matches current, real-world data.
- "Inaccurate"   — the claim was once true (or close) but is outdated, stale,
                    or slightly wrong (an old statistic, a superseded version
                    number, a since-changed figure).
- "False"        — no credible evidence supports the claim, or it directly
                    contradicts what reliable sources say.
- "Unverifiable" — you searched but could not find enough public information
                    to confirm or deny it.

Write a one-sentence explanation in your own words (never quote sources
verbatim for more than a few words). If Inaccurate or False, state the correct
current fact. List 1-3 source URLs you actually used.

After researching every claim, respond with ONLY a final JSON array as your
entire response — no introductory text, no closing remarks, no markdown code
fences. Schema:
[
  {
    "id": "c1",
    "verdict": "Verified|Inaccurate|False|Unverifiable",
    "explanation": "<one sentence, your own words>",
    "correct_fact": "<the correct, current fact, or empty string if Verified>",
    "sources": ["<url1>", "<url2>"]
  }
]
Every claim's id from the input must appear exactly once in your output."""


def verify_claims(client: genai.Client, claims: list[dict], model: str):
    today = datetime.now().strftime("%B %d, %Y")
    user_content = (
        f"Today's date is {today}.\n\nClaims to verify:\n"
        + json.dumps(claims, ensure_ascii=False, indent=2)
    )
    config = types.GenerateContentConfig(
        system_instruction=VERIFY_SYSTEM,
        tools=[types.Tool(google_search=types.GoogleSearch())],
    )
    resp = client.models.generate_content(model=model, contents=user_content, config=config)
    verdicts = safe_json_loads(resp.text, fallback=[])

    search_queries = []
    try:
        gm = resp.candidates[0].grounding_metadata
        if gm and gm.web_search_queries:
            search_queries = list(gm.web_search_queries)
    except Exception:
        pass
    return verdicts, search_queries


def run_pipeline(client: genai.Client, document_text: str, model: str, progress_cb=None):
    if progress_cb:
        progress_cb("Extracting checkable claims from the document…", 0.18)
    claims = extract_claims(client, document_text, model)

    if not claims:
        return [], [], []

    if progress_cb:
        progress_cb(f"Searching the live web to verify {len(claims)} claim(s)…", 0.55)
    verdicts, search_queries = verify_claims(client, claims, model)

    if progress_cb:
        progress_cb("Compiling report…", 0.9)

    by_id = {c["id"]: c for c in claims}
    merged = []
    for v in verdicts:
        cid = v.get("id")
        base = by_id.get(cid, {})
        merged.append({
            "id": cid,
            "claim": base.get("claim", "(claim text unavailable)"),
            "type": base.get("type", "other"),
            "quote": base.get("quote", ""),
            "verdict": v.get("verdict", "Unverifiable"),
            "explanation": v.get("explanation", ""),
            "correct_fact": v.get("correct_fact", ""),
            "sources": v.get("sources", []),
        })

    covered_ids = {m["id"] for m in merged}
    for c in claims:
        if c["id"] not in covered_ids:
            merged.append({
                **c, "verdict": "Unverifiable",
                "explanation": "The verification step did not return a result for this claim.",
                "correct_fact": "", "sources": [],
            })

    if progress_cb:
        progress_cb("Done.", 1.0)
    return claims, merged, search_queries


# --------------------------------------------------------------------------
# UI
# --------------------------------------------------------------------------

def render_header():
    st.markdown(
        f"""
        <div class="fc-hero">
            <div class="fc-hero-tag">{icon('zap', 13)} Fact-Check Agent · powered by Gemini</div>
            <div class="fc-hero-title">{icon('search', 24)} The Truth Layer for marketing PDFs</div>
            <div class="fc-hero-sub">Upload a PDF. We extract its claims, verify each one against
            live web data with Grounding with Google Search, and flag what's outdated, false, or fine.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def badge_html(verdict: str) -> str:
    s = VERDICT_STYLE.get(verdict, VERDICT_STYLE["Unverifiable"])
    return (
        f'<span class="fc-badge" style="background:{s["bg"]}; color:{s["color"]};">'
        f'{icon(s["icon"], 13)} {verdict}</span>'
    )


def claim_card_html(m: dict) -> str:
    s = VERDICT_STYLE.get(m["verdict"], VERDICT_STYLE["Unverifiable"])
    quote_html = (
        f'<div class="fc-quote">{icon("quote", 12)} {m["quote"]}</div>' if m.get("quote") else ""
    )
    explain_html = f'<div class="fc-explain">{m["explanation"]}</div>' if m.get("explanation") else ""
    correct_html = (
        f'<div class="fc-correct"><b>Correct fact:</b> {m["correct_fact"]}</div>'
        if m.get("correct_fact") else ""
    )
    sources = [u for u in m.get("sources", []) if u]
    sources_html = ""
    if sources:
        chips = "".join(
            f'<a class="fc-source-chip" href="{u}" target="_blank">{icon("link", 12)} source</a>'
            for u in sources
        )
        sources_html = f'<div class="fc-sources">{chips}</div>'

    return f"""
    <div class="fc-card" style="border-left:4px solid {s['color']};">
        <div class="fc-card-head">
            <div class="fc-claim-text">{m['claim']}</div>
            {badge_html(m['verdict'])}
        </div>
        <span class="fc-chip">{m.get('type','other')}</span>
        {quote_html}
        {explain_html}
        {correct_html}
        {sources_html}
    </div>
    """


def render_results(merged: list[dict], search_queries: list[str]):
    counts = {"Verified": 0, "Inaccurate": 0, "False": 0, "Unverifiable": 0}
    for m in merged:
        counts[m["verdict"]] = counts.get(m["verdict"], 0) + 1
    total = max(sum(counts.values()), 1)

    cols = st.columns(4)
    for col, key in zip(cols, ["Verified", "Inaccurate", "False", "Unverifiable"]):
        s = VERDICT_STYLE[key]
        col.markdown(
            f"""<div class="fc-stat" style="background:{s['bg']};">
                    <div class="fc-stat-num" style="color:{s['color']};">{counts[key]}</div>
                    <div class="fc-stat-label" style="color:{s['color']};">{icon(s['icon'],12)} {key}</div>
                </div>""",
            unsafe_allow_html=True,
        )

    segments = "".join(
        f'<div style="flex:{counts[k]}; background:{VERDICT_STYLE[k]["color"]};"></div>'
        for k in ["Verified", "Inaccurate", "False", "Unverifiable"] if counts[k] > 0
    )
    st.markdown(f'<div class="fc-proportion">{segments}</div>', unsafe_allow_html=True)
    st.write("")

    tab_report, tab_table = st.tabs(["📋  Report", "🗂  Table"])

    with tab_report:
        order = {"False": 0, "Inaccurate": 1, "Unverifiable": 2, "Verified": 3}
        for m in sorted(merged, key=lambda x: order.get(x["verdict"], 9)):
            st.markdown(claim_card_html(m), unsafe_allow_html=True)

        if search_queries:
            with st.expander(f"🔍 {len(search_queries)} search quer{'y' if len(search_queries)==1 else 'ies'} run during verification"):
                for q in search_queries:
                    st.markdown(f"- *{q}*")

    with tab_table:
        st.dataframe(results_to_dataframe(merged), use_container_width=True, hide_index=True)


def results_to_dataframe(merged: list[dict]) -> pd.DataFrame:
    rows = []
    for m in merged:
        rows.append({
            "Claim": m["claim"],
            "Type": m["type"],
            "Verdict": m["verdict"],
            "Explanation": m["explanation"],
            "Correct Fact": m["correct_fact"],
            "Sources": ", ".join(m.get("sources", [])),
        })
    return pd.DataFrame(rows)


def main():
    inject_css()
    render_header()

    if "model_name" not in st.session_state:
        st.session_state.model_name = DEFAULT_MODEL

    client = get_client()

    with st.sidebar:
        st.markdown("### ⚙️ Status")
        if client:
            st.success("Gemini API key detected.")
        else:
            st.error("No GEMINI_API_KEY found.")
            st.caption(
                "Set it as a local environment variable, in `.streamlit/secrets.toml`, "
                "or as a Secret in Streamlit Community Cloud → App settings."
            )

        st.markdown("---")
        st.markdown("### Model")
        st.session_state.model_name = st.text_input(
            "Gemini model", value=st.session_state.model_name,
            help="Change this if Google renames/retires the default free model.",
        )

        st.markdown("---")
        st.markdown("### How it works")
        st.markdown(
            "1. **Extract** — Gemini reads the PDF and pulls out checkable claims.\n"
            "2. **Verify** — Gemini searches the live web (Grounding with Google Search) for each claim.\n"
            "3. **Report** — every claim is labeled Verified, Inaccurate, False, or "
            "Unverifiable, with the correct fact and sources."
        )
        st.markdown("---")
        st.markdown("### Limits (MVP)")
        st.caption(
            f"- Up to {MAX_CLAIMS} claims per document\n"
            f"- Up to ~{MAX_CHARS_FROM_PDF // 1000}k characters of text read per PDF\n"
            "- AI-generated verdicts can be wrong — treat this as a fast first pass, "
            "not a final legal/compliance check."
        )

    uploaded = st.file_uploader("Upload a PDF to fact-check", type=["pdf"])

    if uploaded is None:
        st.markdown(
            f"""<div style="background:#F1F0FA; border-radius:12px; padding:0.9rem 1.1rem;
                    color:{VIOLET_DEEP}; display:flex; align-items:center; gap:8px; font-size:0.95rem;">
                    {icon('upload', 16)} Upload a PDF — e.g. a press release, pitch deck export,
                    or blog post — to get started.
                </div>""",
            unsafe_allow_html=True,
        )
        st.markdown(
            "Don't have one handy? This repo ships a **`sample_trap_document.pdf`** "
            "(see the README) with a few intentionally wrong stats, perfect for a first test run."
        )
        return

    file_bytes = uploaded.read()

    with st.spinner("Reading PDF…"):
        document_text, page_count = extract_pdf_text(file_bytes)

    if not document_text.strip():
        st.error(
            "Couldn't extract any text from this PDF. It may be a scanned/image-only "
            "document — OCR support isn't included in this MVP."
        )
        return

    st.caption(f"📄 {uploaded.name} — {page_count} page(s), {len(document_text):,} characters read.")

    run_clicked = st.button("🔎 Run Fact-Check", type="primary", disabled=client is None)
    if client is None:
        st.warning("Add a GEMINI_API_KEY to run the fact-check (see sidebar).")

    cache_key = f"results::{uploaded.name}::{len(file_bytes)}"

    if run_clicked:
        progress_bar = st.progress(0.0)
        status = st.empty()

        def cb(msg, pct):
            status.write(msg)
            progress_bar.progress(pct)

        try:
            claims, merged, search_queries = run_pipeline(
                client, document_text, st.session_state.model_name, progress_cb=cb
            )
            st.session_state[cache_key] = {"merged": merged, "queries": search_queries}
        except Exception as e:
            st.error(f"Something went wrong while fact-checking: {e}")
            return
        finally:
            progress_bar.empty()
            status.empty()

        if not claims:
            st.warning("No checkable factual claims were found in this document.")
            return

    if cache_key in st.session_state:
        result = st.session_state[cache_key]
        merged, search_queries = result["merged"], result["queries"]
        st.markdown("### Results")
        render_results(merged, search_queries)

        df = results_to_dataframe(merged)
        col_a, col_b = st.columns(2)
        col_a.download_button(
            "⬇️ Download report (CSV)",
            df.to_csv(index=False).encode("utf-8"),
            file_name="fact_check_report.csv",
            mime="text/csv",
        )
        col_b.download_button(
            "⬇️ Download report (JSON)",
            json.dumps(merged, indent=2).encode("utf-8"),
            file_name="fact_check_report.json",
            mime="application/json",
        )


if __name__ == "__main__":
    main()
