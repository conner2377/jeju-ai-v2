import time

import streamlit as st

from core.condition import age_of, assess, Vitals
from core.mobility import phase
from core.recommender import MOBILITY_TYPES, TravelerProfile, rank
from core.state import go
from ui.components import chips, esc, md, place_card, section
from ui.icons import icon

# 한라산 능선 · 오름 · 바다 물결 (단색 레이어, 장식용)
SCENE = """<svg class='scene' viewBox='0 0 720 320' preserveAspectRatio='none' xmlns='http://www.w3.org/2000/svg' aria-hidden='true'>
<path d='M0 250 C120 230 190 150 300 120 C360 104 420 70 470 66 C540 60 600 110 660 150 C690 170 710 182 720 186 L720 320 L0 320 Z' fill='#FFC08A' opacity='.42'/>
<path d='M0 270 C80 250 140 220 210 214 C260 210 300 190 340 186 C400 180 440 214 500 220 C580 228 650 200 720 210 L720 320 L0 320 Z' fill='#FF9F57' opacity='.5'/>
<path d='M0 292 C60 282 120 296 180 288 C240 280 300 298 360 290 C420 282 480 298 540 290 C600 282 660 296 720 288 L720 320 L0 320 Z' fill='#E35400' opacity='.55'/>
<path d='M40 300 C90 294 140 304 190 298 M260 304 C310 298 360 308 410 302 M480 300 C530 294 580 304 630 298' stroke='#FFE2C4' stroke-width='3' fill='none' stroke-linecap='round' opacity='.7'/>
</svg>"""

SERVICES = [
    ("b-lg", "route", "맞춤 코스 추천", "몸 상태·이동 방법·원하는 분위기를 알려 주시면 계단을 피하고 화장실과 쉼터까지 챙긴 하루를 짜 드려요.", "코스 추천"),
    ("b-md", "heart", "안심 케어", "스마트워치 신호를 3초마다 읽고, 무리하기 전에 먼저 쉬어 갈 곳을 알려 드려요.", "안심 케어"),
    ("b-sm", "users", "동행 헬퍼", "휠체어 이동·수어·간호까지", "동행 헬퍼"),
    ("b-sm", "car", "이동 지원", "리프트 차량을 바로 호출", "이동 지원"),
]


def _status_widgets():
    ss = st.session_state
    cards = []
    w = ss.get("wear")
    if w:
        w.tick()
        s = w.latest
        prof = ss.profile
        wx = w.weather()
        a = assess(Vitals(hr=s.hr, spo2=s.spo2, stress=s.stress, sleep=w.sleep_h, active=w.active_minutes(), temp=wx["temp"], rain=wx["rain"],
                          fatigue=ss.get("cv_fatigue", 2), mood=ss.get("cv_mood") or "편안해요"),
                   age=age_of(prof["age_group"]), resting_hr=int(prof["resting_hr"]))
        cards.append(("안심 케어", f"컨디션 {a.score}점", f"심박 {s.hr} · 산소 {s.spo2}%", "live", "안심 케어"))
    else:
        cards.append(("안심 케어", "웨어러블 미연결", "연결하면 실시간으로 지켜봐요", "live off", "안심 케어"))
    active = [b for b in ss.bookings if b.get("status") not in ("취소",) and not b.get("review")]
    if active:
        b = active[0]
        cards.append(("동행 헬퍼", f"{b['helper']} · {b.get('status', '요청')}", f"{b['date'][5:]} {b['time']}", "live", "동행 헬퍼"))
    else:
        cards.append(("동행 헬퍼", "예약 없음", "필요한 도움에 맞춰 찾아 드려요", "live off", "동행 헬퍼"))
    ride = ss.ride if ss.ride.get("t0") else None
    if ride and phase(ride)["status"] not in ("completed", "cancelled"):
        ph = phase(ride)
        cards.append(("이동 지원", ph["label"], f"{ride['dest_name']} · {ph['remain'] or ''}{'분' if ph['remain'] else ''}", "live", "이동 지원"))
    else:
        cards.append(("이동 지원", "호출 대기", "리프트 차량을 바로 부를 수 있어요", "live off", "이동 지원"))
    cols = st.columns(3)
    for col, (k, t, d, live, target) in zip(cols, cards):
        with col:
            md(f"<div class='card lift'><div style='display:flex;justify-content:space-between;align-items:center'><span style='font-size:15px;color:var(--ink-3);font-weight:600'>{k}</span>"
               f"<span class='{live}'><i></i>{'LIVE' if live == 'live' else 'OFF'}</span></div>"
               f"<div style='font-size:20px;font-weight:800;color:var(--ink);margin-top:10px'>{esc(t)}</div><div style='font-size:15px;color:var(--ink-4)'>{esc(d)}</div></div>")
            st.button(f"{k} 열기", key=f"w_{target}", type="tertiary", on_click=go, args=(target,), icon=":material/arrow_forward:")


