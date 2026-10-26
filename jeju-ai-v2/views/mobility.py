import time
from datetime import datetime

import streamlit as st

from core.config import MOBILITY_CENTER_NAME, MOBILITY_CENTER_TEL
from core.mobility import (APPROACH_S, AUTO_REPLY, BOARD_S, DRIVERS, SEARCH_S, STEPS, TRIP_S, VEHICLES, car_start, estimate,
                           phase)
from core.state import notify
from ui.components import banner, esc, md, page_head, section, stat
from ui.maps import ride_map, road_path

QUICK = ["천천히 와 주세요", "휠체어가 있어요", "입구 앞에 있어요"]


def _flow(step: int) -> str:
    return "<div class='flow'>" + "".join(
        f"<div class='{'done' if i < step else 'now' if i == step else ''}'>{t}</div>" for i, t in enumerate(STEPS)) + "</div>"


def _call(dest, vk, gps, est):
    ss = st.session_state
    start = car_start(*gps)
    ss.ride = {
        "t0": time.time(), "vehicle": vk, "driver": DRIVERS[vk], "dest": dest.id, "dest_name": dest.name,
        "car_path": road_path((start, tuple(gps))), "trip_path": road_path((tuple(gps), (dest.lat, dest.lon))),
        "chat": [], "logged": False, "share": ss.get("mv_share", True), **est,
    }
    if ss.ride["share"]:
        notify(f"보호자 {ss.profile.get('guardian_name') or ''}".strip(), f"{ss.profile.get('name')}님이 {dest.name}(으)로 이동을 시작해요 · {VEHICLES[vk]['label']}", "문자")


@st.fragment(run_every=1)
def _status():
    ss = st.session_state
    ride = ss.ride
    ph = phase(ride)
    d = ride["driver"]
    if ph["status"] == "completed" and not ride["logged"]:
        ride["logged"] = True
        ss.rides.insert(0, {"time": datetime.now().strftime("%m/%d %H:%M"), "dest": ride["dest_name"],
                            "vehicle": VEHICLES[ride["vehicle"]]["label"], "driver": d["name"], "fare": ride["fare"]})
        if ride["share"]:
            notify(f"보호자 {ss.profile.get('guardian_name') or ''}".strip(), f"{ss.profile.get('name')}님이 {ride['dest_name']}에 도착했어요", "문자")
        st.rerun(scope="app")

    # 기사 자동 답장 (메시지 2초 뒤)
    for m in ride["chat"]:
        if m["who"] == "me" and not m.get("answered") and time.time() - m["ts"] > 2:
            m["answered"] = True
            reply = next((r for k, r in AUTO_REPLY.items() if k in m["text"]), "네, 확인했습니다.")
            ride["chat"].append({"who": "them", "text": reply, "ts": time.time(), "at": datetime.now().strftime("%H:%M")})

    remain = f"{ph['remain']}분" if ph["remain"] else ("탑승 중" if ph["status"] == "boarding" else "도착")
    sub = {"searching": "배차까지", "arriving": "도착까지", "riding": "목적지까지"}.get(ph["status"], "")
    md(f"""<div class='card'>
        <div style='display:flex;justify-content:space-between;align-items:flex-start;gap:12px'>
          <div><div style='font-size:22px;font-weight:800;color:var(--ink)'>{esc(ph['label'])}</div>
          <div style='font-size:15px;color:var(--ink-4);margin-top:2px'>현재 위치 → {esc(ride['dest_name'])} · {ride['km']}km</div></div>
          <div style='text-align:right'><div style='font-size:30px;font-weight:800;color:var(--brand-text)'>{remain}</div><div style='font-size:14px;color:var(--ink-4)'>{sub}</div></div>
        </div>{_flow(ph['step'])}</div>""")
    if ph["step"] >= 1:
        st.write("")
        md(f"""<div class='card'><div style='display:flex;gap:16px;align-items:center'>
            <div class='avatar'>{esc(d['name'][0])}</div>
            <div style='flex:1;min-width:0'><div style='font-size:19px;font-weight:700;color:var(--ink)'>{esc(d['name'])} <span style='font-size:15px;color:var(--ink-4);font-weight:500'>★ {d['rating']} · 운행 {d['trips']:,}회</span></div>
            <div style='font-size:15px;color:var(--ink-3)'>{esc(d['car'])} · <b style='color:var(--ink)'>{esc(d['plate'])}</b></div></div></div></div>""")
        if ride["chat"]:
            md("<div class='chat'>" + "".join(
                f"<div class='bubble {m['who']}'>{esc(m['text'])}<time>{m['at']}</time></div>" for m in ride["chat"][-4:]) + "</div>")
        q = st.pills("기사님께 빠른 메시지", QUICK, key=f"q_{len(ride['chat'])}")
        if q:
            ride["chat"].append({"who": "me", "text": q, "ts": time.time(), "at": datetime.now().strftime("%H:%M")})
            st.rerun(scope="fragment")
    st.write("")
    if ph["status"] in ("searching", "arriving"):
        if st.button("호출 취소", use_container_width=True, key="ride_cancel"):
            ride["cancelled"] = True
            st.rerun(scope="app")


