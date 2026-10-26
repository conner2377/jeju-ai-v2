"""웨어러블 연동 (더미 기기).

실제 기기 대신 '가상 웨어러블'이 3초마다 생체 신호를 보내는 것처럼 동작합니다.
- 연결 흐름: 기기 검색 → 데이터 권한 동의 → 동기화 → 연결됨
- 데이터: 심박·산소포화도·스트레스·피부 온도·걸음 수·배터리 (상황 시뮬레이터에 따라 값이 서서히 변함)
- 이벤트: 낙상 감지 (테스트 버튼으로 발생)
실제 연동 시 `WearableStream.tick()`의 생성 부분만 기기 SDK·헬스 플랫폼 수신값으로 바꾸면 됩니다.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

DEVICES = [
    {"id": "watch-g", "name": "갤럭시 워치", "model": "Watch 7 · 44mm", "battery": 82},
    {"id": "watch-a", "name": "애플 워치", "model": "Series 10 · 46mm", "battery": 67},
    {"id": "band-f", "name": "피트니스 밴드", "model": "Charge 6", "battery": 91},
]

PERMISSIONS = [
    ("hr", "심박수", "1분마다 측정해 과부하를 알려 드려요"),
    ("spo2", "산소포화도", "호흡 이상을 빨리 알아차려요"),
    ("stress", "스트레스", "긴장도가 높으면 쉬어 갈 곳을 추천해요"),
    ("sleep", "수면", "지난밤 수면으로 오늘 일정 강도를 조절해요"),
    ("activity", "걸음·활동 시간", "쉬지 않고 오래 움직이면 알려 드려요"),
    ("fall", "낙상 감지", "넘어지면 보호자에게 자동으로 알려요"),
    ("location", "위치", "응급 시 위치를 공유하고 근처 장소를 찾아요"),
]

# 상황별 목표값 (값이 이 방향으로 천천히 움직임)
SITUATIONS = {
    "평상시": dict(hr=76, spo2=98, stress=32, skin=33.2, temp=22, rain=10, step_rate=0.9),
    "더운 오후": dict(hr=104, spo2=97, stress=58, skin=35.6, temp=32, rain=10, step_rate=1.2),
    "피로 누적": dict(hr=97, spo2=96, stress=74, skin=34.1, temp=21, rain=80, step_rate=0.5),
    "응급 상황": dict(hr=138, spo2=89, stress=88, skin=34.8, temp=27, rain=20, step_rate=0.0),
}

SAMPLE_SEC = 3
HISTORY = 40


@dataclass
class Sample:
    ts: float
    hr: int
    spo2: int
    stress: int
    skin: float
    steps: int
    battery: int


@dataclass
class WearableStream:
    device: dict
    connected_at: float
    situation: str = "평상시"
    sleep_h: float = 6.8
    samples: list = field(default_factory=list)
    active_since: float = 0.0
    fall_at: float | None = None
    fall_handled: bool = False
    rng_seed: int = 7

    def __post_init__(self):
        if not self.samples:
            t = self.connected_at - SAMPLE_SEC * 12
            base = SITUATIONS[self.situation]
            rnd = random.Random(self.rng_seed)
            self.samples = [Sample(t + i * SAMPLE_SEC, base["hr"] + rnd.randint(-4, 4), base["spo2"], base["stress"] + rnd.randint(-5, 5),
                                   base["skin"], 3200 + i * 3, self.device["battery"]) for i in range(12)]
        self.active_since = self.connected_at - 25 * 60

    # ---- 데이터 생성 -------------------------------------------------------
    def tick(self, now: float | None = None) -> None:
        now = now or time.time()
        last = self.samples[-1]
        n = int((now - last.ts) // SAMPLE_SEC)
        if n <= 0:
            return
        target = SITUATIONS[self.situation]
        rnd = random.Random(int(last.ts * 10) ^ self.rng_seed)
        for i in range(min(n, HISTORY)):
            prev = self.samples[-1]
            k = 0.35  # 목표값으로 다가가는 속도
            hr = prev.hr + (target["hr"] - prev.hr) * k + rnd.gauss(0, 2.2)
            spo2 = prev.spo2 + (target["spo2"] - prev.spo2) * k + rnd.gauss(0, 0.35)
            stress = prev.stress + (target["stress"] - prev.stress) * k + rnd.gauss(0, 2.5)
            skin = prev.skin + (target["skin"] - prev.skin) * k + rnd.gauss(0, 0.05)
            steps = prev.steps + max(0, int(target["step_rate"] * SAMPLE_SEC * 1.6 + rnd.gauss(0, 1)))
            battery = max(5, prev.battery - (1 if rnd.random() < 0.02 else 0))
            self.samples.append(Sample(prev.ts + SAMPLE_SEC, int(round(hr)), int(round(min(100, spo2))), int(max(0, min(100, round(stress)))),
                                       round(skin, 1), steps, battery))
        self.samples = self.samples[-HISTORY:]

    def set_situation(self, name: str) -> None:
        self.situation = name
        self.sleep_h = {"평상시": 7.1, "더운 오후": 6.4, "피로 누적": 5.2, "응급 상황": 5.0}[name]
        if name in ("피로 누적", "더운 오후"):
            self.active_since = time.time() - (95 if name == "피로 누적" else 70) * 60
        elif name == "평상시":
            self.active_since = time.time() - 25 * 60

    def trigger_fall(self) -> None:
        self.fall_at = time.time()
        self.fall_handled = False

    # ---- 조회 --------------------------------------------------------------
    @property
    def latest(self) -> Sample:
        return self.samples[-1]

    def series(self, attr: str) -> list:
        return [getattr(s, attr) for s in self.samples]

    def active_minutes(self) -> int:
        return int((time.time() - self.active_since) / 60)

    def weather(self) -> dict:
        t = SITUATIONS[self.situation]
        return {"temp": t["temp"], "rain": t["rain"]}

    def synced_ago(self) -> int:
        return int(time.time() - self.latest.ts)


def sparkline(values: list, color: str, lo: float | None = None, hi: float | None = None, w: int = 200, h: int = 40) -> str:
    """값 목록 → 인라인 SVG 선 그래프 (최근 2분)."""
    if len(values) < 2:
        return ""
    lo = min(values) if lo is None else min(lo, min(values))
    hi = max(values) if hi is None else max(hi, max(values))
    span = (hi - lo) or 1
    pts = [(i * w / (len(values) - 1), h - 4 - (v - lo) / span * (h - 8)) for i, v in enumerate(values)]
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    lx, ly = pts[-1]
    return (f"<svg class='spark' viewBox='0 0 {w} {h}' preserveAspectRatio='none' aria-hidden='true'>"
            f"<path d='{d}' fill='none' stroke='{color}' stroke-width='2' vector-effect='non-scaling-stroke' stroke-linejoin='round' stroke-linecap='round'/>"
            "</svg>")
