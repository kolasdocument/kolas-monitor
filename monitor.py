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

# 2. 세션 및 접속 설정
session = requests.Session()
main_url = "https://www.knab.go.kr/inf/bbs/lawrecsroom/LawRecsRoomList.do"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Origin': 'https://www.knab.go.kr',
    'Referer': main_url,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
}

updated_docs = []
current_info = last_info.copy()

# 3. 전수 조사 시작
page = 1
while True:
    print(f"--- {page}페이지 정밀 분석 중 ---")
    
    # 서버가 응답을 주기 위해 필요한 '필수 파라미터' 전체 세트
    payload = {
        'pageIndex': str(page),
        'searchCondition': 'all',
        'searchKeyword': '',
        'searchSDate': '',
        'searchEDate': '',
        'searchDocType': ''
    }
    
    try:
        # POST 요청으로 데이터 가져오기
        response = session.post(main_url, headers=headers, data=payload)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 실제 게시물이 들어있는 행(tr) 추출
        rows = soup.select('table.board_list tbody tr')

        # 게시물이 없거나 '등록된 게시물이 없습니다' 문구가 뜨면 종료
        if not rows or "등록된 게시물이 없습니다" in soup.text:
            print(f"총 {page-1}페이지까지 탐색 완료.")
            break

        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 4: continue
            
            title_text = cols[3].get_text(" ", strip=True)
            
            # 날짜 추출 (YYYY.MM.DD)
            date_match = re.search(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', title_text)
            
            if date_match:
                year, month, day = date_match.groups()
                current_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                
                for doc_code in last_info.keys():
                    clean_doc = doc_code.replace('-', '')
                    clean_title = title_text.replace('-', '').replace('_', '')
                    
                    if clean_doc in clean_title:
                        current_info[doc_code] = current_date
                        if current_date > last_info[doc_code]:
                            print(f"[업데이트!] {doc_code}: {current_date}")
                            updated_docs.append(f"▶ {doc_code} 개정 발견\n- 제목: {title_text}\n- 기존: {last_info[doc_code]}\n- 현재: {current_date}")
                        break

        page += 1
        if page > 30: break # 무한루프 방지

    except Exception as e:
        print(f"에러 발생: {e}")
        break

# 4. 결과 발송 및 저장
if updated_docs:
    message_body = "KOLAS 전체 페이지 업데이트 결과:\n\n" + "\n\n".join(set(updated_docs))
    msg = MIMEText(message_body)
    msg['Subject'] = "[KOLAS] 전수조사 개정 알림"
    msg['From'] = os.environ['GMAIL_USER']
    msg['To'] = os.environ['RECEIVER_EMAIL']

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(os.environ['GMAIL_USER'], os.environ['GMAIL_PW'])
        server.sendmail(msg['From'], msg['To'], msg.as_string())

    with open('last_data.txt', 'w', encoding='utf-8') as f:
        for code, date in sorted(current_info.items()):
            f.write(f"{code}|{date}\n")
    print("메일 발송 성공!")
else:
    print("검사 완료. 현재 최신 상태입니다.")
