import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import glob
import os
import gzip
from datetime import datetime

# ==========================================
# 🌌 K-PROTOCOL 절대 상수
# ==========================================
C_K = 297880197.6          # 절대 광속 (m/s)
S_EARTH = 1.006419562      # 지구 기하학적 왜곡 계수
DECAY_RATE_YR = 0.0023     # 연간 광속 감쇠율 (m/s)

st.set_page_config(page_title="K-PROTOCOL VLBI Analyzer", layout="wide")

st.title("🌌 K-PROTOCOL: VLBI 40-Year Time-Drift Analyzer")
st.markdown("NASA CDDIS 원시 데이터 분석 엔진 (시뮬레이션 및 실증 교차 검증)")
st.markdown("---")

# ==========================================
# 🎛️ 왼쪽 사이드바 (파싱 위치 실시간 조절기)
# ==========================================
with st.sidebar:
    st.header("⚙️ 데이터 파싱 설정")
    st.write("실제 관측값이 있는 텍스트 열(Column Index)을 조절하세요. (기본: 20~40)")
    col_start = st.number_input("Delay 시작 위치", value=20, step=1)
    col_end = st.number_input("Delay 끝 위치", value=40, step=1)
    
    st.markdown("---")
    data_mode = st.radio(
        "📊 Y축 데이터 소스 선택", 
        [
            "1. [시뮬레이션] K-PROTOCOL 공식 (기존)", 
            "2. [실증] 진짜 NASA 관측 Delay (오차 증명용)"
        ]
    )

view_mode = st.radio("👁️ 그래프 레이어 보기 옵션", 
                     ["전체 보기 (데이터 + 예측선 포개짐)", "관측 시점 데이터만 보기 (회색 점)", "예측선만 보기 (붉은 선)"], 
                     horizontal=True)

# ==========================================
# 🔍 무적의 범용 파서 (에러 방어 완벽 적용)
# ==========================================
def parse_ngs_lines(lines, c_start, c_end):
    data_list = []
    current_date = None
    for line in lines:
        if isinstance(line, bytes):
            line = line.decode('utf-8', errors='ignore')
        padded_line = line.rstrip('\n\r').ljust(80)
        card_num = padded_line[78:80]
        
        if card_num == '01':
            try:
                yr = int(padded_line[29:33].strip())
                full_yr = yr if yr > 1000 else (1900 + yr if yr > 70 else 2000 + yr)
                mo = int(padded_line[34:36].strip())
                dy = int(padded_line[37:39].strip())
                hr = int(padded_line[40:43].strip() or 0)
                mn = int(padded_line[43:46].strip() or 0)
                sc = float(padded_line[46:56].strip() or 0.0)
                current_date = datetime(full_yr, mo, dy, hr, mn, int(sc))
            except:
                current_date = None
                
        elif card_num == '02' and current_date is not None:
            # 기본적으로 날짜(X축)는 무조건 저장해서 앱이 터지지 않게 보장합니다.
            row_data = {'date': current_date}
            
            try:
                # 사이드바에서 설정한 위치의 진짜 관측값을 추출 시도합니다.
                raw_delay = padded_line[c_start:c_end].strip()
                if raw_delay:
                    row_data['obs_delay_ns'] = float(raw_delay) / 1000.0  # 단위 변환
            except:
                pass # 변환에 실패해도 멈추지 않고 날짜만 가져갑니다.
            
            data_list.append(row_data)
            current_date = None
            
    return data_list

# ==========================================
# 📂 data 폴더 강제 읽기
# ==========================================
all_data = []
local_files = [f for f in glob.glob('data/*') if os.path.isfile(f)]

if not local_files:
    st.error("🚨 `data` 폴더가 비어있습니다. NASA 원시 데이터를 `data` 폴더에 넣어주세요.")
else:
    with st.spinner(f"🚀 `data` 폴더의 파일 {len(local_files)}개를 파싱 중입니다..."):
        for filepath in local_files:
            try:
                if filepath.endswith('.gz'):
                    with gzip.open(filepath, 'rt', encoding='utf-8', errors='ignore') as f:
                        all_data.extend(parse_ngs_lines(f.readlines(), col_start, col_end))
                else:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        all_data.extend(parse_ngs_lines(f.readlines(), col_start, col_end))
            except Exception:
                pass

    # ==========================================
    # 📊 데이터 플롯
    # ==========================================
    if not all_data:
        st.warning("⚠️ 파일은 읽었으나 데이터를 찾지 못했습니다.")
    else:
        df = pd.DataFrame(all_data)
        df = df.sort_values('date')
        base_date = df['date'].min()
        df['years_elapsed'] = (df['date'] - base_date).dt.total_seconds() / (365.25 * 24 * 3600)
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        show_data = "데이터" in view_mode or "전체" in view_mode
        show_pred = "예측선" in view_mode or "전체" in view_mode

        # ---------------------------------------------------------
        # [모드 1] 시뮬레이션 (저자님의 원본 로직 - 무조건 완벽한 사선)
        # ---------------------------------------------------------
        if "시뮬레이션" in data_mode:
            df['k_delay_ns'] = (df['years_elapsed'] * DECAY_RATE_YR / C_K) * S_EARTH * 1e9
            
            if show_data:
                ax.scatter(df['years_elapsed'], df['k_delay_ns'], 
                           alpha=0.5, s=40, color='gray', label="Simulated Nodes (K-PROTOCOL)")
            
            st.success(f"🎯 [시뮬레이션 모드] 총 **{len(df):,}개**의 데이터 포인트가 K-PROTOCOL 공식에 따라 시각화되었습니다.")

        # ---------------------------------------------------------
        # [모드 2] 실증 (진짜 우주 관측 데이터)
        # ---------------------------------------------------------
        else:
            # 실제 데이터(obs_delay_ns)가 파싱된 행만 남김
            real_df = df.dropna(subset=['obs_delay_ns']) 
            
            if real_df.empty:
                st.error("🚨 파일에서 실제 관측 데이터(Delay)를 추출하지 못했습니다. 왼쪽 사이드바에서 'Delay 시작/끝 위치' 숫자를 조절해 보세요.")
            else:
                if show_data:
                    ax.scatter(real_df['years_elapsed'], real_df['obs_delay_ns'], 
                               alpha=0.5, s=40, color='blue', label="Real Observation (Raw Delay)")
                
                st.success(f"🔥 [실증 모드] 총 **{len(real_df):,}개**의 진짜 우주 관측 데이터가 로드되었습니다! (수식 비적용)")
                # Y축 스케일 자동 조절
                ax.autoscale(enable=
