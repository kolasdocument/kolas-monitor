import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
import os
import re
import time

# 1. 기준 데이터 설정
last_info = {}
if os.path.exists('last_data.txt'):
    with open('last_data.txt', 'r', encoding='utf-8') as f:
        for line in f:
            if '|' in line:
                code, date = line.strip().split('|')
                last_info[code.strip()] = date.strip()

LIST_URL = "https://www.knab.go.kr/inf/bbs/lawrecsroom/LawRecsRoomList.do"

# [핵심] 엑셀 매크로(MSXML2.XMLHTTP) 및 실제 브라우저와 구분이 안 가도록 헤더 강화
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Origin': 'https://www.knab.go.kr',
    'Referer': LIST_URL,
    'Connection': 'keep-alive'
}

updated_docs = []
current_info = last_info.copy()

# 2. 전수 조사 루프
page = 1
session = requests.Session() # 세션을 사용해 쿠키를 유지

while True:
    print(f"--- {page}페이지 분석 중 ---")
    
    # 엑셀 매크로에서 성공했던 파라미터 그대로 사용
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
        # 엑셀처럼 POST 요청
        response = session.post(LIST_URL, headers=headers, data=payload, timeout=20)
        
        # 만약 응답이 비어있다면 보안 차단 가능성 있음
        if not response.text.strip():
            print(f"{page}페이지 응답이 비어있습니다. 보안 차단이 의심됩니다.")
            break
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 테이블 행 찾기 (KOLAS 게시판 구조)
        rows = soup.select('table.board_list tbody tr')

        # 게시물이 없거나 '등록된 게시물이 없습니다' 문구가 보이면 종료
        if not rows or "등록된 게시물이 없습니다" in soup.text:
            print(f"총 {page-1}페이지까지 전수 조사를 완료했습니다.")
            break

        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 4: continue
            
            # 제목 텍스트 (엑셀의 tdList(3))
            title_text = cols[3].get_text(" ", strip=True)
            
            # 지정일 (엑셀의 tdList(2))
            designated_date_raw = cols[2].get_text(strip=True)
            
            # 날짜 추출 (제목에서 우선 추출, 없으면 지정일 사용)
            date_match = re.search(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', title_text)
            
            if date_match:
                year, month, day = date_match.groups()
                current_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            elif re.match(r'\d{4}-\d{2}-\d{2}', designated_date_raw):
                current_date = designated_date_raw
            else:
                continue
                
            # 문서번호 확인 (KOLAS-R-001 등)
            for doc_code in last_info.keys():
                # 엑셀 방식처럼 유연한 비교 (하이픈 무시)
                if doc_code.replace('-', '') in title_text.replace('-', ''):
                    current_info[doc_code] = current_date
                    
                    # 기준 날짜보다 최신이면 알림
                    if current_date > last_info[doc_code]:
                        print(f"  [!] {doc_code} 업데이트 확인: {current_date}")
                        updated_docs.append(f"▶ {doc_code} 개정\n- 제목: {title_text}\n- 기존: {last_info[doc_code]}\n- 현재: {current_date}")
                    break

        page += 1
        time.sleep(1) # 서버 과부하 방지 및 차단 회피를 위한 휴식
        if page > 40: break

    except Exception as e:
        print(f"에러: {e}")
        break

# 3. 메일 발송 및 데이터 갱신
if updated_docs:
    # 중복 제거 및 리스트 생성
    unique_updates = list(set(updated_docs))
    message_body = "KOLAS 최신 개정 현황:\n\n" + "\n\n".join(unique_updates)
    
    msg = MIMEText(message_body)
    msg['Subject'] = f"[KOLAS] {len(unique_updates)}건의 관리문서 개정 발견"
    msg['From'] = os.environ['GMAIL_USER']
    msg['To'] = os.environ['RECEIVER_EMAIL']

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(os.environ['GMAIL_USER'], os.environ['GMAIL_PW'])
        server.sendmail(msg['From'], msg['To'], msg.as_string())

    with open('last_data.txt', 'w', encoding='utf-8') as f:
        for code, date in sorted(current_info.items()):
            f.write(f"{code}|{date}\n")
    print("메일 발송 및 데이터 저장 성공!")
else:
    print("모든 페이지 검사 결과 최신 상태입니다.")
