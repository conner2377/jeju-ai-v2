import time
from datetime import datetime

import streamlit as st

from core.condition import LEVELS, MOOD_CARE, Vitals, age_of, alternatives, assess, nearest_er
from core.recommender import TravelerProfile
from core.state import go, notify
from core.wearable import DEVICES, PERMISSIONS, SITUATIONS, WearableStream, sparkline
from ui.components import banner, chips, esc, md, page_head, section
from ui.icons import icon
from ui.maps import care_map

LEVEL_TONE = {"good": ("good", "var(--good)", "shield"), "caution": ("caution", "#C98A00", "clock"),
              "rest": ("rest", "var(--brand)", "coffee"), "danger": ("danger", "var(--bad)", "alert")}
LEVEL_RANK = {"good": 0, "caution": 1, "rest": 2, "danger": 3}
FALL_WAIT = 30  # 낙상 감지 후 자동 신고까지 대기(초)


# ---------------------------------------------------------------------------
# 긴급 도움
# ---------------------------------------------------------------------------
def _guardian(prof) -> str:
    return f"보호자 {prof.get('guardian_name') or '(미등록)'}"


def _send_emergency(prof, gps, reason: str) -> None:
    loc = f"https://www.google.com/maps?q={gps[0]:.5f},{gps[1]:.5f}"
    notify(_guardian(prof), f"[혼디 제주] {prof.get('name')}님 {reason}. 현재 위치 {loc}", "문자")
    for b in st.session_state.bookings:
        if b.get("status") in ("확정", "만나러 가는 중", "동행 중"):
            notify(f"헬퍼 {b['helper']}", f"{prof.get('name')}님 {reason}. 위치 확인 후 연락 바랍니다.", "앱 푸시")
            break


@st.dialog("긴급 도움 요청")
def sos_dialog(gps, prof):
    md("<p style='font-size:18px;color:var(--ink);font-weight:600;margin:0 0 4px'>지금 계신 곳에서 움직이지 말고 도움을 요청하세요.</p>"
       "<p style='color:var(--ink-3);margin:0 0 16px'>아래 버튼을 누르면 휴대폰에서 바로 전화가 걸려요.</p>")
    with st.container(key="sos_dialog"):
        st.link_button("119 응급 신고", "tel:119", type="primary", use_container_width=True, icon=":material/call:")
    if prof.get("guardian_tel"):
        st.link_button(f"보호자 {prof.get('guardian_name') or ''}에게 전화", f"tel:{prof['guardian_tel']}", use_container_width=True, icon=":material/family_restroom:")
    if st.button("보호자·헬퍼에게 위치 알리기", use_container_width=True, icon=":material/share_location:"):
        _send_emergency(prof, gps, "긴급 도움 요청")
        st.success("현재 위치와 함께 알림을 보냈어요.")
    if not prof.get("guardian_tel"):
        md("<p style='font-size:15px;color:var(--ink-4)'>내 여행 › 내 정보에서 보호자 연락처를 등록하면 바로 전화할 수 있어요.</p>")
    md("<div class='section-title'>가까운 응급실</div>")
    md("".join(f"<div class='row'><div class='grow'><div class='t'>{esc(h['name'])}</div><div class='d'>{esc(h['addr'])}</div></div>"
               f"<div style='font-weight:700;color:var(--ink-2)'>{h['km']}km</div></div>" for h in nearest_er(*gps)))


