import os
import requests
from bs4 import BeautifulSoup
import re

# GitHub Secrets에서 정보를 안전하게 가져옵니다.
USERNAME = os.getenv('NASA_USER')
PASSWORD = os.getenv('NASA_PASS')
YEARS = ['1980', '1990', '2000', '2010', '2020']
SAVE_DIR = 'data'

if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

# NASA 보안 리다이렉트 대응용 클래스
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
        print(f"🚀 {year}년 데이터 탐색 시작...")
        url = f"https://cddis.nasa.gov/archive/vlbi/ivsdata/ngs/{year}/"
        
        try:
            resp = session.get(url, auth=auth)
            if resp.status_code != 200:
                print(f"❌ {year}년 접속 실패 (코드: {resp.status_code})")
                continue

            soup = BeautifulSoup(resp.text, 'html.parser')
            # R1, R4 세션 또는 용량이 큰 X 세션 위주로 필터링
            links = [a['href'] for a in soup.find_all('a', href=True) 
                     if a['href'].endswith('.gz') and any(x in a['href'].upper() for x in ['R1', 'R4', 'X'])]
            
            best_files = {}
            for link in links:
                base = link.split('__N')[0]
                try:
                    ver_part = link.split('__N')[1].split('.')[0]
                    ver = int(re.sub(r'[^0-9]', '', ver_part))
                    if base not in best_files or ver > best_files[base]['ver']:
                        best_files[base] = {'ver': ver, 'link': link}
                except: continue

            for base in list(best_files.keys())[:7]: 
                fname = best_files[base]['link']
                save_path = os.path.join(SAVE_DIR, fname)
                if os.path.exists(save_path): continue
                
                print(f"📥 다운로드: {fname}")
                file_resp = session.get(url + fname, auth=auth)
                if file_resp.status_code == 200:
                    with open(save_path, 'wb') as f:
                        f.write(file_resp.content)
            print(f"✅ {year}년 완료")
        except Exception as e:
            print(f"❌ {year}년 에러: {e}")

if __name__ == "__main__":
    download_data()
