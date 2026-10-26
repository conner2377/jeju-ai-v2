"""한국관광공사 무장애 여행 API(KorWithService2)로 제주 관광지 데이터를 다시 수집합니다.

사용법:
    TOUR_API_KEY=발급받은키 python scripts/collect_tour_data.py
결과는 data/api_tour_data.csv 로 저장되며, 앱은 다음 실행 때 자동으로 반영합니다.
"""
import os
import re
import sys
import time
from pathlib import Path

import pandas as pd
import requests

# =====================================================================
# [설정 및 환경 변수]
# =====================================================================
API_KEY = os.environ.get("TOUR_API_KEY", "")
OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "api_tour_data.csv"
BASE_URL = "https://apis.data.go.kr/B551011/KorWithService2"
AREA_CODE_JEJU = "39"  

# =====================================================================
# [테마 분류 알고리즘] 텍스트 기반 카테고리 자동 할당
# =====================================================================
def categorize_place(title, desc_data):
    """
    장소명과 설명 텍스트를 분석하여 적절한 관광 테마(분류)를 부여합니다.
    """
    combined_text = str(title) + " " + str(desc_data)
    
    if re.search(r'숲|오름|해변|바다|폭포|공원|자연|생태|수목원|계곡|동굴', combined_text):
        return "🌳 자연 및 생태"
    elif re.search(r'미술|박물관|전시|기념관|갤러리|센터|역사', combined_text):
        return "🏛️ 전시 및 관람"
    elif re.search(r'체험|테마|랜드|시장|마을|레저|테마파크', combined_text):
        return "🎢 테마 및 체험"
    elif re.search(r'카페|다원|휴양|온천|정원', combined_text):
        return "☕ 휴식 및 힐링"
    else:
        return "📍 복합 관광지"

# =====================================================================
# [점수 알고리즘] 무장애 통합 배점표
# =====================================================================
def score_facility(fac_data, desc_data):
    score_details = {
        "A_mobility_elderly": 0,  
        "B_infant_family": 0,     
        "C_sensory_impaired": 0,  
        "F_risk_penalty": 0       
    }
    found_keywords = []
    combined_text = str(fac_data) + " " + str(desc_data)

    if fac_data.get('wheelchair') != "" or re.search(r'휠체어.*대여|휠체어.*가능', combined_text):
        score_details["A_mobility_elderly"] += 8
        found_keywords.append("[이동] 휠체어 대여")
    if fac_data.get('route') != "" or re.search(r'평지|단차 없음|완만|휠체어 접근|무단차', combined_text):
        score_details["A_mobility_elderly"] += 10
        found_keywords.append("[이동] 무단차/평탄한 길")
    if fac_data.get('elevator') != "" or '엘리베이터' in combined_text or '승강기' in combined_text:
        score_details["A_mobility_elderly"] += 5
        found_keywords.append("[이동] 엘리베이터")
    if fac_data.get('parking') != "" or re.search(r'장애인.*주차|전용.*주차', combined_text):
        score_details["A_mobility_elderly"] += 5
        found_keywords.append("[편의] 장애인 주차구역")
    if fac_data.get('restroom') != "" or '장애인 화장실' in combined_text:
        score_details["A_mobility_elderly"] += 5
        found_keywords.append("[편의] 장애인 화장실")

    if fac_data.get('stroller') != "" or re.search(r'유모차.*대여|유모차.*가능', combined_text):
        score_details["B_infant_family"] += 8
        found_keywords.append("[영유아] 유모차 대여")
    if fac_data.get('lactationroom') != "" or '수유실' in combined_text:
        score_details["B_infant_family"] += 8
        found_keywords.append("[영유아] 수유실")
    if fac_data.get('babysparechair') != "" or '기저귀' in combined_text or '유아용' in combined_text:
        score_details["B_infant_family"] += 5
        found_keywords.append("[영유아] 유아 편의시설")

    if fac_data.get('braileblock') != "" or '점자' in combined_text:
        score_details["C_sensory_impaired"] += 4
        found_keywords.append("[시각] 점자블록/안내")
    if fac_data.get('audioguide') != "" or '오디오가이드' in combined_text or '음성안내' in combined_text:
        score_details["C_sensory_impaired"] += 3
        found_keywords.append("[시각] 음성안내")
    if fac_data.get('signguide') != "" or '수어' in combined_text or '수화' in combined_text or '자막' in combined_text:
        score_details["C_sensory_impaired"] += 3
        found_keywords.append("[청각] 수어/자막안내")
    if fac_data.get('guidehuman') != "" or '안내요원' in combined_text:
        score_details["C_sensory_impaired"] += 2
        found_keywords.append("[공통] 안내요원 배치")

    if re.search(r'경사|흙길|돌길|자갈|계단이 많|가파른', combined_text):
        score_details["F_risk_penalty"] -= 10
        found_keywords.append("🚨 [주의] 휠체어/유모차 이동 제한(경사/계단)")
    if '사전 예약 필수' in combined_text or '예약해야' in combined_text:
        score_details["F_risk_penalty"] -= 2
        found_keywords.append("🚨 [주의] 사전예약 필요")

    total_score = sum(score_details.values())
    
    if total_score >= 35: grade = "A. 적극 추천 (모두에게 편안함)"
    elif total_score >= 20: grade = "B. 추천 (대부분 접근 가능)"
    elif total_score >= 5: grade = "C. 조건부 추천 (동반자 필요)"
    else: grade = "D. 주의 필요 (이동 제약 큼)"

    return total_score, grade, " / ".join(set(found_keywords))