# ---------------------------------------------------------------------------
# 1) 웨어러블 연결 흐름
# ---------------------------------------------------------------------------
def _connect_flow():
    ss = st.session_state
    step = ss.wear_flow
    if step is None:
        md(f"""<div class='hero-card' style='padding:40px 36px;margin-top:8px'>
            <span class='eyebrow'>{icon('heart', 16)} 웨어러블 연동</span>
            <h1 style='font-size:clamp(28px,4vw,40px) !important'>스마트워치를 연결하면<br>여행 내내 곁에서 지켜볼게요</h1>
            <p>심박·산소포화도·스트레스·낙상을 3초마다 확인해, 무리하기 전에 먼저 쉬어 갈 곳을 알려 드려요.</p></div>""")
        c1, _ = st.columns([1, 2])
        if c1.button("웨어러블 연결하기", type="primary", use_container_width=True, icon=":material/watch:"):
            ss.wear_flow = "pick"
            st.rerun()
        section("연결하면 이런 게 달라져요")
        cols = st.columns(3)
        for col, (t, d) in zip(cols, [("실시간 컨디션 점수", "8가지 신호를 모아 0~100점으로 보여 드려요"),
                                      ("먼저 알려 드려요", "상태가 나빠지면 알림과 함께 근처 쉼터를 추천해요"),
                                      ("넘어지면 자동 신고", "30초 안에 응답이 없으면 보호자에게 위치를 보내요")]):
            col.markdown(f"<div class='card'><h4>{t}</h4><p>{d}</p></div>", unsafe_allow_html=True)
        return

    md(f"<div class='flow'>" + "".join(
        f"<div class='{'done' if i < idx else 'now' if i == idx else ''}'>{t}</div>"
        for idx in [["pick", "perm", "sync"].index(step)] for i, t in enumerate(["기기 선택", "권한 동의", "동기화"])) + "</div>")
    st.write("")

    if step == "pick":
        if not ss.get("wear_scanned"):
            with st.spinner("근처 기기를 찾고 있어요"):
                time.sleep(1.2)
            ss.wear_scanned = True
        section(f"기기 {len(DEVICES)}대를 찾았어요", "블루투스 · 시뮬레이션")
        cols = st.columns(len(DEVICES))
        for col, d in zip(cols, DEVICES):
            with col:
                md(f"<div class='device'>{icon('heart', 26, 'var(--brand)')}<div style='font-size:19px;font-weight:700;color:var(--ink);margin-top:10px'>{d['name']}</div>"
                   f"<div style='font-size:15px;color:var(--ink-4)'>{d['model']} · 배터리 {d['battery']}%</div></div>")
                if st.button("이 기기 연결", key=f"pick_{d['id']}", use_container_width=True):
                    ss.wear_device = d
                    ss.wear_flow = "perm"
                    st.rerun()
        if st.button("취소", type="tertiary"):
            ss.wear_flow = None
            st.rerun()

    elif step == "perm":
        d = ss.wear_device
        section(f"{d['name']}에서 받아올 정보를 골라 주세요", "언제든 바꿀 수 있어요")
        with st.container(key="panel_perm"):
            for key, label, why in PERMISSIONS:
                st.checkbox(f"**{label}** · {why}", value=True, key=f"perm_{key}")
        c1, c2 = st.columns([2, 1])
        if c1.button("동의하고 연결", type="primary", use_container_width=True):
            ss.wear_flow = "sync"
            st.rerun()
        if c2.button("이전", use_container_width=True):
            ss.wear_flow = "pick"
            st.rerun()

    elif step == "sync":
        d = ss.wear_device
        bar = st.progress(0, text="기기와 연결하는 중")
        for i, msg in enumerate(["기기와 연결하는 중", "최근 7일 수면 기록 받는 중", "심박·산소포화도 기준값 계산 중", "실시간 측정 시작"]):
            for p in range(25):
                bar.progress(min(100, i * 25 + p + 1), text=msg)
                time.sleep(0.02)
        ss.wear = WearableStream(device=d, connected_at=time.time())
        ss.wear_flow = None
        ss.care_alerts.insert(0, {"time": datetime.now().strftime("%H:%M:%S"), "level": "good", "text": f"{d['name']} 연결됨 · 실시간 측정 시작"})
        st.rerun()


# ---------------------------------------------------------------------------
# 2) 연결 후 대시보드 (3초마다 자동 갱신)
# ---------------------------------------------------------------------------
def _vital(label, value, unit, values, color, note, tone="", lo=None, hi=None, ico="heart"):
    c = {"good": "var(--good)", "warn": "#9A5B00", "bad": "var(--bad)"}.get(tone, "var(--ink-4)")
    return (f"<div class='vital'><div class='k'>{icon(ico, 15)}{label}</div><div class='v'>{value}<small>{unit}</small></div>"
            f"{sparkline(values, color, lo, hi)}<div class='s' style='color:{c}'>{esc(note)}</div></div>")


