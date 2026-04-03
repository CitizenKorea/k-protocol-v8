import os
import requests
from bs4 import BeautifulSoup

# GitHub Secrets에서 정보를 가져옵니다.
USERNAME = os.getenv('NASA_USER')
PASSWORD = os.getenv('NASA_PASS')
YEARS = ['1980', '1990', '2000', '2010', '2020']
SAVE_DIR = 'data'

if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

def download_data():
    session = requests.Session()
    session.auth = (USERNAME, PASSWORD)

    for year in YEARS:
        url = f"https://cddis.nasa.gov/archive/vlbi/ivsdata/ngs/{year}/"
        try:
            resp = session.get(url)
            soup = BeautifulSoup(resp.text, 'html.parser')
            # R1, R4 세션 또는 용량이 큰 X 세션 위주로 필터링
            links = [a['href'] for a in soup.find_all('a', href=True) 
                     if a['href'].endswith('.gz') and any(x in a['href'].upper() for x in ['R1', 'R4', 'X'])]
            
            # 각 세션별 최신 버전만 골라내기
            best_files = {}
            for link in links:
                base = link.split('__N')[0]
                try:
                    ver = int(link.split('__N')[1].split('.')[0])
                    if base not in best_files or ver > best_files[base]['ver']:
                        best_files[base] = {'ver': ver, 'link': link}
                except: continue

            # 연도별로 상위 5개씩만 다운로드
            for base in list(best_files.keys())[:5]:
                fname = best_files[base]['link']
                save_path = os.path.join(SAVE_DIR, fname)
                print(f"📥 {year}년 데이터 수집: {fname}")
                r = session.get(url + fname)
                with open(save_path, 'wb') as f:
                    f.write(r.content)
        except Exception as e:
            print(f"❌ {year}년 처리 중 에러: {e}")

if __name__ == "__main__":
    download_data()