def render(places):
    ss = st.session_state
    gps = ss.gps
    page_head("이동 지원", "현재 위치로 휠체어 리프트 차량이나 대형 택시를 불러 목적지까지 편하게 이동하세요.")
    by_id = {p.id: p for p in places}
    names = sorted(places, key=lambda p: p.name)
    ride = ss.ride if ss.ride.get("t0") else None
    ph = phase(ride) if ride else None
    active = ph and ph["status"] not in ("completed", "cancelled")

    if ride and active:
        c1, c2 = st.columns([1, 1.15], gap="large")
        with c1:
            _status()
        with c2:
            ride_map(ride["car_path"], ride["trip_path"], int(ride["t0"] * 1000), SEARCH_S, APPROACH_S, BOARD_S, TRIP_S, height=520)
        return

    if ride and ph["status"] == "completed":
        d = ride["driver"]
        section("이동을 마쳤어요", ride["dest_name"])
        c1, c2 = st.columns([1, 1], gap="large")
        with c1:
            md(f"""<div class='card receipt'>
                <div class='row'><div class='grow d'>차량</div><div class='t'>{esc(VEHICLES[ride['vehicle']]['label'])} · {esc(d['plate'])}</div></div>
                <div class='row'><div class='grow d'>기사</div><div class='t'>{esc(d['name'])}</div></div>
                <div class='row'><div class='grow d'>이동 거리</div><div class='t'>{ride['km']}km</div></div>
                <div class='row'><div class='grow d'>요금 (더미)</div><div class='t' style='font-size:22px;font-weight:800'>{ride['fare']:,}원</div></div></div>""")
        with c2:
            md("<div style='font-size:17px;font-weight:700;color:var(--ink);margin-bottom:6px'>기사님은 어떠셨나요?</div>")
            st.feedback("stars", key=f"ride_rate_{int(ride['t0'])}")
            if st.button("새로 부르기", type="primary", use_container_width=True):
                ss.ride = {"status": "idle"}
                st.rerun()
        return

    if ride and ph["status"] == "cancelled":
        banner("neutral", "호출을 취소했어요", "언제든 다시 부를 수 있어요.", "car")
        st.write("")

    default = ss.pop("ride_dest", None)
    if default and default in by_id:
        ss.mv_dest = default
    ss.setdefault("mv_dest", next((p.id for p in names if p.name == "천지연폭포"), names[0].id))
    ss.setdefault("mv_vehicle", "lift" if "휠체어" in ss.profile["mobility"] else "wide")
    with st.container(key="panel_ride"):
        md("<div style='font-size:15px;color:var(--ink-4);font-weight:600'>출발</div>"
           "<div style='font-size:18px;color:var(--ink);font-weight:600;margin:2px 0 14px'>현재 위치 · 서귀포 중앙로 인근 <span class='demo-tag'>GPS 더미</span></div>")
        st.selectbox("도착", [p.id for p in names], key="mv_dest", format_func=lambda i: f"{by_id[i].name} · {by_id[i].zone}")
        st.segmented_control("차량 종류", list(VEHICLES), key="mv_vehicle", format_func=lambda k: VEHICLES[k]["label"])
        vk = ss.mv_vehicle or "lift"
        md(f"<div style='font-size:15px;color:var(--ink-3);margin:-4px 0 8px'>{esc(VEHICLES[vk]['desc'])}</div>")
        st.toggle("보호자에게 출발·도착 알리기", value=True, key="mv_share")

    dest = by_id[ss.mv_dest]
    est = estimate(vk, gps[0], gps[1], dest.lat, dest.lon)
    st.write("")
    cols = st.columns(4)
    cols[0].markdown(stat("예상 대기", est["wait_min"], "분"), unsafe_allow_html=True)
    cols[1].markdown(stat("이동 시간", est["ride_min"], "분"), unsafe_allow_html=True)
    cols[2].markdown(stat("이동 거리", est["km"], "km"), unsafe_allow_html=True)
    cols[3].markdown(stat("예상 요금", f"{est['fare']:,}", "원", "더미 요금"), unsafe_allow_html=True)
    st.write("")
    if st.button(f"{VEHICLES[vk]['label']} 부르기", type="primary", use_container_width=True, icon=":material/local_taxi:"):
        _call(dest, vk, gps, est)
        st.rerun()

    if ss.rides:
        section("최근 이용")
        md("<div class='card'>" + "".join(
            f"<div class='row'><div class='grow'><div class='t'>{esc(r['dest'])}</div><div class='d'>{esc(r['time'])} · {esc(r['vehicle'])} · {esc(r['driver'])}</div></div>"
            f"<div class='t'>{r.get('fare', 0):,}원</div></div>" for r in ss.rides[:5]) + "</div>")
    if MOBILITY_CENTER_TEL:
        st.write("")
        st.link_button(f"{MOBILITY_CENTER_NAME}에 전화하기", f"tel:{MOBILITY_CENTER_TEL}", use_container_width=True, icon=":material/call:")
