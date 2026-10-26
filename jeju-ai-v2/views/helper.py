import time
import uuid
from datetime import date, datetime, time as dtime, timedelta

import streamlit as st

from core.data import ZONES
from core.helpers import (ACCEPT_S, APPROACH_S, CHECKIN_S, FLOW, HELPERS, SKILLS, booking_status, estimate_cost, helper_reply,
                          match, needs_for, rating_of)
from core.state import notify
from ui.components import banner, chips, esc, md, page_head, section
from ui.icons import icon

HOURS = [2, 4, 6, 8]
STEP_OF = {"요청": 0, "수락": 1, "만나러 가는 중": 2, "동행 중": 3, "완료": 4}


def _won(n: int) -> str:
    return f"{n:,}원"


def _now() -> str:
    return datetime.now().strftime("%H:%M")


def _create(h, day, start, hours, needs, meet, note):
    end = (datetime.combine(day, start) + timedelta(hours=hours)).time()
    b = {"id": uuid.uuid4().hex[:8], "helper_id": h.id, "helper": h.name, "role": h.role, "date": day.isoformat(),
         "time": f"{start.strftime('%H:%M')}–{end.strftime('%H:%M')}", "meet": meet, "note": note, "cost": estimate_cost(h, hours),
         "needs": [SKILLS[n] for n in needs], "requested_at": time.time(), "started_at": None, "ended_at": None,
         "cancelled": False, "review": None, "status": "요청", "seen": [],
         "chat": [{"who": "sys", "text": f"{h.name} 헬퍼에게 동행을 요청했어요", "at": _now(), "ts": time.time()}]}
    if note:
        b["chat"].append({"who": "me", "text": note, "at": _now(), "ts": time.time(), "answered": True})
    st.session_state.bookings.insert(0, b)
    return b


@st.dialog("동행 예약 요청")
def book_dialog(m, day: date, start: dtime, hours: int, needs: list):
    h = m.helper
    md(f"<div style='display:flex;gap:14px;align-items:center;margin-bottom:16px'><div class='avatar'>{esc(h.name[0])}</div>"
       f"<div><div style='font-size:20px;font-weight:700;color:var(--ink)'>{esc(h.name)}</div>"
       f"<div style='color:var(--ink-4);font-size:15px'>{esc(h.role)} · 경력 {h.years}년</div></div></div>")
    plan = st.session_state.plan
    spots = ["현재 위치"] + ([s.scored.place.name for d in plan["plans"] for s in d.stops] if plan and plan.get("plans") else [])
    meet = st.selectbox("만날 곳", spots)
    note = st.text_area("헬퍼에게 전할 내용", placeholder="예) 휠체어에서 차로 옮겨 타실 때 도움이 필요해요. 오후에 혈압약을 드세요.")
    end = (datetime.combine(day, start) + timedelta(hours=hours)).time()
    md(f"<div class='card soft' style='margin:8px 0 16px'>"
       f"<div class='row'><div class='grow d'>일정</div><div class='t'>{day.month}월 {day.day}일 {start.strftime('%H:%M')}–{end.strftime('%H:%M')}</div></div>"
       f"<div class='row'><div class='grow d'>시간당</div><div class='t'>{_won(h.rate)}</div></div>"
       f"<div class='row'><div class='grow d'>예상 금액</div><div class='t' style='font-size:20px'>{_won(estimate_cost(h, hours))}</div></div></div>")
    if st.button("예약 요청 보내기", type="primary", use_container_width=True):
        _create(h, day, start, hours, needs, meet, note.strip())
        st.rerun()


