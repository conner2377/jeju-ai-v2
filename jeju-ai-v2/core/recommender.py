"""개인 맞춤 무장애 코스 추천 엔진.

1) 여행자 프로필(이동 유형·체력·원하는 분위기·필수 시설)로 장소별 적합도를 계산하고
2) 하루 단위로 가까운 장소끼리 묶은 뒤 최근접 순서로 동선을 정렬하고
3) 점심·카페 휴식을 끼워 넣고 체력에 맞춰 체류·휴식 시간을 조정한 타임라인을 만듭니다.

LLM 없이도 항상 동작하며, 모든 추천에는 사람이 읽을 수 있는 '추천 이유'가 붙습니다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.data import FACILITIES, MOODS, Place, haversine_km, travel_minutes

MOBILITY_TYPES = {
    "휠체어": "휠체어 사용",
    "보행보조": "지팡이·보행기",
    "시니어": "고령자",
    "유모차": "유모차 동반",
    "시각": "시각 지원",
    "청각": "청각 지원",
    "인지": "인지·발달 지원",
}

STAMINA = {"낮음": 0.0, "보통": 0.5, "높음": 1.0}
PACE = {"여유롭게": 2, "적당히": 3, "알차게": 4}  # 하루 관광지 수


@dataclass
class TravelerProfile:
    mobility: list = field(default_factory=lambda: ["휠체어", "시니어"])
    stamina: str = "낮음"
    moods: list = field(default_factory=lambda: ["안정"])
    must_have: list = field(default_factory=lambda: ["restroom", "parking"])
    prefer_indoor: bool = False
    zone: str = "전체"
    days: int = 1
    pace: str = "여유롭게"
    request: str = ""


@dataclass
class Scored:
    place: Place
    score: int
    reasons: list
    warnings: list


# ---------------------------------------------------------------------------
# 1. 장소 적합도
# ---------------------------------------------------------------------------
def _need_fit(p: Place, prof: TravelerProfile) -> tuple[float, list, list]:
    f = p.facilities
    fit, reasons, warns = 0.0, [], []
    m = set(prof.mobility)
    if "휠체어" in m:
        fit += 30 if f["flat"] else -25
        fit += 10 if f["restroom"] else -10
        if f["flat"]:
            reasons.append("휠체어로 다닐 수 있는 평탄로")
        else:
            warns.append("휠체어 동선 정보 부족")
    if "보행보조" in m or "시니어" in m:
        fit += 15 if f["flat"] else -5
        fit += 8 if f["wheelchair_rent"] else 0
        if f["wheelchair_rent"]:
            reasons.append("현장 휠체어 대여 가능")
    if "유모차" in m:
        fit += 12 if (f["stroller"] or f["flat"]) else -8
        fit += 10 if f["lactation"] else 0
        if f["lactation"]:
            reasons.append("수유실 있음")
    if "시각" in m:
        hit = f["braille"] or f["audio"] or f["guide"]
        fit += 20 if hit else -5
        if hit:
            reasons.append("점자·음성·안내 요원 지원")
    if "청각" in m:
        hit = f["sign"] or f["guide"] or p.indoor
        fit += 12 if hit else 0
        if f["sign"]:
            reasons.append("수어·자막 안내")
    if "인지" in m:
        fit += 15 if "안정" in p.moods else (-10 if "활력" in p.moods else 0)
        if "안정" in p.moods:
            reasons.append("조용하고 자극이 적은 환경")
    if f["restroom"] and "장애인 화장실" not in " ".join(reasons):
        reasons.append("장애인 화장실")
    if f["parking"]:
        reasons.append("장애인 주차")
    for c in p.cautions:
        fit -= 20 if "휠체어" in m else 8
        warns.append(c)
    return fit, reasons, warns


def _keyword_bonus(p: Place, text: str) -> tuple[float, list]:
    if not text:
        return 0.0, []
    bonus, reasons = 0.0, []
    hay = f"{p.name} {p.highlight} {p.emotion} {p.category}"
    keywords = {
        "바다|해변|해안|오션": r"바다|해변|해안|오션|해수욕|절리|섭지|용머리",
        "숲|산책|자연": r"숲|자연|휴양림|비자|공원|정원",
        "전복": r"전복",
        "갈치": r"갈치",
        "흑돼지|고기": r"흑돼지|근고기|돼지",
        "국수": r"국수",
        "꽃|정원": r"꽃|정원|매화|카멜리아",
        "미술|전시|미디어|박물관": r"미디어|뮤지엄|박물관|전시|아트",
        "아이|어린이": r"아이|키티|스누피|테디|아쿠아|미로",
        "차|녹차": r"녹차|티|다희연",
    }
    for user_pat, place_pat in keywords.items():
        if re.search(user_pat, text) and re.search(place_pat, hay):
            bonus += 40 if p.category == "맛집" else 18
            reasons.append(f"요청하신 '{re.search(user_pat, text).group(0)}' 반영")
    return bonus, reasons[:1]


def parse_request(text: str, prof: TravelerProfile) -> TravelerProfile:
    """자유 문장에서 조건을 추가로 읽어냅니다. (예: '비 오면 실내', '휠체어 부모님')"""
    if not text:
        return prof
    if re.search(r"휠체어", text) and "휠체어" not in prof.mobility:
        prof.mobility.append("휠체어")
    if re.search(r"부모님|어르신|할머니|할아버지|칠순|팔순|노인", text) and "시니어" not in prof.mobility:
        prof.mobility.append("시니어")
    if re.search(r"유모차|아기|영유아", text) and "유모차" not in prof.mobility:
        prof.mobility.append("유모차")
    if re.search(r"비\s?(오|와|소식)|실내|더위|폭염", text):
        prof.prefer_indoor = True
    if re.search(r"체력이? (안 좋|약|부족)|힘들어|피곤", text):
        prof.stamina = "낮음"
    if m := re.search(r"([1-3])\s*박", text):
        prof.days = min(3, int(m.group(1)) + 1)
    for mood, pat in {"안정": r"힐링|조용|편안|쉬", "해방": r"바다|탁 트|시원", "몰입": r"전시|미디어|볼거리", "활력": r"신나|재미|활기"}.items():
        if re.search(pat, text) and mood not in prof.moods:
            prof.moods.append(mood)
    return prof


def score_place(p: Place, prof: TravelerProfile) -> Scored | None:
    for req in prof.must_have:
        if not p.facilities.get(req):
            return None
    need, reasons, warns = _need_fit(p, prof)
    mood_hit = [m for m in p.moods if m in prof.moods]
    mood = 20 if mood_hit else 0
    if mood_hit:
        reasons.insert(0, f"{MOODS[mood_hit[0]]} 분위기")
    indoor = (15 if p.indoor else -10) if prof.prefer_indoor else 0
    if prof.prefer_indoor and p.indoor:
        reasons.append("날씨 영향 없는 실내")
    zone = 0 if prof.zone in ("전체", p.zone) else -30
    kw, kw_reasons = _keyword_bonus(p, prof.request)
    raw = 8 + p.access_score * 0.45 + need * 0.5 + mood * 0.75 + indoor + zone + kw
    return Scored(p, int(max(0, min(100, raw))), (kw_reasons + reasons)[:4], warns[:2])


def rank(places: list[Place], prof: TravelerProfile, categories: tuple | None = None) -> list[Scored]:
    out = []
    for p in places:
        if categories and p.category not in categories:
            continue
        s = score_place(p, prof)
        if s:
            out.append(s)
    return sorted(out, key=lambda s: s.score, reverse=True)


# ---------------------------------------------------------------------------
# 2. 일정 구성
# ---------------------------------------------------------------------------
SIGHT_CATS = ("자연", "전시·체험", "문화·역사", "휴양")


@dataclass
class Stop:
    kind: str  # sight | meal | cafe
    scored: Scored
    arrive: str
    stay_min: int
    travel_min: int
    travel_km: float
    tips: list


@dataclass
class DayPlan:
    day: int
    stops: list
    total_km: float
    total_travel_min: int
    end_time: str
    trimmed: bool = False


def _fmt(mins: int) -> str:
    return f"{mins // 60:02d}:{mins % 60:02d}"


def _nearest(cands: list[Scored], lat, lon, used: set, max_km=40.0, penalty=1.5) -> Scored | None:
    best, best_v = None, -1e9
    for s in cands:
        if s.place.id in used:
            continue
        d = haversine_km(lat, lon, s.place.lat, s.place.lon)
        if d > max_km:
            continue
        v = s.score - d * penalty  # 적합도와 거리의 균형
        if v > best_v:
            best, best_v = s, v
    return best


def _tips(p: Place, prof: TravelerProfile) -> list:
    tips = []
    if p.parking_note:
        tips.append(f"주차 · {p.parking_note}")
    if p.restroom_note:
        tips.append(f"화장실 · {p.restroom_note}")
    if p.access_note:
        tips.append(f"편의 · {p.access_note}")
    if p.facilities.get("wheelchair_rent") and ("시니어" in prof.mobility or "보행보조" in prof.mobility):
        tips.append("입구에서 휠체어를 빌려 체력을 아끼세요")
    for req in prof.must_have:
        if not p.facilities.get(req):
            hint = {"restroom": "직전 장소에서 화장실을 미리 이용하세요", "parking": "도착 전 주차 가능 여부를 전화로 확인하세요"}.get(req, "방문 전 확인하세요")
            tips.insert(0, f"주의 · {FACILITIES[req]} 정보가 없어요. {hint}")
    for c in p.cautions:
        tips.append(f"주의 · {c}")
    return tips[:4]


def _insert(seq: list, pos: int, kind: str, cands: list, used: set, max_detour: float = 60.0) -> bool:
    before = seq[pos - 1][1].place if pos > 0 else None
    after = seq[pos][1].place if pos < len(seq) else None
    best, best_v = None, -1e9
    for c in cands:
        if c.place.id in used:
            continue
        p = c.place
        d1 = haversine_km(before.lat, before.lon, p.lat, p.lon) if before else 0
        d2 = haversine_km(p.lat, p.lon, after.lat, after.lon) if after else 0
        base = haversine_km(before.lat, before.lon, after.lat, after.lon) if before and after else 0
        detour = d1 + d2 - base
        if detour > max_detour:
            continue
        v = c.score - detour * 3.0
        if v > best_v:
            best, best_v = c, v
    if best:
        seq.insert(pos, (kind, best))
        used.add(best.place.id)
        return True
    return False


def _schedule(sequence, prof, wheelchair, slow, rest):
    clock = 10 * 60
    stops, total_km, total_tm, prev = [], 0.0, 0, None
    for kind, s in sequence:
        km = haversine_km(prev.lat, prev.lon, s.place.lat, s.place.lon) if prev else 0.0
        tm = travel_minutes(km, wheelchair) if prev else 0
        clock += tm + (rest if prev else 0)
        base = {"sight": 70 if s.place.indoor else 60, "meal": 60, "cafe": 45}[kind]
        stay = int(round(base * slow / 5) * 5)
        stops.append(Stop(kind, s, _fmt(clock), stay, tm, round(km, 1), _tips(s.place, prof)))
        clock += stay
        total_km += km
        total_tm += tm
        prev = s.place
    return stops, clock, total_km, total_tm


def _compose_day(seed, sights, meals, meals_any, cafes, cafes_any, used, n_sights):
    """하루 일정 후보를 만든다. used 는 복사본으로 다뤄 실패 시 되돌리기 쉽게 한다."""
    used = set(used) | {seed.place.id}
    day = [seed]
    while len(day) < n_sights:
        last = day[-1].place
        cands = [s for s in sights if haversine_km(s.place.lat, s.place.lon, seed.place.lat, seed.place.lon) <= 25]
        nxt = _nearest(cands, last.lat, last.lon, used, max_km=20, penalty=2.0)
        if not nxt:
            break
        day.append(nxt)
        used.add(nxt.place.id)
    seq = [("sight", s) for s in day]
    _insert(seq, 1, "meal", meals, used, max_detour=25) or _insert(seq, 1, "meal", meals_any, used, max_detour=45)
    cafe_pos = len(seq) - 1 if len(day) >= 3 else len(seq)
    _insert(seq, cafe_pos, "cafe", cafes, used, max_detour=15) or _insert(seq, cafe_pos, "cafe", cafes_any, used, max_detour=15)
    return seq, used


def build_itinerary(places: list[Place], prof: TravelerProfile) -> list[DayPlan]:
    ranked = rank(places, prof)
    sights = [s for s in ranked if s.place.category in SIGHT_CATS]
    meals = [s for s in ranked if s.place.category == "맛집"]
    cafes = [s for s in ranked if s.place.category == "카페"]
    # 필수 시설 조건을 만족하는 식당·카페가 근처에 없을 때 쓸 완화 후보
    ranked_all = rank(places, TravelerProfile(**{**prof.__dict__, "must_have": []}))
    meals_any = [s for s in ranked_all if s.place.category == "맛집"]
    cafes_any = [s for s in ranked_all if s.place.category == "카페"]

    per_day = PACE.get(prof.pace, 3)
    stamina = STAMINA.get(prof.stamina, 0.5)
    wheelchair = "휠체어" in prof.mobility
    slow = 1.25 - 0.25 * stamina  # 체력이 낮을수록 체류 시간 여유
    rest = int(20 - 10 * stamina)  # 장소 사이 휴식
    used: set = set()
    plans: list[DayPlan] = []

    for d in range(1, max(1, prof.days) + 1):
        free = [s for s in sights if s.place.id not in used]
        # 근처(20km)에 식사할 곳이 있는 관광지에서만 하루를 시작합니다
        free = [s for s in free if any(
            m.place.id not in used and haversine_km(s.place.lat, s.place.lon, m.place.lat, m.place.lon) <= 20 for m in meals_any
        )] or free
        if not free:
            break
        prev_pts = [st.scored.place for dp in plans for st in dp.stops]
        if prev_pts:
            # 전날과 다른 권역에서 시작해 같은 장소 주변만 맴돌지 않게 합니다
            seed = max(free, key=lambda s: s.score + min(20, min(haversine_km(s.place.lat, s.place.lon, q.lat, q.lon) for q in prev_pts)))
        else:
            seed = free[0]
        n = per_day
        while True:
            seq, day_used = _compose_day(seed, sights, meals, meals_any, cafes, cafes_any, used, n)
            stops, end, km, tm = _schedule(seq, prof, wheelchair, slow, rest)
            # 하루 일정이 18시 30분을 넘기면 관광지 수를 줄여 다시 짭니다 (피로 누적 방지)
            if end <= 18 * 60 + 30 or n <= 1:
                break
            n -= 1
        used = day_used
        plans.append(DayPlan(d, stops, round(km, 1), tm, _fmt(end), trimmed=n < per_day))
    return plans


def plan_summary(plans: list[DayPlan]) -> dict:
    stops = [st for d in plans for st in d.stops]
    if not stops:
        return {"count": 0, "avg": 0, "km": 0, "travel": 0}
    return {
        "count": len(stops),
        "avg": int(sum(s.scored.place.access_score for s in stops) / len(stops)),
        "km": round(sum(d.total_km for d in plans), 1),
        "travel": sum(d.total_travel_min for d in plans),
    }


def plan_to_text(plans: list[DayPlan]) -> str:
    lines = []
    for d in plans:
        lines.append(f"{d.day}일차")
        for s in d.stops:
            p = s.scored.place
            lines.append(f"- {s.arrive} {p.name} ({p.category}, {s.stay_min}분) / 이유: {', '.join(s.scored.reasons)} / 주의: {', '.join(s.scored.warnings) or '없음'}")
    return "\n".join(lines)


def plan_from_names(places: list[Place], names: list[str], prof: TravelerProfile) -> list[DayPlan]:
    """테마 코스처럼 장소가 정해진 일정에 시간표·팁을 붙입니다."""
    from core.data import find

    relaxed = TravelerProfile(**{**prof.__dict__, "must_have": []})
    seq = []
    for n in names:
        p = find(places, n)
        if not p:
            continue
        s = score_place(p, relaxed)
        kind = "meal" if p.category == "맛집" else "cafe" if p.category == "카페" else "sight"
        seq.append((kind, s))
    stamina = STAMINA.get(prof.stamina, 0.5)
    stops, end, km, tm = _schedule(seq, prof, "휠체어" in prof.mobility, 1.25 - 0.25 * stamina, int(20 - 10 * stamina))
    return [DayPlan(1, stops, round(km, 1), tm, _fmt(end))]


THEMES = [
    {"title": "부모님과 서귀포 정원 산책", "tag": "시니어 · 휠체어", "desc": "턱 없는 정원 두 곳 사이에 단차 없는 식당을 넣은 느긋한 하루",
     "places": ["노리매공원", "춘심이네 본점", "카멜리아힐"]},
    {"title": "비 와도 괜찮은 실내 코스", "tag": "실내 · 날씨 걱정 없음", "desc": "엘리베이터와 넓은 통로가 있는 박물관·전시관 위주로 다녀요",
     "places": ["제주항공우주박물관", "춘심이네 본점", "헬로키티아일랜드"]},
    {"title": "휠체어로 만나는 남쪽 바다", "tag": "휠체어 · 바다", "desc": "주상절리와 용머리해안 뷰포인트까지 휠체어로 다가갈 수 있어요",
     "places": ["주상절리대", "고집돌우럭 중문점", "용머리해안"]},
    {"title": "마음이 차분해지는 동쪽 숲", "tag": "인지 지원 · 조용한 곳", "desc": "자극이 적은 녹차밭과 숲, 여유로운 카페로 천천히 쉬어 가요",
     "places": ["다희연", "비자림", "카페글렌코"]},
    {"title": "감각으로 즐기는 제주", "tag": "시각 · 청각 지원", "desc": "점자 안내와 안내 요원이 있는 곳, 소리와 촉감이 살아 있는 곳을 골랐어요",
     "places": ["넥슨컴퓨터박물관", "돈사돈 본점", "다희연"]},
    {"title": "아이와 함께 표선 나들이", "tag": "유모차 · 가족", "desc": "유모차를 빌릴 수 있는 민속촌과 실내 놀이 체험을 한 번에",
     "places": ["제주민속촌", "다이나믹 메이즈 제주", "카페글렌코"]},
]
