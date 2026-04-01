import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
import os
import re
import time

# 1. 대상 문서 및 초기 데이터
TARGET_CODES = ["KOLAS-R-001", "KOLAS-R-002", "KOLAS-R-003", "KOLAS-R-004", "KOLAS-R-005", "KOLAS-R-006", "KOLAS-R-007", "KOLAS-SR-002", "KOLAS-G-001", "KOLAS-G-004", "KOLAS-G-005", "KOLAS-G-008", "KOLAS-G-011", "KOLAS-G-013"]

last_info = {}
if os.path.exists('last_data.txt'):
    with open('last_data.txt', 'r', encoding='utf-8') as f:
        for line in f:
            if '|' in line:
                code, date = line.strip().split('|')
                last_info[code.strip()] = date.strip()

LIST_URL = "https://www.knab.go.kr/inf/bbs/lawrecsroom/LawRecsRoomList.do"

# [수정] 엑셀/브라우저와 구분이 불가능한 정밀 헤더
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Origin': 'https://www.knab.go.kr',
    'Referer': 'https://www.knab.go.kr/inf/bbs/lawrecsroom/LawRecsRoom.do',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User': '?1'
}

updated_docs = []
current_info = last_info.copy()
session = requests.Session()

# 2. 분석 시작
for page in range(1, 6): # 일단 5페이지까지만 테스트
    print(f"▶ 페이지 {page} 분석 중...")
    
    # 엑셀 매크로의 데이터 구조
    payload = f"pageNo={page}&boardSn=&xlsDownloadYn=N&totalCount=&searchCat3=&searchStartDate=&searchEndDate=&searchType=A&searchKeyword="
    
    try:
        # data에 딕셔너리가 아닌 '문자열'을 직접 전달 (엑셀 방식)
        response = session.post(LIST_URL, headers=headers, data=payload, timeout=20)
        response.encoding = 'utf-8'
        
        # HTML 본문이 제대로 왔는지 검사
        if "board_list" not in response.text:
            print(f"   ⚠️ 데이터 수신 실패 (보안 차단 가능성)")
            # 디버깅을 위해 응답 내용 일부 출력 (선택 사항)
            # print(response.text[:200]) 
            break
            
        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.select('table.board_list tbody tr')
        
        if not rows or "등록된 게시물이 없습니다" in response.text:
            break

        print(f"   ✅ {len(rows)}개 항목 로드 완료")

        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 4: continue
            
            title = cols[3].get_text(" ", strip=True)
            designated_date = cols[2].get_text(strip=True)
            
            # 날짜 추출
            date_match = re.search(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', title)
            row_date = f"{date_match.group(1)}-{date_match.group(2).zfill(2)}-{date_match.group(3).zfill(2)}" if date_match else designated_date

            for code in TARGET_CODES:
                if code.replace('-', '') in title.replace('-', ''):
                    if row_date > last_info.get(code, "2000-01-01"):
                        print(f"   [!] 신규 업데이트: {code}")
                        updated_docs.append(f"• {code}\n  - 제목: {title}\n  - 날짜: {row_date}")
                        current_info[code] = row_date
                    break
        
        time.sleep(1)

    except Exception as e:
        print(f"   ❌ 오류 발생: {e}")
        break

# 3. 결과 발송 및 저장
if updated_docs:
    # (메일 발송 로직은 이전과 동일)
    msg = MIMEText("KOLAS 개정 알림:\n\n" + "\n\n".join(set(updated_docs)))
    msg['Subject'] = "[KOLAS] 관리문서 업데이트"
    msg['From'] = os.environ['GMAIL_USER']
    msg['To'] = os.environ['RECEIVER_EMAIL']
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(os.environ['GMAIL_USER'], os.environ['GMAIL_PW'])
        server.sendmail(msg['From'], msg['To'], msg.as_string())
    
    with open('last_data.txt', 'w', encoding='utf-8') as f:
        for code, date in sorted(current_info.items()):
            f.write(f"{code}|{date}\n")
    print("✅ 완료")
else:
    print("ℹ️ 변동 없음")
