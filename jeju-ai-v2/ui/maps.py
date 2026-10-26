"""Leaflet 지도 렌더링 (외부 API 키 불필요).

- 배경: OpenStreetMap 표준 타일을 채도를 낮춰 차분하게 표시합니다. (CARTO 타일은 이제 API 키가 필요해 쓰지 않습니다)
- 도로 경로: OSRM 공개 길찾기 서버로 실제 도로 모양을 받아오고, 실패하면 직선으로 그립니다.
- 차량 이동: 지도 안의 자바스크립트가 출발 시각 기준으로 차량 위치를 직접 움직여 화면 깜빡임이 없습니다.
"""
from __future__ import annotations

import json
from math import cos, radians, sqrt

import requests
import streamlit as st
import streamlit.components.v1 as components

BRAND = "#F2650A"
INK = "#191F28"
BLUE = "#2F6FED"
RED = "#D22030"
GRAY = "#8B95A1"

_HEAD = """<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
html,body,#m{height:100%;margin:0;background:#EEF0F2;font-family:'Pretendard Variable',Pretendard,-apple-system,sans-serif}
.leaflet-tile-pane{filter:saturate(.35) brightness(1.04) contrast(.95)}
.leaflet-container{border-radius:20px}
.pin{display:grid;place-items:center;border-radius:50%;color:#fff;font:700 13px/1 sans-serif;border:3px solid #fff;box-shadow:0 2px 8px rgba(0,0,0,.28)}
.tag{background:#fff;border-radius:10px;padding:6px 10px;font:600 12px/1.3 sans-serif;color:#191F28;box-shadow:0 2px 8px rgba(0,0,0,.18);white-space:nowrap}
.pulse{width:18px;height:18px;border-radius:50%;background:%BLUE%;border:3px solid #fff;box-shadow:0 0 0 0 rgba(47,111,237,.5);animation:p 1.8s infinite}
@keyframes p{0%{box-shadow:0 0 0 0 rgba(47,111,237,.45)}100%{box-shadow:0 0 0 18px rgba(47,111,237,0)}}
.car{width:34px;height:34px;border-radius:12px;background:#191F28;display:grid;place-items:center;border:3px solid #fff;box-shadow:0 3px 10px rgba(0,0,0,.3)}
.leaflet-popup-content{font:14px/1.5 sans-serif;margin:10px 14px}
</style></head><body><div id="m"></div><script>
var map=L.map('m',{zoomControl:true,attributionControl:true,scrollWheelZoom:false});
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; OpenStreetMap'}).addTo(map);
function pin(lat,lon,label,color,size,tip,pop){var s=size||30;var m=L.marker([lat,lon],{icon:L.divIcon({className:'',html:'<div class="pin" style="width:'+s+'px;height:'+s+'px;background:'+color+'">'+label+'</div>',iconSize:[s,s],iconAnchor:[s/2,s/2]})}).addTo(map);if(tip)m.bindTooltip(tip);if(pop)m.bindPopup(pop);return m}
function me(lat,lon,tip){return L.marker([lat,lon],{icon:L.divIcon({className:'',html:'<div class="pulse"></div>',iconSize:[18,18],iconAnchor:[9,9]})}).addTo(map).bindTooltip(tip||'현재 위치')}
""".replace("%BLUE%", BLUE)

_TAIL = "</script></body></html>"


def _esc(s: str) -> str:
    return json.dumps(str(s), ensure_ascii=False)


def _show(js: str, height: int) -> None:
    components.html(_HEAD + js + _TAIL, height=height)


