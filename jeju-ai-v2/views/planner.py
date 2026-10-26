from datetime import datetime

import streamlit as st

from core import llm
from core.data import FACILITIES, MOODS, ZONES
from core.recommender import (MOBILITY_TYPES, PACE, THEMES, TravelerProfile, build_itinerary, parse_request,
                              plan_from_ai, plan_from_names, plan_summary, plan_to_text)
from core.state import go
from ui.components import banner, chips, esc, map_links, md, page_head, section, stat
from ui.icons import icon
from ui.maps import route_map

KIND_LABEL = {"sight": "둘러보기", "meal": "식사", "cafe": "카페에서 쉬기"}
DAYS = {"당일": 1, "1박 2일": 2, "2박 3일": 3}
MUST = ["restroom", "parking", "flat", "elevator"]


def _defaults():
    prof = st.session_state.profile
    ss = st.session_state
    ss.setdefault("pl_mob", list(prof["mobility"]))
    ss.setdefault("pl_stamina", prof["stamina"])
    ss.setdefault("pl_moods", list(prof["moods"]))
    ss.setdefault("pl_must", [m for m in prof["must_have"] if m in MUST])
    ss.setdefault("pl_days", "당일")
    ss.setdefault("pl_pace", "여유롭게")
    ss.setdefault("pl_zone", "전체")
    ss.setdefault("pl_indoor", False)
    ss.setdefault("pl_req", "")
    ss.setdefault("pl_feel", "편안해요")


def _timeline(day) -> str:
    out = ["<div class='tl'>"]
    for n, s in enumerate(day.stops, 1):
        p = s.scored.place
        if s.travel_min:
            out.append(f"<div class='tl-move'>{icon('car', 16)} 이동 약 {s.travel_min}분 · {s.travel_km}km</div>")
        dot = str(n)
        tips = "".join(
            f"<li><b>{esc(t.split(' · ', 1)[0])}</b> {esc(t.split(' · ', 1)[1]) if ' · ' in t else ''}</li>" for t in s.tips
        )
        naver, google = map_links(p)
        warn = chips([f"주의 · {w}" for w in s.scored.warnings], "warn") if s.scored.warnings else ""
        out.append(f"""<div class='tl-item'><div class='tl-dot {s.kind}'>{dot}</div><div class='tl-card'>
          <div class='tl-time'>{s.arrive} · {KIND_LABEL[s.kind]} {s.stay_min}분{f" &nbsp;{icon('utensils' if s.kind == 'meal' else 'coffee', 15)}" if s.kind != 'sight' else ''}</div>
          <h4>{esc(p.name)}</h4>
          <div style='font-size:15px;color:var(--ink-4)'>{esc(p.address)}</div>
          {f"<div class='tl-note'>{icon('spark', 16)}<span>{esc(s.note)}</span></div>" if s.note else ''}
          {chips(s.scored.reasons, 'brand')}{warn}
          {f"<ul class='tl-tips'>{tips}</ul>" if tips else ''}
          <div style='display:flex;gap:16px;margin-top:12px;font-size:15px;font-weight:600'>
            <a href='{naver}' target='_blank' rel='noopener'>네이버 지도</a><a href='{google}' target='_blank' rel='noopener'>구글 지도</a></div>
        </div></div>""")
    out.append("</div>")
    return "".join(out)


def render_plan(plans, key: str) -> None:
    s = plan_summary(plans)
    cols = st.columns(4)
    cols[0].markdown(stat("방문 장소", s["count"], "곳"), unsafe_allow_html=True)
    cols[1].markdown(stat("평균 접근성", s["avg"], "점"), unsafe_allow_html=True)
    cols[2].markdown(stat("총 이동 거리", s["km"], "km"), unsafe_allow_html=True)
    cols[3].markdown(stat("총 이동 시간", s["travel"], "분"), unsafe_allow_html=True)
    tabs = st.tabs([f"{d.day}일차" for d in plans]) if len(plans) > 1 else [st.container()]
    for tab, d in zip(tabs, plans):
        with tab:
            if d.trimmed:
                banner("info", "체력을 고려해 일정을 줄였어요", f"이동 시간과 휴식 시간을 넣으면 하루가 길어져서 관광지 수를 줄였어요. {d.end_time}쯤 일정이 끝나요.", "clock")
            c1, c2 = st.columns([1.1, 1], gap="large")
            with c1:
                md(_timeline(d))
            with c2, st.container(key=f"sticky_{key}_{d.day}"):
                pts = [(x.scored.place.lat, x.scored.place.lon, x.scored.place.name, x.kind) for x in d.stops]
                route_map(pts, key=f"{key}-d{d.day}", height=460)
                md(f"<div style='font-size:15px;color:var(--ink-4);margin-top:8px'>10:00 출발 · {d.end_time} 일정 종료 예상 · 장소 사이 휴식 시간 포함</div>")


