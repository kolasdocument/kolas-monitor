import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
import os
import re
import time

# 1. 기존 데이터 로드
last_info = {}
if os.path.exists('last_data.txt'):
    with open('last_data.txt', 'r', encoding='utf-8') as f:
        for line in f:
            if '|' in line:
                code, date = line.strip().split('|')
                last_info[code.strip()] = date.strip()

# 실제 데이터가 들어오는 '진짜' 주소
BASE_URL = "https://www.knab.go.kr/inf/bbs/lawrecsroom/LawRecsRoom.do"
LIST_URL = "https://www.knab.go.kr/inf/bbs/lawrecsroom/LawRecsRoomList.do"

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Origin': 'https://www.knab.go.kr',
    'Referer': BASE_URL,
    'Upgrade-Insecure-Requests': '1'
}

updated_docs = []
current_info = last_info.copy()

# 2. 세션 생성 및 '입장권(쿠키)' 획득
session = requests.Session()

try:
    # 먼저 메인 리스트 페이지에 접속하여 서버가 주는 세션 쿠키를 받습니다.
    print("사이트 접속 및 세션 확보 중...")
    first_res = session.get(BASE_URL, headers=headers, timeout=20)
    time.sleep(2) # 실제 사람처럼 약간의 대기
except Exception as e:
    print(f"초기 접속 실패: {e}")

# 3. 페이지 탐색 시작
page = 1
while True:
    print(f"--- {page}페이지 데이터 요청 중 ---")
    
    # 엑셀 매크로에서 성공했던 파라미터 100% 복제
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
        # 세션(쿠키)을 유지한 상태로 데이터 요청
        response = session.post(LIST_URL, headers=headers, data=payload, timeout=30)
        response.encoding = 'utf-8'
        
        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.select('table.board_list tbody tr')

        # 데이터가 없는 경우 종료 조건
        if not rows or "등록된 게시물이 없습니다" in soup.text:
            print(f"마지막 페이지({page-1})까지 확인을 마쳤습니다.")
            break

        print(f"  성공: {len(rows)}개의 항목을 발견했습니다.")

        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 4: continue
            
            title_text = cols[3].get_text(" ", strip=True)
            designated_date = cols[2].get_text(strip=True)
            
            # 날짜 추출 (제목의 날짜 우선, 없으면 지정일)
            date_match = re.search(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', title_text)
            if date_match:
                year, month, day = date_match.groups()
                current_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            else:
                current_date = designated_date

            # 문서 코드 대조 (KOLAS-R-001 등)
            for doc_code in last_info.keys():
                if doc_code.replace('-', '') in title_text.replace('-', ''):
                    current_info[doc_code] = current_date
                    if current_date > last_info[doc_code]:
                        print(f"  [!] 업데이트! {doc_code}: {current_date}")
                        updated_docs.append(f"▶ {doc_code} 개정\n- 제목: {title_text}\n- 날짜: {current_date}")
                    break

        page += 1
        time.sleep(1) # 차단 방지를 위한 간격
        if page > 30: break

    except Exception as e:
        print(f"데이터 요청 중 에러: {e}")
        break

# 4. 결과 발송
if updated_docs:
    msg_text = "KOLAS 전체 페이지 모니터링 결과:\n\n" + "\n\n".join(set(updated_docs))
    msg = MIMEText(msg_text)
    msg['Subject'] = "[KOLAS] 관리문서 업데이트 알림"
    msg['From'] = os.environ['GMAIL_USER']
    msg['To'] = os.environ['RECEIVER_EMAIL']

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(os.environ['GMAIL_USER'], os.environ['GMAIL_PW'])
        server.sendmail(msg['From'], msg['To'], msg.as_string())

    with open('last_data.txt', 'w', encoding='utf-8') as f:
        for code, date in sorted(current_info.items()):
            f.write(f"{code}|{date}\n")
    print("갱신 및 메일 발송 완료!")
else:
    print("변동 사항이 없습니다.")
