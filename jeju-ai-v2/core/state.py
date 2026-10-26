"""세션 상태 초기화와 화면 간 이동."""
from __future__ import annotations

import streamlit as st


from core.config import DEMO_GPS

PAGES = ["홈", "코스 추천", "장소 찾기", "안심 케어", "동행 헬퍼", "이동 지원", "내 여행"]

DEFAULT_PROFILE = {
    "name": "여행자",
    "age_group": "70대",
    "mobility": ["휠체어", "시니어"],
    "stamina": "낮음",
    "moods": ["안정"],
    "must_have": ["restroom", "parking"],
    "resting_hr": 72,
    "guardian_name": "",
    "guardian_tel": "",
    "health_note": "",
}


def init_state() -> None:
    ss = st.session_state
    ss.setdefault("page", "홈")
    ss.setdefault("profile", dict(DEFAULT_PROFILE))
    ss.setdefault("plan", None)          # 최근 생성한 코스 {"plans":..., "profile":..., "ai":...}
    ss.setdefault("saved_trips", [])     # 저장한 코스
    ss.setdefault("bookings", [])        # 헬퍼 예약
    ss.setdefault("rides", [])           # 이동 지원 이용 내역
    ss.setdefault("ride", {"status": "idle"})
    ss.setdefault("gps", DEMO_GPS)
    ss.setdefault("wear", None)          # 연결된 WearableStream
    ss.setdefault("wear_flow", None)     # 연결 단계: pick | perm | sync
    ss.setdefault("care_alerts", [])     # 상태 변화 알림 이력
    ss.setdefault("notify_log", [])      # 보호자·헬퍼에게 보낸 알림(시뮬레이션)
    ss.setdefault("helper_stats", {})    # 후기 반영된 헬퍼 평점
    ss.setdefault("a11y_large", False)
    ss.setdefault("a11y_contrast", False)


def notify(to: str, text: str, channel: str = "문자") -> None:
    """보호자·헬퍼 알림 발송(시뮬레이션). 실제 서비스에서는 문자/푸시 API 호출 지점입니다."""
    from datetime import datetime
    st.session_state.notify_log.insert(0, {"time": datetime.now().strftime("%H:%M:%S"), "to": to, "text": text, "channel": channel})


def go(page: str) -> None:
    """버튼 on_click 콜백용. 네비게이션 위젯보다 먼저 값을 바꿉니다."""
    st.session_state.page = page
    st.session_state.nav = page
