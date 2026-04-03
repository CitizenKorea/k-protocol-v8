import os
import requests
from bs4 import BeautifulSoup
import re

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
    # NASA 보안은 리다이렉트를 따라가며 인증을 유지하는게 핵심입니다.
    session.auth = (USERNAME, PASSWORD)
    auth = NASAAuth(USERNAME, PASSWORD)

    for year in YEARS:
        print(f"🚀 {year}년 정밀 스캔 시작...")
        url = f"https://cddis.nasa.gov/archive/vlbi/ivsdata/ngs/{year}/"
        
        try:
            # 1. 페이지 접속 시도
            resp = session.get(url, auth=auth, allow_redirects=True)
            
            # [진단] 페이지 내용 확인
            if "Earthdata Login" in resp.text:
                print(f"❌ {year}년 실패: 로그인 페이지에서 멈췄습니다. 아이디/비번 혹은 권한 설정을 확인하세요.")
                continue
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            all_links = [a['href'] for a in soup.find_all('a', href=True)]
            print(f"🔍 총 {len(all_links)}개의 링크를 발견했습니다.")

            # 2. 파일 필터링 (조건을 더 완만하게 수정)
            gz_links = [l for l in all_links if l.endswith('.gz')]
            valid_links = [l for l in gz_links if any(x in l.upper() for x in ['R1', 'R4', 'X', 'S'])]
            print(f"📦 그 중 조건에 맞는 파일은 {len(valid_links)}개입니다.")
            
            best_files = {}
            for link in valid_links:
                # 파일명만 추출 (경로 포함 시 대비)
                fname = link.split('/')[-1]
                # 버전 숫자 추출 (_N 또는 __N 모두 대응)
                match = re.search(r'N(\d+)', fname)
                if match:
                    base = fname.split('N')[0]
                    ver = int(match.group(1))
                    if base not in best_files or ver > best_files[base]['ver']:
                        best_files[base] = {'ver': ver, 'link': link}

            # 3. 다운로드 실행
            count = 0
            for base in list(best_files.keys())[:8]:
                link = best_files[base]['link']
                fname = link.split('/')[-1]
                save_path = os.path.join(SAVE_DIR, fname)
                
                print(f"📥 다운로드 시도: {fname}")
                # NASA는 파일 요청 시 다시 한번 인증이 필요할 수 있습니다.
                f_resp = session.get(url + link if not link.startswith('http') else link, auth=auth)
                
                if f_resp.status_code == 200:
                    with open(save_path, 'wb') as f:
                        f.write(f_resp.content)
                    count += 1
                else:
                    print(f"   ⚠️ 다운로드 실패 (코드: {f_resp.status_code})")
            
            print(f"✅ {year}년 완료: {count}개 성공")
            
        except Exception as e:
            print(f"❌ {year}년 치명적 에러: {e}")

if __name__ == "__main__":
    download_data()