# ---------------------------------------------------------------------------
# 진행 중인 동행 (2초마다 갱신)
# ---------------------------------------------------------------------------
def _advance(b: dict, now: float) -> str:
    """상태 변화에 맞춰 헬퍼 쪽 메시지를 넣는다 (더미 헬퍼 서버 역할)."""
    stt = booking_status(b, now)
    b["status"] = {"수락": "확정"}.get(stt, stt)
    seen = b["seen"]
    if stt != "요청" and "accept" not in seen and not b["cancelled"]:
        seen.append("accept")
        b["chat"] += [{"who": "sys", "text": f"{b['helper']} 헬퍼가 요청을 수락했어요 · 예약 확정", "at": _now(), "ts": now},
                      {"who": "them", "text": f"안녕하세요, {b['helper']}입니다. {b['date'][5:].replace('-', '월 ')}일 {b['time'][:5]}에 {b['meet']}에서 뵐게요. 미리 알려 주실 건강 상태나 필요한 도움이 있으면 편하게 말씀해 주세요.", "at": _now(), "ts": now}]
        st.toast(f"{b['helper']} 헬퍼가 동행을 수락했어요", icon="🤝")
    if stt in ("만나러 가는 중", "동행 중") and "depart" not in seen:
        seen.append("depart")
        b["chat"].append({"who": "them", "text": f"지금 {b['meet']}(으)로 출발했어요. 10분 정도 걸려요.", "at": _now(), "ts": now})
    if stt == "동행 중" and "arrive" not in seen:
        seen.append("arrive")
        b["chat"].append({"who": "sys", "text": "헬퍼가 도착해 동행을 시작했어요", "at": _now(), "ts": now})
        notify(f"보호자 {st.session_state.profile.get('guardian_name') or ''}".strip(), f"{b['helper']} 헬퍼와 동행을 시작했어요 ({b['meet']})", "문자")
    if stt == "동행 중" and "checkin" not in seen and now - b["started_at"] >= APPROACH_S + CHECKIN_S:
        seen.append("checkin")
        b["chat"].append({"who": "them", "text": "1시간째 이동 중이에요. 잠시 앉아서 물 한 잔 드시고 가실까요?", "at": _now(), "ts": now})
    for m in b["chat"]:
        if m["who"] == "me" and not m.get("answered") and now - m["ts"] > 2 and stt != "요청":
            m["answered"] = True
            b["chat"].append({"who": "them", "text": helper_reply(m["text"]), "at": _now(), "ts": now})
    return stt


def _bubble(m: dict) -> str:
    stamp = "" if m["who"] == "sys" else f"<time>{m['at']}</time>"
    return f"<div class='bubble {m['who']}'>{esc(m['text'])}{stamp}</div>"


def _flow(stt: str) -> str:
    step = STEP_OF.get(stt, 0)
    return "<div class='flow'>" + "".join(
        f"<div class='{'done' if i < step or stt == '완료' else 'now' if i == step else ''}'>{t}</div>" for i, t in enumerate(FLOW)) + "</div>"


