"""온길 · 제주 무장애 여행 (Streamlit)

실행: streamlit run app.py
"""
import streamlit as st

from core.config import APP_NAME, APP_TAGLINE
from core.data import load_places
from core.state import PAGES, init_state
from ui.components import md
from ui.icons import icon
from ui.theme import apply_theme

st.set_page_config(page_title=f"{APP_NAME} · 제주 무장애 여행", page_icon="🍊", layout="wide", initial_sidebar_state="collapsed")


@st.cache_data(show_spinner=False)
def _places():
    return load_places()


init_state()
apply_theme()
places = _places()
if not places:
    st.error("관광지 데이터를 찾지 못했어요. data 폴더에 CSV 파일이 있는지 확인해 주세요.")
    st.stop()

# ---------------------------------------------------------------- 상단 바
with st.container(key="topbar"):
    c1, c2 = st.columns([4, 1], vertical_alignment="center")
    with c1:
        md(f"<div class='brand'><div class='brand-mark'>{icon('tangerine', 19, '#fff', 2.2)}</div>"
           f"<span class='brand-name'>{APP_NAME}</span><span class='brand-sub'>{APP_TAGLINE}</span></div>")
    with c2:
        with st.popover("보기 설정", icon=":material/text_increase:"):
            st.toggle("큰 글씨", key="a11y_large", help="모든 글자와 버튼을 15% 크게 보여줘요")
            st.toggle("고대비", key="a11y_contrast", help="글자와 테두리를 더 진하게 보여줘요")
    if st.session_state.get("nav") not in PAGES:
        st.session_state.nav = st.session_state.page
    st.radio("메뉴", PAGES, key="nav", horizontal=True, label_visibility="collapsed",
             on_change=lambda: st.session_state.update(page=st.session_state.nav))

page = st.session_state.page

if page == "홈":
    from views import home as view
elif page == "코스 추천":
    from views import planner as view
elif page == "장소 찾기":
    from views import explore as view
elif page == "안심 케어":
    from views import care as view
elif page == "동행 헬퍼":
    from views import helper as view
elif page == "이동 지원":
    from views import mobility as view
else:
    from views import mypage as view

view.render(places)

md(f"""<div class='foot'>{APP_NAME}는 한국관광공사 무장애 여행 정보와 자체 조사 데이터를 바탕으로 해요.
현장 상황은 바뀔 수 있으니 방문 전 시설에 한 번 더 확인해 주세요.<br>
웨어러블·배차·헬퍼는 더미 데이터로 동작하며 실제 호출이나 결제는 일어나지 않아요. 응급 상황에서는 바로 119에 연락하세요.</div>""")
