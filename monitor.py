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

# URL 설정
BASE_URL = "https://www.knab.go.kr/inf/bbs/lawrecsroom/LawRecsRoom.do"
LIST_URL = "https://www.knab.go.kr/inf/bbs/lawrecsroom/LawRecsRoomList.do"

# 헤더를 엑셀(MSXML) 수준으로 단순화하면서도 브라우저처럼 보이게 설정
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0',
    'Content-Type': 'application/x-www-form-urlencoded', # 엑셀과 동일 설정
    'Accept': '*/*',
    'Origin': 'https://www.knab.go.kr',
    'Referer': BASE_URL
}

updated_docs = []
current_info = last_info.copy()

session = requests.Session()

# 2. 첫 접속으로 세션 유지 (엑셀은 안 하지만 파이썬은 필요할 수 있음)
try:
    session.get(BASE_URL, headers=headers, timeout=10)
except:
    pass

# 3. 페이지 탐색 시작
page = 1
while True:
    print(f"--- {page}페이지 시도 중 ---")
    
    # [핵심] 엑셀 매크로의 postData와 글자 하나 안 틀리고 똑같이 만듭니다.
    # 딕셔너리가 아닌 '문자열'로 직접 조립합니다.
    raw_payload = (
        f"pageNo={page}"
        "&boardSn="
        "&xlsDownloadYn=N"
        "&totalCount="
        "&searchCat3="
        "&searchStartDate="
        "&searchEndDate="
        "&searchType=A"
        "&searchKeyword="
    )
    
    try:
        # data 파라미터에 딕셔너리가 아닌 조립된 문자열(raw_payload)을 넣습니다.
        response = session.post(LIST_URL, headers=headers, data=raw_payload, timeout=20)
        
        # 서버 응답 확인
        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.select('table.board_list tbody tr')

        # 데이터 검증 로그
        if not rows or "등록된 게시물이 없습니다" in soup.text:
            # 만약 1페이지부터 이 메시지가 뜬다면 서버가 우리를 차단한 것입니다.
            if page == 1:
                print("⚠️ 경고: 1페이지부터 데이터를 가져오지 못했습니다. (보안 차단 가능성)")
            break

        print(f"  -> {len(rows)}개의 항목 발견!")

        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 4: continue
            
            title_text = cols[3].get_text(" ", strip=True)
            designated_date = cols[2].get_text(strip=True)
            
            date_match = re.search(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', title_text)
            current_date = f"{date_match.group(1)}-{date_match.group(2).zfill(2)}-{date_match.group(3).zfill(2)}" if date_match else designated_date

            for doc_code in last_info.keys():
                if doc_code.replace('-', '') in title_text.replace('-', ''):
                    current_info[doc_code] = current_date
                    if current_date > last_info[doc_code]:
                        print(f"  [!] 업데이트: {doc_code}")
                        updated_docs.append(f"▶ {doc_code} 개정\n- 제목: {title_text}\n- 날짜: {current_date}")
                    break

        page += 1
        time.sleep(1) # 차단 방지
        if page > 30: break

    except Exception as e:
        print(f"에러 발생: {e}")
        break

# 4. 결과 처리
if updated_docs:
    msg_text = "KOLAS 모니터링 결과:\n\n" + "\n\n".join(set(updated_docs))
    msg = MIMEText(msg_text)
    msg['Subject'] = "[KOLAS] 개정 문서 알림"
    msg['From'] = os.environ['GMAIL_USER']
    msg['To'] = os.environ['RECEIVER_EMAIL']

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(os.environ['GMAIL_USER'], os.environ['GMAIL_PW'])
        server.sendmail(msg['From'], msg['To'], msg.as_string())

    with open('last_data.txt', 'w', encoding='utf-8') as f:
        for code, date in sorted(current_info.items()):
            f.write(f"{code}|{date}\n")
    print("성공적으로 처리되었습니다.")
else:
    print("변동 사항이 없습니다.")