# ---------------------------------------------------------------------------
# 도로 경로
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False, ttl=60 * 60 * 24)
def road_path(points: tuple) -> list:
    """[(lat, lon), ...] → 도로를 따라가는 좌표 목록. 실패하면 입력 좌표 그대로."""
    if len(points) < 2:
        return [list(p) for p in points]
    coords = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in points)
    try:
        r = requests.get(f"https://router.project-osrm.org/route/v1/driving/{coords}",
                         params={"overview": "full", "geometries": "geojson"}, timeout=4)
        r.raise_for_status()
        line = r.json()["routes"][0]["geometry"]["coordinates"]
        step = max(1, len(line) // 400)  # 너무 촘촘하면 줄여서 전달
        return [[round(lat, 5), round(lon, 5)] for lon, lat in line[::step]] + [[points[-1][0], points[-1][1]]]
    except Exception:
        return [list(p) for p in points]


def path_km(path: list) -> float:
    total = 0.0
    for (a, b), (c, d) in zip(path, path[1:]):
        dx = (d - b) * 111.32 * cos(radians((a + c) / 2))
        dy = (c - a) * 110.57
        total += sqrt(dx * dx + dy * dy)
    return total


# ---------------------------------------------------------------------------
# 지도 종류
# ---------------------------------------------------------------------------
def route_map(points: list[tuple], key: str = "", height: int = 420, start: tuple | None = None) -> None:
    """points: [(lat, lon, label, kind)] kind: sight|meal|cafe"""
    if not points:
        return
    seq = ([(start[0], start[1])] if start else []) + [(p[0], p[1]) for p in points]
    path = road_path(tuple(seq)) if len(seq) > 1 else []
    js = []
    if path:
        js.append(f"L.polyline({json.dumps(path)},{{color:'#FFFFFF',weight:9,opacity:.9}}).addTo(map);")
        js.append(f"L.polyline({json.dumps(path)},{{color:'{BRAND}',weight:5,opacity:.95}}).addTo(map);")
    if start:
        js.append(f"me({start[0]},{start[1]});")
    for i, p in enumerate(points, 1):
        color = BRAND if p[3] == "sight" else INK
        js.append(f"pin({p[0]},{p[1]},'{i}','{color}',30,{_esc(f'{i}. {p[2]}')},{_esc(p[2])});")
    b = [[p[0], p[1]] for p in points] + ([list(start)] if start else [])
    js.append(f"map.fitBounds({json.dumps(b)},{{padding:[40,40],maxZoom:14}});")
    _show("".join(js), height)


def places_map(places, key: str = "", height: int = 520, highlight: set | None = None) -> None:
    js = []
    for p in places:
        color = BRAND if (highlight and p.id in highlight) or not highlight else INK
        pop = f"<b>{p.name}</b><br>{p.category} · {p.address}"
        js.append(f"pin({p.lat},{p.lon},'','{color}',16,{_esc(p.name)},{_esc(pop)});")
    if places:
        js.append(f"map.fitBounds({json.dumps([[p.lat, p.lon] for p in places])},{{padding:[30,30]}});")
    else:
        js.append("map.setView([33.38,126.55],10);")
    _show("".join(js), height)


def care_map(gps: tuple, alts, er=None, key: str = "", height: int = 380) -> None:
    js = [f"me({gps[0]},{gps[1]});"]
    b = [list(gps)]
    for i, a in enumerate(alts, 1):
        b.append([a.place.lat, a.place.lon])
        js.append(f"L.polyline([[{gps[0]},{gps[1]}],[{a.place.lat},{a.place.lon}]],{{color:'{GRAY}',weight:2,dashArray:'6 6'}}).addTo(map);")
        js.append(f"pin({a.place.lat},{a.place.lon},'{i}','{BRAND}',30,{_esc(f'{i}. {a.place.name} · 약 {a.minutes}분')},{_esc(a.place.name)});")
    for h in er or []:
        b.append([h["lat"], h["lon"]])
        js.append(f"pin({h['lat']},{h['lon']},'+','{RED}',26,{_esc('응급실 · ' + h['name'])},{_esc(h['addr'])});")
    js.append(f"map.fitBounds({json.dumps(b)},{{padding:[40,40],maxZoom:14}});")
    _show("".join(js), height)


def ride_map(car_path: list, trip_path: list, t0_ms: int, search_s: float, approach_s: float, board_s: float, trip_s: float,
             height: int = 380) -> None:
    """차량 이동 애니메이션. 시간 계산은 화면(Python)의 상태 판정과 같은 공식을 씁니다."""
    pickup, dest = trip_path[0], trip_path[-1]
    js = f"""
var car={json.dumps(car_path)}, trip={json.dumps(trip_path)};
var t0={t0_ms}, S={search_s}, A={approach_s}, B={board_s}, T={trip_s};
L.polyline(trip,{{color:'#FFFFFF',weight:9,opacity:.9}}).addTo(map);
L.polyline(trip,{{color:'{BRAND}',weight:5}}).addTo(map);
var approach=L.polyline(car,{{color:'{INK}',weight:4,dashArray:'2 8',opacity:.7}}).addTo(map);
me({pickup[0]},{pickup[1]},'탑승 위치');
pin({dest[0]},{dest[1]},'도착','{INK}',40,'목적지');
var carM=L.marker(car[0],{{icon:L.divIcon({{className:'',html:'<div class="car"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M19 17h2v-4l-2.5-4H14V6H3v11h2"/><circle cx="7.5" cy="17.5" r="2"/><circle cx="16.5" cy="17.5" r="2"/></svg></div>',iconSize:[34,34],iconAnchor:[17,17]}}),zIndexOffset:1000}}).addTo(map);
function cum(p){{var c=[0];for(var i=1;i<p.length;i++){{var dx=(p[i][1]-p[i-1][1])*Math.cos(p[i][0]*Math.PI/180),dy=p[i][0]-p[i-1][0];c.push(c[i-1]+Math.sqrt(dx*dx+dy*dy));}}return c}}
var cc=cum(car), tc=cum(trip);
function at(p,c,f){{f=Math.max(0,Math.min(1,f));var d=f*c[c.length-1];for(var i=1;i<c.length;i++){{if(c[i]>=d){{var r=(d-c[i-1])/((c[i]-c[i-1])||1);return [p[i-1][0]+(p[i][0]-p[i-1][0])*r,p[i-1][1]+(p[i][1]-p[i-1][1])*r]}}}}return p[p.length-1]}}
map.fitBounds(car.concat(trip),{{padding:[40,40],maxZoom:15}});
function step(){{var e=(Date.now()-t0)/1000, pos;
 if(e<S){{pos=car[0]}} else if(e<S+A){{pos=at(car,cc,(e-S)/A)}} else if(e<S+A+B){{pos=trip[0]; approach.setStyle({{opacity:0}})}} else {{pos=at(trip,tc,(e-S-A-B)/T); approach.setStyle({{opacity:0}})}}
 carM.setLatLng(pos);}}
step(); setInterval(step,250);
"""
    _show(js, height)
