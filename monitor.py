import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
import os
import re

# 1. 기준 데이터 불러오기
last_info = {}
if os.path.exists('last_data.txt'):
    with open('last_data.txt', 'r', encoding='utf-8') as f:
        for line in f:
            if '|' in line:
                code, date = line.strip().split('|')
                last_info[code] = date

headers = {'User-Agent': 'Mozilla/5.0'}
updated_docs = []
current_info = last_info.copy()

# 2. 확실하게 1페이지부터 5페이지까지 반복
for page in range(1, 6):
    print(f"{page}페이지 분석 시작...")
    url = f"https://www.knab.go.kr/inf/bbs/lawrecsroom/LawRecsRoomList.do?pageIndex={page}"
    
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 테이블 안의 모든 줄(tr) 가져오기
        rows = soup.select('table.board_list tbody tr')

        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 4: continue
            
            # 관리문서코드 (예: KOLAS-R-001)
            doc_code = cols[1].text.strip()
            # 제목 (예: ... (2025.01.08.))
            title = cols[3].text.strip()
            
            # 제목에서 날짜 추출 (괄호 안의 숫자.숫자.숫자 형태)
            date_match = re.search(r'\((\d{4})\.(\d{1,2})\.(\d{1,2})\.\)', title)
            
            if date_match:
                # 2025.1.8 -> 2025-01-08 형태로 표준화
                year, month, day = date_match.groups()
                current_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                
                # 내가 감시하는 리스트에 있는지 확인
                if doc_code in last_info:
                    current_info[doc_code] = current_date
                    # 비교: 사이트 날짜가 기록된 날짜보다 '문자열상' 더 크면(최신이면)
                    if current_date > last_info[doc_code]:
                        updated_docs.append(f"▶ {doc_code} 개정 발견!\n   - 이전: {last_info[doc_code]}\n   - 현재: {current_date}")
                        print(f"[발견] {doc_code}: {last_info[doc_code]} -> {current_date}")

    except Exception as e:
        print(f"{page}페이지 처리 중 에러: {e}")

# 3. 결과 알림 및 저장
if updated_docs:
    # 중복 제거 및 메일 본문 작성
    message_body = "KOLAS 관리문서 업데이트 알림입니다.\n\n" + "\n\n".join(set(updated_docs))
    msg = MIMEText(message_body)
    msg['Subject'] = "[KOLAS 알림] 관리문서 개정 업데이트"
    msg['From'] = os.environ['GMAIL_USER']
    msg['To'] = os.environ['RECEIVER_EMAIL']

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(os.environ['GMAIL_USER'], os.environ['GMAIL_PW'])
        server.sendmail(msg['From'], msg['To'], msg.as_string())

    # last_data.txt 갱신
    with open('last_data.txt', 'w', encoding='utf-8') as f:
        for code, date in sorted(current_info.items()):
            f.write(f"{code}|{date}\n")
    print("메일 발송 완료 및 기준 데이터 갱신 성공!")
else:
    print("모든 페이지 검사 결과, 변동 사항이 없습니다.")
