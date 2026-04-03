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
st.title("⚖️ K-PROTOCOL: 대륙 이동 vs 광속 감쇠 (자동 기선 추출판)")
st.markdown("파일 내에 존재하는 **모든 관측소**를 자동으로 찾아내어, 40년 동안 가장 오래 관측된 기선을 추적합니다.")
st.markdown("---")

# ==========================================
# 🔍 헤더에서 존재하는 모든 관측소 자동 추출
# ==========================================
def extract_all_stations(lines):
    stations = {}
    for line in lines:
        if isinstance(line, bytes): 
            line = line.decode('utf-8', errors='ignore')
        
        # NGS 헤더의 위치 정보는 첫 번째 $END 전에 있습니다.
        if "$END" in line: 
            break 
        
        parts = line.split()
        if len(parts) >= 4:
            try:
                # X, Y, Z 좌표가 맞는지 검증 (지구 반지름 스케일의 큰 숫자인지 확인)
                x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                if abs(x) > 100000 and abs(y) > 100000:
                    stations[parts[0]] = np.array([x, y, z])
            except ValueError:
                pass
    return stations

# ==========================================
# 📂 데이터 로드 및 전방위 기선 계산
# ==========================================
baselines = []
local_files = [f for f in glob.glob('data/*') if os.path.isfile(f)]

if not local_files:
    st.error("🚨 `data` 폴더가 비어있습니다. 데이터를 넣어주세요.")
else:
    with st.spinner("🚀 파일 내 모든 관측소를 찾아내어 기선 거리를 계산 중입니다..."):
        for filepath in local_files:
            fname = os.path.basename(filepath)
            if len(fname) < 5: continue 
            
            try:
                # 파일명에서 연도 추출 (예: 80SEP -> 1980)
                year_str = re.search(r'\d+', fname)
                if not year_str: continue
                yr_val = int(year_str.group()[:2])
                year = yr_val + (1900 if yr_val > 70 else 2000)
                
                open_func = gzip.open if filepath.endswith('.gz') else open
                with open_func(filepath, 'rt', encoding='utf-8', errors='ignore') as f:
                    # 파일 안에 있는 모든 관측소와 좌표를 가져옵니다.
                    stations = extract_all_stations(f.readlines())
                    st_names = list(stations.keys())
                    
                    # 관측소 간의 모든 조합(기선)의 거리를 계산합니다.
                    for i in range(len(st_names)):
                        for j in range(i+1, len(st_names)):
                            s1, s2 = sorted([st_names[i], st_names[j]])
                            dist = np.linalg.norm(stations[s1] - stations[s2])
                            baseline_name = f"{s1} - {s2}"
                            baselines.append({'year': year, 'baseline': baseline_name, 'distance': dist})
            except Exception as e:
                pass

    # ==========================================
    # 📊 기선 선택 및 시각화
    # ==========================================
    if not baselines:
        st.warning("⚠️ 좌표를 추출할 수 없습니다. 파일 규격을 확인하세요.")
    else:
        df = pd.DataFrame(baselines)
        # 같은 해에 동일한 기선이 여러 번 측정되었다면 평균을 냅니다.
        df_avg = df.groupby(['year', 'baseline'])['distance'].mean().reset_index()
        
        # 기선별로 몇 년 치 데이터가 있는지 카운트
        baseline_counts = df_avg.groupby('baseline')['year'].nunique()
        # 최소 2개 연도 이상 관측된 기선만 필터링
        valid_baselines = baseline_counts[baseline_counts >= 2].index.tolist()
        
        if not valid_baselines:
            st.error("🚨 최소 2년 이상 연속 관측된 기선이 없습니다.")
        else:
            # 데이터가 가장 많은 기선 순으로 정렬
            valid_baselines.sort(key=lambda b: baseline_counts[b], reverse=True)
            
            with st.sidebar:
                st.header("⚙️ 분석 기선(Baseline) 선택")
                st.write("발견된 관측소 쌍 중 하나를 선택하세요.")
                # 사용자가 드롭다운으로 기선을 고를 수 있게 합니다.
                selected_baseline = st.selectbox(
                    "기선 목록 (데이터 수 순)", 
                    valid_baselines, 
                    format_func=lambda x: f"{x} ({baseline_counts[x]}개 연도)"
                )
            
            # 선택된 기선의 데이터만 추출
            plot_df = df_avg[df_avg['baseline'] == selected_baseline].sort_values('year')
            
            st.success(f"🔥 **{selected_baseline}** 기선의 데이터를 성공적으로 로드했습니다. ({plot_df['year'].min()}년 ~ {plot_df['year'].max()}년)")

            fig, ax = plt.subplots(figsize=(12, 6))
            
            x_raw = plot_df['year'].values
            x_norm = x_raw - x_raw.min()
            y_raw = plot_df['distance'].values
            y_norm = y_raw - y_raw[0]
            
            # 1. NASA 관측 데이터
            ax.scatter(x_raw, y_norm, color='blue', s=150, alpha=0.7, edgecolors='black', label="NASA Observed Distance")
            
            # 2. 통계적 실제 추세선
            m, b = np.polyfit(x_norm, y_norm, 1)
            ax.plot(x_raw, m * x_norm, 'b--', alpha=0.5, label=f"NASA Trend: {m*1000:.2f} mm/yr")
            
            # 3. K-PROTOCOL 예측 (붉은 실선)
            avg_dist = y_raw.mean()
            k_drift_annual = avg_dist * (DECAY_RATE_YR / C_K) * S_EARTH
            ax.plot(x_raw, k_drift_annual * x_norm, color='red', linewidth=4, label=f"K-PROTOCOL Prediction: {k_drift_annual*1000:.2f} mm/yr")

            ax.set_title(f"Baseline Evolution: {selected_baseline}", fontsize=16, fontweight='bold')
            ax.set_xlabel("Year", fontsize=12)
            ax.set_ylabel("Distance Change (meters)", fontsize=12)
            ax.grid(True, linestyle='--', alpha=0.6)
            ax.legend(fontsize=11)
            
            st.pyplot(fig)
            
            # 지표 출력
            c1, c2, c3 = st.columns(3)
            c1.metric("초기 기선 길이 (Absolute)", f"{y_raw[0]:,.0f} m")
            c2.metric("NASA 관측 속도", f"{m*1000:.2f} mm/yr")
            c3.metric("K-PROTOCOL 예측", f"{k_drift_annual*1000:.2f} mm/yr")

            st.markdown("---")
            st.info("💡 **해석 방법:** 사이드바에서 여러 기선(대륙 쌍)을 바꿔보며 확인하십시오. 만약 대륙 이동이 진짜라면 판의 경계에 따라 어떤 기선은 수축(-)하고 어떤 기선은 확장(+)해야 합니다. 하지만 **모든 기선이 K-PROTOCOL의 붉은 예측선을 따라 일관되게 확장(+)되는 경향을 보인다면, 그것은 대륙이 움직이는 것이 아니라 빛이 느려지고 있다는 완벽한 물증**입니다.")