@st.fragment(run_every=3)
def _live(places):
    ss = st.session_state
    w: WearableStream = ss.wear
    if w is None:
        return
    prof = ss.profile
    gps = ss.gps
    w.tick()
    s = w.latest
    wx = w.weather()
    mood = ss.get("cv_mood") or "편안해요"
    v = Vitals(hr=s.hr, spo2=s.spo2, stress=s.stress, sleep=w.sleep_h, active=w.active_minutes(), temp=wx["temp"], rain=wx["rain"],
               fatigue=ss.get("cv_fatigue", 2), mood=mood)
    a = assess(v, age=age_of(prof.get("age_group", "70대")), resting_hr=int(prof.get("resting_hr", 72)))
    tone, color, ico = LEVEL_TONE[a.level]
    label, msg = LEVELS[a.level]

    # 상태가 바뀌면 알림 기록 · 위험이면 보호자 자동 알림
    prev = ss.get("care_prev_level")
    if prev != a.level:
        ss.care_prev_level = a.level
        if prev is not None:
            worse = LEVEL_RANK[a.level] > LEVEL_RANK[prev]
            ss.care_alerts.insert(0, {"time": datetime.now().strftime("%H:%M:%S"), "level": a.level,
                                      "text": f"컨디션 {LEVELS[prev][0]} → {label} ({a.score}점)"})
            st.toast(f"컨디션이 '{label}' 상태로 {'나빠졌어요' if worse else '좋아졌어요'}", icon="⚠️" if worse else "✅")
            if a.level == "danger":
                _send_emergency(prof, gps, f"컨디션 위험 감지(심박 {s.hr}bpm, 산소포화도 {s.spo2}%)")
                ss.care_alerts.insert(0, {"time": datetime.now().strftime("%H:%M:%S"), "level": "danger", "text": "보호자에게 위치와 상태를 자동으로 알렸어요"})

    # 기기 상태 줄
    md(f"""<div style='display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:4px 0 14px'>
        <span class='live'><i></i>실시간 연결</span>
        <span style='font-size:15px;color:var(--ink-3)'>{esc(w.device['name'])} · 배터리 {s.battery}% · {max(0, w.synced_ago())}초 전 동기화 · 오늘 {s.steps:,}걸음</span></div>""")

    # 낙상 감지
    if w.fall_at and not w.fall_handled:
        left = FALL_WAIT - int(time.time() - w.fall_at)
        if left <= 0:
            w.fall_handled = True
            _send_emergency(prof, gps, "낙상 감지 후 응답 없음")
            ss.care_alerts.insert(0, {"time": datetime.now().strftime("%H:%M:%S"), "level": "danger", "text": "낙상 후 응답이 없어 보호자에게 자동 신고했어요"})
            st.rerun(scope="fragment")
        with st.container(key="panel_fall"):
            md(f"<div style='text-align:center'><div style='font-size:20px;font-weight:700;color:var(--ink)'>넘어지셨나요?</div>"
               f"<div class='countdown'>{left}</div><div style='color:var(--ink-3)'>초 뒤에 보호자에게 자동으로 알려요</div></div>")
            c1, c2 = st.columns(2)
            if c1.button("괜찮아요", use_container_width=True, key="fall_ok"):
                w.fall_handled = True
                ss.care_alerts.insert(0, {"time": datetime.now().strftime("%H:%M:%S"), "level": "caution", "text": "낙상 감지 · 본인이 괜찮다고 응답"})
                st.rerun(scope="fragment")
            with c2, st.container(key="sos_fall"):
                if st.button("도움이 필요해요", type="primary", use_container_width=True, key="fall_help"):
                    w.fall_handled = True
                    _send_emergency(prof, gps, "낙상 후 도움 요청")
                    sos_dialog(gps, prof)

    c1, c2 = st.columns([1.4, 1], gap="large")
    with c1:
        md(f"""<div class='card'><div class='gauge'>
            <div class='ring' style='--p:{a.score};--c:{color}' role='img' aria-label='컨디션 점수 {a.score}점, {label}'>
            <div><div><div class='num'>{a.score}</div><div class='unit'>/ 100</div></div></div></div>
            <div><span class='chip {"good" if a.level == "good" else "bad" if a.level == "danger" else "warn"}' style='font-size:15px'>{icon(ico, 16)} {label}</span>
            <h3 style='margin:10px 0 6px !important;padding:0 !important;font-size:24px !important'>{msg}</h3>
            <p style='margin:0;color:var(--ink-3)'>{datetime.now().strftime('%H:%M:%S')} 기준 · {esc(prof.get('name') or '여행자')}님</p></div></div></div>""")
    with c2:
        with st.container(key="sos"):
            if st.button("긴급 도움 요청", type="primary", use_container_width=True, icon=":material/emergency:"):
                sos_dialog(gps, prof)
        st.button("동행 헬퍼 부르기", use_container_width=True, on_click=go, args=("동행 헬퍼",), icon=":material/group:")
        st.button("휠체어 차량 부르기", use_container_width=True, on_click=go, args=("이동 지원",), icon=":material/accessible:")

    st.write("")
    hr_tone = "bad" if s.hr >= 120 else "warn" if s.hr - int(prof.get("resting_hr", 72)) >= 20 else "good"
    sp_tone = "bad" if s.spo2 < 92 else "warn" if s.spo2 < 95 else "good"
    st_tone = "bad" if s.stress >= 80 else "warn" if s.stress >= 65 else "good"
    sk_tone = "warn" if s.skin >= 35.3 else "good"
    cols = st.columns(4)
    cols[0].markdown(_vital("심박수", s.hr, "bpm", w.series("hr"), "#E5484D", {"bad": "매우 높음", "warn": "평소보다 높음", "good": "안정"}[hr_tone], hr_tone, 60, 110, "heart"), unsafe_allow_html=True)
    cols[1].markdown(_vital("산소포화도", s.spo2, "%", w.series("spo2"), "#2F6FED", {"bad": "낮음 · 확인 필요", "warn": "조금 낮음", "good": "정상"}[sp_tone], sp_tone, 94, 100, "spark"), unsafe_allow_html=True)
    cols[2].markdown(_vital("스트레스", s.stress, "점", w.series("stress"), "#8E4EC6", {"bad": "매우 높음", "warn": "높음", "good": "편안"}[st_tone], st_tone, 20, 70, "leaf"), unsafe_allow_html=True)
    cols[3].markdown(_vital("피부 온도", s.skin, "°C", w.series("skin"), "#F2650A", "더위 주의" if sk_tone == "warn" else "정상", sk_tone, 32.5, 35, "sun"), unsafe_allow_html=True)

    c1, c2 = st.columns([1, 1], gap="large")
    with c1:
        section("지금 이렇게 해 보세요")
        md("<div class='card'>" + "".join(
            f"<div class='row'><div style='width:28px;height:28px;border-radius:50%;background:var(--brand-weak);color:var(--brand-text);display:grid;place-items:center;font-weight:700;font-size:14px;flex:none'>{i}</div>"
            f"<div class='grow t' style='font-weight:500'>{esc(t)}</div></div>" for i, t in enumerate(a.actions, 1)) + "</div>")
    with c2:
        section("판단 근거", "깎인 항목만 표시")
        bad = [f for f in a.factors if f.penalty]
        rows = [f"<div class='factor'><div class='n'>{f.label}</div><div class='val'>{esc(f.value)}</div>"
                f"<div class='note'>{icon('alert', 14, 'var(--bad)')} {esc(f.note)} · -{f.penalty}점</div></div>" for f in bad]
        md("<div class='card'>" + ("".join(rows) or f"<div class='row'>{icon('check', 18, 'var(--good)')}<div class='grow t' style='font-weight:500'>모든 신호가 안정적이에요 · 날씨 {wx['temp']}°C, 강수확률 {wx['rain']}%</div></div>") + "</div>")

    if a.level == "danger":
        section("가까운 응급실", "응급 상황에서는 이동보다 119 신고가 먼저예요")
        md("<div class='card'>" + "".join(
            f"<div class='row'><div class='grow'><div class='t'>{esc(h['name'])}</div><div class='d'>{esc(h['addr'])}</div></div>"
            f"<div style='font-weight:700;color:var(--ink-2)'>{h['km']}km</div></div>" for h in nearest_er(*gps)) + "</div>")
        alts = []
    else:
        tp = TravelerProfile(mobility=list(prof["mobility"]), stamina=prof["stamina"], moods=list(prof["moods"]), must_have=list(prof["must_have"]))
        alts = alternatives(places, tp, a, v, gps[0], gps[1])
    if alts:
        section("지금 가기 좋은 곳", f"{'실내 · ' if not a.outdoor_ok else ''}{MOOD_CARE.get(mood, ('', ''))[1]}")
        c1, c2 = st.columns([1, 1.1], gap="large")
        with c1:
            for i, alt in enumerate(alts, 1):
                p = alt.place
                md(f"<div class='card lift' style='margin-bottom:10px'><div style='display:flex;gap:12px;align-items:flex-start'>"
                   f"<div class='tl-dot' style='position:static;flex:none'>{i}</div><div style='min-width:0'>"
                   f"<div class='meta'>{esc(p.category)} · 약 {alt.minutes}분 ({alt.km}km)</div><h4>{esc(p.name)}</h4>"
                   f"{chips(alt.reasons, 'brand')}</div></div></div>")
                st.button(f"{p.name}(으)로 차량 부르기", key=f"alt_ride_{p.id}", use_container_width=True,
                          on_click=lambda pid=p.id: (st.session_state.update(ride_dest=pid), go("이동 지원")))
        with c2:
            care_map(gps, alts, er=nearest_er(*gps)[:1] if a.level in ("rest", "danger") else None, height=470)

    c1, c2 = st.columns(2, gap="large")
    with c1:
        section("알림 기록")
        dot = {"good": "var(--good)", "caution": "#C98A00", "rest": "var(--brand)", "danger": "var(--bad)"}
        md("<div class='card'>" + ("".join(
            f"<div class='alert-item'><span class='dot' style='background:{dot[x['level']]}'></span><div><div style='font-size:16px;color:var(--ink)'>{esc(x['text'])}</div>"
            f"<div style='font-size:13px;color:var(--ink-4)'>{x['time']}</div></div></div>" for x in ss.care_alerts[:6]) or "<p>아직 알림이 없어요.</p>") + "</div>")
    with c2:
        section("보낸 알림", "시뮬레이션")
        md("<div class='card'>" + ("".join(
            f"<div class='alert-item'><span class='dot' style='background:var(--info)'></span><div><div style='font-size:16px;color:var(--ink)'>{esc(n['to'])} · {esc(n['channel'])}</div>"
            f"<div style='font-size:14px;color:var(--ink-3)'>{esc(n['text'])}</div><div style='font-size:13px;color:var(--ink-4)'>{n['time']}</div></div></div>"
            for n in ss.notify_log[:5]) or "<p style='color:var(--ink-4)'>위험 상황이 생기면 보호자·헬퍼에게 자동으로 알리고 여기에 남겨요.</p>") + "</div>")


