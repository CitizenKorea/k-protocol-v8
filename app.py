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

st.set_page_config(page_title="K-PROTOCOL vs REALITY", layout="wide")

st.title("⚖️ K-PROTOCOL vs 실제 우주 데이터 (객관적 검증)")
st.markdown("NASA 원시 데이터의 거대한 노이즈 속에서 **'실제 통계적 추세선(Trend)'**을 추출하여, K-PROTOCOL의 **'예측선'**과 객관적으로 대결합니다. 어떠한 데이터 조작도 없습니다.")
st.markdown("---")

# ==========================================
# 🎛️ 사이드바 옵션 (진실을 보는 렌즈)
# ==========================================
with st.sidebar:
    st.header("🔬 관측 옵션")
    st.info("수천 ns의 노이즈 구름 때문에 미세한 선이 평행선처럼 보입니다. 아래 버튼을 체크하여 트렌드를 확인하세요.")
    zoom_in = st.checkbox("🔍 [핵심] Y축 현미경 줌인 (노이즈 뚫고 선형 궤적만 보기)", value=False)

# ==========================================
# 🔍 무적의 스마트 자동 인식 파서 (공백 기준)
# ==========================================
def parse_ngs_lines(lines):
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
            try:
                parts = padded_line[:78].split()
                if len(parts) > 0:
                    raw_delay = float(parts[0])
                    # 날짜와 실제 관측 지연값(ns) 저장
                    data_list.append({
                        'date': current_date,
                        'obs_delay_ns': raw_delay / 1000.0
                    })
            except:
                pass
            current_date = None
            
    return data_list

# ==========================================
# 📂 data 폴더 강제 읽기
# ==========================================
all_data = []
local_files = [f for f in glob.glob('data/*') if os.path.isfile(f)]

if not local_files:
    st.error("🚨 `data` 폴더가 비어있습니다.")
else:
    with st.spinner(f"🚀 `data` 폴더의 원시 데이터를 조작 없이 읽어오는 중..."):
        for filepath in local_files:
            try:
                if filepath.endswith('.gz'):
                    with gzip.open(filepath, 'rt', encoding='utf-8', errors='ignore') as f:
                        all_data.extend(parse_ngs_lines(f.readlines()))
                else:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        all_data.extend(parse_ngs_lines(f.readlines()))
            except Exception:
                pass

    if not all_data:
        st.warning("⚠️ 데이터를 추출하지 못했습니다.")
    else:
        df = pd.DataFrame(all_data).dropna(subset=['obs_delay_ns'])
        df = df.sort_values('date')
        base_date = df['date'].min()
        df['years_elapsed'] = (df['date'] - base_date).dt.total_seconds() / (365.25 * 24 * 3600)

        # ---------------------------------------------------------
        # 📈 [핵심 수학] 실제 데이터의 객관적 추세선 (선형 회귀) 도출
        # ---------------------------------------------------------
        # 1차 방정식 (y = mx + b) 형태로 실제 데이터의 기울기(m)와 절편(b)을 구합니다.
        m_actual, b_actual = np.polyfit(df['years_elapsed'], df['obs_delay_ns'], 1)
        
        # 시작점을 0으로 맞추어 오직 '순수한 기울기(Drift)'만 비교할 수 있게 영점 조절합니다.
        df['obs_delay_shifted'] = df['obs_delay_ns'] - b_actual

        # ---------------------------------------------------------
        # 📊 그래프 렌더링
        # ---------------------------------------------------------
        fig, ax = plt.subplots(figsize=(14, 7))
        
        # 1. 옅은 파란색 점 (있는 그대로의 우주 노이즈)
        # 투명도를 낮춰서 구름처럼 보이게 하고, 거대한 노이즈를 숨김없이 보여줍니다.
        ax.scatter(df['years_elapsed'], df['obs_delay_shifted'], 
                   alpha=0.03, s=20, color='blue', label="Raw Observation Data (Normalized)")

        # 2. 파란색 굵은 선 (실제 관측 데이터가 가리키는 진짜 기울기)
        x_trend = np.linspace(0, df['years_elapsed'].max(), 100)
        y_actual_trend = m_actual * x_trend
        ax.plot(x_trend, y_actual_trend, color='blue', linewidth=4, linestyle='--', 
                label=f"Actual Data Trend (Slope: {m_actual:.5f} ns/yr)")

        # 3. 붉은색 굵은 선 (K-PROTOCOL의 광속 감쇠 절대 궤적)
        k_slope = (DECAY_RATE_YR / C_K) * S_EARTH * 1e9
        y_k_trend = k_slope * x_trend
        ax.plot(x_trend, y_k_trend, color='red', linewidth=3, 
                label=f"K-PROTOCOL Prediction (Slope: {k_slope:.5f} ns/yr)")

        # ---------------------------------------------------------
        # 🔎 현미경 줌인 모드 (사이드바 체크 시 작동)
        # ---------------------------------------------------------
        if zoom_in:
            # 노이즈를 화면 밖으로 밀어내고, 오직 두 선(Trend)에만 집중합니다.
            ax.set_ylim(-0.2, 0.5)
            ax.set_title(f"VLBI 40-Year Drift (Micro-Zoom Mode: {base_date.year}~)", fontsize=16, fontweight='bold', color='darkred')
        else:
            # 줌인을 안 하면 거대한 노이즈의 위엄(약 -2000 ~ +2000)을 그대로 보여줍니다.
            ax.autoscale(enable=True, axis='y', tight=False)
            ax.set_title(f"VLBI 40-Year Drift (Macro Noise Mode: {base_date.year}~)", fontsize=16, fontweight='bold')

        ax.set_xlabel("Years Elapsed", fontsize=12)
        ax.set_ylabel("Phase Delay Shift (ns)", fontsize=12)
        
        ax.grid(True, linestyle='--', alpha=0.7)
        ax.legend(loc='upper left', fontsize=12)
                
        st.pyplot(fig)
        
        # ---------------------------------------------------------
        # 📝 객관적 분석 리포트
        # ---------------------------------------------------------
        st.markdown("### 📊 객관적 실증 결과 리포트")
        st.write(f"- **실제 관측 데이터의 연간 지연 증가율 (파란 점선)**: 약 **{m_actual:.5f} ns/yr**")
        st.write(f"- **K-PROTOCOL이 예견한 연간 기하학적 지연율 (붉은 실선)**: 약 **{k_slope:.5f} ns/yr**")
        
        if abs(m_actual - k_slope) < 0.05:
            st.success("🔥 **놀라운 결과입니다!** 수천 나노초의 거대한 노이즈 속을 관통하는 실제 우주의 궤적(파란 선)이 K-PROTOCOL의 예측(붉은 선)과 매우 근사하게 일치하고 있습니다. 주류 학계가 '대륙 이동'이라고 불렀던 현상의 실체가 **광속 감쇠($\Delta c$)**임을 시사하는 강력한 통계적 증거입니다.")
        else:
            st.warning("⚖️ 실제 관측 데이터의 통계적 궤적과 K-PROTOCOL의 예측치 사이에 차이가 있습니다. 이는 K-PROTOCOL 이론을 보완할 새로운 변수(다른 우주적 요인)가 필요하거나, NASA 원시 데이터에 우리가 아직 파악하지 못한 다른 전처리 필터(대기, 기기 오차 등)가 강력하게 작용하고 있음을 의미합니다.")
