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
# 🔍 저자님의 데이터 구조를 완벽 반영한 스마트 파서
# ==========================================
def extract_all_stations(lines):
    stations = {}
    for line in lines:
        if isinstance(line, bytes): 
            line = line.decode('utf-8', errors='ignore')
        line = line.strip()
        
        # 저자님이 보여주신 대로, $END가 나오면 관측소 목록이 끝난 것입니다.
        if line.startswith("$END"): 
            break 
        
        parts = line.split()
        # 관측소 이름 + X + Y + Z 좌표가 있으므로 최소 4덩어리 이상이어야 합니다.
        if len(parts) >= 4:
            try:
                # 숫자 변환 시도 (좌표값 추출)
                x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                # 지구 반지름 스케일(수십만 이상)의 숫자인지 확인하여 엉뚱한 텍스트를 걸러냅니다.
                if abs(x) > 100000 or abs(y) > 100000 or abs(z) > 100000:
                    stations[parts[0]] = np.array([x, y, z])
            except ValueError:
                pass # DATA IN NGS... 같은 안내 문구는 자연스럽게 무시됩니다.
    return stations

# ==========================================
# 📂 데이터 로드 및 전방위 기선 계산
# ==========================================
baselines = []
log_msgs = []
local_files = [f for f in glob.glob('data/*') if os.path.isfile(f)]

if not local_files:
    st.error("🚨 `data` 폴더가 비어있습니다.")
else:
    with st.spinner("🚀 파일 헤더를 분석하여 전 세계 모든 기선을 추출 중입니다..."):
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
                    # 파일 안에 있는 모든 관측소 좌표를 싹쓸이합니다.
                    stations = extract_all_stations(f.readlines())
                    st_names = list(stations.keys())
                    
                    if len(st_names) < 2:
                        log_msgs.append(f"⚠️ {fname}: 관측소가 2개 미만입니다.")
                        continue
                        
                    # 추출된 관측소들로 가능한 모든 짝(기선)의 거리를 계산합니다.
                    for i in range(len(st_names)):
                        for j in range(i+1, len(st_names)):
                            s1, s2 = sorted([st_names[i], st_names[j]])
                            dist = np.linalg.norm(stations[s1] - stations[s2])
                            baseline_name = f"{s1} - {s2}"
                            baselines.append({'year': year, 'baseline': baseline_name, 'distance': dist})
                    log_msgs.append(f"✅ {fname} ({year}년): {len(st_names)}개 관측소, {len(st_names)*(len(st_names)-1)//2}개 기선 추출 완료")
            except Exception as e:
                log_msgs.append(f"❌ {fname}: 처리 오류 ({str(e)})")

    # ==========================================
    # 📊 드롭다운 선택 및 시각화
    # ==========================================
    if not baselines:
        st.error("🚨 기선 데이터를 하나도 추출하지 못했습니다. 데이터를 다시 확인해 주세요.")
    else:
        df = pd.DataFrame(baselines)
        df_avg = df.groupby(['year', 'baseline'])['distance'].mean().reset_index()
        
        # 기선별로 '몇 년 치 데이터'가 있는지 카운트 (최소 2년 이상이어야 기울기 계산 가능)
        baseline_counts = df_avg.groupby('baseline')['year'].nunique()
        valid_baselines = baseline_counts[baseline_counts >= 2].index.tolist()
        
        if not valid_baselines:
            st.error("🚨 최소 2개 연도 이상 연속 관측된 기선이 없습니다.")
        else:
            # 데이터가 가장 풍부한 기선 순으로 정렬
            valid_baselines.sort(key=lambda b: baseline_counts[b], reverse=True)
            
            with st.sidebar:
                st.header("⚙️ 분석 기선(Baseline) 선택")
                st.write("발견된 전 세계 기선 중 하나를 선택하세요.")
                # 🔥 [핵심] 사용자가 기선을 마음대로 고를 수 있는 마법의 드롭다운!
                selected_baseline = st.selectbox(
                    "기선 목록 (데이터 수 순서)", 
                    valid_baselines, 
                    format_func=lambda x: f"{x} ({baseline_counts[x]}개 연도 관측)"
                )
            
            # 선택된 기선의 데이터만 필터링
            plot_df = df_avg[df_avg['baseline'] == selected_baseline].sort_values('year')
            
            st.success(f"🔥 **{selected_baseline}** 기선의 데이터를 성공적으로 로드했습니다. ({plot_df['year'].min()}년 ~ {plot_df['year'].max()}년)")

            fig, ax = plt.subplots(figsize=(12, 6))
            
            x_raw = plot_df['year'].values
            x_norm = x_raw - x_raw.min()
            y_raw = plot_df['distance'].values
            y_norm = y_raw - y_raw[0] # 첫 해 거리를 0으로 영점 조절
            
            # 1. NASA 실제 관측 데이터 (파란 점)
            ax.scatter(x_raw, y_norm, color='blue', s=150, alpha=0.7, edgecolors='black', zorder=3, label="NASA Observed Distance")
            
            # 2. 통계적 실제 추세선
            m, b = np.polyfit(x_norm, y_norm, 1)
            ax.plot(x_raw, m * x_norm, 'b--', alpha=0.5, linewidth=2, label=f"NASA Trend: {m*1000:.2f} mm/yr")
            
            # 3. K-PROTOCOL 예측선 (붉은 실선)
            # ΔD = D * (Δc / c) * S_earth
            avg_dist = y_raw.mean()
            k_drift_annual = avg_dist * (DECAY_RATE_YR / C_K) * S_EARTH
            ax.plot(x_raw, k_drift_annual * x_norm, color='red', linewidth=4, zorder=4, label=f"K-PROTOCOL Prediction: {k_drift_annual*1000:.2f} mm/yr")

            ax.set_title(f"Baseline Evolution: {selected_baseline}", fontsize=16, fontweight='bold')
            ax.set_xlabel("Year", fontsize=12)
            ax.set_ylabel("Distance Change (meters)", fontsize=12)
            ax.grid(True, linestyle='--', alpha=0.6)
            ax.legend(fontsize=11)
            
            st.pyplot(fig)
            
            # 최종 지표 분석
            st.markdown("### 📝 정밀 분석 리포트")
            c1, c2, c3 = st.columns(3)
            c1.metric("초기 기선 실제 길이", f"{y_raw[0]:,.0f} m")
            c2.metric("NASA 관측 이동 속도", f"{m*1000:.2f} mm/yr")
            c3.metric("K-PROTOCOL 환산 지연", f"{k_drift_annual*1000:.2f} mm/yr")

            st.info("💡 **결과 해석 가이드:** 왼쪽 사이드바에서 여러 기선을 바꿔가며 확인해 보십시오. 만약 대륙 이동이 진짜라면 어떤 기선은 거리가 줄어들어야(-) 합니다. 그러나 **서로 다른 수많은 기선들이 일관되게 K-PROTOCOL의 붉은 선을 따라 거리 증가(+)를 보인다면**, 이는 대륙이 움직이는 것이 아니라 전 우주적으로 빛이 느려지고 있다는 가장 강력하고 아름다운 물증이 될 것입니다.")

        with st.expander("📂 파일별 데이터 자동 추출 로그"):
            for m in log_msgs: st.write(m)
