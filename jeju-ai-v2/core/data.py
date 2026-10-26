"""관광지 데이터 통합 모듈.

두 개의 원본 CSV를 하나의 표준 스키마로 합칩니다.
- tour_data.csv      : 수기 큐레이션 데이터 (인지감성·교통편의·대표메뉴 포함)
- api_tour_data.csv  : 한국관광공사 무장애 API 수집 데이터 (원본 시설 정보 포함)

모든 장소는 동일한 시설 플래그(주차·화장실·평탄로 등), 분위기 태그, 실내 여부,
권역, 접근성 점수(0~100)를 갖게 되며 추천·케어·탐색 기능이 이 값을 공통으로 사용합니다.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from math import asin, cos, radians, sin, sqrt

import pandas as pd

from core.config import DATA_DIR

# ---------------------------------------------------------------------------
# 표준 어휘
# ---------------------------------------------------------------------------
FACILITIES = {
    "parking": "장애인 주차",
    "restroom": "장애인 화장실",
    "flat": "평탄로·경사로",
    "elevator": "엘리베이터",
    "wheelchair_rent": "휠체어 대여",
    "stroller": "유모차 대여",
    "lactation": "수유실",
    "braille": "점자·촉각 안내",
    "audio": "음성 안내",
    "sign": "수어·자막 안내",
    "guide": "안내 요원",
}

MOODS = {
    "안정": "마음이 차분해지는",
    "해방": "탁 트여 시원한",
    "몰입": "감각에 푹 빠지는",
    "활력": "즐겁고 활기찬",
    "따뜻함": "포근하고 다정한",
}

CATEGORIES = ["자연", "전시·체험", "문화·역사", "휴양", "맛집", "카페"]

ZONES = ["제주시권", "서귀포권", "동부권", "서부권", "중산간"]

_MOOD_KEYWORDS = {
    "안정": r"안정|편안|고요|힐링|피로 회복|차분|여유|고즈넉|피톤치드",
    "해방": r"해방|바다|뻥|탁 트|휴양|오션|바닷바람|시원",
    "몰입": r"몰입|경외|신비|압도|호기심|미디어|지적|웅장",
    "활력": r"활기|설렘|즐거움|발랄|에너지|북적|동심|트렌디",
    "따뜻함": r"따뜻|포근|향수|위로|정갈|친근|아기자기|로맨틱|대접",
}

# API 데이터는 분류가 '복합 관광지'로 뭉쳐 있어 장소별로 다시 지정합니다.
_API_OVERRIDES = {
    "곽지해수욕장": ("자연", "에메랄드빛 바다와 넓은 백사장이 주는 탁 트인 해방감", "애월 해변 산책"),
    "금능석물원": ("문화·역사", "돌하르방 조각 사이를 걷는 고즈넉하고 차분한 시간", "제주 석조 공예"),
    "금룡사(제주)": ("문화·역사", "조용한 사찰이 주는 고요한 안정감", "김녕 해안 사찰"),
    "금호리조트 제주": ("휴양", "바다를 내려다보며 쉬어 가는 여유로운 휴양", "장애인 객실·식당 보유"),
    "금호리조트 제주아쿠아나": ("휴양", "따뜻한 물속에서 몸을 풀어 주는 편안한 휴식", "실내외 워터파크"),
    "김녕미로공원": ("전시·체험", "미로를 따라 걷는 즐거움과 가벼운 설렘", "랜디 미로 정원"),
    "남원 큰엉해안": ("자연", "해안 절벽 위 산책로에서 느끼는 시원한 해방감", "해안 경승지 산책로"),
    "넥슨컴퓨터박물관": ("전시·체험", "추억의 게임과 컴퓨터가 주는 지적 호기심과 몰입감", "체험형 컴퓨터 전시"),
    "노리매공원": ("자연", "매화와 연못 정원이 주는 편안하고 고요한 힐링", "매화 정원 산책"),
    "다이나믹 메이즈 제주": ("전시·체험", "실내 놀이 체험이 주는 활기찬 즐거움", "실내 미로 체험"),
    "다희연": ("자연", "녹차밭 사이를 걷는 차분하고 여유로운 시간", "녹차밭·동굴 카페"),
    "대포주상절리": ("자연", "신비로운 절경에 압도되는 시각적 몰입감", "육각형 바위기둥 절경"),
    "돈내코 원앙폭포": ("자연", "맑은 계곡물 소리가 주는 시원한 안정감", "계곡·폭포"),
}

# 같은 장소가 두 데이터에 다른 이름으로 들어 있는 경우 하나로 합칩니다. (API 이름 → 큐레이션 이름)
_ALIASES = {"대포주상절리": "주상절리대"}

_TOUR_CATEGORY = {"자연": "자연", "관광": "전시·체험", "맛집": "맛집", "카페": "카페"}

_INDOOR_NAME = r"뮤지엄|박물관|미술관|벙커|아쿠아|리조트|메이즈|아일랜드|국수|해장국|우럭|돈사돈|숙성도|춘심이네|블루보틀|테라로사|카페"


@dataclass
class Place:
    id: str
    name: str
    category: str
    address: str
    lat: float
    lon: float
    facilities: dict = field(default_factory=dict)
    restroom_note: str = ""
    parking_note: str = ""
    access_note: str = ""
    transport: str = ""
    emotion: str = ""
    moods: list = field(default_factory=list)
    highlight: str = ""
    audience: str = ""
    cautions: list = field(default_factory=list)
    indoor: bool = False
    zone: str = ""
    access_score: int = 0
    source: str = ""


# ---------------------------------------------------------------------------
# 유틸리티
# ---------------------------------------------------------------------------
def haversine_km(lat1, lon1, lat2, lon2) -> float:
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * asin(sqrt(a))


def travel_minutes(km: float, wheelchair: bool = False) -> int:
    """도로 우회 계수 1.35, 평균 35km/h, 승하차 준비 시간을 더한 이동 시간 추정."""
    drive = km * 1.35 / 35 * 60
    boarding = 12 if wheelchair else 5
    return int(round(drive + boarding))


def zone_of(lat: float, lon: float) -> str:
    if lon >= 126.70:
        return "동부권"
    if lon <= 126.36:
        return "서부권"
    if lat >= 33.42:
        return "제주시권"
    if lat <= 33.30:
        return "서귀포권"
    return "중산간"


def _moods_from(text: str) -> list:
    found = [m for m, pat in _MOOD_KEYWORDS.items() if re.search(pat, text or "")]
    return found or ["안정"]


def _sections(text: str) -> dict:
    """'[주차] ... [화장실] ...' 형식을 {'주차': '...', '화장실': '...'} 로 분해."""
    return {k.strip(): v.strip() for k, v in re.findall(r"\[([^\]]+)\]\s*([^\[]*)", str(text or ""))}


def _score(f: dict, cautions: list) -> int:
    s = 0
    s += 15 if f.get("parking") else 0
    s += 20 if f.get("restroom") else 0
    s += 25 if f.get("flat") else 0
    s += 10 if f.get("elevator") else 0
    s += 10 if f.get("wheelchair_rent") else 0
    s += 5 if f.get("guide") else 0
    s += min(10, 5 * sum(bool(f.get(k)) for k in ("braille", "audio", "sign")))
    s += 5 if (f.get("stroller") or f.get("lactation")) else 0
    s -= 12 * len(cautions)
    return max(0, min(100, s))


def grade_of(score: int) -> tuple[str, str]:
    """(등급, 설명)"""
    if score >= 75:
        return "A", "누구나 편하게"
    if score >= 55:
        return "B", "대부분 접근 가능"
    if score >= 35:
        return "C", "동행자와 함께"
    return "D", "사전 확인 필요"


# ---------------------------------------------------------------------------
# 원본별 파서
# ---------------------------------------------------------------------------
def _from_curated(row) -> Place:
    sec = _sections(row["상세무장애정보"])
    parking, restroom, benefit = sec.get("주차", ""), sec.get("화장실", ""), sec.get("혜택", "")
    allt = f"{parking} {restroom} {benefit}"
    f = {k: False for k in FACILITIES}
    f["parking"] = bool(re.search(r"장애인|휠체어 전용|전용 주차장|대형 주차장|공영주차장", parking))
    f["restroom"] = bool(re.search(r"장애인|휠체어|완비|넓음", restroom))
    f["flat"] = bool(re.search(r"평탄|단차 없|경사로|평면|휠체어 진입|휠체어 가능|휠체어로|휠체어 탑승|휠체어 테이블|엘리베이터|무장애|공간 확보", allt))
    f["elevator"] = "엘리베이터" in allt
    f["wheelchair_rent"] = bool(re.search(r"휠체어[^ ]*\s*(무료\s*)?대여|휠체어/유모차 무료 대여", allt))
    f["stroller"] = "유모차" in allt
    cautions = []
    if re.search(r"좁음|어두움|흙길|협소", allt + str(row["교통편의"])):
        cautions.append(re.search(r"\(([^)]*)\)", benefit).group(1) if re.search(r"\(([^)]*)\)", benefit) else "일부 구간 이동 주의")
    if "일반 화장실" in restroom or "상가 화장실" in restroom:
        cautions.append("장애인 전용 화장실 아님")
        f["restroom"] = False
    name = str(row["장소명"])
    cat = _TOUR_CATEGORY.get(str(row["분류"]).strip(), "자연")
    emotion = str(row["인지감성"])
    indoor = cat in ("전시·체험", "맛집", "카페") and not re.search(r"가든|테마파크|민속촌|에코랜드", name)
    return Place(
        id="", name=name, category=cat, address=str(row["주소"]),
        lat=float(row["위도"]), lon=float(row["경도"]), facilities=f,
        restroom_note=restroom, parking_note=parking, access_note=benefit,
        transport=str(row["교통편의"]), emotion=emotion, moods=_moods_from(emotion),
        highlight=str(row["대표메뉴_특징"]), audience=str(row["추천대상"]),
        cautions=cautions, indoor=indoor, source="curated",
    )


def _from_api(row) -> Place:
    try:
        raw = ast.literal_eval(str(row["원본데이터"]))
    except (ValueError, SyntaxError):
        raw = {}
    raw = {k: re.sub(r"<br\s*/?>|_무장애 편의시설", " ", str(v or "")).strip() for k, v in raw.items()}
    info = str(row["상세무장애정보"]) if pd.notna(row["상세무장애정보"]) else ""
    f = {k: False for k in FACILITIES}
    f["parking"] = bool(raw.get("parking")) or "장애인 주차" in info
    f["restroom"] = bool(raw.get("restroom")) or "장애인 화장실" in info
    f["flat"] = bool(raw.get("route")) or "무단차" in info or bool(re.search(r"휠체어.*(접근|진입)", raw.get("exit", "")))
    f["elevator"] = bool(raw.get("elevator")) or "엘리베이터" in info
    f["wheelchair_rent"] = bool(raw.get("wheelchair")) or "휠체어 대여" in info
    f["stroller"] = bool(raw.get("stroller")) or "유모차 대여" in info
    f["lactation"] = bool(raw.get("lactationroom")) or "수유실" in info
    f["braille"] = bool(raw.get("braileblock")) or "점자" in info
    f["audio"] = bool(raw.get("audioguide")) or "음성안내" in info
    f["sign"] = bool(raw.get("signguide")) or "수어" in info
    f["guide"] = bool(raw.get("guidehuman")) or "안내요원" in info
    cautions = []
    if "[주의]" in info and "이동 제한" in info:
        cautions.append(raw.get("exit") if "계단" in raw.get("exit", "") else "일부 구간 경사·계단 있음")
    name = str(row["장소명"])
    cat, emotion, highlight = _API_OVERRIDES.get(name, ("자연", "", ""))
    indoor = bool(re.search(_INDOOR_NAME, name)) or cat == "전시·체험" and "미로공원" not in name
    return Place(
        id="", name=name, category=cat, address=str(row["주소"]),
        lat=float(row["위도"]), lon=float(row["경도"]), facilities=f,
        restroom_note=raw.get("restroom", ""), parking_note=raw.get("parking", ""),
        access_note=" · ".join(dict.fromkeys(x for x in (raw.get("route"), raw.get("exit"), raw.get("room"), raw.get("handicapetc")) if x)),
        transport=raw.get("publictransport", ""), emotion=emotion, moods=_moods_from(emotion),
        highlight=highlight, audience="", cautions=cautions, indoor=indoor, source="api",
    )


def _merge(base: Place, extra: Place) -> Place:
    for k, v in extra.facilities.items():
        base.facilities[k] = base.facilities.get(k) or v
    base.lat, base.lon = extra.lat, extra.lon  # API 좌표가 더 정밀함
    base.address = extra.address or base.address
    base.source = "curated+api"
    return base


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------
def load_places() -> list[Place]:
    places: dict[str, Place] = {}
    curated = DATA_DIR / "tour_data.csv"
    api = DATA_DIR / "api_tour_data.csv"
    if curated.exists():
        for _, r in pd.read_csv(curated, encoding="utf-8-sig").iterrows():
            p = _from_curated(r)
            places[p.name] = p
    if api.exists():
        df = pd.read_csv(api, encoding="utf-8-sig").drop_duplicates(subset=["장소명"])
        for _, r in df.iterrows():
            if pd.isna(r["위도"]) or pd.isna(r["경도"]):
                continue
            p = _from_api(r)
            target = _ALIASES.get(p.name, p.name)
            places[target] = _merge(places[target], p) if target in places else p
    out = []
    for i, p in enumerate(sorted(places.values(), key=lambda x: x.name)):
        p.id = f"p{i:03d}"
        p.zone = zone_of(p.lat, p.lon)
        p.access_score = _score(p.facilities, p.cautions)
        out.append(p)
    return out


def facility_labels(p: Place) -> list[str]:
    return [FACILITIES[k] for k, v in p.facilities.items() if v]


def find(places: list[Place], name: str) -> Place | None:
    for p in places:
        if p.name == name:
            return p
    for p in places:
        if name and (name in p.name or p.name in name):
            return p
    return None
