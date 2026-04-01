import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
import os
import re
import time

# 1. 대상 문서 리스트 (엑셀 GetTargetCodes 동일)
TARGET_CODES = [
    "KOLAS-R-001", "KOLAS-R-002", "KOLAS-R-003", "KOLAS-R-004",
    "KOLAS-R-005", "KOLAS-R-006", "KOLAS-R-007", "KOLAS-SR-002",
    "KOLAS-G-001", "KOLAS-G-004", "KOLAS-G-005", "KOLAS-G-008",
    "KOLAS-G-011", "KOLAS-G-013"
]

# 2. 기준 데이터 로드
last_info = {}
if os.path.exists('last_data.txt'):
    with open('last_data.txt', 'r', encoding='utf-8') as f:
        for line in f:
            if '|' in line:
                code, date = line.strip().split('|')
                last_info[code.strip()] = date.strip()
else:
    # 파일이 없으면 오늘 날짜로 초기값 설정
    for code in TARGET_CODES:
        last_info[code] = "2000-01-01"

LIST_URL = "https://www.knab.go.kr/inf/bbs/lawrecsroom/LawRecsRoomList.do"

# 3. 브라우저 헤더 설정
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Referer': 'https://www.knab.go.kr/inf/bbs/lawrecsroom/LawRecsRoom.do'
}

updated_docs = []
current_info = last_info.copy()

# 4. 세션 유지 및 탐색
session = requests.Session()

for page in range(1, 11): # 우선 1~10페이지만 정밀 탐색
    print(f"▶ 페이지 {page} 분석 중...")
    
    # 엑셀 매크로의 postData와 100% 동일하게 구성
    payload = {
        'pageNo': str(page),
        'boardSn': '',
        'xlsDownloadYn': 'N',
        'totalCount': '',
        'searchCat3': '',
        'searchStartDate': '',
        'searchEndDate': '',
        'searchType': 'A',
        'searchKeyword': ''
    }
    
    try:
        # 엑셀처럼 POST 요청 (타임아웃 넉넉히)
        response = session.post(LIST_URL, headers=headers, data=payload, timeout=30)
        response.encoding = 'utf-8'
        
        if response.status_code != 200 or "board_list" not in response.text:
            print(f"   ⚠️ 응답 오류 (상태코드: {response.status_code})")
            break
            
        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.select('table.board_list tbody tr')
        
        if not rows or "등록된 게시물이 없습니다" in response.text:
            break

        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 4: continue
            
            title = cols[3].get_text(" ", strip=True)
            designated_date = cols[2].get_text(strip=True) # 지정일
            
            # 제목에서 날짜 추출 (엑셀 ExtractLastDateFromTitle 동일 로직)
            date_match = re.search(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', title)
            if date_match:
                y, m, d = date_match.groups()
                row_date = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
            else:
                row_date = designated_date

            # 관리 대상 문서인지 확인
            for code in TARGET_CODES:
                if code.replace('-', '') in title.replace('-', ''):
                    # 날짜 비교 및 업데이트
                    if row_date > last_info.get(code, "2000-01-01"):
                        print(f"   [!] 발견: {code} ({row_date})")
                        updated_docs.append(f"• {code}\n  - 제목: {title}\n  - 날짜: {row_date}")
                        current_info[code] = row_date
                    break
        
        time.sleep(1.5)

    except Exception as e:
        print(f"   ❌ 에러: {e}")
        break

# 5. 결과 발송
if updated_docs:
    content = "KOLAS 관리문서 업데이트 내역:\n\n" + "\n\n".join(set(updated_docs))
    msg = MIMEText(content)
    msg['Subject'] = f"[KOLAS 알림] {len(updated_docs)}건의 개정 문서 발견"
    msg['From'] = os.environ['GMAIL_USER']
    msg['To'] = os.environ['RECEIVER_EMAIL']

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(os.environ['GMAIL_USER'], os.environ['GMAIL_PW'])
        server.sendmail(msg['From'], msg['To'], msg.as_string())
    
    # 갱신된 날짜 저장
    with open('last_data.txt', 'w', encoding='utf-8') as f:
        for code, date in sorted(current_info.items()):
            f.write(f"{code}|{date}\n")
    print("✅ 메일 발송 및 데이터 갱신 완료")
else:
    print("ℹ️ 변경 사항이 없습니다.")