def render(places):
    prof = st.session_state.profile
    name = prof.get("name") or "여행자"
    good = sum(p.access_score >= 55 for p in places)
    rest = sum(p.facilities["restroom"] for p in places)

    md(f"""<div class='hero-card'>
      <span class='eyebrow'>{icon('wheelchair', 16)} 혼디 · ‘함께’를 뜻하는 제주어</span>
      <h1>{esc(name)}님,<br>제주는 혼디 걸어요</h1>
      <p>계단 없는 길, 가까운 화장실, 쉬어 갈 타이밍까지.<br>여행 전 계획부터 여행 중 안전까지 곁에서 함께할게요.</p>
      <div class='hero-stats'><div><b>{len(places)}곳</b><span>무장애 정보 확인</span></div><div><b>{good}곳</b><span>접근성 A·B 등급</span></div><div><b>{rest}곳</b><span>장애인 화장실</span></div></div>
      {SCENE}</div>""")
    b1, b2, _ = st.columns([1, 1, 1.3])
    b1.button("내 코스 만들기", type="primary", use_container_width=True, on_click=go, args=("코스 추천",), icon=":material/route:")
    b2.button("지금 컨디션 확인", use_container_width=True, on_click=go, args=("안심 케어",), icon=":material/favorite:")

    section("지금 내 여행", "실시간")
    _status_widgets()

    section("혼디가 도와드려요")
    cells = []
    for cls, ico, title, desc, target in SERVICES:
        big = f"<div class='big'>{len(places)}<span style='font-size:18px;font-weight:600;opacity:.7'>곳 중에서 골라요</span></div>" if cls == "b-lg" else ""
        cells.append(f"<div class='{cls}'><div class='ico'>{icon(ico, 22)}</div><h4>{title}</h4><p>{desc}</p>{big}</div>")
    md("<div class='bento'>" + "".join(cells) + "</div>")
    cols = st.columns(4)
    for col, (_, _, title, _, target) in zip(cols, SERVICES):
        col.button(f"{title} 바로가기", key=f"feat_{target}", use_container_width=True, on_click=go, args=(target,))

    section("내 여행 조건", "추천과 케어에 모두 반영돼요")
    with st.container(key="panel_profile"):
        c1, c2 = st.columns([3, 1], vertical_alignment="center")
        with c1:
            mob = [MOBILITY_TYPES.get(m, m) for m in prof["mobility"]] or ["특별한 제약 없음"]
            md(f"<div style='font-size:17px;color:var(--ink-2);font-weight:600'>{esc(prof['age_group'])} · 체력 {esc(prof['stamina'])}</div>"
               + chips(mob, "brand") + chips([f"선호 분위기 · {m}" for m in prof["moods"]]))
        with c2:
            st.button("조건 바꾸기", use_container_width=True, on_click=go, args=("내 여행",), key="home_edit")

    tp = TravelerProfile(mobility=list(prof["mobility"]), stamina=prof["stamina"], moods=list(prof["moods"]), must_have=list(prof["must_have"]))
    picks = rank(places, tp, categories=("자연", "전시·체험", "문화·역사", "휴양"))[:3]
    section(f"{name}님께 잘 맞는 곳", "내 조건 적합도 순")
    cols = st.columns(3)
    for col, s in zip(cols, picks):
        with col:
            md(place_card(s.place, reasons=s.reasons[:3], extra=f"<div style='margin-top:14px;font-size:15px;color:var(--ink-3)'>적합도 <b style='color:var(--brand-text)'>{s.score}</b> / 100</div>"))
