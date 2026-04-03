import os
import requests
from bs4 import BeautifulSoup
import re

# GitHub Secrets에서 NASA 계정 정보를 가져옵니다.
USERNAME = os.getenv('NASA_USER')
PASSWORD = os.getenv('NASA_PASS')
YEARS = ['1980', '1990', '2000', '2010', '2020']
SAVE_DIR = 'data'
os.makedirs(SAVE_DIR, exist_ok=True)

# 🚀 [핵심 돌파구] NASA 공식 권장 방식: 서버에 VIP 패스(.netrc)를 직접 만듭니다.
netrc_path = os.path.expanduser('~/.netrc')
with open(netrc_path, 'w') as f:
    f.write(f"machine urs.earthdata.nasa.gov login {USERNAME} password {PASSWORD}\n")
os.chmod(netrc_path, 0o600) # 보안 권한 설정

def download_data():
    # Session 객체만 만들면, requests가 알아서 VIP 패스(.netrc)를 들고 들어갑니다.
    session = requests.Session()
    
    for year in YEARS:
        print(f"🚀 {year}년 폴더 VIP 패스로 접근 중...")
        url = f"https://cddis.nasa.gov/archive/vlbi/ivsdata/ngs/{year}/"
        
        try:
            resp = session.get(url)
            
            # 접근이 거부되어 로그인 페이지로 쫓겨났는지 확인
            if "Earthdata Login" in resp.text:
                print(f"❌ {year}년 실패: VIP 패스가 거부되었습니다. (아이디/비밀번호 오타 확인 필요)")
                continue

            soup = BeautifulSoup(resp.text, 'html.parser')
            links = [a['href'] for a in soup.find_all('a', href=True) if a['href'].endswith('.gz')]
            valid_links = [l for l in links if any(x in l.upper() for x in ['R1', 'R4', 'X', 'S'])]
            
            if not valid_links:
                print(f"⚠️ {year}년: 폴더는 열렸으나 조건(R1, R4 등)에 맞는 파일이 없습니다.")
                continue
                
            print(f"🔍 {year}년: {len(valid_links)}개의 타겟 데이터 발견, 다운로드 준비!")
            
            best_files = {}
            for link in valid_links:
                fname = link.split('/')[-1]
                match = re.search(r'N(\d+)', fname)
                if match:
                    base = fname.split('N')[0]
                    ver = int(match.group(1))
                    if base not in best_files or ver > best_files[base]['ver']:
                        best_files[base] = {'ver': ver, 'link': link}

            count = 0
            for base in list(best_files.keys())[:10]:
                link = best_files[base]['link']
                fname = link.split('/')[-1]
                save_path = os.path.join(SAVE_DIR, fname)
                
                if os.path.exists(save_path): 
                    continue
                
                print(f"   📥 다운로드 중: {fname}")
                f_resp = session.get(url + link if not link.startswith('http') else link)
                
                if f_resp.status_code == 200 and len(f_resp.content) > 1000:
                    with open(save_path, 'wb') as f:
                        f.write(f_resp.content)
                    count += 1
                    print(f"   ✅ 다운로드 완료! ({len(f_resp.content)//1024} KB)")
                else:
                    print(f"   ⚠️ 실패: 빈 파일입니다.")
                    
            print(f"🎯 {year}년 총 {count}개 파일 획득 성공\n")
            
        except Exception as e:
            print(f"❌ {year}년 치명적 에러: {e}\n")

if __name__ == "__main__":
    if not USERNAME or not PASSWORD:
        print("🚨 오류: 깃허브 Secrets에 NASA_USER 또는 NASA_PASS가 없습니다!")
    else:
        download_data()
