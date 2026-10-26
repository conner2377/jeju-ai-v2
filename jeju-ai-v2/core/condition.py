"""여행 중 안전·컨디션 케어 엔진.

웨어러블(심박·SpO2·스트레스·수면·활동 시간), 날씨(기온·강수), 본인 체감(피로도·기분)을
함께 읽어 0~100 컨디션 점수와 4단계 상태를 만들고, 상태에 맞는 행동 지침과
근처 대체 장소(인지감성 매칭)를 제안합니다. 실제 센서 연동 전에는 시나리오 값으로 시연합니다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from core.data import Place, haversine_km, travel_minutes
from core.recommender import TravelerProfile, score_place

LEVELS = {
    "good": ("좋음", "지금처럼 여행하셔도 좋아요"),
    "caution": ("주의", "조금 쉬어 가는 게 좋아요"),
    "rest": ("휴식 필요", "일정을 줄이고 충분히 쉬세요"),
    "danger": ("위험", "지금 바로 도움을 요청하세요"),
}

# 기분 → 추천할 장소 분위기 (인지감성 매칭)
MOOD_CARE = {
    "편안해요": ("안정", "지금의 편안함을 이어갈 수 있는 조용한 곳"),
    "설레요": ("몰입", "설렘을 채워 줄 볼거리가 있는 곳"),
    "피곤해요": ("따뜻함", "앉아서 쉬어 갈 수 있는 아늑한 곳"),
    "불안해요": ("안정", "자극이 적고 마음이 차분해지는 곳"),
    "답답해요": ("해방", "탁 트인 풍경으로 기분을 환기할 수 있는 곳"),
}

SCENARIOS = {
    "평상시": dict(hr=78, spo2=98, stress=35, sleep=7.2, active=30, temp=22, rain=10, fatigue=2, mood="편안해요"),
    "더운 오후": dict(hr=104, spo2=97, stress=58, sleep=6.4, active=75, temp=32, rain=10, fatigue=3, mood="답답해요"),
    "비 예보 · 피로": dict(hr=96, spo2=97, stress=72, sleep=5.4, active=95, temp=21, rain=80, fatigue=4, mood="피곤해요"),
    "응급 의심": dict(hr=138, spo2=89, stress=88, sleep=5.0, active=40, temp=27, rain=20, fatigue=5, mood="불안해요"),
}

# 응급실 운영 의료기관 (좌표는 지도 표시용 근사값입니다. 실제 이동 전 119 안내를 따르세요)
ER_HOSPITALS = [
    {"name": "제주대학교병원", "addr": "제주시 아란13길 15", "lat": 33.4673, "lon": 126.5455},
    {"name": "제주한라병원", "addr": "제주시 도령로 65", "lat": 33.4856, "lon": 126.4858},
    {"name": "서귀포의료원", "addr": "서귀포시 장수로 47", "lat": 33.2568, "lon": 126.5605},
]


@dataclass
class Vitals:
    hr: int = 78
    spo2: int = 98
    stress: int = 35
    sleep: float = 7.0
    active: int = 30
    temp: int = 22
    rain: int = 10
    fatigue: int = 2
    mood: str = "편안해요"


@dataclass
class Factor:
    label: str
    value: str
    penalty: int
    note: str


@dataclass
class Assessment:
    score: int
    level: str
    factors: list = field(default_factory=list)
    actions: list = field(default_factory=list)
    emergency: bool = False
    outdoor_ok: bool = True


def age_of(age_group: str) -> int:
    try:
        return int(str(age_group).replace("대", "").replace("이상", "").strip() or 70) + 5
    except ValueError:
        return 70


def assess(v: Vitals, age: int = 70, resting_hr: int = 72) -> Assessment:
    f: list[Factor] = []
    max_hr = 220 - age
    hr_gap = v.hr - resting_hr
    emergency = False

    if v.hr >= 0.85 * max_hr or v.hr >= 130:
        f.append(Factor("심박수", f"{v.hr}bpm", 40, f"연령 기준 최대 심박의 {int(v.hr / max_hr * 100)}%예요"))
        emergency = v.hr >= 130
    elif hr_gap >= 30:
        f.append(Factor("심박수", f"{v.hr}bpm", 20, f"평소보다 {hr_gap}bpm 높아요"))
    elif hr_gap >= 20:
        f.append(Factor("심박수", f"{v.hr}bpm", 10, f"평소보다 {hr_gap}bpm 높아요"))
    else:
        f.append(Factor("심박수", f"{v.hr}bpm", 0, "안정 범위예요"))

    if v.spo2 < 90:
        f.append(Factor("산소포화도", f"{v.spo2}%", 45, "의료진 확인이 필요한 수준이에요"))
        emergency = True
    elif v.spo2 < 94:
        f.append(Factor("산소포화도", f"{v.spo2}%", 25, "평소보다 낮아요. 앉아서 천천히 호흡하세요"))
    elif v.spo2 < 96:
        f.append(Factor("산소포화도", f"{v.spo2}%", 8, "조금 낮은 편이에요"))
    else:
        f.append(Factor("산소포화도", f"{v.spo2}%", 0, "정상이에요"))

    sp = 20 if v.stress >= 80 else 10 if v.stress >= 65 else 0
    f.append(Factor("스트레스", f"{v.stress}점", sp, "긴장도가 높아요" if sp else "편안한 편이에요"))

    sl = 15 if v.sleep < 5 else 8 if v.sleep < 6.5 else 0
    f.append(Factor("지난밤 수면", f"{v.sleep:.1f}시간", sl, "수면이 부족해요" if sl else "충분해요"))

    ac = 15 if v.active >= 90 else 8 if v.active >= 60 else 0
    f.append(Factor("연속 활동", f"{v.active}분", ac, "쉬지 않고 오래 움직였어요" if ac else "적당해요"))

    senior = 1.3 if age >= 65 else 1.0
    hp = int((15 if v.temp >= 31 else 7 if v.temp >= 28 else 0) * senior)
    f.append(Factor("기온", f"{v.temp}°C", hp, "더위에 지치기 쉬워요" if hp else "활동하기 좋아요"))

    fp = {4: 10, 5: 20}.get(v.fatigue, 0)
    f.append(Factor("체감 피로", f"{v.fatigue}/5", fp, "많이 피곤하다고 하셨어요" if fp else "괜찮다고 하셨어요"))

    mp = 5 if v.mood in ("불안해요", "답답해요") else 0
    f.append(Factor("지금 기분", v.mood, mp, MOOD_CARE.get(v.mood, ("", ""))[1]))

    score = max(0, 100 - sum(x.penalty for x in f))
    if emergency or score < 40:
        level = "danger"
    elif score < 60:
        level = "rest"
    elif score < 80:
        level = "caution"
    else:
        level = "good"
    outdoor_ok = v.rain < 60 and v.temp < 31 and level in ("good", "caution")

    actions = []
    if level == "danger":
        actions += ["움직임을 멈추고 그늘진 곳에 앉으세요", "119에 연락하거나 보호자·헬퍼에게 알리세요", "숨쉬기가 불편하면 상체를 세우고 천천히 호흡하세요"]
    else:
        if level == "rest":
            actions.append("남은 일정을 1곳 줄이고 30분 이상 앉아서 쉬세요")
        elif level == "caution":
            actions.append("다음 장소로 가기 전 15분 정도 쉬어 가세요")
        if hp:
            actions.append("물을 한 컵 이상 드시고 실내로 이동하세요")
        if v.rain >= 60:
            actions.append(f"1시간 안에 비 소식(강수확률 {v.rain}%)이 있어요. 실내 일정으로 바꾸는 게 좋아요")
        if sl:
            actions.append("오늘은 경사·장거리 이동을 피하고 짧은 동선으로 다니세요")
        if sp or mp:
            actions.append("사람이 적고 조용한 곳에서 잠시 마음을 가라앉히세요")
        if level == "good" and not actions:
            actions.append("컨디션이 좋아요. 계획한 일정대로 즐기세요")
    return Assessment(score, level, f, actions, emergency, outdoor_ok)


@dataclass
class Alternative:
    place: Place
    km: float
    minutes: int
    reasons: list


def alternatives(places: list[Place], prof: TravelerProfile, a: Assessment, v: Vitals, lat: float, lon: float, limit=3) -> list[Alternative]:
    target_mood, _ = MOOD_CARE.get(v.mood, ("안정", ""))
    care_prof = TravelerProfile(**{**prof.__dict__, "moods": [target_mood], "prefer_indoor": not a.outdoor_ok, "zone": "전체", "request": ""})
    out = []
    for p in places:
        s = score_place(p, care_prof)
        if not s:
            continue
        km = haversine_km(lat, lon, p.lat, p.lon)
        if not a.outdoor_ok and not p.indoor:
            continue
        value = s.score - km * 2.2 + (12 if target_mood in p.moods else 0) + (8 if p.category == "카페" and v.fatigue >= 4 else 0)
        reasons = []
        if target_mood in p.moods:
            reasons.append(MOOD_CARE[v.mood][1])
        if p.indoor:
            reasons.append("날씨 영향 없는 실내")
        reasons += [r for r in s.reasons if r not in reasons][:2]
        out.append((value, Alternative(p, round(km, 1), travel_minutes(km, "휠체어" in prof.mobility), reasons[:3])))
    out.sort(key=lambda x: x[0], reverse=True)
    return [x[1] for x in out[:limit]]


def nearest_er(lat: float, lon: float) -> list[dict]:
    rows = [{**h, "km": round(haversine_km(lat, lon, h["lat"], h["lon"]), 1)} for h in ER_HOSPITALS]
    return sorted(rows, key=lambda h: h["km"])
