"""선택 기능: Gemini로 코스 해설을 덧붙입니다.

키가 없거나 패키지가 없으면 조용히 비활성화되며, 앱의 핵심 기능(추천·케어·매칭)은
모두 규칙 기반 엔진으로 동작합니다. LLM에는 엔진이 고른 장소만 전달해 지어낸 장소가 나오지 않게 합니다.
"""
from __future__ import annotations

from core.config import GEMINI_MODEL, get_secret


def available() -> bool:
    if not get_secret("GOOGLE_API_KEY"):
        return False
    try:
        import langchain_google_genai  # noqa: F401
        return True
    except ImportError:
        return False


def explain_course(plan_text: str, profile_text: str) -> str:
    from langchain_google_genai import ChatGoogleGenerativeAI

    llm = ChatGoogleGenerativeAI(model=GEMINI_MODEL, temperature=0.5, google_api_key=get_secret("GOOGLE_API_KEY"), transport="rest")
    prompt = f"""당신은 제주 무장애 여행 전문 코디네이터입니다.
아래 여행자 정보와 이미 확정된 일정을 바탕으로, 여행자에게 건네는 짧은 안내문을 써 주세요.

[여행자]
{profile_text}

[확정 일정]
{plan_text}

규칙:
- 일정에 없는 장소는 절대 새로 추천하지 마세요.
- 한국어 존댓말, 친근하지만 차분한 톤. 이모지는 쓰지 마세요.
- 형식: 첫 줄에 한 문장 요약. 그다음 '이렇게 다니면 편해요' 아래에 3~5개의 짧은 bullet(이동·화장실·휴식·주차 팁).
- 전체 600자 이내.
"""
    return llm.invoke(prompt).content
