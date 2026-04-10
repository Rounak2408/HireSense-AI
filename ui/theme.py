"""Premium SaaS theming: light/dark CSS injection."""

from __future__ import annotations

import streamlit as st


def inject_theme() -> None:
    theme = st.session_state.get("theme", "dark")
    if theme == "dark":
        css = _dark_css()
    else:
        css = _light_css()
    st.markdown(css, unsafe_allow_html=True)


def theme_toggle() -> None:
    st.session_state.setdefault("theme", "dark")
    st.sidebar.markdown('<div class="hs-theme-label">Appearance</div>', unsafe_allow_html=True)
    c1, c2 = st.sidebar.columns(2)
    if c1.button("Moon", key="hs_theme_dark", use_container_width=True):
        st.session_state.theme = "dark"
    if c2.button("Light", key="hs_theme_light", use_container_width=True):
        st.session_state.theme = "light"
    st.sidebar.caption(f"Current theme: {st.session_state.theme.title()}")


def _base_css(vars_block: str) -> str:
    return f"""
    <style>
    /* Avoid external @import (blocked offline / strict browsers can stall CSS parsing). */
    html, body, [class*="css"]  {{
      font-family: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }}

    :root {{
      {vars_block}
    }}

    html, body {{
      width: 100%;
      max-width: 100%;
      overflow-x: hidden;
    }}

    .stApp {{
      background: var(--hs-bg);
      color: var(--hs-fg);
      width: 100%;
      max-width: 100%;
      overflow-x: hidden;
      position: relative;
      isolation: isolate;
    }}

    .stApp::before,
    .stApp::after {{
      display: none !important;
      content: none !important;
    }}

    .stApp, .stApp p, .stApp span, .stApp label, .stMarkdown, .stCaption {{
      color: var(--hs-fg);
    }}

    /* Keep header layout intact (height:0 broke some Streamlit versions — blank main area). */
    header[data-testid="stHeader"] {{
      background: transparent !important;
      border-bottom: none !important;
      box-shadow: none !important;
    }}

    div[data-testid="stToolbar"] {{
      right: 0.6rem !important;
      top: 0.35rem !important;
    }}

    /* Layout rhythm */
    .block-container {{
      padding-top: 0.55rem !important;
      padding-bottom: 2.0rem !important;
      max-width: 1250px;
      position: relative;
      z-index: 1;
    }}

    section[data-testid="stSidebar"] {{
      background: var(--hs-sidebar);
      border-right: 1px solid var(--hs-border);
    }}

    section[data-testid="stSidebar"] .block-container {{
      padding-top: 1.1rem !important;
    }}

    div[data-testid="stVerticalBlock"] > div:has(> div.hs-card) {{
      gap: 0.75rem;
    }}

    .hs-card {{
      background: var(--hs-card);
      border: 1px solid var(--hs-border);
      border-radius: 18px;
      padding: 1.35rem 1.45rem;
      box-shadow: var(--hs-shadow);
      margin-bottom: 0.78rem;
      position: relative;
      overflow: hidden;
    }}

    .hs-card::after {{
      content: "";
      position: absolute;
      inset: 0;
      pointer-events: none;
      border-radius: inherit;
      background: linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0));
    }}

    .hs-card:hover {{
      transform: translateY(-2px);
      transition: transform .2s ease, box-shadow .2s ease;
      box-shadow: 0 24px 48px rgba(0,0,0,.32);
    }}

    .hs-workspace-headline {{
      margin: 0.32rem 0 1.35rem 0;
      padding: 1.05rem 1.1rem;
      border: 1px solid var(--hs-border);
      border-radius: 18px;
      background: linear-gradient(125deg, rgba(124,58,237,.16), rgba(6,182,212,.08));
      box-shadow: var(--hs-shadow-soft);
    }}

    .hs-workspace-kicker {{
      font-size: .78rem;
      text-transform: uppercase;
      letter-spacing: .08em;
      color: var(--hs-muted);
      font-weight: 700;
      margin-bottom: .28rem;
    }}

    .hs-workspace-subline {{
      font-size: .98rem;
      line-height: 1.5;
      color: var(--hs-fg);
      opacity: .95;
    }}

    .hs-panel-shell {{
      border: 1px solid var(--hs-border);
      border-radius: 20px;
      padding: 1.08rem 1.08rem 0.62rem 1.08rem;
      background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01));
      box-shadow: var(--hs-shadow-soft);
      margin-bottom: 1.08rem;
    }}

    .hs-input-panel {{
      border-color: rgba(99,102,241,.24);
    }}

    .hs-ai-panel {{
      border-color: rgba(34,211,238,.24);
    }}

    .hs-readiness-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: .55rem;
      margin: .2rem 0 .35rem 0;
    }}

    .hs-readiness-grid > div {{
      border: 1px solid var(--hs-border);
      border-radius: 10px;
      padding: .5rem .58rem;
      background: var(--hs-surface);
      font-size: .83rem;
      color: var(--hs-fg);
    }}

    .hs-file-preview-chip {{
      display: inline-flex;
      margin-top: .18rem;
      border: 1px solid var(--hs-border);
      border-radius: 999px;
      padding: .2rem .52rem;
      background: rgba(16,185,129,.14);
      color: #a7f3d0;
      font-size: .74rem;
      font-weight: 700;
      letter-spacing: .02em;
    }}

    .hs-ai-suggestion-card {{
      border-color: rgba(99,102,241,.28);
      background: linear-gradient(145deg, rgba(99,102,241,.13), rgba(15,23,42,.5));
    }}

    .hs-empty-illustrated {{
      border-style: dashed;
      border-color: rgba(148,163,184,.34);
      background: linear-gradient(135deg, rgba(99,102,241,.12), rgba(15,23,42,.42));
    }}

    .hs-hero-score {{
      border-color: rgba(34,211,238,.35);
      background: linear-gradient(135deg, rgba(99,102,241,.2), rgba(34,211,238,.1) 45%, rgba(15,23,42,.42));
      box-shadow: 0 26px 44px rgba(0,0,0,.34), 0 0 0 1px rgba(255,255,255,.05) inset;
    }}

    .hs-score-kicker {{
      font-size: .75rem;
      text-transform: uppercase;
      letter-spacing: .08em;
      color: var(--hs-muted);
      font-weight: 700;
      margin-bottom: .15rem;
    }}

    .hs-score-main {{
      font-size: clamp(2.0rem, 3.8vw, 3.0rem);
      line-height: 1.0;
      font-weight: 800;
      letter-spacing: -0.03em;
      margin: .12rem 0 .22rem 0;
      color: #dbeafe;
      text-shadow: 0 0 24px rgba(59,130,246,.28);
    }}

    .hs-score-sub {{
      font-size: .9rem;
      color: var(--hs-fg);
      opacity: .92;
    }}

    .hs-surface {{
      background: var(--hs-surface);
      border: 1px solid var(--hs-border);
      border-radius: 18px;
      padding: 1.15rem 1.15rem;
      box-shadow: var(--hs-shadow);
    }}

    .hs-section-title {{
      font-size: 1.12rem;
      font-weight: 700;
      letter-spacing: -0.02em;
      margin: 0.25rem 0 0.15rem 0;
    }}

    .hs-subtitle {{
      color: var(--hs-muted);
      font-size: 0.92rem;
      margin-bottom: 0.65rem;
    }}

    .hs-card h4 {{
      margin: 0 0 0.35rem 0;
      font-weight: 600;
      letter-spacing: -0.02em;
    }}

    .hs-muted {{
      color: var(--hs-muted);
      font-size: 0.92rem;
    }}

    .hs-badge {{
      display: inline-block;
      padding: 0.12rem 0.55rem;
      border-radius: 999px;
      font-size: 0.72rem;
      font-weight: 600;
      background: var(--hs-badge-bg);
      color: var(--hs-badge-fg);
      margin: 0.15rem 0.25rem 0 0;
    }}

    .hs-badge.ok {{ background: rgba(16,185,129,0.2); color: #34d399; }}
    .hs-badge.warn {{ background: rgba(245,158,11,0.2); color: #fbbf24; }}
    .hs-badge.bad {{ background: rgba(248,113,113,0.2); color: #fca5a5; }}

    .hs-pill {{
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      padding: 0.24rem 0.65rem;
      border-radius: 999px;
      font-size: 0.78rem;
      font-weight: 700;
      letter-spacing: -0.01em;
      background: var(--hs-chip);
      border: 1px solid var(--hs-border);
      color: var(--hs-fg);
    }}

    .hs-pill strong {{
      font-weight: 800;
    }}

    .hs-skill {{
      display: inline-block;
      padding: 0.2rem 0.55rem;
      border-radius: 8px;
      font-size: 0.75rem;
      margin: 0.15rem 0.25rem 0 0;
      background: var(--hs-chip);
      border: 1px solid var(--hs-border);
    }}

    .hs-brand {{
      font-weight: 700;
      letter-spacing: -0.03em;
      font-size: 1.35rem;
      margin-bottom: 0.15rem;
    }}

    .hs-tagline {{
      font-size: 0.85rem;
      color: var(--hs-muted);
      margin-bottom: 1rem;
    }}

    .hs-topbar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      margin-bottom: 0.75rem;
    }}

    .hs-topbar h2 {{
      margin: 0;
      letter-spacing: -0.03em;
      font-weight: 800;
    }}

    .hs-hero {{
      background: linear-gradient(135deg, rgba(124,58,237,0.18), rgba(6,182,212,0.12) 45%, rgba(15,23,42,0.05));
      border: 1px solid var(--hs-border);
      border-radius: 24px;
      padding: 1.3rem 1.35rem;
      margin-bottom: 0.8rem;
      box-shadow: var(--hs-shadow);
      animation: hsFadeIn .45s ease-out;
    }}

    .hs-hero h1 {{
      margin: 0 0 0.35rem 0;
      font-size: 2rem;
      letter-spacing: -0.04em;
      line-height: 1.08;
      font-weight: 800;
    }}

    .hs-hero p {{
      margin: 0 0 0.55rem 0;
      color: var(--hs-muted);
      font-size: 0.95rem;
    }}

    .hs-kicker {{
      display: inline-block;
      margin-bottom: 0.35rem;
      font-size: 0.78rem;
      color: var(--hs-muted);
      letter-spacing: 0.03em;
      text-transform: uppercase;
      font-weight: 700;
    }}

    .hs-auth-story {{
      background: var(--hs-surface);
      border: 1px solid var(--hs-border);
      border-radius: 20px;
      padding: 1.1rem 1.15rem;
      box-shadow: var(--hs-shadow-soft);
      min-height: 390px;
    }}

    .hs-auth-story h3 {{
      margin: 0 0 0.45rem 0;
      letter-spacing: -0.02em;
      font-size: 1.3rem;
    }}

    .hs-auth-story p {{
      color: var(--hs-muted);
      margin: 0 0 .9rem 0;
      line-height: 1.5;
    }}

    .hs-auth-list-item {{
      display: flex;
      align-items: flex-start;
      gap: .6rem;
      margin-bottom: .7rem;
      color: var(--hs-fg);
      font-size: .92rem;
    }}

    .hs-auth-dot {{
      width: 9px;
      height: 9px;
      border-radius: 999px;
      margin-top: .36rem;
      background: linear-gradient(120deg, #22d3ee, #7c3aed);
      box-shadow: 0 0 14px rgba(124,58,237,.55);
      flex: 0 0 auto;
    }}

    .hs-auth-card {{
      background: var(--hs-card-glass);
      border: 1px solid var(--hs-border);
      border-radius: 22px;
      padding: 1.05rem 1.05rem .9rem 1.05rem;
      box-shadow: var(--hs-shadow);
      backdrop-filter: blur(10px);
      -webkit-backdrop-filter: blur(10px);
      animation: hsFloat .35s ease-out;
    }}

    .hs-auth-centered {{
      max-width: 540px;
      margin: 0 auto;
    }}

    .hs-auth-brand-line {{
      width: 100%;
      border: 1px solid var(--hs-border);
      border-radius: 999px;
      padding: .42rem .7rem;
      margin: 0 0 .62rem 0;
      text-align: center;
      font-size: .84rem;
      font-weight: 800;
      letter-spacing: .08em;
      text-transform: uppercase;
      color: var(--hs-fg);
      background: linear-gradient(120deg, rgba(99,102,241,.14), rgba(34,211,238,.1));
      box-shadow: inset 0 1px 0 rgba(255,255,255,.1);
    }}

    .hs-auth-preview-card {{
      margin: 0.7rem auto 1.1rem auto;
      max-width: 760px;
      background: var(--hs-card-glass);
      border: 1px solid var(--hs-border);
      border-radius: 18px;
      padding: 0.95rem 1rem;
      box-shadow: var(--hs-shadow-soft);
    }}

    .hs-preview-chip {{
      display: inline-flex;
      align-items: center;
      padding: .28rem .62rem;
      border-radius: 999px;
      border: 1px solid var(--hs-border);
      background: var(--hs-surface);
      color: var(--hs-fg);
      font-size: .76rem;
      font-weight: 700;
      letter-spacing: .01em;
      margin-top: .1rem;
    }}

    .hs-locked-suggestion {{
      filter: blur(3px);
      opacity: 0.58;
      user-select: none;
      pointer-events: none;
    }}

    .hs-auth-shell {{
      text-align: center;
      margin: 1.2rem auto 0.9rem auto;
      position: relative;
      z-index: 1;
    }}

    .hs-auth-shell h1 {{
      margin: .15rem 0 .35rem 0;
      font-size: 3.1rem;
      letter-spacing: -0.05em;
      font-weight: 800;
      line-height: 1.02;
    }}

    .hs-auth-shell p {{
      margin: 0 auto;
      max-width: 560px;
      color: var(--hs-muted);
      font-size: 0.98rem;
      line-height: 1.55;
    }}

    .hs-auth-kicker {{
      display: inline-flex;
      align-items: center;
      gap: .45rem;
      padding: .24rem .62rem;
      border: 1px solid var(--hs-border);
      border-radius: 999px;
      font-size: .76rem;
      color: var(--hs-muted);
      background: var(--hs-surface);
      margin-bottom: .55rem;
      font-weight: 700;
      letter-spacing: .04em;
      text-transform: uppercase;
    }}

    .hs-auth-glow {{
      position: absolute;
      inset: -30px auto auto 50%;
      transform: translateX(-50%);
      width: min(760px, 92vw);
      height: 220px;
      border-radius: 999px;
      background: radial-gradient(circle at center, rgba(59,130,246,.32), rgba(124,58,237,.22) 38%, rgba(8,47,73,0) 72%);
      filter: blur(18px);
      z-index: -1;
      pointer-events: none;
    }}

    .hs-signup-popup-wrap {{
      position: relative;
      margin: 0.6rem auto 0.9rem auto;
      max-width: 540px;
      animation: hsFadeIn .3s ease-out;
    }}

    .hs-signup-popup-card {{
      border: 1px solid var(--hs-border);
      border-radius: 18px;
      padding: 0.95rem 1rem;
      background: linear-gradient(140deg, rgba(99,102,241,.18), rgba(34,211,238,.08));
      box-shadow: 0 14px 34px rgba(79,70,229,.28), inset 0 1px 0 rgba(255,255,255,.08);
      text-align: center;
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
    }}

    .hs-signup-popup-badge {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border: 1px solid var(--hs-border);
      background: var(--hs-surface);
      border-radius: 999px;
      padding: 0.2rem 0.58rem;
      font-size: 0.72rem;
      font-weight: 700;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      color: var(--hs-muted);
    }}

    .hs-signup-popup-card h3 {{
      margin: 0.45rem 0 0.25rem 0;
      font-size: 1.2rem;
      letter-spacing: -0.02em;
    }}

    .hs-signup-popup-card p {{
      margin: 0;
      color: var(--hs-muted);
      font-size: 0.92rem;
    }}

    .hs-mobile-wall {{
      display: none !important;
    }}

    div[data-testid="stMetric"] {{
      background: var(--hs-card);
      border: 1px solid var(--hs-border);
      border-radius: 14px;
      padding: 0.75rem;
      box-shadow: var(--hs-shadow);
    }}

    /* Buttons + inputs */
    .stButton > button {{
      border-radius: 10px !important;
      border: 1px solid var(--hs-border) !important;
      background: var(--hs-button) !important;
      color: var(--hs-fg) !important;
      font-weight: 600 !important;
      transition: all .18s ease !important;
      min-height: 40px;
    }}

    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] {{
      border-radius: 12px !important;
      color: var(--hs-input-fg) !important;
      background: var(--hs-input-bg) !important;
      border: 1px solid var(--hs-input-border) !important;
    }}

    .stTextArea textarea {{
      min-height: 170px !important;
      border: 1px solid var(--hs-input-border) !important;
      background: var(--hs-input-bg) !important;
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.03) !important;
    }}

    .stTextInput input::placeholder,
    .stTextArea textarea::placeholder {{
      color: var(--hs-muted) !important;
      opacity: 0.92 !important;
    }}

    .stTextInput input:focus,
    .stTextArea textarea:focus {{
      border-color: var(--hs-focus) !important;
      box-shadow: 0 0 0 1px var(--hs-focus) !important;
    }}

    .stSelectbox div[data-baseweb="select"] *,
    .stMultiSelect div[data-baseweb="select"] * {{
      color: var(--hs-input-fg) !important;
    }}

    .stSelectbox div[data-baseweb="select"] > div,
    .stMultiSelect div[data-baseweb="select"] > div {{
      background: var(--hs-input-bg) !important;
      border: 1px solid var(--hs-input-border) !important;
      color: var(--hs-input-fg) !important;
    }}

    .stSelectbox div[data-baseweb="select"] span,
    .stSelectbox div[data-baseweb="select"] p,
    .stMultiSelect div[data-baseweb="select"] span,
    .stMultiSelect div[data-baseweb="select"] p {{
      color: var(--hs-input-fg) !important;
      opacity: 1 !important;
    }}

    .stSelectbox svg, .stMultiSelect svg {{
      color: var(--hs-input-fg) !important;
      fill: var(--hs-input-fg) !important;
    }}

    /* BaseWeb dropdown menu in light mode */
    div[role="listbox"] {{
      background: var(--hs-card) !important;
      border: 1px solid var(--hs-border) !important;
    }}

    div[role="option"] {{
      color: var(--hs-fg) !important;
    }}

    .stFileUploader > div {{
      background: var(--hs-surface) !important;
      border-radius: 14px !important;
      border: 1px dashed var(--hs-border) !important;
    }}

    .stFileUploader small,
    .stFileUploader label,
    .stFileUploader span,
    .stFileUploader p {{
      color: var(--hs-fg) !important;
    }}

    .stFileUploader [data-testid="stFileUploaderDropzoneInstructions"] div,
    .stFileUploader [data-testid="stFileUploaderDropzoneInstructions"] span,
    .stFileUploader [data-testid="stFileUploaderDropzoneInstructions"] small,
    .stFileUploader [data-testid="stFileUploaderDropzoneInstructions"] p {{
      color: var(--hs-input-fg) !important;
      opacity: 1 !important;
    }}

    .stFileUploader [data-testid="stFileUploaderDropzone"] small,
    .stFileUploader [data-testid="stFileUploaderDropzone"] p,
    .stFileUploader [data-testid="stFileUploaderDropzone"] span {{
      color: var(--hs-input-fg) !important;
      opacity: 1 !important;
    }}

    .stFileUploader section button {{
      background: var(--hs-upload-btn-bg) !important;
      color: var(--hs-upload-btn-fg) !important;
      border: 1px solid var(--hs-border) !important;
      border-radius: 10px !important;
      font-weight: 700 !important;
    }}

    .stFileUploader section small {{
      color: var(--hs-muted) !important;
      opacity: 1 !important;
    }}

    .stButton > button[kind="primary"] {{
      background: linear-gradient(120deg, #7c3aed, #4f46e5) !important;
      border: none !important;
      color: white !important;
      font-weight: 700 !important;
      letter-spacing: 0.01em;
      box-shadow: 0 10px 24px rgba(79,70,229,0.35), 0 0 0 1px rgba(255,255,255,0.08) inset;
      border-radius: 12px !important;
    }}

    .stButton > button:hover {{
      transform: translateY(-1px);
      transition: all .18s ease;
      box-shadow: 0 14px 26px rgba(0,0,0,0.22);
    }}

    div[data-testid="stDataFrame"] * {{
      font-size: .88rem !important;
    }}

    div[data-testid="stDataFrame"] [role="row"] {{
      border-bottom: 1px solid rgba(148,163,184,.12);
    }}

    /* Dataframes */
    div[data-testid="stDataFrame"] {{
      background: var(--hs-card);
      border-radius: 14px;
      border: 1px solid var(--hs-border);
      overflow: hidden;
    }}

    .stTabs [data-baseweb="tab-list"] {{
      gap: 6px;
      background: var(--hs-surface);
      border: 1px solid var(--hs-border);
      border-radius: 12px;
      padding: 4px;
    }}

    .stTabs [aria-selected="true"] {{
      background: var(--hs-tab-active) !important;
      border-radius: 10px !important;
      color: white !important;
      box-shadow: 0 8px 20px rgba(79,70,229,.28);
    }}

    .stTabs [data-baseweb="tab"] {{
      color: var(--hs-fg) !important;
      font-weight: 600;
    }}

    /* Auth tabs: premium segmented style */
    .hs-auth-card .stTabs [data-baseweb="tab-list"] {{
      display: grid !important;
      grid-template-columns: 1fr 1fr;
      gap: 6px;
      border-radius: 14px;
      padding: 5px;
      background: var(--hs-surface);
      border: 1px solid var(--hs-border);
      margin-bottom: 0.85rem;
    }}

    .hs-auth-card .stTabs [data-baseweb="tab"] {{
      justify-content: center !important;
      text-align: center !important;
      min-height: 40px !important;
      border-radius: 10px !important;
      font-weight: 700 !important;
      letter-spacing: 0.01em;
      color: var(--hs-muted) !important;
      transition: all .18s ease !important;
    }}

    .hs-auth-card .stTabs [aria-selected="true"] {{
      background: var(--hs-tab-active) !important;
      color: #fff !important;
      box-shadow: 0 10px 24px rgba(79,70,229,.32);
    }}

    /* Remove odd default indicator line in auth tabs */
    .hs-auth-card .stTabs [data-baseweb="tab-highlight"] {{
      display: none !important;
    }}

    div[data-testid="stExpander"] {{
      border: 1px solid var(--hs-border) !important;
      border-radius: 14px !important;
      background: var(--hs-card) !important;
      overflow: hidden;
    }}

    div[data-testid="stExpander"] details summary p,
    div[data-testid="stExpander"] details div {{
      color: var(--hs-fg) !important;
    }}

    div[data-testid="stAlert"] {{
      border-radius: 12px !important;
      border: 1px solid var(--hs-border) !important;
    }}

    div[data-testid="stAlert"] * {{
      color: var(--hs-fg) !important;
    }}

    div[data-testid="stSidebarNav"] {{
      border-top: 1px solid var(--hs-border);
      margin-top: 0.7rem;
      padding-top: 0.7rem;
    }}

    .hs-theme-label {{
      font-size: .78rem;
      text-transform: uppercase;
      letter-spacing: .06em;
      color: var(--hs-muted);
      margin: .25rem 0 .35rem 0;
      font-weight: 700;
    }}

    @keyframes hsFadeIn {{
      from {{ opacity: 0; transform: translateY(6px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}

    @keyframes hsFloat {{
      from {{ opacity: 0; transform: translateY(10px) scale(.99); }}
      to {{ opacity: 1; transform: translateY(0) scale(1); }}
    }}

    @keyframes hsDrift {{
      from {{ transform: translate3d(0, 0, 0) scale(1); }}
      to {{ transform: translate3d(-2%, 2%, 0) scale(1.04); }}
    }}

    @media (max-width: 1100px) {{
      .hs-auth-shell h1 {{ font-size: 2.4rem; }}
    }}

    @media (max-width: 900px) {{
      /* Force main viewport to never reserve left space for sidebar state. */
      div[data-testid="stAppViewContainer"],
      div[data-testid="stAppViewContainer"] > .main,
      div[data-testid="stMain"],
      section[data-testid="stMain"],
      div[data-testid="stMainBlockContainer"] {{
        margin-left: 0 !important;
        left: 0 !important;
        inset-inline-start: 0 !important;
        transform: none !important;
        width: 100% !important;
        max-width: 100% !important;
        overflow-x: hidden !important;
      }}

      div[data-testid="stAppViewContainer"],
      div[data-testid="stMain"],
      div[data-testid="stMainBlockContainer"] {{
        width: 100% !important;
        max-width: 100% !important;
        overflow-x: hidden !important;
      }}

      .block-container {{
        width: 100% !important;
        max-width: 100% !important;
        margin: 0 !important;
        padding: 0.45rem 0.5rem 1.05rem 0.5rem !important;
      }}

      .hs-hero {{
        border-radius: 16px;
        padding: 0.9rem 0.95rem;
      }}

      .hs-hero h1 {{
        font-size: 1.45rem;
      }}

      .hs-auth-shell {{
        margin-top: 0.65rem;
      }}

      .hs-auth-shell h1 {{
        font-size: 2rem;
      }}

      .hs-auth-shell p {{
        font-size: 0.9rem;
        line-height: 1.45;
        padding: 0 0.2rem;
      }}

      .hs-auth-centered {{
        max-width: 100%;
      }}

      .hs-auth-card {{
        border-radius: 16px;
        padding: 0.8rem 0.75rem 0.78rem 0.75rem;
      }}

      .hs-auth-brand-line {{
        padding: 0.36rem 0.55rem;
        font-size: 0.76rem;
        letter-spacing: 0.06em;
      }}

      .hs-workspace-headline {{
        padding: .74rem .78rem;
      }}

      .hs-panel-shell {{
        border-radius: 14px;
        padding: .68rem .64rem .4rem .64rem;
      }}

      .hs-score-main {{
        font-size: 2.15rem;
      }}

      .hs-card {{
        border-radius: 14px;
        padding: 0.95rem 0.92rem;
      }}

      div[data-testid="stMetric"] {{
        padding: 0.55rem;
      }}

      /* Stack all Streamlit column layouts on mobile */
      div[data-testid="stHorizontalBlock"] {{
        flex-direction: column !important;
        gap: 0.6rem !important;
      }}

      div[data-testid="stHorizontalBlock"] > div {{
        width: 100% !important;
        flex: 1 1 100% !important;
        min-width: 100% !important;
      }}

      .stButton > button {{
        width: 100% !important;
        min-height: 42px;
        border-radius: 12px !important;
      }}

      .stTextInput input,
      .stSelectbox div[data-baseweb="select"] > div {{
        min-height: 42px !important;
        font-size: 0.95rem !important;
      }}

      .stFileUploader > div {{
        border-radius: 12px !important;
      }}

      .stFileUploader [data-testid="stFileUploaderDropzone"] {{
        padding: 0.45rem 0.5rem !important;
      }}

      .stTabs [data-baseweb="tab-list"] {{
        overflow-x: auto;
        white-space: nowrap;
      }}

      /* Streamlit may reserve a left gutter for sidebar control on small screens. */
      div[data-testid="collapsedControl"] {{
        margin-left: 0 !important;
        padding-left: 0 !important;
        left: 0.2rem !important;
        position: fixed !important;
        z-index: 1000 !important;
        width: auto !important;
        min-width: 0 !important;
      }}

      /* Sidebar hidden state should not consume layout width on mobile. */
      section[data-testid="stSidebar"][aria-expanded="false"] {{
        min-width: 0 !important;
        max-width: 0 !important;
        width: 0 !important;
        border-right: none !important;
      }}
    }}

    @media (max-width: 640px) {{
      .block-container {{
        padding: 0.35rem 0.42rem 0.9rem 0.42rem !important;
      }}

      .hs-brand {{
        font-size: 1.12rem;
      }}

      .hs-tagline {{
        font-size: 0.77rem;
      }}

      .hs-kicker {{
        font-size: 0.7rem;
      }}

      .hs-auth-preview-card {{
        padding: 0.72rem;
      }}

      section[data-testid="stSidebar"] {{
        min-width: 76vw !important;
        max-width: 76vw !important;
      }}

      .hs-auth-card {{
        border-radius: 14px;
        padding: 0.72rem 0.68rem 0.7rem 0.68rem;
      }}

      .hs-auth-brand-line {{
        margin-bottom: 0.4rem;
        font-size: 0.72rem;
        padding: 0.32rem 0.5rem;
      }}

      .hs-signup-popup-card {{
        border-radius: 14px;
        padding: 0.75rem 0.8rem;
      }}

      .hs-signup-popup-card h3 {{
        font-size: 1.02rem;
      }}

      .hs-signup-popup-card p {{
        font-size: 0.84rem;
      }}

      .hs-auth-shell {{
        margin: 0.45rem auto 0.55rem auto;
      }}

      .hs-auth-shell h1 {{
        font-size: 1.7rem;
      }}

      .hs-auth-shell p {{
        max-width: 95%;
        font-size: 0.86rem;
        line-height: 1.4;
      }}

      .hs-auth-glow {{
        width: min(520px, 96vw);
        height: 150px;
        filter: blur(14px);
      }}

      .stTextInput input,
      .stSelectbox div[data-baseweb="select"] > div {{
        min-height: 40px !important;
        border-radius: 10px !important;
        font-size: 0.92rem !important;
      }}

      .stButton > button {{
        min-height: 40px;
        font-size: 0.95rem !important;
      }}
    }}
    </style>
    """