@st.fragment(run_every=2)
def _active():
    ss = st.session_state
    now = time.time()
    items = [b for b in ss.bookings if not b["cancelled"] and not b.get("review")]
    if not items:
        return
    section("진행 중인 동행", f"{len(items)}건")
    for b in items:
        stt = _advance(b, now)
        h = next(x for x in HELPERS if x.id == b["helper_id"])
        label = {"요청": f"{b['helper']} 헬퍼의 응답을 기다리고 있어요",
                 "수락": "예약이 확정됐어요", "만나러 가는 중": f"{b['helper']} 헬퍼가 만나러 가고 있어요",
                 "동행 중": "동행 중이에요", "완료": "동행을 마쳤어요"}[stt]
        with st.container(key=f"panel_bk_{b['id']}"):
            c1, c2 = st.columns([1.2, 1], gap="large")
            with c1:
                extra = ""
                if stt == "요청":
                    extra = f" · 약 {max(1, int(ACCEPT_S - (now - b['requested_at'])))}초"
                elif stt == "만나러 가는 중":
                    extra = f" · 약 {max(1, int(APPROACH_S - (now - b['started_at'])))}분 뒤 도착"
                elif stt == "동행 중":
                    extra = f" · {int((now - b['started_at'] - APPROACH_S) // 1)}분째"
                md(f"""<div style='display:flex;gap:14px;align-items:center'><div class='avatar'>{esc(h.name[0])}</div><div>
                    <div style='font-size:20px;font-weight:800;color:var(--ink)'>{esc(label)}<span style='font-size:15px;color:var(--ink-4);font-weight:500'>{extra}</span></div>
                    <div style='font-size:15px;color:var(--ink-3)'>{esc(b['helper'])} {esc(b['role'])} · {esc(b['date'])} {esc(b['time'])} · {esc(b['meet'])} · {_won(b['cost'])}</div></div></div>
                    {_flow(stt)}""")
                st.write("")
                if stt == "요청":
                    if st.button("요청 취소", key=f"cx_{b['id']}", use_container_width=True):
                        b["cancelled"] = True
                        b["status"] = "취소"
                        st.rerun(scope="fragment")
                elif stt == "수락":
                    a, c = st.columns(2)
                    if a.button("동행 시작하기", key=f"st_{b['id']}", type="primary", use_container_width=True, help="시연: 예약 당일로 이동해 헬퍼가 출발해요"):
                        b["started_at"] = time.time()
                        st.rerun(scope="fragment")
                    if c.button("예약 취소", key=f"cx2_{b['id']}", use_container_width=True):
                        b["cancelled"] = True
                        b["status"] = "취소"
                        notify(f"헬퍼 {b['helper']}", "예약이 취소되었습니다.", "앱 푸시")
                        st.rerun(scope="fragment")
                elif stt == "동행 중":
                    if st.button("동행 마치기", key=f"end_{b['id']}", type="primary", use_container_width=True):
                        b["ended_at"] = time.time()
                        b["chat"].append({"who": "sys", "text": "동행을 마쳤어요. 후기를 남겨 주세요", "at": _now(), "ts": time.time()})
                        st.rerun(scope="fragment")
                elif stt == "완료":
                    md("<div style='font-size:17px;font-weight:700;color:var(--ink)'>동행은 어떠셨나요?</div>")
                    stars = st.feedback("stars", key=f"rvs_{b['id']}")
                    text = st.text_input("후기 (선택)", placeholder="예) 화장실 위치를 미리 알아봐 주셔서 편했어요", key=f"rvt_{b['id']}")
                    if st.button("후기 남기기", type="primary", use_container_width=True, key=f"rvb_{b['id']}"):
                        score = (stars if stars is not None else 4) + 1
                        b["review"] = {"stars": score, "text": text.strip()}
                        ss.helper_stats.setdefault(b["helper_id"], []).append(score)
                        st.toast("후기를 남겼어요. 헬퍼 평점에 반영됐어요", icon="⭐")
                        st.rerun(scope="fragment")
            with c2:
                md("<div class='chat'>" + "".join(_bubble(m) for m in b["chat"][-6:]) + "</div>")
                if stt not in ("완료",):
                    with st.form(f"chat_{b['id']}", clear_on_submit=True, border=False):
                        a, c = st.columns([3, 1], vertical_alignment="bottom")
                        msg = a.text_input("헬퍼에게 메시지", placeholder="예) 화장실 자주 가셔야 해요", label_visibility="collapsed")
                        if c.form_submit_button("보내기", use_container_width=True) and msg.strip():
                            b["chat"].append({"who": "me", "text": msg.strip(), "at": _now(), "ts": time.time()})
                            st.rerun(scope="fragment")


