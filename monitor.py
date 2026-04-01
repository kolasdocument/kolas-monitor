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

# 2. 접속 설정 (엑셀 매크로와 동일한 주소 및 방식)
LIST_URL = "https://www.knab.go.kr/inf/bbs/lawrecsroom/LawRecsRoomList.do"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Referer': LIST_URL
}

updated_docs = []
current_info = last_info.copy()

# 3. 전수 조사 시작 (엑셀의 totalPages 로직 반영)
page = 1
while True:
    print(f"--- {page}페이지 분석 중 ---")
    
    # [핵심 수정] 엑셀 매크로에서 사용한 변수명(pageNo, searchType 등)으로 전면 교체
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
        response = requests.post(LIST_URL, headers=headers, data=payload)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 게시물 테이블 행 추출
        rows = soup.select('table.board_list tbody tr')

        # 게시물이 없거나 "등록된 게시물이 없습니다" 문구가 보이면 종료
        if not rows or "등록된 게시물이 없습니다" in soup.text:
            print(f"총 {page-1}페이지까지 탐색을 완료했습니다.")
            break

        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 4: continue
            
            # 제목 텍스트 (엑셀의 tdList(3) 부분)
            title_text = cols[3].get_text(" ", strip=True)
            
            # [날짜 추출] 엑셀의 ExtractLastDateFromTitle 로직 (YYYY.MM.DD. 패턴)
            date_match = re.search(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', title_text)
            
            if date_match:
                year, month, day = date_match.groups()
                current_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                
                # [문서번호 대조] 엑셀의 ExtractDocCodeFromTitle 로직 (KOLAS-R-001 등)
                for doc_code in last_info.keys():
                    # 특수기호 제거 후 유연하게 비교
                    clean_doc = doc_code.replace('-', '')
                    clean_title = title_text.replace('-', '').replace('_', '')
                    
                    if clean_doc in clean_title:
                        current_info[doc_code] = current_date
                        
                        # 내 기록보다 최신 날짜라면 업데이트 목록에 추가
                        if current_date > last_info[doc_code]:
                            print(f"[업데이트 발견!] {doc_code}: {current_date}")
                            updated_docs.append(f"▶ {doc_code} 개정 발견\n- 제목: {title_text}\n- 기존: {last_info[doc_code]}\n- 현재: {current_date}")
                        break

        page += 1
        if page > 50: break # 안전 장치

    except Exception as e:
        print(f"에러 발생: {e}")
        break

# 4. 결과 발송 및 저장
if updated_docs:
    message_body = "KOLAS 전수조사 업데이트 리포트:\n\n" + "\n\n".join(set(updated_docs))
    msg = MIMEText(message_body)
    msg['Subject'] = "[KOLAS] 관리문서 개정 알림"
    msg['From'] = os.environ['GMAIL_USER']
    msg['To'] = os.environ['RECEIVER_EMAIL']

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(os.environ['GMAIL_USER'], os.environ['GMAIL_PW'])
        server.sendmail(msg['From'], msg['To'], msg.as_string())

    with open('last_data.txt', 'w', encoding='utf-8') as f:
        for code, date in sorted(current_info.items()):
            f.write(f"{code}|{date}\n")
    print("성공적으로 메일을 발송하고 데이터를 갱신했습니다.")
else:
    print("전체 페이지 검사 결과, 변동 사항이 없습니다.")
