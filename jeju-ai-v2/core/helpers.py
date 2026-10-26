"""트래블헬퍼 매칭 엔진.

여행자에게 필요한 지원(이동 보조·시니어 케어·수어·시각 안내 등)과 날짜, 활동 권역,
선호 조건을 기준으로 헬퍼별 적합도를 계산하고 '왜 이 헬퍼인지'를 함께 돌려줍니다.
헬퍼 정보는 시연용 가상 데이터입니다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

SKILLS = {
    "transfer": "휠체어 이승·이동 보조",
    "senior": "시니어 케어",
    "sign": "수어 통역",
    "visual": "시각 안내",
    "dementia": "인지 지원",
    "medical": "간호·응급 처치",
    "driving": "리프트 차량 운전",
    "infant": "영유아 돌봄",
    "course": "무장애 동선 안내",
}

# 이동 유형 → 기본으로 필요한 지원
NEED_BY_MOBILITY = {
    "휠체어": ["transfer", "course"],
    "보행보조": ["transfer"],
    "시니어": ["senior"],
    "유모차": ["infant"],
    "시각": ["visual"],
    "청각": ["sign"],
    "인지": ["dementia"],
}

WEEKDAYS = "월화수목금토일"


@dataclass
class Helper:
    id: str
    name: str
    role: str
    years: int
    rating: float
    reviews: int
    skills: list
    zones: list
    days: str  # 활동 요일 (예: "월화수목금")
    rate: int  # 시간당 요금(원)
    langs: list = field(default_factory=list)
    certs: list = field(default_factory=list)
    intro: str = ""


HELPERS = [
    Helper("h01", "김서연", "요양보호사", 6, 4.9, 128, ["transfer", "senior", "course"], ["서귀포권", "서부권"], "월화수목금토", 22000,
           ["한국어"], ["요양보호사 1급", "장애인 활동지원사"], "휠체어 여행 동행 6년. 방문지 동선과 화장실 위치를 미리 확인해 둡니다."),
    Helper("h02", "박준호", "활동지원사", 4, 4.8, 94, ["sign", "transfer", "course"], ["제주시권", "동부권"], "수목금토일", 21000,
           ["한국어", "한국수어"], ["수어통역사", "장애인 활동지원사"], "수어 통역과 이동 보조를 함께 합니다. 청각장애 여행자 동행 경험이 많아요."),
    Helper("h03", "이하늘", "보행 안내사", 5, 5.0, 71, ["visual", "senior", "course"], ["제주시권", "중산간"], "월화수목금", 20000,
           ["한국어", "영어"], ["시각장애인 보행지도사"], "풍경과 공간을 말로 자세히 설명하고 촉각 안내로 함께 걷습니다."),
    Helper("h04", "최민지", "간호사", 9, 4.9, 156, ["medical", "senior", "dementia"], ["서귀포권", "동부권"], "토일", 30000,
           ["한국어", "일본어"], ["간호사 면허", "BLS 응급처치"], "만성질환이 있는 어르신 여행 동행 전문. 복약과 컨디션을 함께 챙깁니다."),
    Helper("h05", "정우성", "특장차 기사 겸 헬퍼", 7, 4.7, 203, ["driving", "transfer"], ["제주시권", "서귀포권", "동부권", "서부권", "중산간"], "월화수목금토일", 28000,
           ["한국어"], ["1종 대형 운전면허", "휠체어 고정 교육 이수"], "휠체어 리프트 차량으로 이동과 승하차를 한 번에 도와드려요."),
    Helper("h06", "한지우", "보육교사", 3, 4.8, 48, ["infant", "course"], ["제주시권", "서부권"], "금토일", 18000,
           ["한국어", "중국어"], ["보육교사 2급"], "아이 동반 가족 여행을 돕습니다. 수유실·유모차 동선을 미리 챙겨요."),
    Helper("h07", "오세린", "치매전문 요양보호사", 8, 4.9, 87, ["dementia", "senior", "transfer"], ["제주시권", "중산간", "동부권"], "월수금토", 24000,
           ["한국어"], ["치매전문교육 이수", "요양보호사 1급"], "낯선 곳에서도 편안하도록 익숙한 대화와 쉬는 시간을 자주 만듭니다."),
    Helper("h08", "강태민", "여행 코디네이터", 5, 4.6, 112, ["course", "senior"], ["서귀포권", "서부권", "중산간"], "월화수목금토일", 17000,
           ["한국어", "영어", "일본어"], ["관광통역안내사"], "무장애 관광지 정보에 밝아 일정 조율과 예약 대행을 맡습니다."),
]


@dataclass
class Match:
    helper: Helper
    score: int
    reasons: list
    missing: list
    available: bool


def needs_for(mobility: list) -> list:
    out = []
    for m in mobility:
        for n in NEED_BY_MOBILITY.get(m, []):
            if n not in out:
                out.append(n)
    return out


def match(needs: list, day: date, zone: str = "전체", min_rating: float = 0.0, budget: int | None = None, stats: dict | None = None) -> list[Match]:
    wd = WEEKDAYS[day.weekday()]
    out = []
    for h in HELPERS:
        rating = rating_of(h, stats or {})[0]
        if rating < min_rating:
            continue
        covered = [n for n in needs if n in h.skills]
        missing = [n for n in needs if n not in h.skills]
        coverage = len(covered) / len(needs) if needs else 1.0
        available = wd in h.days
        zone_ok = zone == "전체" or zone in h.zones
        score = (
            coverage * 50
            + (15 if available else 0)
            + (15 if zone_ok else 0)
            + (rating - 4.0) * 10
            + min(h.years, 10)
        )
        if budget and h.rate > budget:
            score -= 10
        reasons = [SKILLS[n] for n in covered]
        if available:
            reasons.append(f"{day.month}월 {day.day}일({wd}) 가능")
        if zone_ok and zone != "전체":
            reasons.append(f"{zone} 활동")
        out.append(Match(h, int(max(0, min(100, score))), reasons, [SKILLS[n] for n in missing], available))
    return sorted(out, key=lambda m: (m.available, m.score), reverse=True)


def estimate_cost(h: Helper, hours: int) -> int:
    return h.rate * hours


# ---------------------------------------------------------------------------
# 예약 진행 (더미 헬퍼 서버)
# ---------------------------------------------------------------------------
ACCEPT_S = 5      # 요청 후 헬퍼가 수락하기까지(초)
APPROACH_S = 10   # 동행 시작 후 헬퍼가 만날 곳에 도착하기까지(초)
CHECKIN_S = 20    # 동행 중 헬퍼가 컨디션을 묻는 시점(초)
FLOW = ["요청", "수락", "만나러 가는 중", "동행 중", "완료"]

HELPER_REPLY = [
    ("화장실", "가까운 장애인 화장실 위치를 미리 확인해 둘게요. 필요하시면 언제든 말씀해 주세요."),
    ("약", "복약 시간 알려 주시면 제가 같이 챙길게요."),
    ("휠체어", "휠체어 이승 보조 가능합니다. 차량 탑승도 도와드릴게요."),
    ("늦", "괜찮아요. 천천히 오셔도 기다리고 있을게요."),
    ("어디", "말씀하신 만날 곳 입구 앞에서 주황색 조끼를 입고 기다릴게요."),
]


def booking_status(b: dict, now: float) -> str:
    if b.get("cancelled"):
        return "취소"
    if b.get("ended_at"):
        return "완료"
    if b.get("started_at"):
        return "동행 중" if now - b["started_at"] >= APPROACH_S else "만나러 가는 중"
    return "수락" if now - b["requested_at"] >= ACCEPT_S else "요청"


def helper_reply(text: str) -> str:
    for k, r in HELPER_REPLY:
        if k in text:
            return r
    return "네, 확인했어요. 당일에 편하게 말씀해 주세요."


def rating_of(h: Helper, stats: dict) -> tuple[float, int]:
    s = stats.get(h.id)
    if not s:
        return h.rating, h.reviews
    total = h.rating * h.reviews + sum(s)
    n = h.reviews + len(s)
    return round(total / n, 2), n
