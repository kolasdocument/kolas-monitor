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

# 2. 1페이지부터 5페이지까지 탐색
for page in range(1, 6):
    print(f"--- {page}페이지 분석 중 ---")
    url = f"https://www.knab.go.kr/inf/bbs/lawrecsroom/LawRecsRoomList.do?pageIndex={page}"
    
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.select('table.board_list tbody tr')

        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 4: continue
            
            title_text = cols[3].get_text(strip=True)
            
            # [날짜 추출] 제목의 마지막 괄호 안 날짜 (예: 2025.01.08)
            date_match = re.search(r'\((\d{4})\.(\d{1,2})\.(\d{1,2})\.\)$', title_text)
            if not date_match: # 형식 다를 경우 대비해 한 번 더 시도
                date_match = re.search(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', title_text)
            
            if date_match:
                year, month, day = date_match.groups()
                current_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                
                # [문서번호 대조] 엑셀의 번호가 제목에 포함되어 있는지 확인
                for doc_code in last_info.keys():
                    # 특수기호(언더바/하이픈) 차이를 무시하기 위해 하이픈을 제거하고 비교하거나 
                    # 포함 여부를 아주 유연하게 확인합니다.
                    clean_code = doc_code.replace('-', '')
                    clean_title = title_text.replace('-', '').replace('_', '')
                    
                    if clean_code in clean_title:
                        current_info[doc_code] = current_date
                        
                        # 비교: 사이트 날짜가 기록된 날짜보다 최신이면 알림
                        if current_date > last_info[doc_code]:
                            print(f"[발견!] {doc_code}: {last_info[doc_code]} -> {current_date}")
                            updated_docs.append(f"▶ {doc_code} 개정 발견!\n   - 제목: {title_text}\n   - 기존: {last_info[doc_code]}\n   - 현재: {current_date}")
                        break 

    except Exception as e:
        print(f"에러 발생: {e}")

# 3. 메일 발송 및 데이터 저장
if updated_docs:
    message_body = "KOLAS 관리문서 업데이트 알림입니다.\n\n" + "\n\n".join(set(updated_docs))
    msg = MIMEText(message_body)
    msg['Subject'] = "[KOLAS 알림] 관리문서 개정 업데이트"
    msg['From'] = os.environ['GMAIL_USER']
    msg['To'] = os.environ['RECEIVER_EMAIL']

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(os.environ['GMAIL_USER'], os.environ['GMAIL_PW'])
        server.sendmail(msg['From'], msg['To'], msg.as_string())

    with open('last_data.txt', 'w', encoding='utf-8') as f:
        for code, date in sorted(current_info.items()):
            f.write(f"{code}|{date}\n")
    print("메일 발송 및 갱신 성공!")
else:
    print("변동 사항이 없습니다.")
