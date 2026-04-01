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

url = "https://www.knab.go.kr/inf/bbs/lawrecsroom/LawRecsRoomList.do"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Content-Type': 'application/x-www-form-urlencoded'
}

updated_docs = []
current_info = last_info.copy()

# 2. 전수 조사 시작 (최대 20페이지까지 탐색 설정)
for page in range(1, 21):
    print(f"--- {page}페이지 정밀 탐색 중 ---")
    
    # 서버에 보낼 데이터 주머니 (POST 방식 전용)
    payload = {
        'pageIndex': str(page),
        'searchCondition': 'all',
        'searchKeyword': ''
    }
    
    try:
        response = requests.post(url, headers=headers, data=payload)
        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.select('table.board_list tbody tr')

        # 더 이상 게시물이 없거나 "등록된 게시물이 없습니다" 문구가 보이면 중단
        if not rows or "등록된 게시물이 없습니다" in soup.text:
            print(f"{page-1}페이지에서 탐색을 완료했습니다.")
            break

        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 4: continue
            
            # 제목 텍스트 추출
            title_area = cols[3].get_text(" ", strip=True)
            
            # 제목에서 날짜 추출 (숫자.숫자.숫자 형태)
            date_match = re.search(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', title_area)
            
            if date_match:
                year, month, day = date_match.groups()
                # 2025-01-08 형태로 표준화
                current_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                
                # 내 리스트에 있는 문서인지 확인
                for doc_code in last_info.keys():
                    if doc_code in title_area:
                        current_info[doc_code] = current_date
                        
                        # [핵심] 기록된 날짜보다 웹사이트 날짜가 더 크면(최신이면)
                        if current_date > last_info[doc_code]:
                            print(f"[업데이트 발견] {doc_code}: {last_info[doc_code]} -> {current_date}")
                            updated_docs.append(f"▶ {doc_code} 개정 발견\n- 제목: {title_area}\n- 기존: {last_info[doc_code]}\n- 최신: {current_date}")
                        break

    except Exception as e:
        print(f"{page}페이지 분석 중 오류 발생: {e}")
        break

# 3. 알림 발송 및 데이터 저장
if updated_docs:
    message_body = "KOLAS 관리문서 전수조사 업데이트 리포트:\n\n" + "\n\n".join(set(updated_docs))
    msg = MIMEText(message_body)
    msg['Subject'] = "[KOLAS] 전수조사 결과 개정 문서 발견"
    msg['From'] = os.environ['GMAIL_USER']
    msg['To'] = os.environ['RECEIVER_EMAIL']

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(os.environ['GMAIL_USER'], os.environ['GMAIL_PW'])
        server.sendmail(msg['From'], msg['To'], msg.as_string())

    # 파일 갱신 (내림차순 정렬 저장)
    with open('last_data.txt', 'w', encoding='utf-8') as f:
        for code, date in sorted(current_info.items()):
            f.write(f"{code}|{date}\n")
    print("메일 발송 및 데이터 갱신 완료!")
else:
    print("전체 페이지를 확인했으나 변동 사항이 없습니다.")
