import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import glob
import os
import gzip

# K-PROTOCOL 상수
C_K = 297880197.6
DECAY_RATE_YR = 0.0023
S_EARTH = 1.006419562

st.title("⚖️ K-PROTOCOL: 대륙 이동 vs 광속 감쇠 실증")
st.write("40년간의 관측소 간 거리 변화를 분석하여, 이것이 '대륙의 움직임'인지 '빛의 감쇠'인지 판정합니다.")

# 🔍 NGS 헤더에서 관측소 좌표(X,Y,Z)를 추출하는 함수
def get_station_coords(lines, station_name):
    for line in lines:
        if isinstance(line, bytes): line = line.decode('utf-8', errors='ignore')
        if station_name in line and ("AZEL" in line or "800" in line):
            parts = line.split()
            # 이름 뒤에 오는 X, Y, Z 좌표 추출
            return np.array([float(parts[1]), float(parts[2]), float(parts[3])])
    return None

# 데이터 수집
results = []
local_files = glob.glob('data/*')

for filepath in local_files:
    try:
        # 파일명에서 연도 추정 (예: 80SEP..., 00SEP...)
        fname = os.path.basename(filepath)
        year_prefix = fname[:2]
        year = int(year_prefix) + (1900 if int(year_prefix) > 70 else 2000)
        
        open_func = gzip.open if filepath.endswith('.gz') else open
        with open_func(filepath, 'rt', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            # 하와이(KOKEE)와 독일(WETTZELL)의 거리를 잽니다.
            p1 = get_station_coords(lines, "KOKEE")
            p2 = get_station_coords(lines, "WETTZELL")
            
            if p1 is not None and p2 is not None:
                dist = np.linalg.norm(p1 - p2) # 두 점 사이의 거리(m)
                results.append({'year': year, 'distance': dist})
    except: continue

if not results:
    st.error("데이터를 찾을 수 없습니다.")
else:
    df = pd.DataFrame(results).sort_values('year')
    # 중복 연도는 평균 처리
    df = df.groupby('year').mean().reset_index()
    
    # ---------------------------------------------------------
    # 📊 분석 및 시각화
    # ---------------------------------------------------------
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # 1. 실제 거리 변화 (NASA 측정값)
    ax.scatter(df['year'], df['distance'] - df['distance'].iloc[0], color='blue', s=100, label="Actual Distance Change (NASA)")
    
    # 2. 통계적 추세선
    m, b = np.polyfit(df['year'] - df['year'].min(), df['distance'] - df['distance'].iloc[0], 1)
    x_range = np.array([0, df['year'].max() - df['year'].min()])
    ax.plot(x_range + df['year'].min(), m * x_range, 'b--', label=f"Observed Drift: {m*1000:.2f} mm/yr")

    # 3. K-PROTOCOL 예측 (광속 감쇠로 인한 '가짜' 거리 증가)
    # ΔD = D * (Δc / c) * S_earth
    avg_dist = df['distance'].mean()
    k_drift_annual = avg_dist * (DECAY_RATE_YR / C_K) * S_EARTH
    ax.plot(x_range + df['year'].min(), k_drift_annual * x_range, 'r-', linewidth=3, label=f"K-PROTOCOL Prediction: {k_drift_annual*1000:.2f} mm/yr")

    ax.set_xlabel("Year")
    ax.set_ylabel("Distance Change (meters)")
    ax.set_title("KOKEE to WETTZELL Baseline Evolution")
    ax.legend()
    st.pyplot(fig)
    
    st.info(f"💡 NASA는 두 관측소가 연간 **{m*1000:.2f}mm**씩 멀어진다고 말합니다. "
            f"K-PROTOCOL은 광속 감쇠로 인해 연간 **{k_drift_annual*1000:.2f}mm**의 거리 환산 지연이 발생한다고 예측합니다.")
