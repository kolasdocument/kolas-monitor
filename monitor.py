import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
import os
import re

# 1. KOLAS 법령/공고/지침 게시판 주소
url = "https://www.knab.go.kr/inf/bbs/lawrecsroom/LawRecsRoomList.do"
headers = {'User-Agent': 'Mozilla/5.0'}

# 2. 기준 데이터(last_data.txt) 불러오기
last_info = {}
if os.path.exists('last_data.txt'):
    with open('last_data.txt', 'r', encoding='utf-8') as f:
        for line in f:
            if '|' in line:
                code, date = line.strip().split('|')
                last_info[code] = date

# 3. 웹사이트 접속 및 데이터 추출
response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.text, 'html.parser')
rows = soup.select('table.board_list tbody tr')

current_info = {}
updated_docs = []

for row in rows:
    cols = row.find_all('td')
    if len(cols) < 4: continue
    
    doc_code = cols[1].text.strip() # 관리문서코드 (예: KOLAS-G-001)
    title = cols[3].text.strip()    # 제목 (예: <최신본>... (2024.1.2.))
    
    # 정규표현식으로 제목 맨 뒤의 날짜 (YYYY.MM.DD.) 추출
    date_match = re.search(r'\((\d{4}\.\d{1,2}\.\d{1,2})\.\)$', title)
    
    if date_match:
        # 추출한 날짜를 비교하기 쉽게 2024-01-02 형태로 변환
        raw_date = date_match.group(1)
        current_date = "-".join([d.zfill(2) for d in raw_date.split('.')])
        
        # 우리가 추적하는 14개 문서 리스트에 있는 경우에만 처리
        if doc_code in last_info:
            current_info[doc_code] = current_date
            
            # 기준 데이터의 날짜보다 최신인지 비교
            if current_date > last_info[doc_code]:
                updated_docs.append(f"▶ {doc_code} 문서가 개정되었습니다!\n   - 이전 날짜: {last_info[doc_code]}\n   - 최신 날짜: {current_date}")

# 4. 변경사항이 있을 때만 메일 발송
if updated_docs:
    message_body = "KOLAS 관리문서 실시간 모니터링 알림입니다.\n\n" + "\n\n".join(updated_docs)
    msg = MIMEText(message_body)
    msg['Subject'] = "[알림] KOLAS 관리문서 최신 개정 발견"
    msg['From'] = os.environ['GMAIL_USER']
    msg['To'] = os.environ['RECEIVER_EMAIL']

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(os.environ['GMAIL_USER'], os.environ['GMAIL_PW'])
        server.sendmail(msg['From'], msg['To'], msg.as_string())

    # 5. 다음 비교를 위해 last_data.txt를 최신 날짜로 업데이트
    # (이미 확인한 업데이트는 다시 알리지 않도록 저장)
    # 기존 데이터 중 바뀌지 않은 것도 포함해서 전체 다시 쓰기
    full_save_data = last_info.copy()
    full_save_data.update(current_info)
    
    with open('last_data.txt', 'w', encoding='utf-8') as f:
        for code, date in sorted(full_save_data.items()):
            f.write(f"{code}|{date}\n")
            
    print("업데이트 발견! 메일을 발송하고 데이터를 갱신했습니다.")
else:
    print("변동 사항이 없습니다.")
