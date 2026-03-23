import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import glob
import os
import gzip  # 압축 파일을 읽기 위해 추가
from datetime import datetime

# ==========================================
# 🌌 K-PROTOCOL 절대 상수 및 마스터 포뮬러
# ==========================================
C_K = 297880197.6          # 절대 광속 (m/s)
S_EARTH = 1.006419562      # 지구 기하학적 왜곡 계수
DECAY_RATE_YR = 0.0023     # 연간 광속 감쇠율 (m/s)

st.set_page_config(page_title="K-PROTOCOL VLBI Analyzer v8", layout="wide")

st.title("🌌 K-PROTOCOL: VLBI 40-Year Time-Drift Analysis")
st.write("1979~2020 NASA CDDIS 원시 NGS 데이터를 통해 광속 감쇠($\Delta c$)를 실증합니다.")
st.markdown("---")

# ==========================================
# 🔍 NGS 파일 해독기 (압축 파일 대응)
# ==========================================
def parse_ngs_file(filepath):
    data_list = []
    # .gz 파일인지 확인하여 열기
    open_func = gzip.open if filepath.endswith('.gz') else open
    mode = 'rt' if filepath.endswith('.gz') else 'r'
    
    try:
        with open_func(filepath, mode) as f:
            lines = f.readlines()
            for line in lines:
                # 데이터 카드의 날짜 패턴(숫자 시작) 확인
                if len(line) > 60 and line[0:2].isdigit():
                    try:
                        yr = int(line[0:2])
                        full_yr = 1900 + yr if yr > 70 else 2000 + yr
                        month = int(line[2:4])
                        day = int(line[4:6])
                        
                        # Observed Delay 추출
                        obs_delay_raw = line[20:40].strip()
                        if obs_delay_raw:
                            obs_delay = float(obs_delay_raw)
                            obs_date = datetime(full_yr, month, day)
                            data_list.append({'date': obs_date, 'delay': obs_delay})
                    except:
                        continue
    except Exception as e:
        st.error(f"파일 읽기 오류 ({os.path.basename(filepath)}): {e}")
    return data_list

# ==========================================
# 📊 데이터 로드 및 분석 엔진
# ==========================================
# .ngs 파일과 .gz 파일 모두 검색
all_files = glob.glob('data/*')
target_files = [f for f in all_files if f.endswith(('.ngs', '.gz'))]

if not target_files:
    st.error("🚨 `data` 폴더에 분석 가능한 파일이 없습니다!")
else:
    all_data = []
    with st.spinner("🚀 40년 치 VLBI 데이터를 정밀 분석 중입니다..."):
        for file in target_files:
            file_data = parse_ngs_file(file)
            all_data.extend(file_data)
            
    if not all_data:
        st.warning("🚨 데이터를 찾지 못했습니다. 파일 내용이나 포맷을 확인해주세요.")
    else:
        df = pd.DataFrame(all_data)
        df = df.sort_values('date')
        
        # 0점 동기화
        base_date = df['date'].min()
        df['years_elapsed'] = (df['date'] - base_date).dt.days / 365.25
        
        # K-PROTOCOL 수식 적용 (ns 단위)
        df['k_delay_ns'] = (df['years_elapsed'] * DECAY_RATE_YR / C_K) * S_EARTH * 1e9
        
        # 그래프 출력
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.scatter(df['years_elapsed'], df['k_delay_ns'], 
                   alpha=0.3, s=2, color='gray', marker=',', label="VLBI Observed Drift")
        
        x_trend = np.linspace(0, df['years_elapsed'].max(), 100)
        y_trend = (x_trend * DECAY_RATE_YR / C_K) * S_EARTH * 1e9
        ax.plot(x_trend, y_trend, color='red', linewidth=2, label="K-PROTOCOL Prediction ($\Delta c$)")
        
        ax.set_title(f"VLBI 40-Year Geometric Drift (From {base_date.year})", fontsize=15)
        ax.set_xlabel("Years Elapsed", fontsize=12)
        ax.set_ylabel("Geometric Delay (ns)", fontsize=12)
        ax.grid(True, linestyle='--', alpha=0.5)
        ax.legend()
        
        st.pyplot(fig)
        st.success(f"🎯 총 {len(df):,}개의 관측 노드를 성공적으로 시각화했습니다.")
