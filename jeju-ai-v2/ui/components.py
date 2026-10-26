"""재사용 화면 조각. 모든 사용자·데이터 문자열은 esc()로 이스케이프합니다."""
from __future__ import annotations

import html
import urllib.parse

import streamlit as st

from core.data import Place, facility_labels, grade_of
from ui.icons import icon


def esc(x) -> str:
    return html.escape(str(x if x is not None else ""))


def tidy(html_str: str) -> str:
    """빈 줄·들여쓰기를 없애 마크다운이 HTML을 코드 블록으로 오해하지 않게 합니다."""
    return " ".join(line.strip() for line in html_str.splitlines() if line.strip())


def md(html_str: str) -> None:
    st.markdown(tidy(html_str), unsafe_allow_html=True)


def page_head(title: str, desc: str = "") -> None:
    md(f"<div class='page-head'><h2>{esc(title)}</h2>{f'<p>{esc(desc)}</p>' if desc else ''}</div>")


def section(title: str, sub: str = "") -> None:
    md(f"<div class='section-title'>{esc(title)}{f'<small>{esc(sub)}</small>' if sub else ''}</div>")


def chips(items, tone: str = "") -> str:
    return "<div class='chips'>" + "".join(f"<span class='chip {tone}'>{esc(i)}</span>" for i in items) + "</div>"


def banner(tone: str, title: str, body: str = "", ico: str = "alert") -> None:
    md(f"<div class='banner {tone}'><div class='ico'>{icon(ico, 22)}</div><div><h4>{esc(title)}</h4>{f'<p>{body}</p>' if body else ''}</div></div>")


def stat(label: str, value, unit: str = "", sub: str = "", tone: str = "") -> str:
    color = {"good": "var(--good)", "warn": "var(--warn)", "bad": "var(--bad)"}.get(tone, "var(--ink-4)")
    return (f"<div class='stat'><div class='k'>{esc(label)}</div><div class='v'>{esc(value)}<small>{esc(unit)}</small></div>"
            f"{f'<div class=s style=color:{color}>{esc(sub)}</div>' if sub else ''}</div>")


def empty(title: str, desc: str, ico: str = "bookmark") -> None:
    md(f"<div class='empty'>{icon(ico, 32, 'var(--ink-4)')}<h4>{esc(title)}</h4><p style='margin:0;font-size:16px'>{esc(desc)}</p></div>")


def map_links(p: Place) -> tuple[str, str]:
    q = urllib.parse.quote(f"{p.name} {p.address}")
    return f"https://map.naver.com/p/search/{q}", f"https://www.google.com/maps/search/?api=1&query={q}"


def place_card(p: Place, extra: str = "", reasons: list | None = None, show_grade: bool = True) -> str:
    g, gdesc = grade_of(p.access_score)
    fac = facility_labels(p)[:5]
    reason_html = chips(reasons, "brand") if reasons else ""
    caution = chips([f"주의 · {c}" for c in p.cautions[:1]], "warn") if p.cautions else ""
    grade_html = f"<span class='grade {g}' title='접근성 {g}등급 · {gdesc}'>{g}</span>" if show_grade else ""
    return f"""
    <div class='card lift'>
      <div style='display:flex;justify-content:space-between;gap:12px;align-items:flex-start'>
        <div style='min-width:0'>
          <div class='meta'>{esc(p.category)} · {esc(p.zone)}{' · 실내' if p.indoor else ''}</div>
          <h4>{esc(p.name)}</h4>
        </div>
        {grade_html}
      </div>
      <p>{esc(p.emotion or p.highlight)}</p>
      {reason_html}
      {chips(fac) if fac and not reasons else ''}
      {caution}
      {extra}
    </div>"""


def grade_legend() -> str:
    items = [("A", "누구나 편하게"), ("B", "대부분 접근 가능"), ("C", "동행자와 함께"), ("D", "사전 확인 필요")]
    return "<div style='display:flex;gap:14px;flex-wrap:wrap;align-items:center;font-size:15px;color:var(--ink-3)'>" + "".join(
        f"<span style='display:inline-flex;gap:6px;align-items:center'><span class='grade {g}' style='width:26px;height:26px;font-size:13px;border-radius:8px'>{g}</span>{d}</span>" for g, d in items) + "</div>"
