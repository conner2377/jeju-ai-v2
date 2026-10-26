"""인지감성 AI 코스 추천 (Gemini).

흐름: 여행자 조건·지금 기분·원하는 분위기 → AI가 서로 다른 테마 3개 제안 → 하나를 고르면
AI가 일정을 짜고, 이후 '2일차를 실내로' 같은 수정 요청도 대화로 반영합니다.

AI에는 장소 데이터베이스(시설·인지감성·주의 사항·접근성 점수)를 함께 넘기고 JSON으로만 답하게 합니다.
돌아온 장소 이름은 데이터베이스와 대조해 없는 장소는 버리므로, 지어낸 장소가 화면에 나오지 않습니다.
키가 없거나 호출이 실패하면 화면은 규칙 기반 엔진(core/recommender.py)으로 대신 일정을 짭니다.
"""
from __future__ import annotations

import json
import re

from core.config import GEMINI_MODEL, get_secret
from core.data import MOODS, Place, facility_labels, grade_of
from core.recommender import MOBILITY_TYPES, PACE, TravelerProfile, score_place

# 지금 기분 → 여행에서 채워 주면 좋은 감정 (인지감성 매칭)
FEELINGS = {
    "편안해요": "지금의 편안함을 오래 이어 가고 싶어요",
    "설레요": "설렘을 더 크게 채워 줄 볼거리가 필요해요",
    "피곤해요": "앉아서 쉬며 회복할 수 있는 곳이 필요해요",
    "불안해요": "자극이 적고 마음이 차분해지는 곳이 필요해요",
    "답답해요": "탁 트인 풍경으로 기분을 환기하고 싶어요",
}

_FALLBACK_THEMES = [
    {"title": "조용한 숲과 정원에서 쉬어 가기", "summary": "평탄한 산책로와 쉼터가 많은 곳 위주로 천천히 걸어요", "mood": "안정", "places": []},
    {"title": "탁 트인 남쪽 바다 바라보기", "summary": "휠체어로 다가갈 수 있는 해안 전망대에서 바다를 즐겨요", "mood": "해방", "places": []},
    {"title": "비와 더위 걱정 없는 실내 감성 여행", "summary": "엘리베이터와 넓은 통로가 있는 전시관과 카페를 이어요", "mood": "몰입", "places": []},
]


def available() -> bool:
    if not get_secret("GOOGLE_API_KEY"):
        return False
    try:
        import langchain_google_genai  # noqa: F401
        return True
    except ImportError:
        return False


def _invoke(prompt: str, temperature: float = 0.7) -> str:
    from langchain_google_genai import ChatGoogleGenerativeAI

    llm = ChatGoogleGenerativeAI(model=GEMINI_MODEL, temperature=temperature, google_api_key=get_secret("GOOGLE_API_KEY"),
                                 transport="rest", timeout=90, max_retries=1)
    out = llm.invoke(prompt).content
    if isinstance(out, list):  # 일부 버전은 조각 목록으로 돌려줍니다
        out = "".join(c.get("text", "") if isinstance(c, dict) else str(c) for c in out)
    return str(out)


def _json(text: str):
    """응답에서 JSON 부분만 꺼냅니다. (```json 블록이나 앞뒤 설명이 붙어 와도 처리)"""
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    body = m.group(1) if m else text
    start = min([i for i in (body.find("{"), body.find("[")) if i >= 0], default=-1)
    if start < 0:
        raise ValueError("JSON 없음")
    end = max(body.rfind("}"), body.rfind("]"))
    return json.loads(body[start:end + 1])


# ---------------------------------------------------------------------------
# 프롬프트 재료
# ---------------------------------------------------------------------------
def profile_text(prof: TravelerProfile, feeling: str = "") -> str:
    mob = ", ".join(MOBILITY_TYPES.get(m, m) for m in prof.mobility) or "특별한 제약 없음"
    moods = ", ".join(f"{m}({MOODS.get(m, '')})" for m in prof.moods) or "상관없음"
    days = {1: "당일", 2: "1박 2일", 3: "2박 3일"}.get(prof.days, f"{prof.days}일")
    lines = [
        f"- 이동·소통 지원: {mob}",
        f"- 체력: {prof.stamina} / 하루 관광지 {PACE.get(prof.pace, 3)}곳 정도({prof.pace})",
        f"- 기간: {days} / 지역: {prof.zone}{' / 실내 위주 희망' if prof.prefer_indoor else ''}",
        f"- 원하는 여행 분위기: {moods}",
    ]
    if feeling:
        lines.append(f"- 지금 기분: {feeling} → {FEELINGS.get(feeling, '')}")
    if prof.must_have:
        from core.data import FACILITIES
        lines.append(f"- 꼭 있어야 하는 시설: {', '.join(FACILITIES[k] for k in prof.must_have)}")
    lines.append(f"- 추가 요청: {prof.request or '없음'}")
    return "\n".join(lines)


