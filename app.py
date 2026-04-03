import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import glob
import os
import gzip
import re

# ==========================================
# 🌌 K-PROTOCOL 마스터 상수
# ==========================================
C_K = 297880197.6          # 절대 광속 (m/s)
S_EARTH = 1.006419562      # 지구 기하학적 왜곡 계수
DECAY_RATE_YR = 0.0023     # 연간 광속 감쇠율 (m/s)

st.set_page_config(page_title="K-PROTOCOL Master Baseline", layout="wide")
st.title("⚖️ K-PROTOCOL: 대륙 이동 vs 광속 감쇠 (전 세계 기선 자동 분석)")
st.markdown("NASA NGS 파일의 헤더를 자동 스캔하여, 40년간 존재하는 **모든 관측소 조합(기선)**의 거리 변화를 추적합니다.")
st.markdown("---")

# ==========================================
# 🔍 [수정] 어떤 형식이든 좌표를 찾아내는 유연한 파서
# ==========================================
def extract_stations_smart(lines):
    stations = {}
    for line in lines:
        if isinstance(line, bytes): line = line.decode('utf-8', errors='ignore')
        up_line = line.upper().strip()
        
        if up_line.startswith("$END"): break # 헤더 종료
        
        # 줄 안에서 연속된 숫자 3개(X, Y, Z 좌표)를 찾습니다.
        # 좌표는 보통 1,000,000 단위의 큰 숫자입니다.
        nums = re.findall(r"[-+]?\d+\.\d+", up_line)
        if len(nums) >= 3:
            # 줄의 맨 앞 단어(또는 숫자 뒤에 숨은 단어)를 관측소 이름으로 추정
            parts = up_line.split()
            # 숫자 뭉치 바로 앞의 텍스트를 이름으로 잡습니다.
            for i, p in enumerate(parts):
                try:
                    float(p) # 숫자라면 이름이 아님
                except ValueError:
                    name = p # 텍스트가 나오면 이름으로 간주
                    try:
                        # 그 뒤에 숫자 3개가 나란히 오는지 확인
                        x, y, z = float(parts[i+1]), float(parts[i+2]), float(parts[i+3])
                        if abs(x) > 100000: # 지구 반지름 스케일 검증
                            stations[name] = np.array([x, y, z])
                            break
                    except: continue
    return stations

# ==========================================
# 📂 데이터 로드 및 전방위 기선 계산
# ==========================================
baselines = []
inventory = {} # 어떤 파일에 어떤 역이 있는지 기록

local_files = [f for f in glob.glob('data/*') if os.path.isfile(f)]

if not local_files:
    st.error("🚨 `data` 폴더가 비어있습니다. 데이터를 넣어주세요.")
else:
    with st.spinner("🚀 파일 헤더를 정밀 분석 중입니다..."):
        for filepath in local_files:
            fname = os.path.basename(filepath)
            try:
                year_match = re.search(r'\d+', fname)
                yr_val = int(year_match.group()[:2]) if year_match else 0
                year = yr_val + (1900 if yr_val > 70 else 2000)
                
                open_func = gzip.open if filepath.endswith('.gz') else open
                with open_func(filepath, 'rt', encoding='utf-8', errors='ignore') as f:
                    stations = extract_stations_smart(f.readlines())
                    st_names = sorted(stations.keys())
                    inventory[fname] = st_names
                    
                    for i in range(len(st_names)):
                        for j in range(i+1, len(st_names)):
                            s1, s2 = st_names[i], st_names[j]
                            dist = np.linalg.norm(stations[s1] - stations[s2])
                            baselines.append({'year': year, 'baseline': f"{s1} - {s2}", 'distance': dist})
            except: continue

    if not baselines:
        st.error("🚨 기선을 하나도 추출하지 못했습니다. 파일 내부 형식을 확인하세요.")
    else:
        df = pd.DataFrame(baselines)
        df_avg = df.groupby(['year', 'baseline'])['distance'].mean().reset_index()
        baseline_counts = df_avg.groupby('baseline')['year'].nunique()
        
        # 2년 이상 데이터가 있는 기선을 우선순위로 정렬
        valid_baselines = baseline_counts.index.tolist()
        valid_baselines.sort(key=lambda b: baseline_counts[b], reverse=True)
        
        with st.sidebar:
            st.header("⚙️ 분석 기선 선택")
            selected_baseline = st.selectbox("기선 목록", valid_baselines, 
                                             format_func=lambda x: f"{x} ({baseline_counts[x]}개 연도)")
        
        plot_df = df_avg[df_avg['baseline'] == selected_baseline].sort_values('year')
        
        fig, ax = plt.subplots(figsize=(12, 6))
        x_raw = plot_df['year'].values
        y_raw = plot_df['distance'].values
        
        if len(plot_df) < 2:
            st.warning("⚠️ 선택한 기선은 데이터가 1개 연도뿐입니다. 다른 기선을 선택해 보세요.")
            ax.scatter(x_raw, y_raw, color='blue', s=200)
        else:
            x_norm = x_raw - x_raw.min()
            y_norm = y_raw - y_raw[0]
            ax.scatter(x_raw, y_norm, color='blue', s=150, alpha=0.7, edgecolors='black', label="NASA Observed")
            m, b = np.polyfit(x_norm, y_norm, 1)
            ax.plot(x_raw, m * x_norm, 'b--', label=f"NASA Trend: {m*1000:.2f} mm/yr")
            
            # K-PROTOCOL 예측
            avg_dist = y_raw.mean()
            k_drift_annual = avg_dist * (DECAY_RATE_YR / C_K) * S_EARTH
            ax.plot(x_raw, k_drift_annual * x_norm, color='red', linewidth=4, label=f"K-PROTOCOL Prediction: {k_drift_annual*1000:.2f} mm/yr")

        ax.set_title(f"Baseline: {selected_baseline}", fontsize=16, fontweight='bold')
        ax.set_xlabel("Year")
        ax.set_ylabel("Distance Change (m)")
        ax.legend()
        st.pyplot(fig)

        # 📋 데이터 인벤토리 (디버깅용)
        with st.expander("📂 파일별 발견된 관측소 목록 (내 데이터 확인용)"):
            st.write(inventory)