# =====================================================================
# [API 연동 파이프라인] 데이터 요청 및 가공
# =====================================================================
def fetch_jeju_tour_data(max_items=30):
    print(f"제주도 무장애 관광지 데이터 수집 시작 (목표: {max_items}개)...")
    dataset = []
    
    search_url = f"{BASE_URL}/areaBasedList2"
    full_url = (f"{search_url}?"
                f"ServiceKey={API_KEY}&"
                f"numOfRows={max_items}&"
                f"pageNo=1&"
                f"MobileOS=ETC&"
                f"MobileApp=JejuBarrierFree&"
                f"_type=json&"
                f"areaCode={AREA_CODE_JEJU}&"
                f"contentTypeId=12")
    
    try:
        response = requests.get(full_url, timeout=15)
        if response.status_code != 200:
            print(f"❌ 서버 응답 에러: {response.status_code}")
            return None

        data = response.json()
        items = data.get('response', {}).get('body', {}).get('items', {}).get('item', [])
        
        if not items:
            print("❌ 데이터가 없습니다.")
            return None
            
        print(f"✅ {len(items)}개의 관광지 목록을 가져왔습니다.")
        
        for item in items:
            content_id = item.get('contentid')
            title = item.get('title')
            addr = item.get('addr1')
            mapx = item.get('mapx')
            mapy = item.get('mapy')
            
            # 공통 정보 (개요)
            detail_url = f"{BASE_URL}/detailCommon2"
            detail_params = {"ServiceKey": API_KEY, "MobileOS": "ETC", "MobileApp": "JejuBarrierFree", "_type": "json", "contentId": content_id, "overviewYN": "Y"}
            overview_text = ""
            try:
                res_detail = requests.get(detail_url, params=detail_params, timeout=15)
                overview_items = res_detail.json().get('response', {}).get('body', {}).get('items', {}).get('item', [])
                if overview_items: overview_text = overview_items[0].get('overview', '')
            except Exception: pass

            # 무장애 정보
            bf_url = f"{BASE_URL}/detailWithTour2"
            bf_params = {"ServiceKey": API_KEY, "MobileOS": "ETC", "MobileApp": "JejuBarrierFree", "_type": "json", "contentId": content_id}
            fac_data = {}
            try:
                res_bf = requests.get(bf_url, params=bf_params, timeout=15)
                bf_items = res_bf.json().get('response', {}).get('body', {}).get('items', {}).get('item', [])
                if bf_items: fac_data = bf_items[0]
            except Exception: pass
            
            # 데이터 가공 (점수 및 테마 분류)
            total_score, grade, keywords = score_facility(fac_data, overview_text)
            category_name = categorize_place(title, overview_text) # 🚨 테마 자동 분류 적용!
            
            dataset.append({
                "분류": category_name,
                "장소명": title,
                "주소": addr,
                "위도": mapy,
                "경도": mapx,
                "상세무장애정보": keywords, 
                "추천점수": total_score,
                "추천등급": grade,
                "원본데이터": str(fac_data) 
            })
            time.sleep(0.5) 

    except Exception as e:
        print(f"에러 발생: {e}")
        return None

    df = pd.DataFrame(dataset)
    df.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
    print(f"\n🎉 작업 완료! {len(df)}개의 데이터가 저장되었습니다.")
    return df

if __name__ == "__main__":
    if not API_KEY:
        sys.exit("TOUR_API_KEY 환경 변수를 설정해 주세요.")
    result_df = fetch_jeju_tour_data(max_items=int(os.environ.get("MAX_ITEMS", "30")))