def catalog(places: list[Place], prof: TravelerProfile) -> str:
    """AI에게 넘길 장소 데이터베이스. 규칙 엔진의 적합도를 참고값으로 붙여 정렬합니다."""
    relaxed = TravelerProfile(**{**prof.__dict__, "must_have": []})
    rows = []
    for p in places:
        s = score_place(p, relaxed)
        ok_must = all(p.facilities.get(k) for k in prof.must_have)
        grade = grade_of(p.access_score)[0]
        fit = s.score if s else 0
        head = f"{p.name} | {p.category} | {p.zone}{' | 실내' if p.indoor else ''} | 접근성 {grade}등급({p.access_score}) | 참고 적합도 {fit}"
        if not ok_must:
            head += " | 필수 시설 일부 없음"
        extra = ""
        if p.cautions:
            extra += " / 주의: " + ", ".join(p.cautions)
        if p.highlight:
            extra += " / 특징: " + p.highlight
        body = (f"  인지감성: {p.emotion or '-'} (분위기: {', '.join(p.moods) or '-'})\n"
                f"  시설: {', '.join(facility_labels(p)) or '정보 없음'}{extra}")
        rows.append((fit, ok_must, head + "\n" + body))
    rows.sort(key=lambda r: (r[1], r[0]), reverse=True)
    return "\n".join(r[2] for r in rows)


_RULES = """규칙:
- 반드시 [장소 데이터베이스]에 있는 장소 이름만, 적힌 그대로 쓰세요. 없는 장소를 지어내면 안 됩니다.
- 여행자의 '지금 기분'과 '원하는 여행 분위기'를 장소의 인지감성과 맞추는 것이 가장 중요합니다.
- 휠체어·보행 보조가 있으면 접근성 A·B등급과 평탄로가 있는 곳을 우선하고, '주의' 사항이 있는 곳은 피하세요.
- '필수 시설 일부 없음'인 장소는 되도록 쓰지 마세요.
- 하루 동선은 같은 권역 안에서 가까운 곳끼리 묶고, 점심 식당 1곳을 넣고, 체력이 낮으면 카페 휴식도 넣으세요.
- 한국어 존댓말, 차분하고 다정한 톤. 이모지는 쓰지 마세요."""


def suggest_themes(places: list[Place], prof: TravelerProfile, feeling: str = "") -> list[dict]:
    prompt = f"""당신은 시니어·장애인 여행자를 위한 제주 무장애 여행 코디네이터이자 감성 큐레이터입니다.
여행자의 몸 상태와 지금 마음을 읽고, 서로 다른 감정을 채워 주는 여행 테마 3개를 제안하세요.

[여행자]
{profile_text(prof, feeling)}

[장소 데이터베이스] (이름 | 분류 | 권역 | 접근성 | 참고 적합도)
{catalog(places, prof)}

{_RULES}
- 세 테마는 분위기(안정·해방·몰입·활력·따뜻함 중)가 서로 달라야 합니다.
- 각 테마마다 핵심 장소 2~4곳을 고르세요.

아래 JSON 하나로만 답하세요:
{{"themes": [{{"title": "테마 제목(20자 이내)", "summary": "왜 지금 이 여행자에게 맞는지 한 문장", "mood": "안정", "places": ["장소명", "장소명"]}}]}}"""
    data = _json(_invoke(prompt, 0.8))
    themes = data.get("themes", data) if isinstance(data, dict) else data
    names = {p.name for p in places}
    out = []
    for t in themes[:3]:
        if not isinstance(t, dict) or not t.get("title"):
            continue
        out.append({"title": str(t["title"])[:40], "summary": str(t.get("summary", "")),
                    "mood": t.get("mood") if t.get("mood") in MOODS else "", "places": [n for n in t.get("places", []) if n in names][:4]})
    return out or _FALLBACK_THEMES


def plan_course(places: list[Place], prof: TravelerProfile, feeling: str, theme: dict,
                previous: str = "", feedback: str = "") -> dict:
    """AI 일정. 반환: {"title", "briefing", "days": [[{"name","why","tip"}...], ...]}"""
    per_day = PACE.get(prof.pace, 3)
    revise = ""
    if previous and feedback:
        revise = f"""
[지금 일정]
{previous}

[여행자의 수정 요청]
{feedback}
→ 요청한 부분만 바꾸고 나머지는 되도록 그대로 두세요."""
    prompt = f"""당신은 시니어·장애인 여행자를 위한 제주 무장애 여행 코디네이터이자 감성 큐레이터입니다.
선택한 테마로 {prof.days}일 일정을 짜 주세요. 하루에 관광지 {per_day}곳 안팎과 식당 1곳, 필요하면 카페 1곳입니다.

[여행자]
{profile_text(prof, feeling)}

[선택한 테마]
{theme.get('title', '')} — {theme.get('summary', '')} (핵심 장소: {', '.join(theme.get('places', [])) or '자유'})

[장소 데이터베이스] (이름 | 분류 | 권역 | 접근성 | 참고 적합도)
{catalog(places, prof)}
{revise}
{_RULES}
- 각 장소의 why에는 이 여행자의 기분·분위기와 장소의 인지감성이 어떻게 맞는지 한 문장으로 쓰세요.
- tip에는 휠체어·유모차 동선, 주차, 화장실, 쉬어 갈 곳 같은 실전 팁을 한 문장으로 쓰세요.
- 방문 순서대로 나열하세요.

아래 JSON 하나로만 답하세요:
{{"title": "일정 제목(25자 이내)", "briefing": "여행자에게 건네는 2~3문장 요약",
  "days": [{{"day": 1, "stops": [{{"name": "장소명", "why": "추천 이유", "tip": "실전 팁"}}]}}]}}"""
    data = _json(_invoke(prompt, 0.6))
    days = []
    for d in data.get("days", [])[:max(1, prof.days)]:
        stops = [s for s in d.get("stops", []) if isinstance(s, dict) and s.get("name")]
        if stops:
            days.append(stops)
    return {"title": str(data.get("title") or theme.get("title", "AI 맞춤 코스"))[:40],
            "briefing": str(data.get("briefing", "")), "days": days}