def _dark_css() -> str:
    vars_block = """
      --hs-bg: linear-gradient(160deg, #0b1020 0%, #0f172a 40%, #0b1020 100%);
      --hs-sidebar: rgba(15, 23, 42, 0.92);
      --hs-card: rgba(30, 41, 59, 0.72);
      --hs-card-glass: rgba(15, 23, 42, 0.72);
      --hs-surface: rgba(2, 6, 23, 0.35);
      --hs-border: rgba(148, 163, 184, 0.18);
      --hs-fg: #e2e8f0;
      --hs-muted: #94a3b8;
      --hs-shadow: 0 18px 45px rgba(0,0,0,0.35);
      --hs-shadow-soft: 0 12px 32px rgba(0,0,0,0.24);
      --hs-badge-bg: rgba(56, 189, 248, 0.15);
      --hs-badge-fg: #7dd3fc;
      --hs-chip: rgba(15, 23, 42, 0.65);
      --hs-button: rgba(15, 23, 42, 0.65);
      --hs-tab-active: linear-gradient(120deg, #7c3aed, #4f46e5);
      --hs-upload-btn-bg: rgba(15, 23, 42, 0.7);
      --hs-upload-btn-fg: #e2e8f0;
      --hs-input-bg: rgba(15, 23, 42, 0.7);
      --hs-input-fg: #e2e8f0;
      --hs-input-border: rgba(148, 163, 184, 0.35);
      --hs-focus: rgba(124, 58, 237, 0.65);
    """
    return _base_css(vars_block)


