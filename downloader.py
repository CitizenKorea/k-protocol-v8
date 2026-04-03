import os
import requests
from bs4 import BeautifulSoup
import re

# GitHub Secrets에서 정보를 가져옵니다.
USERNAME = os.getenv('NASA_USER')
PASSWORD = os.getenv('NASA_PASS')
YEARS = ['1980', '1990', '2000', '2010', '2020']
SAVE_DIR = 'data'

if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

class NASAAuth(requests.auth.AuthBase):
    def __init__(self, user, pw):
        self.user = user
        self.pw = pw
    def __call__(self, r):
        r.headers['Authorization'] = requests.auth._basic_auth_str(self.user, self.pw)
        return r

def download_data():
    session = requests.Session()
    auth = NASAAuth(USERNAME, PASSWORD)

    for year in YEARS:
        print(f"🚀 {year}년 데이터 정밀 스캔 시작...")
        url = f"https://cddis.nasa.gov/archive/vlbi/ivsdata/ngs/{year}/"
        
        try:
            resp = session.get(url, auth=auth)
            if resp.status_code != 200:
                print(f"❌ {year}년 접속 실패: {resp.status_code}")
                continue

            soup = BeautifulSoup(resp.text, 'html.parser')
            # 1. 모든 .gz 파일 링크를 가져옵니다.
            all_links = [a['href'] for a in soup.find_all('a', href=True) if a['href'].endswith('.gz')]
            
            # 2. R1, R4, X, S 세션 중 하나라도 포함된 것 필터링 (80년대 S 세션 추가)
            valid_links = [l for l in all_links if any(x in l.upper() for x in ['R1', 'R4', 'X', 'S'])]
            
            best_files = {}
            for link in valid_links:
                # 💡 핵심 수정: _N 또는 __N 뒤의 숫자를 유연하게 추출
                match = re.search(r'(_+N)(\d+)', link)
                if match:
                    base = link.split(match.group(1))[0] # N 앞부분 (세션명)
                    ver = int(match.group(2))           # N 뒷부분 (버전숫자)
                    
                    if base not in best_files or ver > best_files[base]['ver']:
                        best_files[base] = {'ver': ver, 'link': link}

            # 3. 각 연도별로 상위 10개씩 다운로드
            count = 0
            for base in list(best_files.keys())[:10]:
                fname = best_files[base]['link']
                save_path = os.path.join(SAVE_DIR, fname)
                
                print(f"📥 발견: {fname} (버전 {best_files[base]['ver']})")
                file_resp = session.get(url + fname, auth=auth)
                if file_resp.status_code == 200:
                    with open(save_path, 'wb') as f:
                        f.write(file_resp.content)
                    count += 1
            print(f"✅ {year}년 완료: {count}개 수집됨")
            
        except Exception as e:
            print(f"❌ {year}년 에러: {e}")

if __name__ == "__main__":
    download_data()
