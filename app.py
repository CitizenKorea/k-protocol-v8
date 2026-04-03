import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import glob
import os
import gzip

# ==========================================
# 🌌 K-PROTOCOL 마스터 상수
# ==========================================
C_K = 297880197.6          # 절대 광속 (m/s)
S_EARTH = 1.006419562      # 지구 기하학적 왜곡 계수
DECAY_RATE_YR = 0.0023     # 연간 광속 감쇠율 (m/s)

st.set_page_config(page_title="K-PROTOCOL Baseline Analyzer", layout="wide")
st.title("⚖️ K-PROTOCOL: 대륙 이동 vs 광속 감쇠 실증")
st.markdown("40년간의 관측소 간 거리 변화를 분석하여, 이것이 '대륙의 움직임'인지 '빛의 감쇠'인지 판정합니다.")
st.markdown("---")

# 🔍 NGS 헤더에서 관측소 좌표(X,Y,Z)를 추출하는 스마트 함수
def get_station_coords(lines, target_name):
    target_name = target_name.upper().strip()
    for line in lines:
        if isinstance(line, bytes): line = line.decode('utf-8', errors='ignore')
        up_line = line.upper()
        if target_name in up_line and ("AZEL" in up_line or " 800" in up_line):
            parts = up_line.split()
            try:
                # 관측소 이름 바로 뒤의 숫자 3개를 가져옵니다.
                idx = parts.index(target_name)
                return np.array([float(parts[idx+1]), float(parts[idx+2]), float(parts[idx+3])])
            except (ValueError, IndexError):
                continue
    return None

# ==========================================
# 📂 데이터 로드 및 처리
# ==========================================
results = []
log_msgs = []
local_files = glob.glob('data/*')

if not local_files:
    st.error("🚨 `data` 폴더에 분석할 NASA NGS 파일이 없습니다.")
else:
    with st.spinner("🚀 관측소 기선 데이터를 추출 중입니다..."):
        for filepath in local_files:
            fname = os.path.basename(filepath)
            try:
                # 파일명에서 연도 추출 (예: 80SEP... -> 1980)
                prefix = "".join(filter(str.isdigit, fname[:2]))
                if not prefix: continue
                yr_val = int(prefix)
                year = yr_val + (1900 if yr_val > 70 else 2000)
                
                open_func = gzip.open if filepath.endswith('.gz') else open
                with open_func(filepath, 'rt', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    # 하와이(KOKEE)와 독일(WETTZELL) 기선 분석
                    p1 = get_station_coords(lines, "KOKEE")
                    p2 = get_station_coords(lines, "WETTZELL")
                    
                    if p1 is not None and p2 is not None:
                        dist = np.linalg.norm(p1 - p2)
                        results.append({'year': year, 'distance': dist, 'file': fname})
                        log_msgs.append(f"✅ {fname}: 거리 {dist:,.3f}m 추출 성공")
                    else:
                        log_msgs.append(f"❌ {fname}: KOKEE 또는 WETTZELL 좌표 없음")
            except Exception as e:
                log_msgs.append(f"⚠️ {fname}: 분석 오류 ({str(e)})")

    # 데이터 프레임 구축
    if not results:
        st.warning("⚠️ 유효한 기선(KOKEE-WETTZELL) 데이터를 하나도 찾지 못했습니다. 파일 내부의 관측소 이름을 확인해 주세요.")
        with st.expander("상세 로그 확인"):
            for m in log_msgs: st.write(m)
    else:
        df = pd.DataFrame(results).sort_values('year')
        # 같은 연도 데이터는 평균값 사용
        df_avg = df.groupby('year')['distance'].mean().reset_index()
        
        st.success(f"🎯 총 {len(df_avg)}개 연도의 기선 변화 데이터를 확보했습니다. ({df_avg['year'].min()}년 ~ {df_avg['year'].max()}년)")

        # ---------------------------------------------------------
        # 📈 수학적 분석 (LinAlgError 방어)
        # ---------------------------------------------------------
        if len(df_avg) < 2:
            st.error("🚨 분석 실패: 최소 2개 연도 이상의 데이터가 필요합니다. 현재 데이터가 너무 적어 기울기를 계산할 수 없습니다.")
        else:
            fig, ax = plt.subplots(figsize=(12, 6))
            
            # X, Y 정규화 (시작점을 0으로)
            x_raw = df_avg['year'].values
            x_norm = x_raw - x_raw.min()
            y_raw = df_avg['distance'].values
            y_norm = y_raw - y_raw[0]
            
            # 1. 실제 관측 데이터 점
            ax.scatter(x_raw, y_norm, color='blue', s=120, edgecolors='black', zorder=3, label="NASA Baseline Length (Observed)")
            
            # 2. 통계적 실제 추세선 (파란 점선)
            m, b = np.polyfit(x_norm, y_norm, 1)
            ax.plot(x_raw, m * x_norm, 'b--', alpha=0.6, label=f"NASA Drift: {m*1000:.2f} mm/yr")
            
            # 3. K-PROTOCOL 예측선 (붉은 실선)
            # ΔD = D * (Δc / c) * S_earth
            avg_dist = y_raw.mean()
            k_drift_annual = avg_dist * (DECAY_RATE_YR / C_K) * S_EARTH
            ax.plot(x_raw, k_drift_annual * x_norm, color='red', linewidth=4, zorder=4, 
                    label=f"K-PROTOCOL Prediction: {k_drift_annual*1000:.2f} mm/yr")

            ax.set_xlabel("Year", fontsize=12)
            ax.set_ylabel("Distance Change (m)", fontsize=12)
            ax.set_title("KOKEE to WETTZELL: Real Baseline Evolution vs Prediction", fontsize=15, fontweight='bold')
            ax.grid(True, linestyle='--', alpha=0.5)
            ax.legend(fontsize=11)
            
            st.pyplot(fig)
            
            # 결과 리포트
            col1, col2 = st.columns(2)
            col1.metric("NASA 관측 이동 속도", f"{m*1000:.2f} mm/yr", delta_color="inverse")
            col2.metric("K-PROTOCOL 예측 속도", f"{k_drift_annual*1000:.2f} mm/yr")
            
            st.markdown("---")
            st.markdown("### 📝 최종 분석")
            diff_percent = abs(m - k_drift_annual) / k_drift_annual * 100
            if diff_percent < 20:
                st.balloons()
                st.success(f"🔥 **결정적 증거 포착!** NASA의 대륙 이동 관측치와 K-PROTOCOL의 광속 감쇠 예측치가 **{100-diff_percent:.1f}%** 일치합니다. 이것은 대륙 이동이 아닌 광속 감쇠의 증거일 가능성이 매우 높습니다.")
            else:
                st.info("💡 두 값의 차이를 확인하십시오. 기울기의 방향(+, -)이 같고 수치적 오차 범위 내에 있다면, 광속 감쇠 이론을 지지하는 강력한 데이터가 됩니다.")

        with st.expander("📂 데이터 추출 상세 로그 보기"):
            for m in log_msgs: st.write(m)
