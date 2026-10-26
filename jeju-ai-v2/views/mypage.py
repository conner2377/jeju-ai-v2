import streamlit as st

from core.data import FACILITIES, MOODS
from core.recommender import MOBILITY_TYPES
from core.state import go
from ui.components import empty, esc, md, page_head, section
from views.planner import render_plan

AGES = ["10대", "20대", "30대", "40대", "50대", "60대", "70대", "80대 이상"]


def _profile_form():
    prof = st.session_state.profile
    with st.form("profile_form", border=False):
        with st.container(key="panel_profile_form"):
            c1, c2 = st.columns(2)
            name = c1.text_input("이름(호칭)", prof["name"], max_chars=20)
            age = c2.selectbox("연령대", AGES, index=AGES.index(prof["age_group"]) if prof["age_group"] in AGES else 6)
            mob = st.pills("이동·소통 지원", list(MOBILITY_TYPES), selection_mode="multi", default=prof["mobility"], format_func=lambda k: MOBILITY_TYPES[k])
            c1, c2 = st.columns(2)
            with c1:
                stamina = st.segmented_control("체력", ["낮음", "보통", "높음"], default=prof["stamina"])
            with c2:
                resting = st.number_input("평소 안정 시 심박수 (bpm)", 40, 120, int(prof["resting_hr"]), help="모르면 그대로 두세요. 컨디션 판단 기준이 돼요")
            moods = st.pills("좋아하는 여행 분위기", list(MOODS), selection_mode="multi", default=prof["moods"], format_func=lambda m: f"{m} · {MOODS[m]}")
            must = st.pills("꼭 필요한 시설", ["restroom", "parking", "flat", "elevator"], selection_mode="multi", default=prof["must_have"], format_func=lambda k: FACILITIES[k])
        section("안전 정보", "긴급 도움 요청 때 사용돼요")
        with st.container(key="panel_safety"):
            c1, c2 = st.columns(2)
            gname = c1.text_input("보호자 이름", prof["guardian_name"], placeholder="예) 아들 김민수")
            gtel = c2.text_input("보호자 연락처", prof["guardian_tel"], placeholder="010-0000-0000")
            note = st.text_area("건강 메모", prof["health_note"], placeholder="예) 고혈압약 복용 중, 페니실린 알레르기")
        saved = st.form_submit_button("저장하기", type="primary", use_container_width=True)
    if saved:
        st.session_state.profile.update({
            "name": name.strip() or "여행자", "age_group": age, "mobility": list(mob or []), "stamina": stamina or "보통",
            "moods": list(moods or ["안정"]), "must_have": list(must or []), "resting_hr": int(resting),
            "guardian_name": gname.strip(), "guardian_tel": gtel.strip(), "health_note": note.strip(),
        })
        # 다른 화면의 입력 기본값을 새 프로필로 다시 채우도록 초기화
        for k in [k for k in st.session_state.keys() if str(k).startswith(("pl_", "hp_needs"))]:
            del st.session_state[k]
        st.toast("내 정보를 저장했어요. 추천과 케어에 바로 반영돼요")


@st.dialog("저장한 코스", width="large")
def trip_dialog(trip):
    md(f"<h3 style='margin:0 0 12px !important;padding:0 !important'>{esc(trip['title'])}</h3>")
    render_plan(trip["plans"], key=f"saved-{trip['created']}")
    if trip.get("ai"):
        st.markdown(trip["ai"])


def render(places):
    ss = st.session_state
    page_head("내 여행", "내 정보와 저장한 코스, 예약 내역을 모아 볼 수 있어요.")
    t1, t2, t3 = st.tabs(["내 정보", f"저장한 코스 {len(ss.saved_trips)}", "예약·기록"])
    with t1:
        _profile_form()
    with t2:
        if not ss.saved_trips:
            empty("아직 저장한 코스가 없어요", "코스 추천에서 마음에 드는 일정을 저장해 보세요.")
            st.button("코스 만들러 가기", type="primary", on_click=go, args=("코스 추천",))
        for i, t in enumerate(ss.saved_trips):
            names = [s.scored.place.name for d in t["plans"] for s in d.stops]
            with st.container(key=f"panel_trip_{i}"):
                c1, c2 = st.columns([3, 1], vertical_alignment="center")
                c1.markdown(f"<div style='font-size:18px;font-weight:700;color:var(--ink)'>{esc(t['title'])}</div>"
                            f"<div style='font-size:15px;color:var(--ink-4);margin-top:4px'>{esc(' → '.join(names[:5]))}{' …' if len(names) > 5 else ''}</div>"
                            f"<div style='font-size:14px;color:var(--ink-4);margin-top:4px'>{esc(t['created'])} 저장</div>", unsafe_allow_html=True)
                if c2.button("열기", key=f"trip_open_{i}", use_container_width=True):
                    trip_dialog(t)
    with t3:
        section("동행 헬퍼 예약")
        if ss.bookings:
            md("<div class='card'>" + "".join(
                f"<div class='row'><div class='grow'><div class='t'>{esc(b['helper'])} ({esc(b['role'])})</div>"
                f"<div class='d'>{esc(b['date'])} {esc(b['time'])} · {esc(b['meet'])} · {b['cost']:,}원</div></div><span class='chip {'bad' if b.get('status') == '취소' else 'good'}'>{esc(b.get('status', ''))}</span></div>"
                for b in ss.bookings) + "</div>")
        else:
            empty("예약 내역이 없어요", "동행 헬퍼에서 필요한 도움을 요청할 수 있어요.", "users")
        section("이동 지원 이용")
        if ss.rides:
            md("<div class='card'>" + "".join(
                f"<div class='row'><div class='grow'><div class='t'>{esc(r['dest'])}</div><div class='d'>{esc(r['time'])} · {esc(r['vehicle'])} · {esc(r['driver'])}</div></div></div>"
                for r in ss.rides) + "</div>")
        else:
            empty("이용 내역이 없어요", "이동 지원에서 휠체어 차량을 부를 수 있어요.", "car")
        section("보낸 알림", "보호자·헬퍼 · 시뮬레이션")
        if ss.notify_log:
            md("<div class='card'>" + "".join(
                f"<div class='row'><div class='grow'><div class='t'>{esc(n['to'])} · {esc(n['channel'])}</div><div class='d'>{esc(n['time'])} · {esc(n['text'])}</div></div></div>"
                for n in ss.notify_log[:10]) + "</div>")
        else:
            empty("보낸 알림이 없어요", "위험 상황이나 이동 시작·도착 때 보호자에게 자동으로 알려요.", "phone")
        section("컨디션 알림 기록")
        if ss.care_alerts:
            md("<div class='card'>" + "".join(
                f"<div class='row'><div class='grow'><div class='t'>{esc(c['text'])}</div><div class='d'>{esc(c['time'])}</div></div></div>"
                for c in ss.care_alerts[:10]) + "</div>")
        else:
            empty("기록이 없어요", "안심 케어에서 웨어러블을 연결하면 컨디션 변화가 자동으로 남아요.", "heart")
