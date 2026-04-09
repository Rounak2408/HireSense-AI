"""Reusable UI fragments (HTML + Streamlit helpers)."""

from __future__ import annotations

import streamlit as st


def mobile_wall() -> None:
    # Kept for backward compatibility; mobile is now fully supported.
    return


def brand_header() -> None:
    st.sidebar.markdown(
        """
        <div class="hs-brand">HireSense AI</div>
        <div class="hs-tagline">Resume screening & candidate intelligence</div>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str | None = None, pill: str | None = None) -> None:
    sub = f'<div class="hs-subtitle">{subtitle}</div>' if subtitle else ""
    p = f'<span class="hs-pill">{pill}</span>' if pill else ""
    st.markdown(
        f"""
        <div class="hs-topbar">
          <div>
            <h2>{title}</h2>
            {sub}
          </div>
          <div>{p}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def card(title: str, body: str, badge: str | None = None) -> None:
    b = f'<span class="hs-badge">{badge}</span>' if badge else ""
    st.markdown(
        f'<div class="hs-card"><h4>{title}</h4>{b}<div class="hs-muted">{body}</div></div>',
        unsafe_allow_html=True,
    )


def kpi_card(label: str, value: str, delta: str | None = None, tone: str = "neutral") -> None:
    badge_cls = "hs-badge"
    if tone == "positive":
        badge_cls += " ok"
    elif tone == "warning":
        badge_cls += " warn"
    elif tone == "negative":
        badge_cls += " bad"
    d = f'<span class="{badge_cls}">{delta}</span>' if delta else ""
    st.markdown(
        f"""
        <div class="hs-card">
          <div class="hs-muted">{label}</div>
          <div style="display:flex;align-items:baseline;justify-content:space-between;gap:0.75rem;">
            <div style="font-size:1.75rem;font-weight:800;letter-spacing:-0.03em;margin-top:0.25rem;">{value}</div>
            <div>{d}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def empty_state(title: str, body: str, action_hint: str | None = None) -> None:
    hint = (
        "<div class='hs-muted' style='margin-top:0.5rem;'><strong>Next:</strong> "
        + action_hint
        + "</div>"
        if action_hint
        else ""
    )
    st.markdown(
        f"""
        <div class="hs-card">
          <span class="hs-badge">Empty state</span>
          <h4 style="margin-top:0.5rem;">{title}</h4>
          <div class="hs-muted">{body}</div>
          {hint}
        </div>
        """,
        unsafe_allow_html=True,
    )


def skill_chips(skills: list[str], limit: int = 24) -> None:
    if not skills:
        st.caption("No skills extracted.")
        return
    chips = "".join(f'<span class="hs-skill">{s}</span>' for s in skills[:limit])
    st.markdown(chips, unsafe_allow_html=True)


def insight_cards(items: list[dict]) -> None:
    for it in items:
        tone = it.get("tone", "neutral")
        cls = "hs-badge"
        if tone == "positive":
            cls += " ok"
        elif tone == "warning":
            cls += " warn"
        elif tone == "negative":
            cls += " bad"
        st.markdown(
            f"""
            <div class="hs-card">
              <span class="{cls}">Insight</span>
              <h4 style="margin-top:0.5rem;">{it.get("title","")}</h4>
              <div class="hs-muted">{it.get("detail","")}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def progress_pct(label: str, value: float, help_text: str | None = None) -> None:
    v = max(0.0, min(100.0, float(value)))
    st.markdown(f"**{label}** — {v:.1f}%")
    st.progress(v / 100.0)
    if help_text:
        st.caption(help_text)
