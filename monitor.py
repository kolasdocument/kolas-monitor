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
                last_info[code.strip()] = date.strip()

headers = {'User-Agent': 'Mozilla/5.0'}
updated_docs = []
current_info = last_info.copy()

# 2. 1~5페이지 탐색
for page in range(1, 6):
    print(f"--- {page}페이지 정밀 분석 중 ---")
    url = f"https://www.knab.go.kr/inf/bbs/lawrecsroom/LawRecsRoomList.do?pageIndex={page}"
    
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.select('table.board_list tbody tr')

        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 4: continue
            
            # 제목 셀 안의 모든 텍스트를 공백 제거하고 합치기
            title_area = cols[3].get_text(" ", strip=True) 
            
            # [날짜 추출 핵심] 숫자.숫자.숫자 형태라면 무엇이든 추출 (괄호 유무 상관없음)
            date_match = re.search(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', title_area)
            
            if date_match:
                year, month, day = date_match.groups()
                # 2025-01-08 형태로 표준화
                current_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                
                # [문서번호 매칭]
                for doc_code in last_info.keys():
                    # 문서번호(예: R-001)가 제목 텍스트에 포함되어 있는지 확인
                    if doc_code in title_area:
                        current_info[doc_code] = current_date
                        
                        # 날짜 비교: 웹사이트 날짜(current)가 기존(last)보다 크면 발견!
                        if current_date > last_info[doc_code]:
                            print(f"[성공!] {doc_code} 발견: {last_info[doc_code]} -> {current_date}")
                            updated_docs.append(f"▶ {doc_code} 개정 알림\n- 제목: {title_area}\n- 기존: {last_info[doc_code]}\n- 현재: {current_date}")
                        break

    except Exception as e:
        print(f"에러: {e}")

# 3. 발송 및 저장
if updated_docs:
    message_body = "KOLAS 업데이트 리포트:\n\n" + "\n\n".join(set(updated_docs))
    msg = MIMEText(message_body)
    msg['Subject'] = "[KOLAS 알림] 개정 문서 발견"
    msg['From'] = os.environ['GMAIL_USER']
    msg['To'] = os.environ['RECEIVER_EMAIL']

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(os.environ['GMAIL_USER'], os.environ['GMAIL_PW'])
        server.sendmail(msg['From'], msg['To'], msg.as_string())

    with open('last_data.txt', 'w', encoding='utf-8') as f:
        for code, date in sorted(current_info.items()):
            f.write(f"{code}|{date}\n")
    print("메일 발송 완료!")
else:
    print("모든 페이지를 뒤졌으나 변동 사항이 없습니다.")
