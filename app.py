import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import glob
import os
import gzip
import io
from datetime import datetime

# ==========================================
# 🌌 K-PROTOCOL 절대 상수 및 마스터 포뮬러
# ==========================================
C_K = 297880197.6          # 절대 광속 (m/s)
S_EARTH = 1.006419562      # 지구 기하학적 왜곡 계수
DECAY_RATE_YR = 0.0023     # 연간 광속 감쇠율 (m/s)

st.set_page_config(page_title="K-PROTOCOL VLBI Analyzer (Empirical Proof)", layout="wide")

# ==========================================
# 🌐 다국어 및 UI 텍스트
# ==========================================
lang_opt = st.radio("Language / 언어 선택", ["한국어 (KO)", "English (EN)"], horizontal=True)
is_ko = "KO" in lang_opt

T = {
    "title": "🌌 K-PROTOCOL: VLBI 40-Year Time-Drift Analysis (진짜 관측 데이터 실증판)",
    "desc": "1979~2020 NASA CDDIS 원시 NGS 데이터의 '실제 관측 지연(Observed Delay)'을 추출하여 광속 감쇠($\Delta c$)를 실증합니다." if is_ko else "Demonstrating the speed of light decay ($\Delta c$) using actual observed delays from 1979-2020 NASA CDDIS raw NGS data.",
    "view_label": "👁️ 그래프 레이어 보기 옵션" if is_ko else "👁️ Graph Layer Options",
    "v_all": "전체 보기 (데이터 + 예측선 포개짐)" if is_ko else "View All (Data + Prediction Overlap)",
    "v_data": "관측 시점 데이터만 보기 (회색 점)" if is_ko else "Observation Points Only (Gray Dots)",
    "v_pred": "예측선만 보기 (붉은 선)" if is_ko else "Prediction Line Only (Red Line)",
    "upload_title": "📂 직접 데이터 업로드 및 테스트" if is_ko else "📂 Upload & Test Data",
    "upload_help": "NASA CDDIS에서 다운받은 .ngs 또는 .gz 파일을 드래그하여 추가하세요." if is_ko else "Drag and drop .ngs or .gz files downloaded from NASA CDDIS.",
}

st.title(T["title"])
st.write(T["desc"])
st.markdown("---")

view_mode = st.radio(T["view_label"], [T["v_all"], T["v_data"], T["v_pred"]], horizontal=True)

# ==========================================
# 🔍 [핵심 수정 1] 진짜 우주 관측값(Delay) 파서
# ==========================================
def parse_ngs_lines(lines, filename=""):
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
                # NGS 파일 규격: Card 02의 21번째~40번째 칸이 'Observed Delay (피코초, ps)' 입니다.
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
# 📂 왼쪽 사이드바: 데이터 다운로드 링크 & 업로더
# ==========================================
with st.sidebar:
    st.header(T["upload_title"])
    st.markdown("[🔗 NASA CDDIS VLBI Archive (Download)](https://cddis.nasa.gov/archive/vlbi/ivsdata/ngs/)")
    
    uploaded_files = st.file_uploader(
        T["upload_help"], 
        type=["ngs", "gz"], 
        accept_multiple_files=True
    )

all_data = []
local_files = glob.glob('data/*')
target_local = [f for f in local_files if f.endswith(('.ngs', '.gz'))]

for filepath in target_local:
    open_func = gzip.open if filepath.endswith('.gz') else open
    mode = 'rt' if filepath.endswith('.gz') else 'r'
    try:
        with open_func(filepath, mode) as f:
            all_data.extend(parse_ngs_lines(f.readlines(), os.path.basename(filepath)))
    except:
        pass

if uploaded_files:
    for u_file in uploaded_files:
        try:
            if u_file.name.endswith('.gz'):
                with gzip.open(u_file, 'rt') as f:
                    all_data.extend(parse_ngs_lines(f.readlines(), u_file.name))
            else:
                stringio = io.StringIO(u_file.getvalue().decode('utf-8', errors='ignore'))
                all_data.extend(parse_ngs_lines(stringio.readlines(), u_file.name))
        except:
            pass

# ==========================================
# 📊 [핵심 수정 2] 데이터 플롯 (동어반복 제거)
# ==========================================
if not all_data:
    st.info("💡 사이드바에서 데이터를 업로드하거나 `data` 폴더에 파일을 넣어주세요.")
else:
    with st.spinner("🚀 진짜 관측 잔차(Raw Residuals)를 추출하여 정렬 중입니다..."):
        df = pd.DataFrame(all_data)
        df = df.dropna(subset=['obs_delay_ns']) # 값이 있는 것만 필터링
        df = df.sort_values('date')
        
        base_date = df['date'].min()
        df['years_elapsed'] = (df['date'] - base_date).dt.total_seconds() / (365.25 * 24 * 3600)
        
        # 🚨주의: 예전 코드에 있던 df['k_delay_ns'] 강제 계산 코드를 완전히 삭제했습니다!
        
        show_data = view_mode in [T["v_all"], T["v_data"]]
        show_pred = view_mode in [T["v_all"], T["v_pred"]]
        
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
        st.success(f"🎯 총 **{len(df):,}개**의 진짜 관측 데이터(수식 비적용)가 렌더링 되었습니다. 붉은 선과 일치하는지 확인해 보십시오!")
