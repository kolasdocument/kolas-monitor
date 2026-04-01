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

# 2. 세션 및 접속 설정 (보안 우회)
session = requests.Session()
main_url = "https://www.knab.go.kr/inf/bbs/lawrecsroom/LawRecsRoomList.do"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': main_url
}

# 쿠키 생성을 위한 초기 접속
session.get(main_url, headers=headers)

updated_docs = []
current_info = last_info.copy()

# 3. 전수 조사 시작 (1페이지부터 끝까지)
page = 1
while True:
    print(f"--- {page}페이지 분석 중 ---")
    
    payload = {
        'pageIndex': str(page),
        'searchCondition': 'all',
        'searchKeyword': ''
    }
    
    try:
        # POST 방식으로 해당 페이지 데이터 요청
        response = session.post(main_url, headers=headers, data=payload)
        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.select('table.board_list tbody tr')

        # 게시물이 없거나 "등록된 게시물이 없습니다"가 나오면 루프 종료
        if not rows or "등록된 게시물이 없습니다" in soup.text:
            print(f"총 {page-1}페이지까지 모든 탐색을 완료했습니다.")
            break

        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 4: continue
            
            title_text = cols[3].get_text(" ", strip=True)
            
            # [날짜 추출] YYYY.MM.DD 형식 찾기
            date_match = re.search(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', title_text)
            
            if date_match:
                year, month, day = date_match.groups()
                current_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                
                # [문서번호 대조] 내 리스트의 번호가 제목에 포함되어 있는지 확인
                for doc_code in last_info.keys():
                    # 특수기호 차이 무시를 위해 제거 후 비교
                    clean_doc = doc_code.replace('-', '')
                    clean_title = title_text.replace('-', '').replace('_', '')
                    
                    if clean_doc in clean_title:
                        current_info[doc_code] = current_date
                        
                        # 비교: 사이트 날짜가 내 기록보다 최신이면 알림 추가
                        if current_date > last_info[doc_code]:
                            print(f"[발견!] {doc_code}: {last_info[doc_code]} -> {current_date}")
                            updated_docs.append(f"▶ {doc_code} 개정 발견\n- 제목: {title_text}\n- 기존: {last_info[doc_code]}\n- 현재: {current_date}")
                        break # 한 줄에서 하나 찾았으면 다음 줄로

        page += 1 # 다음 페이지로 이동
        if page > 30: # 무한 루프 방지용 안전 장치
            break

    except Exception as e:
        print(f"에러 발생: {e}")
        break

# 4. 결과 알림 및 파일 저장
if updated_docs:
    message_body = "KOLAS 전수조사 업데이트 리포트:\n\n" + "\n\n".join(set(updated_docs))
    msg = MIMEText(message_body)
    msg['Subject'] = "[KOLAS] 전수조사 결과 개정 문서 발견"
    msg['From'] = os.environ['GMAIL_USER']
    msg['To'] = os.environ['RECEIVER_EMAIL']

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(os.environ['GMAIL_USER'], os.environ['GMAIL_PW'])
        server.sendmail(msg['From'], msg['To'], msg.as_string())

    # 최신 날짜로 기준 데이터 갱신
    with open('last_data.txt', 'w', encoding='utf-8') as f:
        for code, date in sorted(current_info.items()):
            f.write(f"{code}|{date}\n")
    print("메일 발송 완료!")
else:
    print("모든 페이지 검사 결과, 변동 사항이 없습니다.")