def render(places):
    ss = st.session_state
    prof = ss.profile
    page_head("동행 헬퍼", "필요한 도움을 고르면 자격과 경험, 활동 지역, 일정이 맞는 동행자를 먼저 보여 드려요.")
    _active()

    ss.setdefault("hp_needs", needs_for(prof["mobility"]) or ["course"])
    ss.setdefault("hp_date", date.today() + timedelta(days=1))
    section("새 동행 찾기")
    with st.container(key="panel_helper"):
        needs = st.pills("어떤 도움이 필요하세요?", list(SKILLS), selection_mode="multi", key="hp_needs", format_func=lambda k: SKILLS[k])
        c1, c2, c3, c4 = st.columns([1.1, 1, 1, 1], vertical_alignment="bottom")
        day = c1.date_input("날짜", key="hp_date", min_value=date.today(), format="YYYY.MM.DD")
        start = c2.selectbox("시작 시간", [dtime(h, m) for h in range(8, 19) for m in (0, 30)], index=4, format_func=lambda t: t.strftime("%H:%M"), key="hp_start")
        hours = c3.selectbox("이용 시간", HOURS, index=1, format_func=lambda x: f"{x}시간", key="hp_hours")
        zone = c4.selectbox("활동 지역", ["전체"] + ZONES, key="hp_zone")

    results = match(list(needs or []), day, zone, stats=ss.helper_stats)
    available = [m for m in results if m.available]
    c1, c2 = st.columns([2, 1], vertical_alignment="center")
    c1.markdown(f"<div class='section-title' style='margin:24px 0 8px'>{len(available)}명이 {day.month}월 {day.day}일에 동행할 수 있어요<small>더미 헬퍼</small></div>", unsafe_allow_html=True)
    if available and c2.button("가장 잘 맞는 헬퍼에게 바로 요청", type="primary", use_container_width=True, icon=":material/bolt:"):
        _create(available[0].helper, day, start, hours, list(needs or []), "현재 위치", "")
        st.rerun()
    if not available:
        banner("neutral", "이 날짜에 가능한 헬퍼가 없어요", "다른 날짜를 골라 보세요.", "users")

    for m in results[:6]:
        h = m.helper
        rating, reviews = rating_of(h, ss.helper_stats)
        missing = chips([f"지원 안 함 · {x}" for x in m.missing], "warn") if m.missing else ""
        with st.container(key=f"panel_h_{h.id}"):
            c1, c2 = st.columns([3, 1.1], vertical_alignment="center", gap="large")
            with c1:
                md(f"""<div style='display:flex;gap:16px;align-items:flex-start'><div class='avatar'>{esc(h.name[0])}</div><div style='min-width:0;flex:1'>
                    <div style='display:flex;gap:8px;align-items:center;flex-wrap:wrap'>
                    <span style='font-size:19px;font-weight:700;color:var(--ink)'>{esc(h.name)}</span>
                    <span style='font-size:15px;color:var(--ink-4)'>{esc(h.role)} · 경력 {h.years}년</span>
                    {'' if m.available else "<span class='chip'>이 날은 쉬어요</span>"}</div>
                    <div style='font-size:15px;color:var(--ink-3);margin-top:2px;display:flex;gap:4px;align-items:center'>{icon('star', 15, 'var(--brand)')} {rating} · 후기 {reviews}</div>
                    <p style='margin:8px 0 0;font-size:16px;color:var(--ink-2)'>{esc(h.intro)}</p>
                    {chips(m.reasons, 'brand')}{missing}
                    <div style='font-size:14px;color:var(--ink-4);margin-top:10px'>자격 · {esc(', '.join(h.certs))} &nbsp;|&nbsp; 언어 · {esc(', '.join(h.langs))}</div>
                    </div></div>""")
            with c2:
                md(f"<div style='font-size:15px;color:var(--ink-3)'>적합도 <b style='color:var(--ink);font-size:22px'>{m.score}</b></div>"
                   f"<div class='bar' style='margin:6px 0 12px' role='img' aria-label='적합도 {m.score}점'><i style='width:{m.score}%;background:var(--brand)'></i></div>"
                   f"<div style='font-size:15px;color:var(--ink-3)'>{hours}시간 <b style='color:var(--ink)'>{_won(estimate_cost(h, hours))}</b></div>")
                if st.button("예약 요청", key=f"book_{h.id}", type="primary" if m.available else "secondary",
                             disabled=not m.available, use_container_width=True):
                    book_dialog(m, day, start, hours, list(needs or []))
