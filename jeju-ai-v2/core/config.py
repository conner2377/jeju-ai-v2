"""앱 전역 설정. API 키는 코드에 직접 쓰지 않고 st.secrets 또는 환경 변수에서만 읽습니다."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

APP_NAME = "혼디 제주"
APP_TAGLINE = "혼디(함께) 걷는 무장애 제주 여행"

GEMINI_MODEL = "gemini-2.5-flash"

# 실제 연락처가 확정되면 입력하세요. 비어 있으면 화면에 표시하지 않습니다.
MOBILITY_CENTER_NAME = "제주 교통약자 이동지원센터"
MOBILITY_CENTER_TEL = ""

# 여행 기준 위치(데모): 서귀포 중앙로 인근
DEMO_GPS = (33.2495, 126.5649)


def get_secret(name: str) -> str:
    """st.secrets → 환경 변수 순서로 비밀 값을 찾습니다. 없으면 빈 문자열."""
    try:
        import streamlit as st
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.environ.get(name, "")