def _profile_from_inputs() -> TravelerProfile:
    ss = st.session_state
    prof = TravelerProfile(
        mobility=list(ss.pl_mob or []), stamina=ss.pl_stamina or "보통", moods=list(ss.pl_moods or ["안정"]),
        must_have=list(ss.pl_must or []), prefer_indoor=bool(ss.pl_indoor), zone=ss.pl_zone or "전체",
        days=DAYS.get(ss.pl_days or "당일", 1), pace=ss.pl_pace or "적당히", request=ss.pl_req.strip(),
    )
    return parse_request(prof.request, prof)


def _rule_plan(places, prof, notice: str = ""):
    with st.spinner("조건에 맞는 장소와 동선을 고르고 있어요"):
        plans = build_itinerary(places, prof)
    st.session_state.plan = {"plans": plans, "profile": prof, "ai": "", "title": _title(prof), "source": "rule",
                             "notice": notice, "created": datetime.now().strftime("%Y-%m-%d %H:%M")}


def _builder(places):
    _defaults()
    ss = st.session_state
    with st.container(key="panel_builder"):
        st.pills("누가 여행하나요?", list(MOBILITY_TYPES), selection_mode="multi", key="pl_mob", format_func=lambda k: MOBILITY_TYPES[k])
        c1, c2 = st.columns(2)
        with c1:
            st.segmented_control("체력", ["낮음", "보통", "높음"], key="pl_stamina")
        with c2:
            st.segmented_control("여행 기간", list(DAYS), key="pl_days")
        st.pills("지금 기분은 어떠세요?", list(llm.FEELINGS), key="pl_feel", help="AI가 지금 마음에 맞는 장소의 분위기를 골라 드려요")
        st.pills("어떤 분위기를 원하세요?", list(MOODS), selection_mode="multi", key="pl_moods", format_func=lambda m: f"{m} · {MOODS[m]}")
        st.pills("꼭 있어야 하는 시설", MUST, selection_mode="multi", key="pl_must", format_func=lambda k: FACILITIES[k])
        c1, c2, c3 = st.columns([1, 1, 1], vertical_alignment="bottom")
        with c1:
            st.segmented_control("하루 일정", list(PACE), key="pl_pace")
        with c2:
            st.selectbox("지역", ["전체"] + ZONES, key="pl_zone")
        with c3:
            st.toggle("실내 위주로", key="pl_indoor", help="비나 더위가 걱정될 때 켜 주세요")
        st.text_input("AI에게 더 알려 주실 것이 있나요? (선택)", key="pl_req", placeholder="예) 아버지가 전복을 좋아하셔요. 요즘 기운이 없으셔서 바다를 보여 드리고 싶어요.")
        go_clicked = st.button("AI 코스 추천받기", type="primary", use_container_width=True, icon=":material/auto_awesome:")
        if not llm.available():
            md("<div style='font-size:15px;color:var(--ink-4);margin-top:8px'>AI 키(GOOGLE_API_KEY)가 없어서 지금은 규칙 기반 엔진으로 추천해요.</div>")

    if go_clicked:
        prof = _profile_from_inputs()
        feeling = ss.pl_feel or ""
        ss.plan = None
        ss.ai_opts = None
        if not llm.available():
            _rule_plan(places, prof, "AI 키가 설정되지 않아 규칙 기반 엔진으로 일정을 짰어요. 키를 넣으면 인지감성 AI 추천으로 바뀌어요.")
            return
        with st.spinner("AI가 지금 기분과 몸 상태에 맞는 테마 3가지를 고르고 있어요"):
            try:
                ss.ai_opts = {"prof": prof, "feeling": feeling, "themes": llm.suggest_themes(places, prof, feeling)}
            except Exception as e:  # 네트워크·키·응답 형식 오류
                _rule_plan(places, prof, f"AI 응답을 받지 못해 규칙 기반 엔진으로 일정을 짰어요. ({type(e).__name__})")


