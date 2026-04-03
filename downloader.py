import os
import requests
import re
from bs4 import BeautifulSoup

# GitHub Secrets에서 NASA 계정 정보를 가져옵니다.
USERNAME = os.getenv('NASA_USER')
PASSWORD = os.getenv('NASA_PASS')
YEARS = ['1980', '1990', '2000', '2010', '2020']
SAVE_DIR = 'data'
os.makedirs(SAVE_DIR, exist_ok=True)

def download_data():
    session = requests.Session()
    session.auth = (USERNAME, PASSWORD)
    
    # [핵심] NASA 보안 인증을 위해 쿠키를 미리 생성합니다.
    print("🔐 NASA Earthdata 서버 인증 시도 중...")
    session.get("https://urs.earthdata.nasa.gov/home")

    for year in YEARS:
        print(f"🚀 {year}년 정밀 스캔 및 다운로드 시작...")
        url = f"https://cddis.nasa.gov/archive/vlbi/ivsdata/ngs/{year}/"
        
        try:
            resp = session.get(url)
            if resp.status_code != 200:
                print(f"❌ {year}년 디렉토리 접속 실패 (HTTP {resp.status_code})")
                continue

            soup = BeautifulSoup(resp.text, 'html.parser')
            # R1, R4, X, S 세션만 정밀 타겟팅
            links = [a['href'] for a in soup.find_all('a', href=True) 
                     if a['href'].endswith('.gz') and any(x in a['href'].upper() for x in ['R1', 'R4', 'X', 'S'])]
            
            best_files = {}
            for link in links:
                fname = link.split('/')[-1]
                match = re.search(r'N(\d+)', fname)
                if match:
                    base = fname.split('N')[0]
                    ver = int(match.group(1))
                    if base not in best_files or ver > best_files[base]['ver']:
                        best_files[base] = {'ver': ver, 'link': link}

            count = 0
            # 연도별로 가장 품질이 좋은 파일 상위 10개씩 추출
            for base in list(best_files.keys())[:10]:
                link = best_files[base]['link']
                fname = link.split('/')[-1]
                save_path = os.path.join(SAVE_DIR, fname)
                
                # 이미 다운받은 파일은 건너뛰어 시간 절약
                if os.path.exists(save_path):
                    print(f"   ⏩ 이미 존재함: {fname}")
                    continue

                print(f"   📥 다운로드 중: {fname}...")
                f_resp = session.get(url + link if not link.startswith('http') else link)
                
                # 용량이 1KB 이하인 깡통 파일은 걸러냅니다.
                if f_resp.status_code == 200 and len(f_resp.content) > 1000:
                    with open(save_path, 'wb') as f:
                        f.write(f_resp.content)
                    count += 1
                    print(f"   ✅ 성공 ({len(f_resp.content)//1024} KB)")
                else:
                    print(f"   ⚠️ 실패 (파일 크기 미달 또는 권한 없음)")
            print(f"🎯 {year}년 스캔 완료: {count}개 신규 수집\n")
            
        except Exception as e:
            print(f"❌ {year}년 처리 중 에러 발생: {e}\n")

if __name__ == "__main__":
    download_data()
