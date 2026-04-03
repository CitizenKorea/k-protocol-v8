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
# 🔍 무적의 범용 파서 (에러 원천 차단)
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
            # 🚨 [수정 포인트] 칼럼이 무조건 존재하도록 기본값(NaN)을 강제 부여합니다.
            row_data = {'date': current_date, 'obs_delay_ns': np.nan}
            
            try:
                raw_delay = padded_line[int(c_start):int(c_end)].strip()
                if raw_delay:
                    row_data['obs_delay_ns'] = float(raw_delay) / 1000.0
            except:
                pass # 숫자로 못 바꿔도 에러 안 내고 쿨하게 넘어갑니다.
            
            data_list.append(row_data)
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
        
        # 🚨 [안전장치 2] 만약 파일 형식이 아예 달라서 칼럼 생성이 안 되었을 경우 대비
        if 'obs_delay_ns' not in df.columns:
            df['obs_delay_ns'] = np.nan
            
        fig, ax = plt.subplots(figsize=(12, 6))
        
        show_data = "데이터" in view_mode or "전체" in view_mode
        show_pred = "예측선" in view_mode or "전체" in view_mode

        if "시뮬레이션" in data_mode:
            df['k_delay_ns'] = (df['years_elapsed'] * DECAY_RATE_YR / C_K) * S_EARTH * 1e9
            
            if show_data:
                ax.scatter(df['years_elapsed'], df['k_delay_ns'], 
                           alpha=0.5, s=40, color='gray', label="Simulated Nodes (K-PROTOCOL)")
            
            st.success(f"🎯 [시뮬레이션 모드] 총 **{len(df):,}개**의 데이터 포인트가 렌더링 되었습니다.")

        else:
            real_df = df.dropna(subset=['obs_delay_ns']) 
            
            if real_df.empty:
                st.error("🚨 현재 설정된 위치(Index)에서 숫자를 찾지 못했습니다. 왼쪽 사이드바에서 [Delay 시작/끝 위치]를 조절해 진짜 관측값이 있는 칸을 찾아주세요!")
            else:
                if show_data:
                    ax.scatter(real_df['years_elapsed'], real_df['obs_delay_ns'], 
                               alpha=0.5, s=40, color='blue', label="Real Observation (Raw Delay)")
                
                st.success(f"🔥 [실증 모드] 총 **{len(real_df):,}개**의 진짜 관측 데이터가 로드되었습니다!")
                ax.autoscale(enable=True, axis='both', tight=False)

        if show_pred:
            x_trend = np.linspace(0, df['years_elapsed'].max(), 100)
            y_trend = (x_trend * DECAY_RATE_YR / C_K) * S_EARTH * 1e9
            ax.plot(x_trend, y_trend, color='red', linewidth=3, label="K-PROTOCOL Prediction ($\Delta c$)")
        
        ax.set_title(f"VLBI 40-Year Geometric Drift (From {base_date.year})", fontsize=15, fontweight='bold')
        ax.set_xlabel("Years Elapsed", fontsize=12)
        ax.set_ylabel("Phase Delay (ns)", fontsize=12)
        
        ax.grid(True, linestyle='--', alpha=0.5)
        ax.legend(loc='upper left', fontsize=11)
                
        st.pyplot(fig)