def _make_ai_plan(places, prof, feeling, theme, previous="", feedback="", history=None):
    ss = st.session_state
    try:
        res = llm.plan_course(places, prof, feeling, theme, previous, feedback)
        plans = plan_from_ai(places, res["days"], prof)
    except Exception as e:
        st.error(f"AI 일정을 만들지 못했어요. 잠시 뒤 다시 시도해 주세요. ({type(e).__name__})")
        return False
    if not plans:
        st.error("AI가 고른 장소를 데이터에서 찾지 못했어요. 다시 시도해 주세요.")
        return False
    ss.plan = {"plans": plans, "profile": prof, "ai": res["briefing"], "title": res["title"], "source": "ai", "theme": theme,
               "feeling": feeling, "history": list(history or []) + ([feedback] if feedback else []),
               "created": datetime.now().strftime("%Y-%m-%d %H:%M")}
    return True


def _theme_picker(places):
    ss = st.session_state
    opts = ss.get("ai_opts")
    if not opts or ss.plan:
        return
    section("AI가 고른 테마", f"지금 기분 · {opts['feeling'] or '선택 안 함'}")
    cols = st.columns(len(opts["themes"]) or 1)
    for i, (col, t) in enumerate(zip(cols, opts["themes"])):
        with col:
            mood = f"<span class='chip brand'>{esc(t['mood'])} · {esc(MOODS[t['mood']])}</span>" if t.get("mood") else ""
            route = f"<div class='meta' style='margin-top:12px'>{esc(' → '.join(t['places']))}</div>" if t["places"] else ""
            md(f"<div class='card ai-theme'><span class='eyebrow'>{icon('spark', 14)} 테마 {i + 1}</span>"
               f"<h4>{esc(t['title'])}</h4><p>{esc(t['summary'])}</p>{mood}{route}</div>")
            if st.button("이 테마로 코스 만들기", key=f"ai_theme_{i}", use_container_width=True, type="primary" if i == 0 else "secondary"):
                with st.spinner("AI가 장소마다 무장애 정보를 확인하며 일정을 짜고 있어요"):
                    if _make_ai_plan(places, opts["prof"], opts["feeling"], t):
                        st.rerun()


def _title(prof: TravelerProfile) -> str:
    who = "·".join(MOBILITY_TYPES[m].split()[0] for m in prof.mobility[:2]) or "모두"
    span = {1: "당일", 2: "1박 2일", 3: "2박 3일"}[prof.days]
    zone = "" if prof.zone == "전체" else f"{prof.zone} "
    return f"{zone}{span} {prof.moods[0] if prof.moods else ''} 여행 ({who})"


