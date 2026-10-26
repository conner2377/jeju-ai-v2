import streamlit as st

from core.data import CATEGORIES, FACILITIES, ZONES, grade_of
from ui.components import banner, chips, esc, grade_legend, map_links, md, page_head, place_card, section
from ui.icons import icon
from ui.maps import route_map, places_map


@st.dialog("장소 정보", width="large")
def place_dialog(p):
    g, gdesc = grade_of(p.access_score)
    md(f"""<div style='display:flex;gap:14px;align-items:center;margin-bottom:12px'>
        <span class='grade {g}' style='width:48px;height:48px;font-size:22px;border-radius:14px'>{g}</span>
        <div><div class='meta' style='font-size:15px;color:var(--ink-4)'>{esc(p.category)} · {esc(p.zone)} · 접근성 {p.access_score}점 ({gdesc})</div>
        <h3 style='margin:2px 0 0 !important;padding:0 !important;font-size:24px !important'>{esc(p.name)}</h3></div></div>
        <p style='color:var(--ink-3);margin:0 0 4px'>{esc(p.emotion)}</p>
        <p style='color:var(--ink-4);font-size:15px;margin:0'>{esc(p.address)}</p>""")
    rows = []
    for k, label in FACILITIES.items():
        ok = p.facilities.get(k)
        rows.append(f"<div style='display:flex;gap:8px;align-items:center;padding:8px 0;font-size:16px;color:{'var(--ink)' if ok else 'var(--ink-4)'}'>"
                    f"{icon('check' if ok else 'chevron', 18, 'var(--good)' if ok else 'var(--line-2)')}{label}"
                    f"<span style='margin-left:auto;font-size:14px'>{'있음' if ok else '정보 없음'}</span></div>")
    c1, c2 = st.columns(2, gap="large")
    with c1:
        md("<div class='section-title' style='margin-top:20px'>편의 시설</div>" + "".join(rows))
    with c2:
        md("<div class='section-title' style='margin-top:20px'>현장 메모</div>")
        notes = [("주차", p.parking_note), ("화장실", p.restroom_note), ("편의", p.access_note), ("교통", p.transport), ("대표", p.highlight)]
        md("".join(f"<div class='row'><div class='grow'><div class='d'>{k}</div><div class='t' style='font-size:16px;font-weight:500'>{esc(v)}</div></div></div>"
                   for k, v in notes if v) or "<p style='color:var(--ink-4)'>등록된 메모가 없어요.</p>")
        if p.cautions:
            banner("caution", "방문 전 확인하세요", esc(" / ".join(p.cautions)))
    route_map([(p.lat, p.lon, p.name, "sight")], key=f"pd-{p.id}", height=280)
    naver, google = map_links(p)
    c1, c2 = st.columns(2)
    c1.link_button("네이버 지도에서 보기", naver, use_container_width=True)
    c2.link_button("구글 지도에서 보기", google, use_container_width=True)


def render(places):
    page_head("장소 찾기", f"제주 무장애 관광지·식당·카페 {len(places)}곳의 편의 시설을 한눈에 비교해 보세요.")
    ss = st.session_state
    with st.container(key="panel_filter"):
        q = st.text_input("장소 이름으로 찾기", placeholder="예) 숲, 박물관, 카페", key="ex_q")
        cats = st.pills("종류", CATEGORIES, selection_mode="multi", key="ex_cat")
        need = st.pills("꼭 있어야 하는 시설", list(FACILITIES), selection_mode="multi", key="ex_need", format_func=lambda k: FACILITIES[k])
        c1, c2, c3 = st.columns(3, vertical_alignment="bottom")
        zone = c1.selectbox("지역", ["전체"] + ZONES, key="ex_zone")
        sort = c2.selectbox("정렬", ["접근성 높은 순", "이름 순"], key="ex_sort")
        indoor = c3.toggle("실내만", key="ex_indoor")

    res = [p for p in places
           if (not q or q.strip() in f"{p.name} {p.category} {p.highlight} {p.emotion}")
           and (not cats or p.category in cats)
           and all(p.facilities.get(n) for n in (need or []))
           and (zone == "전체" or p.zone == zone)
           and (not indoor or p.indoor)]
    res.sort(key=(lambda p: -p.access_score) if sort == "접근성 높은 순" else (lambda p: p.name))

    md(f"<div style='display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin:28px 0 12px'>"
       f"<div class='section-title' style='margin:0'>{len(res)}곳을 찾았어요</div>{grade_legend()}</div>")
    if not res:
        banner("neutral", "조건에 맞는 장소가 없어요", "필터를 하나씩 풀어 보세요.", "search")
        return

    places_map(res, key=f"ex-{len(res)}-{hash(tuple(p.id for p in res)) % 10_000}", height=420)
    st.write("")
    sig = (q, tuple(cats or []), tuple(need or []), zone, sort, indoor)
    if ss.get("ex_sig") != sig:  # 조건이 바뀌면 처음 12곳부터 다시 보여줍니다
        ss.ex_sig, ss.ex_limit = sig, 12
    shown = res[:ss.ex_limit]
    for i in range(0, len(shown), 2):
        cols = st.columns(2)
        for col, p in zip(cols, shown[i:i + 2]):
            with col:
                md(place_card(p))
                if st.button("자세히 보기", key=f"ex_open_{p.id}", use_container_width=True):
                    place_dialog(p)

    if len(res) > len(shown):
        st.button(f"{len(res) - len(shown)}곳 더 보기", use_container_width=True, key="ex_more",
                  on_click=lambda: ss.update(ex_limit=ss.ex_limit + 12))

    section("편의 시설 보유 현황", f"전체 {len(places)}곳 기준")
    rows = []
    for k, label in FACILITIES.items():
        n = sum(p.facilities.get(k, False) for p in places)
        pct = int(n / len(places) * 100)
        rows.append(f"<div style='display:grid;grid-template-columns:130px 1fr 64px;gap:12px;align-items:center;padding:7px 0'>"
                    f"<span style='font-size:15px;color:var(--ink-2);font-weight:600'>{label}</span>"
                    f"<div class='bar' role='img' aria-label='{label} {n}곳 ({pct}%)'><i style='width:{pct}%'></i></div>"
                    f"<span style='font-size:15px;color:var(--ink-3);text-align:right'>{n}곳</span></div>")
    md("<div class='card soft'>" + "".join(rows) + "</div>")
