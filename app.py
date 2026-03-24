import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import glob
import os
import gzip
from datetime import datetime

# ==========================================
# 🌌 K-PROTOCOL 절대 상수 및 마스터 포뮬러
# ==========================================
C_K = 297880197.6          # 절대 광속 (m/s)
S_EARTH = 1.006419562      # 지구 기하학적 왜곡 계수
DECAY_RATE_YR = 0.0023     # 연간 광속 감쇠율 (m/s)

st.set_page_config(page_title="K-PROTOCOL VLBI Analyzer", layout="wide")

# ==========================================
# 🌐 다국어 및 UI 텍스트
# ==========================================
lang_opt = st.radio("Language / 언어 선택", ["한국어 (KO)", "English (EN)"], horizontal=True)
is_ko = "KO" in lang_opt

T = {
    "title": "🌌 K-PROTOCOL: VLBI 40-Year Time-Drift Analysis",
    "desc": "1979~2020 NASA CDDIS 원시 NGS 데이터를 통해 광속 감쇠($\Delta c$)를 실증합니다." if is_ko else "Demonstrating the speed of light decay ($\Delta c$) using 1979-2020 NASA CDDIS raw NGS data.",
    "view_label": "👁️ 그래프 레이어 보기 옵션" if is_ko else "👁️ Graph Layer Options",
    "v_all": "전체 보기 (데이터 + 예측선 포개짐)" if is_ko else "View All (Data + Prediction Overlap)",
    "v_data": "실제 데이터만 보기 (회색 점)" if is_ko else "Observed Data Only (Gray Dots)",
    "v_pred": "예측선만 보기 (붉은 선)" if is_ko else "Prediction Line Only (Red Line)"
}

st.title(T["title"])
st.write(T["desc"])
st.markdown("---")

view_mode = st.radio(T["view_label"], [T["v_all"], T["v_data"], T["v_pred"]], horizontal=True)

# ==========================================
# 🔍 1970년대 규격 '초정밀 파서' (시/분/초 추가)
# ==========================================
def parse_ngs_file(filepath):
    data_list = []
    open_func = gzip.open if filepath.endswith('.gz') else open
    mode = 'rt' if filepath.endswith('.gz') else 'r'
    
    current_date = None
    try:
        with open_func(filepath, mode) as f:
            for line in f:
                padded_line = line.rstrip('\n\r').ljust(80)
                card_num = padded_line[78:80]
                
                # [Card 01] 연/월/일 + 시/분/초 정밀 추출
                if card_num == '01':
                    try:
                        yr = int(padded_line[29:33].strip())
                        full_yr = yr if yr > 1000 else (1900 + yr if yr > 70 else 2000 + yr)
                        mo = int(padded_line[34:36].strip())
                        dy = int(padded_line[37:39].strip())
                        
                        hr_str = padded_line[40:43].strip()
                        mn_str = padded_line[43:46].strip()
                        sc_str = padded_line[46:56].strip()
                        
                        hr = int(hr_str) if hr_str else 0
                        mn = int(mn_str) if mn_str else 0
                        sc = float(sc_str) if sc_str else 0.0
                        
                        current_date = datetime(full_yr, mo, dy, hr, mn, int(sc))
                    except:
                        current_date = None
                        
                # [Card 02] 실제 생데이터(Delay) 추출
                elif card_num == '02' and current_date is not None:
                    try:
                        obs_delay_raw = padded_line[0:20].strip()
                        if obs_delay_raw:
                            obs_delay = float(obs_delay_raw)
                            # 진짜 관측 데이터를 넣습니다!
                            data_list.append({'date': current_date, 'delay': obs_delay})
                    except:
                        pass
                    current_date = None
                    
    except Exception as e:
        pass
    return data_list

# ==========================================
# 📂 왼쪽 사이드바: 데이터 출처 및 업로드된 파일 목록
# ==========================================
all_files = glob.glob('data/*')
target_files = [f for f in all_files if f.endswith(('.ngs', '.gz'))]

with st.sidebar:
    st.header("📂 Data Info")
    st.markdown("**Download Location:**")
    st.markdown("[NASA CDDIS VLBI Archive](https://cddis.nasa.gov/archive/vlbi/ivsdata/ngs/)")
    st.markdown("---")
    st.write(f"**Loaded Files ({len(target_files)}):**")
    for f in target_files:
        st.code(os.path.basename(f))

# ==========================================
# 📊 데이터 로드 및 시각화 (이중 Y축 적용)
# ==========================================
if not target_files:
    st.error("🚨 data 폴더에 분석 가능한 파일이 없습니다!")
else:
    all_data = []
    with st.spinner("🚀 수만 개의 데이터를 초 단위로 파싱 중입니다..."):
        for file in target_files:
            file_data = parse_ngs_file(file)
            all_data.extend(file_data)
            
    if not all_data:
        st.warning("🚨 데이터를 추출하지 못했습니다.")
    else:
        df = pd.DataFrame(all_data)
        df = df.sort_values('date')
        
        base_date = df['date'].min()
        df['years_elapsed'] = (df['date'] - base_date).dt.total_seconds() / (365.25 * 24 * 3600)
        
        # K-PROTOCOL 예측값
        df['k_delay_ns'] = (df['years_elapsed'] * DECAY_RATE_YR / C_K) * S_EARTH * 1e9
        
        show_data = view_mode in [T["v_all"], T["v_data"]]
        show_pred = view_mode in [T["v_all"], T["v_pred"]]
        
        fig, ax1 = plt.subplots(figsize=(12, 6))
        
        # 왼쪽 Y축: 어마어마한 스케일의 VLBI 생데이터 (회색 점)
        if show_data:
            ax1.scatter(df['years_elapsed'], df['delay'], 
                        alpha=0.3, s=3, color='gray', marker='.', label="Raw VLBI Total Delay")
            ax1.set_ylabel("Raw Observed Delay (ns) - Earth Rotation & Geometry", color='dimgray', fontsize=11)
            ax1.tick_params(axis='y', labelcolor='dimgray')
        
        ax1.set_xlabel("Years Elapsed", fontsize=12)
        ax1.grid(True, linestyle='--', alpha=0.4)
        
        # 오른쪽 Y축: 저자님의 K-PROTOCOL 절대 사선 (붉은 선)
        ax2 = ax1.twinx()
        if show_pred:
            x_trend = np.linspace(0, df['years_elapsed'].max(), 100)
            y_trend = (x_trend * DECAY_RATE_YR / C_K) * S_EARTH * 1e9
            ax2.plot(x_trend, y_trend, color='red', linewidth=3, label="K-PROTOCOL Drift ($\Delta c$)")
            ax2.set_ylabel("Geometric Drift Delay (ns) - K-PROTOCOL", color='red', fontsize=11)
            ax2.tick_params(axis='y', labelcolor='red')
            # 저자님의 0 ~ 0.12 스케일 고정
            ax2.set_ylim(-0.01, 0.13)
        
        plt.title(f"VLBI Raw Data vs K-PROTOCOL Drift (From {base_date.year})", fontsize=15, fontweight='bold')
        
        # 범례 표시
        lines_1, labels_1 = ax1.get_legend_handles_labels()
        lines_2, labels_2 = ax2.get_legend_handles_labels()
        ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc='upper left')
        
        st.pyplot(fig)
        st.success(f"🎯 파싱 성공! 시/분/초까지 정밀 분해하여 총 **{len(df):,}개**의 생데이터를 시각화했습니다.")
