"""교통약자 이동 지원 (더미 배차 서버).

호출 시각(t0)을 기준으로 배차 → 차량 접근 → 도착·탑승 → 운행 → 하차가 자동으로 진행됩니다.
화면은 1초마다 상태를 다시 계산하고, 지도 속 차량은 같은 시간표로 브라우저에서 움직입니다.
시연을 위해 실제 시간을 압축합니다 (접근 24초, 운행 30초).
"""
from __future__ import annotations

import time

from core.data import haversine_km, travel_minutes

VEHICLES = {
    "lift": {"label": "휠체어 리프트 차량", "desc": "휠체어에 탄 채로 리프트로 타요 · 교통약자 전용", "wait": 18, "wheelchair": True, "base": 1500, "per_km": 300},
    "wide": {"label": "대형 승합 택시", "desc": "접이식 휠체어·보행기를 실을 수 있어요", "wait": 10, "wheelchair": False, "base": 4800, "per_km": 1000},
    "taxi": {"label": "일반 택시", "desc": "가장 빨리 배차돼요", "wait": 6, "wheelchair": False, "base": 4800, "per_km": 900},
}

DRIVERS = {
    "lift": {"name": "정우성 기사님", "car": "기아 카니발 리프트", "plate": "제주 12바 3456", "rating": 4.9, "trips": 1284},
    "wide": {"name": "문가영 기사님", "car": "현대 스타리아", "plate": "제주 34자 7788", "rating": 4.8, "trips": 932},
    "taxi": {"name": "이진호 기사님", "car": "현대 쏘나타", "plate": "제주 56아 1029", "rating": 4.7, "trips": 2210},
}

# 실제 소요 시간(초) — 시연용 압축
SEARCH_S, APPROACH_S, BOARD_S, TRIP_S = 4.0, 24.0, 6.0, 30.0

STEPS = ["배차 확인", "차량 이동", "도착·탑승", "운행 중", "하차 완료"]

AUTO_REPLY = {
    "천천히": "네, 안전하게 천천히 가겠습니다.",
    "휠체어": "리프트 준비해 두겠습니다. 탑승까지 도와드릴게요.",
    "입구": "확인했습니다. 입구 앞으로 바로 갈게요.",
}


def estimate(vehicle: str, lat1, lon1, lat2, lon2) -> dict:
    km = haversine_km(lat1, lon1, lat2, lon2)
    v = VEHICLES[vehicle]
    road_km = round(km * 1.35, 1)
    return {
        "km": road_km,
        "ride_min": travel_minutes(km, v["wheelchair"]),
        "wait_min": v["wait"],
        "fare": int(round((v["base"] + v["per_km"] * road_km) / 100) * 100),
    }


def car_start(lat: float, lon: float) -> tuple:
    """배정 차량의 출발 지점 (탑승 위치에서 2~3km 떨어진 곳)."""
    return (round(lat + 0.014, 5), round(lon - 0.018, 5))


def phase(ride: dict, now: float | None = None) -> dict:
    """호출 시각 기준 현재 단계와 남은 시간(분, 화면 표시용)을 계산."""
    if ride.get("cancelled"):
        return {"status": "cancelled", "step": -1, "remain": 0, "label": "호출을 취소했어요"}
    e = (now or time.time()) - ride["t0"]
    S, A, B, T = SEARCH_S, APPROACH_S, BOARD_S, TRIP_S
    if e < S:
        return {"status": "searching", "step": 0, "remain": ride["wait_min"], "label": "가까운 차량을 찾고 있어요", "progress": e / S}
    if e < S + A:
        f = (e - S) / A
        return {"status": "arriving", "step": 1, "remain": max(1, round(ride["wait_min"] * (1 - f))), "label": "기사님이 오고 있어요", "progress": f}
    if e < S + A + B:
        return {"status": "boarding", "step": 2, "remain": 0, "label": "차량이 도착했어요. 탑승을 도와드리고 있어요", "progress": (e - S - A) / B}
    if e < S + A + B + T:
        f = (e - S - A - B) / T
        return {"status": "riding", "step": 3, "remain": max(1, round(ride["ride_min"] * (1 - f))), "label": "목적지로 이동하고 있어요", "progress": f}
    return {"status": "completed", "step": 4, "remain": 0, "label": "목적지에 도착했어요", "progress": 1.0}
