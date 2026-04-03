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
st.title("⚖️ K-PROTOCOL: 전 세계 기선 무조건 출력판")
st.markdown("단 1년 치 데이터만 있어도 숨기지 않고 무조건 화면에 띄웁니다. 다운로드하신 파일의 실제 관측소 내역을 확인하십시오.")
st.markdown("---")

# ==========================================
# 🔍 초강력 관측소 추출기 (특수문자 제거, 구조 무시)
# ==========================================
def extract_stations_smart(lines):
    stations = {}
    for line in lines:
        if isinstance(line, bytes): line = line.decode('utf-8', errors='ignore')
        up_line = line.upper().strip()
        
        # 헤더가 끝나면 멈춤
        if "$END" in up_line: break 
        
        parts = up_line.split()
        if len(parts) >= 4:
            # 줄 안에서 "이름 + 숫자3개" 패턴을 이 잡듯이 뒤집니다.
            for i in range(len(parts) - 3):
                try:
                    x, y, z = float(parts[i+1]), float(parts[i+2]), float(parts[i+3])
                    # 지구 반지름(수백만) 스케일의 진짜 좌표인지 확인
                    if abs(x) > 100000:
                        # 관측소 이름에 섞인 이상한 기호 제거
                        name = re.sub(r'[^A-Z0-9]', '', parts[i])
                        stations[name] = np.array([x, y, z])
                        break # 이 줄에서는 좌표를 찾았으니 다음 줄로 이동
                except ValueError:
                    continue
    return stations

# ==========================================
# 📂 데이터 로드 및 싹쓸이
# ==========================================
baselines = []
inventory_list = [] # 화면에 표로 보여줄 내역

local_files = [f for f in glob.glob('data/*') if os.path.isfile(f)]

if not local_files:
    st.error("🚨 `data` 폴더가 비어있습니다. 데이터를 넣어주세요.")
else:
    with st.spinner("🚀 파일 헤더를 정밀 스캔하여 1년 치 데이터라도 무조건 뽑아냅니다..."):
        for filepath in local_files:
            fname = os.path.basename(filepath)
            try:
                # 연도 추출
                year_match = re.search(r'\d+', fname)
                yr_val = int(year_match.group()[:2]) if year_match else 0
                year = yr_val + (1900 if yr_val > 70 else 2000)
                
                open_func = gzip.open if filepath.endswith('.gz') else open
                with open_func(filepath, 'rt', encoding='utf-8', errors='ignore') as f:
                    stations = extract_stations_smart(f.readlines())
                    st_names = sorted(stations.keys())
                    
                    if len(st_names) >= 2:
                        for i in range(len(st_names)):
                            for j in range(i+1, len(st_names)):
                                s1, s2 = st_names[i], st_names[j]
                                dist = np.linalg.norm(stations[s1] - stations[s2])
                                baselines.append({'year': year, 'baseline': f"{s1} - {s2}", 'distance': dist})
                    
                    # 표에 그리기 위해 내역 저장
                    inventory_list.append({
                        "연도": year,
                        "파일명": fname,
                        "관측소 수": len(st_names),
                        "발견된 관측소 목록": ", ".join(st_names) if st_names else "없음"
                    })
            except: continue

    # ==========================================
    # 📊 숨김 없는 결과 출력
    # ==========================================
    if not baselines:
        st.error("🚨 기선을 하나도 추출하지 못했습니다. 파일이 손상되었을 수 있습니다.")
    else:
        df = pd.DataFrame(baselines)
        df_avg = df.groupby(['year', 'baseline'])['distance'].mean().reset_index()
        baseline_counts = df_avg.groupby('baseline')['year'].nunique()
        
        # 🔥 [핵심 수정] 2년 이상 조건 삭제! 모든 기선을 무조건 목록에 띄웁니다.
        all_baselines = baseline_counts.index.tolist()
        all_baselines.sort(key=lambda b: baseline_counts[b], reverse=True)
        
        with st.sidebar:
            st.header("⚙️ 분석 기선 선택")
            st.write("단 1년만 관측된 기선이라도 모두 선택할 수 있습니다.")
            selected_baseline = st.selectbox(
                "기선 목록 (전체)", 
                all_baselines, 
                format_func=lambda x: f"{x} ({baseline_counts[x]}년 관측)"
            )
        
        plot_df = df_avg[df_avg['baseline'] == selected_baseline].sort_values('year')
        
        st.success(f"🔥 **{selected_baseline}** 기선을 선택했습니다.")

        fig, ax = plt.subplots(figsize=(12, 6))
        
        x_raw = plot_df['year'].values
        y_raw = plot_df['distance'].values
        
        # 1년 치 데이터일 경우 점만 찍음 (에러 내지 않음!)
        if len(plot_df) < 2:
            st.warning("⚠️ 이 기선은 1년 치 데이터만 있어서 붉은선(추세)을 그릴 수 없습니다. 아래 파란 점 하나로 절대 거리만 표시합니다.")
            ax.scatter(x_raw, y_raw, color='blue', s=200, edgecolors='black', label="Observed Distance (1 Point)")
            ax.set_ylabel("Absolute Distance (m)", fontsize=12)
            
            # X축이 한 점에 뭉치지 않게 여유 공간 설정
            ax.set_xlim(x_raw[0] - 5, x_raw[0] + 5)
            
        # 2년 치 이상 데이터일 경우 정상적으로 선을 그림
        else:
            x_norm = x_raw - x_raw.min()
            y_norm = y_raw - y_raw[0]
            
            ax.scatter(x_raw, y_norm, color='blue', s=150, alpha=0.7, edgecolors='black', zorder=3, label="NASA Observed")
            m, b = np.polyfit(x_norm, y_norm, 1)
            ax.plot(x_raw, m * x_norm, 'b--', linewidth=2, alpha=0.6, label=f"NASA Trend: {m*1000:.2f} mm/yr")
            
            avg_dist = y_raw.mean()
            k_drift_annual = avg_dist * (DECAY_RATE_YR / C_K) * S_EARTH
            ax.plot(x_raw, k_drift_annual * x_norm, color='red', linewidth=4, zorder=4, label=f"K-PROTOCOL: {k_drift_annual*1000:.2f} mm/yr")
            ax.set_ylabel("Distance Change (m)", fontsize=12)

        ax.set_title(f"Baseline Evolution: {selected_baseline}", fontsize=16, fontweight='bold')
        ax.set_xlabel("Year", fontsize=12)
        ax.grid(True, linestyle='--', alpha=0.6)
        ax.legend(fontsize=11)
        st.pyplot(fig)

        # 📋 데이터 팩트 폭행 테이블 (사용자 파일 내역 검증용)
        st.markdown("### 📋 내 폴더에 있는 파일들의 진짜 내용물 (Fact Check)")
        st.markdown("왜 1년 치 기선이 많은지 아래 표의 **'발견된 관측소 목록'**을 비교해 보세요. 연도별로 참여한 망원경이 달라서 짝꿍이 성립되지 않은 것입니다.")
        
        # 보기 편하게 데이터프레임으로 출력
        inv_df = pd.DataFrame(inventory_list).sort_values('연도')
        st.dataframe(inv_df, use_container_width=True)
