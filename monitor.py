import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
import os
import re

# 1. 설정 및 기준 데이터 불러오기
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

# 2. 1페이지부터 끝까지 무한 반복 (게시물이 없을 때까지)
page = 1
while True:
    print(f"{page}페이지 분석 중...")
    url = f"https://www.knab.go.kr/inf/bbs/lawrecsroom/LawRecsRoomList.do?pageIndex={page}"
    
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.select('table.board_list tbody tr')

        # 더 이상 게시물이 없으면(빈 페이지면) 반복 중단
        if not rows or "등록된 게시물이 없습니다" in soup.text:
            print("모든 페이지 탐색 완료.")
            break

        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 4: continue
            
            doc_code = cols[1].text.strip() # 관리문서코드 (예: KOLAS-R-001)
            title = cols[3].text.strip()    # 제목
            
            # 제목 맨 뒤의 (YYYY.MM.DD.) 추출
            date_match = re.search(r'\((\d{4}\.\d{1,2}\.\d{1,2})\.\)$', title)
            
            if date_match:
                raw_date = date_match.group(1)
                # 2025.01.08 -> 2025-01-08 형태로 변환
                current_date = "-".join([d.zfill(2) for d in raw_date.split('.')])
                
                # 내가 관리하는 14개 문서 리스트에 포함된 경우만 체크
                if doc_code in last_info:
                    current_info[doc_code] = current_date
                    # 비교: 사이트 날짜가 기록된 날짜보다 최신이면 알림 리스트에 추가
                    if current_date > last_info[doc_code]:
                        updated_docs.append(f"▶ {doc_code} 개정 발견!\n   - 기존: {last_info[doc_code]}\n   - 최신: {current_date}")

        page += 1 # 다음 페이지로 이동
        if page > 20: # 혹시 모를 무한 루프 방지 (최대 20페이지까지만)
            break
            
    except Exception as e:
        print(f"에러 발생: {e}")
        break

# 3. 메일 발송 및 데이터 저장
if updated_docs:
    # 중복 알림 방지를 위해 업데이트된 내용만 정리
    message_body = "KOLAS 관리문서 실시간 업데이트 알림:\n\n" + "\n\n".join(set(updated_docs))
    msg = MIMEText(message_body)
    msg['Subject'] = "[KOLAS] 관리문서 개정 알림 (전체 페이지 탐색)"
    msg['From'] = os.environ['GMAIL_USER']
    msg['To'] = os.environ['RECEIVER_EMAIL']

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(os.environ['GMAIL_USER'], os.environ['GMAIL_PW'])
        server.sendmail(msg['From'], msg['To'], msg.as_string())

    # 최신 날짜로 파일 갱신
    with open('last_data.txt', 'w', encoding='utf-8') as f:
        for code, date in sorted(current_info.items()):
            f.write(f"{code}|{date}\n")
    print("메일 발송 및 데이터 갱신 완료!")
else:
    print("변동 사항이 없습니다.")
