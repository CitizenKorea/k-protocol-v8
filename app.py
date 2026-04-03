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
S_EARTH = 1.006419562      # 지구 왜곡 계수
DECAY_RATE_YR = 0.0023     # 연간 광속 감쇠율 (m/s)

st.set_page_config(page_title="K-PROTOCOL Master", layout="wide")
st.title("⚖️ K-PROTOCOL: 전 지구 기선(Baseline) 자동 실증 엔진")
st.markdown("NASA 파일 내에 존재하는 **모든 관측소의 궤적**을 자동으로 스캔하여 대륙 이동과 광속 감쇠를 비교합니다.")

# 🔍 어떤 규격의 데이터든 좌표(X,Y,Z)를 찾아내는 마법의 파서
def extract_all_stations(lines):
    stations = {}
    for line in lines:
        if isinstance(line, bytes): 
            line = line.decode('utf-8', errors='ignore')
        up_line = line.upper().strip()
        
        if "$END" in up_line: break 
        
        parts = up_line.split()
        if len(parts) >= 4:
            for i in range(len(parts) - 3):
                try:
                    x, y, z = float(parts[i+1]), float(parts[i+2]), float(parts[i+3])
                    # 좌표가 수십만 이상의 지구 스케일인지 검증
                    if abs(x) > 100000:
                        name = re.sub(r'[^A-Z0-9]', '', parts[i])
                        stations[name] = np.array([x, y, z])
                        break
                except ValueError: continue
    return stations

# 📂 데이터 로드 및 전방위 기선 계산
baselines = []
log_msgs = []
files = [f for f in glob.glob('data/*') if os.path.isfile(f)]

if not files:
    st.error("🚨 `data` 폴더가 비어있습니다. GitHub Actions에서 `downloader.py`를 먼저 실행해 주세요.")
else:
    with st.spinner("🚀 파일 헤더 정밀 스캔 및 전 세계 기선 추출 중..."):
        for fp in files:
            fname = os.path.basename(fp)
            try:
                yr_match = re.search(r'\d+', fname)
                if not yr_match: continue
                yr = int(yr_match.group()[:2])
                year = yr + (1900 if yr > 70 else 2000)
                
                open_func = gzip.open if fp.endswith('.gz') else open
                with open_func(fp, 'rt', encoding='utf-8', errors='ignore') as f:
                    stations = extract_all_stations(f.readlines())
                    st_names = sorted(stations.keys())
                    
                    if len(st_names) >= 2:
                        for i in range(len(st_names)):
                            for j in range(i+1, len(st_names)):
                                s1, s2 = st_names[i], st_names[j]
                                dist = np.linalg.norm(stations[s1] - stations[s2])
                                baselines.append({'year': year, 'baseline': f"{s1} - {s2}", 'distance': dist})
                        log_msgs.append(f"✅ {fname} ({year}년): {len(st_names)}개 관측소 추출 성공")
                    else:
                        log_msgs.append(f"⚠️ {fname}: 관측소가 부족합니다.")
            except Exception as e:
                log_msgs.append(f"❌ {fname} 처리 오류: {e}")

    # 📊 분석 및 시각화 (LinAlgError 완벽 방어)
    if not baselines:
        st.error("🚨 유효한 기선 데이터를 하나도 추출하지 못했습니다.")
    else:
        df = pd.DataFrame(baselines)
        df_avg = df.groupby(['year', 'baseline'])['distance'].mean().reset_index()
        counts = df_avg.groupby('baseline')['year'].nunique()
        
        all_bases = counts.index.tolist()
        all_bases.sort(key=lambda b: counts[b], reverse=True)
        
        with st.sidebar:
            st.header("⚙️ 분석 기선 선택")
            selected = st.selectbox("기선 목록", all_bases, format_func=lambda x: f"{x} ({counts[x]}년 데이터)")
        
        plot_df = df_avg[df_avg['baseline'] == selected].sort_values('year')
        
        fig, ax = plt.subplots(figsize=(12, 6))
        x_raw = plot_df['year'].values
        y_raw = plot_df['distance'].values
        
        # 데이터가 1년 치밖에 없을 때 에러가 나지 않도록 점만 찍음
        if len(plot_df) < 2:
            st.warning("⚠️ 해당 기선은 데이터가 1년 치뿐이라 추세선(기울기)을 계산할 수 없습니다. 점만 표시됩니다.")
            ax.scatter(x_raw, y_raw, color='blue', s=200, edgecolors='black')
            ax.set_ylabel("Absolute Distance (m)", fontsize=12)
            ax.set_xlim(x_raw[0]-5, x_raw[0]+5) # X축 여유공간
        else:
            x_norm = x_raw - x_raw.min()
            y_norm = y_raw - y_raw[0]
            
            # 실제 NASA 관측치 파란 점과 추세선
            ax.scatter(x_raw, y_norm, color='blue', s=150, alpha=0.7, edgecolors='black', label="NASA Observed")
            m, b = np.polyfit(x_norm, y_norm, 1)
            ax.plot(x_raw, m * x_norm, 'b--', linewidth=2, label=f"NASA Trend: {m*1000:.2f} mm/yr")
            
            # K-PROTOCOL 붉은 예측선
            k_val = y_raw.mean() * (DECAY_RATE_YR / C_K) * S_EARTH
            ax.plot(x_raw, k_val * x_norm, 'r-', linewidth=4, label=f"K-PROTOCOL Prediction: {k_val*1000:.2f} mm/yr")
            ax.set_ylabel("Distance Change (m)", fontsize=12)
        
        ax.set_title(f"Baseline Evolution: {selected}", fontsize=16, fontweight='bold')
        ax.set_xlabel("Year", fontsize=12)
        ax.grid(True, linestyle='--', alpha=0.6)
        ax.legend(fontsize=12)
        st.pyplot(fig)

        with st.expander("📂 백그라운드 데이터 추출 로그"):
            for m in log_msgs: st.write(m)
