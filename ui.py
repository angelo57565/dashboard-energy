"""Pequenos componentes visuais (HTML estilizado pelo tema)."""
import html

import streamlit as st


def banner(kind: str, text: str) -> None:
    """kind: ok | warn | danger | info"""
    st.markdown(f'<div class="eg-banner eg-{kind}">{html.escape(text)}</div>', unsafe_allow_html=True)


def cards(items: list[tuple[str, str]]) -> None:
    body = "".join(
        f'<div class="eg-card"><div class="eg-label">{html.escape(lbl)}</div>'
        f'<div class="eg-value">{html.escape(val)}</div></div>'
        for lbl, val in items
    )
    st.markdown(f'<div class="eg-grid">{body}</div>', unsafe_allow_html=True)


def progress(fraction: float, text: str) -> None:
    pct = max(0.0, fraction) * 100
    over = " over" if fraction > 1 else ""
    st.markdown(
        f'<div class="eg-bar{over}"><div style="width:{min(pct, 100):.1f}%"></div></div>'
        f'<div class="eg-label">{html.escape(text)}</div>',
        unsafe_allow_html=True,
    )


def table(df) -> None:
    st.markdown(
        '<div class="eg-scroll">' + df.to_html(index=False, border=0, classes="eg-table", escape=True) + "</div>",
        unsafe_allow_html=True,
    )


def rerun(auto: bool) -> None:
    """Recarrega só a área que atualiza sozinha (ou a página toda se a atualização automática estiver off)."""
    st.rerun(scope="fragment") if auto else st.rerun()