def _light_css() -> str:
    vars_block = """
      --hs-bg: linear-gradient(160deg, #f2f5fb 0%, #e9eef9 55%, #f3f6fc 100%);
      --hs-sidebar: rgba(255,255,255,0.9);
      --hs-card: rgba(255,255,255,0.96);
      --hs-card-glass: rgba(255,255,255,0.9);
      --hs-surface: rgba(255,255,255,0.88);
      --hs-border: rgba(15, 23, 42, 0.14);
      --hs-fg: #0b1220;
      --hs-muted: #475569;
      --hs-shadow: 0 12px 30px rgba(15, 23, 42, 0.1);
      --hs-shadow-soft: 0 8px 22px rgba(15, 23, 42, 0.08);
      --hs-badge-bg: rgba(37, 99, 235, 0.12);
      --hs-badge-fg: #1d4ed8;
      --hs-chip: rgba(15, 23, 42, 0.06);
      --hs-button: rgba(255,255,255,0.95);
      --hs-tab-active: linear-gradient(120deg, #7c3aed, #4f46e5);
      --hs-upload-btn-bg: rgba(255,255,255,0.98);
      --hs-upload-btn-fg: #0b1220;
      --hs-input-bg: #ffffff;
      --hs-input-fg: #0b1220;
      --hs-input-border: rgba(15, 23, 42, 0.22);
      --hs-focus: rgba(99, 102, 241, 0.65);
    """
    return _base_css(vars_block)
