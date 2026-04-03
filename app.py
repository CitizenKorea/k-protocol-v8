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

st.set_page_config(page_title="K-PROTOCOL Baseline Evolution", layout="wide")
st.title("⚖️ K-PROTOCOL: 대륙 이동 vs 광속 감쇠 최종 실증")
st.markdown("NASA NGS 원시 데이터의 헤더를 전수 조사하여 40년간의 **진짜 거리 변화**를 추출합니다.")

# ==========================================
# 🔍 [초강력 파서] 어떤 형식이든 좌표를 찾아냄
# ==========================================
def get_station_coords_v2(lines, target_name):
    target_name = target_name.upper().strip()
    for line in lines:
        if isinstance(line, bytes): 
            line = line.decode('utf-8', errors='ignore')
        
        up_line = line.upper()
        # 1. 줄이 관측소 이름으로 시작하는지 확인
        if up_line.startswith(target_name):
            # 2. 줄 안에서 숫자(정수 또는 소수)들을 모두 찾아냅니다.
            # 이 패턴은 -1234.567 같은 좌표 형식을 정확히 잡아냅니다.
            numbers = re.findall(r"[-+]?\d*\.\d+|\d+", up_line)
            
            # 3. 좌표는 보통 이름 바로 뒤에 X, Y, Z 순서로 3개가 옵니다.
            if len(numbers) >= 3:
                try:
                    return np.array([float(numbers[0]), float(numbers[1]), float(numbers[2])])
                except:
                    continue
    return None

# ==========================================
# 📂 데이터 로드 및 처리 (40년 궤적 추적)
# ==========================================
results = []
log_msgs = []
# data 폴더 내 모든 파일을 탐색 (디렉토리 제외)
local_files = [f for f in glob.glob('data/*') if os.path.isfile(f)]

if not local_files:
    st.error("🚨 `data` 폴더가 비어있습니다. 데이터를 넣어주세요.")
else:
    with st.spinner("🚀 40년 치 NASA 원시 데이터를 정밀 스캔 중입니다..."):
        for filepath in local_files:
            fname = os.path.basename(filepath)
            # 파일명이 너무 짧거나 숫자가 없는 경우 스킵
            if len(fname) < 5: continue 
            
            try:
                # 파일명 앞 2자리에서 연도 추출 (예: 80, 90, 00, 10, 20)
                year_str = re.search(r'\d+', fname)
                if not year_str: continue
                yr_val = int(year_str.group()[:2])
                year = yr_val + (1900 if yr_val > 70 else 2000)
                
                open_func = gzip.open if filepath.endswith('.gz') else open
                with open_func(filepath, 'rt', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    p1 = get_station_coords_v2(lines, "KOKEE")
                    p2 = get_station_coords_v2(lines, "WETTZELL")
                    
                    if p1 is not None and p2 is not None:
                        dist = np.linalg.norm(p1 - p2)
                        results.append({'year': year, 'distance': dist, 'file': fname})
                        log_msgs.append(f"✅ {fname} ({year}년): {dist:,.3f}m 추출")
                    else:
                        # 좌표를 못 찾은 경우 상세 원인 기록
                        reason = "KOKEE 없음" if p1 is None else ("WETTZELL 없음" if p2 is None else "둘 다 없음")
                        log_msgs.append(f"❌ {fname}: {reason}")
            except Exception as e:
                log_msgs.append(f"⚠️ {fname}: 처리 불가 ({str(e)})")

    # ==========================================
    # 📊 데이터 시각화 (진실의 선)
    # ==========================================
    if not results:
        st.warning("⚠️ 좌표 추출에 실패했습니다. 파일 내부의 관측소 이름(KOKEE, WETTZELL)을 확인하십시오.")
    else:
        df = pd.DataFrame(results).sort_values('year')
        # 같은 연도의 여러 관측값은 평균을 냅니다.
        df_avg = df.groupby('year')['distance'].mean().reset_index()
        
        if len(df_avg) < 2:
            st.error(f"🚨 현재 {df_avg['year'].unique()}년 데이터만 확보되었습니다. 최소 2개 연도 이상이 필요합니다.")
            st.info("파일 이름이 80, 90, 00 등으로 시작하는지, 그리고 파일 내부에 좌표가 있는지 확인하십시오.")
        else:
            st.success(f"🔥 성공! {df_avg['year'].min()}년부터 {df_avg['year'].max()}년까지 총 {len(df_avg)}개 구간 데이터를 확보했습니다.")

            fig, ax = plt.subplots(figsize=(12, 6))
            
            # X축 정규화
            x_raw = df_avg['year'].values
            x_norm = x_raw - x_raw.min()
            # Y축 정규화 (최초 연도 거리를 0으로)
            y_raw = df_avg['distance'].values
            y_norm = y_raw - y_raw[0]
            
            # 1. NASA 실제 관측 데이터 (파란 점)
            ax.scatter(x_raw, y_norm, color='blue', s=150, alpha=0.7, edgecolors='black', label="NASA Observed Baseline")
            
            # 2. 실제 데이터의 통계적 추세 (파란 점선)
            m, b = np.polyfit(x_norm, y_norm, 1)
            ax.plot(x_raw, m * x_norm, 'b--', alpha=0.5, label=f"NASA Trend: {m*1000:.2f} mm/yr")
            
            # 3. K-PROTOCOL 예측 (붉은 실선)
            # ΔD = D * (Δc / c) * S_earth
            avg_dist = y_raw.mean()
            k_drift_annual = avg_dist * (DECAY_RATE_YR / C_K) * S_EARTH
            ax.plot(x_raw, k_drift_annual * x_norm, color='red', linewidth=4, label=f"K-PROTOCOL Prediction: {k_drift_annual*1000:.2f} mm/yr")

            ax.set_title("VLBI Baseline Evolution: Reality vs K-PROTOCOL", fontsize=15, fontweight='bold')
            ax.set_xlabel("Year", fontsize=12)
            ax.set_ylabel("Distance Change (meters)", fontsize=12)
            ax.grid(True, linestyle='--', alpha=0.6)
            ax.legend()
            
            st.pyplot(fig)
            
            # 지표 출력
            c1, c2, c3 = st.columns(3)
            c1.metric("총 관측 기간", f"{x_raw.max() - x_raw.min()}년")
            c2.metric("NASA 관측 속도", f"{m*1000:.2f} mm/yr")
            c3.metric("K-PROTOCOL 예측", f"{k_drift_annual*1000:.2f} mm/yr")

    with st.expander("📂 데이터 추출 로그 (어떤 파일이 성공했는지 확인)"):
        for m in log_msgs: st.write(m)