def _on_situation():
    w = st.session_state.wear
    if w:
        w.set_situation(st.session_state.cv_situation or "평상시")


def render(places):
    ss = st.session_state
    page_head("안심 케어", "웨어러블에서 받은 신호와 날씨, 지금 기분을 함께 보고 쉬어야 할 때와 대신 가면 좋은 곳을 알려 드려요.")
    if ss.wear is None:
        _connect_flow()
        return

    with st.container(key="panel_sensor"):
        md("<div style='font-size:17px;font-weight:700;color:var(--ink);margin-bottom:4px'>지금 기분은 어떠세요?</div>")
        st.pills("지금 기분", list(MOOD_CARE), key="cv_mood", default="편안해요", label_visibility="collapsed")
        st.select_slider("피곤한 정도", options=[1, 2, 3, 4, 5], key="cv_fatigue", value=2,
                         format_func=lambda x: {1: "1 · 아주 괜찮아요", 2: "2 · 괜찮아요", 3: "3 · 보통", 4: "4 · 피곤해요", 5: "5 · 많이 지쳤어요"}[x])
        with st.expander("시연 도구 · 상황 바꿔 보기"):
            st.segmented_control("웨어러블 상황 시뮬레이터", list(SITUATIONS), key="cv_situation", default=ss.wear.situation, on_change=_on_situation,
                                 help="값이 3초마다 이 상황 쪽으로 서서히 바뀌어요")
            c1, c2 = st.columns(2)
            if c1.button("낙상 감지 테스트", use_container_width=True, icon=":material/personal_injury:"):
                ss.wear.trigger_fall()
            if c2.button("웨어러블 연결 해제", use_container_width=True, icon=":material/link_off:"):
                ss.wear = None
                ss.care_prev_level = None
                st.rerun()
    st.write("")
    _live(places)
