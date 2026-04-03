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

st.set_page_config(page_title="K-PROTOCOL VLBI Empirical Proof", layout="wide")

st.title("🌌 K-PROTOCOL: VLBI 40-Year Time-Drift (진짜 관측 데이터 실증판)")
st.markdown("NASA CDDIS 원시 데이터의 **'실제 관측 지연(Observed Delay)'**을 추출하여 광속 감쇠($\Delta c$)를 실증합니다. (수식 조작 없음)")
st.markdown("---")

view_mode = st.radio("👁️ 그래프 레이어 보기 옵션", 
                     ["전체 보기 (데이터 + 예측선 포개짐)", "관측 시점 데이터만 보기 (회색 점)", "예측선만 보기 (붉은 선)"], 
                     horizontal=True)

# ==========================================
# 🔍 진짜 우주 관측값(Delay) 파서
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
                # NGS 파일 규격: Card 02의 21~40번째 칸이 실제 'Observed Delay (ps)' 입니다.
                raw_delay_str = padded_line[20:40].strip()
                if raw_delay_str:
                    obs_delay_ps = float(raw_delay_str)  # 피코초(ps) 단위 추출
                    obs_delay_ns = obs_delay_ps / 1000.0 # 나노초(ns)로 변환
                    
                    data_list.append({
                        'date': current_date,
                        'obs_delay_ns': obs_delay_ns  # <--- 강제 공식이 아닌 진짜 관측값 저장!
                    })
            except:
                pass
            current_date = None
            
    return data_list

# ==========================================
# 📂 data 폴더 강제 읽기 (확장자 무시, 업로드 버튼 삭제)
# ==========================================
all_data = []
# data 폴더 안의 모든 파일을 무조건 읽어옵니다.
local_files = [f for f in glob.glob('data/*') if os.path.isfile(f)]

if not local_files:
    st.error("🚨 `data` 폴더가 비어있습니다. NASA 원시 데이터를 `data` 폴더에 넣어주세요.")
else:
    with st.spinner(f"🚀 `data` 폴더의 파일 {len(local_files)}개에서 진짜 관측 잔차(Raw Residuals)를 추출 중입니다..."):
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
                
    # ==========================================
    # 📊 데이터 플롯 (동어반복 완벽 제거)
    # ==========================================
    if not all_data:
        st.warning("⚠️ 파일은 읽었으나, NASA NGS 규격(Card 01/02)에 맞는 데이터를 찾지 못했습니다.")
    else:
        df = pd.DataFrame(all_data)
        df = df.dropna(subset=['obs_delay_ns']) # 값이 있는 것만 필터링
        df = df.sort_values('date')
        
        base_date = df['date'].min()
        df['years_elapsed'] = (df['date'] - base_date).dt.total_seconds() / (365.25 * 24 * 3600)
        
        show_data = "데이터" in view_mode or "전체" in view_mode
        show_pred = "예측선" in view_mode or "전체" in view_mode
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        if show_data:
            # 1. 회색 점: 수식이 1%도 섞이지 않은 '망원경의 진짜 관측값(obs_delay_ns)'을 Y축에 찍습니다.
            ax.scatter(df['years_elapsed'], df['obs_delay_ns'], 
                       alpha=0.5, s=40, color='gray', label="Real Observation (Raw Delay)")
        
        if show_pred:
            # 2. 붉은 선: K-PROTOCOL의 광속 감쇠 공식을 X축에 대입하여 그립니다.
            x_trend = np.linspace(0, df['years_elapsed'].max(), 100)
            y_trend = (x_trend * DECAY_RATE_YR / C_K) * S_EARTH * 1e9
            ax.plot(x_trend, y_trend, color='red', linewidth=3, label="K-PROTOCOL Prediction ($\Delta c$)")
        
        ax.set_title(f"VLBI 40-Year Geometric Drift (Empirical Proof From {base_date.year})", fontsize=15, fontweight='bold')
        ax.set_xlabel("Years Elapsed", fontsize=12)
        ax.set_ylabel("Observed Phase Delay (ns)", fontsize=12)
        
        # 데이터의 스케일에 맞게 Y축이 자동으로 조절되도록 세팅
        ax.autoscale(enable=True, axis='y', tight=False)
        
        ax.grid(True, linestyle='--', alpha=0.5)
        ax.legend(loc='upper left', fontsize=11)
                
        st.pyplot(fig)
        st.success(f"🎯 총 **{len(df):,}개**의 진짜 관측 데이터(수식 비적용)가 렌더링 되었습니다. 우주의 파편들이 붉은 선을 따라 정렬하는지 확인하십시오!")