def _result(places):
    ss = st.session_state
    plan = ss.plan
    if not plan:
        return
    if plan.get("notice"):
        banner("info", "규칙 기반으로 추천했어요", plan["notice"], "spark")
        st.write("")
    if not plan["plans"]:
        banner("caution", "조건에 맞는 장소를 찾지 못했어요", "꼭 있어야 하는 시설이나 지역 조건을 조금 줄여 보세요.")
        return
    is_ai = plan.get("source") == "ai"
    section(plan["title"], ("AI 추천 · " if is_ai else "") + plan["created"])
    if is_ai and plan.get("ai"):
        with st.container(key="panel_ai"):
            t = plan.get("theme", {})
            md(f"<div style='display:flex;gap:8px;align-items:center;font-weight:700;color:var(--ink);margin-bottom:8px'>{icon('spark', 18, 'var(--brand)')} AI 여행 브리핑</div>"
               f"<div style='font-size:17px;color:var(--ink-2);line-height:1.65'>{esc(plan['ai'])}</div>"
               + chips([x for x in [f"지금 기분 · {plan.get('feeling')}" if plan.get("feeling") else "", f"테마 · {t.get('title', '')}" if t.get("title") else ""] if x], "brand")
               + (chips([f"수정 요청 · {h}" for h in plan.get("history", [])]) if plan.get("history") else ""))
        st.write("")
    render_plan(plan["plans"], key="plan")

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("내 여행에 저장", type="primary", use_container_width=True, icon=":material/bookmark:"):
            ss.saved_trips.insert(0, {**plan})
            st.toast("내 여행에 저장했어요")
    with c2:
        st.button("이 일정에 동행 헬퍼 찾기", use_container_width=True, on_click=go, args=("동행 헬퍼",), icon=":material/group:")
    with c3:
        if is_ai and ss.get("ai_opts"):
            if st.button("다른 테마 고르기", use_container_width=True, icon=":material/swap_horiz:"):
                ss.plan = None
                st.rerun()

    if is_ai:
        st.write("")
        with st.form("ai_feedback", clear_on_submit=True, border=False), st.container(key="panel_feedback"):
            md(f"<div style='display:flex;gap:8px;align-items:center;font-weight:700;color:var(--ink);margin-bottom:4px'>{icon('spark', 18, 'var(--brand)')} AI에게 일정 수정 요청하기</div>")
            c1, c2 = st.columns([4, 1], vertical_alignment="bottom")
            fb = c1.text_input("수정 요청", placeholder="예) 2일차는 실내로 바꿔 주세요. 점심은 흑돼지가 좋아요.", label_visibility="collapsed")
            sent = c2.form_submit_button("수정하기", type="primary", use_container_width=True)
        if sent and fb.strip():
            with st.spinner("AI가 요청을 반영해 일정을 다시 짜고 있어요"):
                if _make_ai_plan(places, plan["profile"], plan.get("feeling", ""), plan.get("theme", {}),
                                 plan_to_text(plan["plans"]), fb.strip(), plan.get("history")):
                    st.rerun()


@st.dialog("테마 코스", width="large")
def _theme_dialog(places, theme):
    md(f"<h3 style='margin:0 0 4px'>{esc(theme['title'])}</h3><p style='color:var(--ink-3);margin:0 0 16px'>{esc(theme['desc'])}</p>")
    prof_d = st.session_state.profile
    prof = TravelerProfile(mobility=list(prof_d["mobility"]), stamina=prof_d["stamina"], moods=list(prof_d["moods"]), must_have=list(prof_d["must_have"]))
    plans = plan_from_names(places, theme["places"], prof)
    md(_timeline(plans[0]))
    route_map([(x.scored.place.lat, x.scored.place.lon, x.scored.place.name, x.kind) for x in plans[0].stops], key=f"theme-{theme['title']}", height=340)
    if st.button("이 코스를 내 여행에 저장", type="primary", use_container_width=True):
        st.session_state.saved_trips.insert(0, {"plans": plans, "profile": prof, "ai": "", "title": theme["title"],
                                                "created": datetime.now().strftime("%Y-%m-%d %H:%M")})
        st.rerun()


def _themes(places):
    md("<p style='color:var(--ink-3);margin:8px 0 16px'>현장 무장애 정보를 확인해 미리 짜 둔 하루 코스예요. 내 조건에 맞춰 시간표가 바뀌어요.</p>")
    for i in range(0, len(THEMES), 3):
        cols = st.columns(3)
        for col, t in zip(cols, THEMES[i:i + 3]):
            with col:
                md(f"<div class='card' style='min-height:210px'><span class='chip blue'>{esc(t['tag'])}</span>"
                   f"<h4 style='margin-top:12px !important'>{esc(t['title'])}</h4><p>{esc(t['desc'])}</p>"
                   f"<div class='meta' style='margin-top:10px'>{' → '.join(esc(p) for p in t['places'])}</div></div>")
                if st.button("코스 자세히 보기", key=f"theme_{t['title']}", use_container_width=True):
                    _theme_dialog(places, t)


def render(places):
    page_head("코스 추천", "몸 상태와 지금 기분을 알려 주시면 AI가 마음에 맞는 분위기의 장소를 골라, 계단·경사를 피하고 화장실과 휴식까지 챙긴 동선을 짜 드려요.")
    t1, t2 = st.tabs(["맞춤 코스 만들기", "테마 코스"])
    with t1:
        _builder(places)
        _theme_picker(places)
        _result(places)
    with t2:
        _themes(places)
