import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import os
import smtplib
from email.mime.text import MIMEText
import traceback
import time

# =========================
# 설정
# =========================
LIST_URL = "https://www.knab.go.kr/inf/bbs/lawrecsroom/LawRecsRoomList.do"
LAST_DATA_FILE = "last_data.txt"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

# =========================
# 유틸 함수
# =========================
def normalize(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", s.upper())

def to_date(date_str: str) -> datetime:
    return datetime.strptime(date_str, "%Y-%m-%d")

def parse_title(title_text: str):
    """
    제목에서 문서코드, 문서제목, 개정일 추출
    """
    # 문서 코드 (KOLAS-R-001 / G / SR)
    code_match = re.search(r"KOLAS[-\s]?(?:SR|R|G)[-\s]?\d{3}", title_text, re.IGNORECASE)
    doc_code = code_match.group(0).replace(" ", "").upper() if code_match else None

    # 개정일 (YYYY.MM.DD 또는 YYYY.M.D)
    date_match = re.search(r"\((20\d{2})\.(\d{1,2})\.(\d{1,2})\)", title_text)
    revised_date = None
    if date_match:
        revised_date = (
            f"{date_match.group(1)}-"
            f"{date_match.group(2).zfill(2)}-"
            f"{date_match.group(3).zfill(2)}"
        )

    # 문서 제목 정리
    doc_title = title_text
    if doc_code:
        doc_title = re.sub(doc_code, "", doc_title, flags=re.IGNORECASE)
    doc_title = re.sub(r"\(20\d{2}\.\d{1,2}\.\d{1,2}\)", "", doc_title)
    doc_title = re.sub(r"^\(최신\)", "", doc_title)
    doc_title = doc_title.strip(" -()")

    return doc_code, doc_title.strip(), revised_date

# =========================
# 기준 데이터 로드
# =========================
last_info = {}
if os.path.exists(LAST_DATA_FILE):
    with open(LAST_DATA_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if "|" in line:
                code, date = line.strip().split("|")
                last_info[code.strip()] = date.strip()

current_info = last_info.copy()
updated_docs = []

# =========================
# 메인 로직
# =========================
try:
    session = requests.Session()

    page = 1
    while page <= 30:
        print(f"▶ 페이지 {page} 처리 중")

        payload = {
            "pageNo": str(page),
            "xlsDownloadYn": "N"
        }

        resp = session.post(LIST_URL, headers=headers, data=payload, timeout=20)
        soup = BeautifulSoup(resp.text, "html.parser")

        rows = soup.select("table.board_list tbody tr")
        if not rows:
            print("⚠️ 게시글 없음 또는 접근 차단")
            break

        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 5:
                continue

            posted_date = cols[3].get_text(strip=True).replace(".", "-")
            title_text = cols[4].get_text(" ", strip=True)

            doc_code, doc_title, revised_date = parse_title(title_text)

            if not doc_code:
                continue

            if revised_date is None:
                revised_date = posted_date

            if doc_code in last_info:
                if to_date(revised_date) > to_date(last_info[doc_code]):
                    updated_docs.append(
                        f"▶ {doc_code}\n"
                        f"- 제목: {doc_title}\n"
                        f"- 개정일: {revised_date}"
                    )
                    current_info[doc_code] = revised_date
            else:
                # 신규 문서
                updated_docs.append(
                    f"▶ {doc_code} (신규)\n"
                    f"- 제목: {doc_title}\n"
                    f"- 게시일: {revised_date}"
                )
                current_info[doc_code] = revised_date

        page += 1
        time.sleep(1)

except Exception:
    print("❌ 실행 중 오류 발생")
    traceback.print_exc()
    raise

# =========================
# 결과 처리 (메일 + 파일 저장)
# =========================
if updated_docs:
    msg_text = "KOLAS 문서 변경 알림\n\n" + "\n\n".join(updated_docs)
    msg = MIMEText(msg_text, _charset="utf-8")
    msg["Subject"] = "[KOLAS] 문서 개정 알림"
    msg["From"] = os.environ["GMAIL_USER"]
    msg["To"] = os.environ["RECEIVER_EMAIL"]

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(os.environ["GMAIL_USER"], os.environ["GMAIL_PW"])
        server.sendmail(msg["From"], msg["To"], msg.as_string())

    with open(LAST_DATA_FILE, "w", encoding="utf-8") as f:
        for code, date in sorted(current_info.items()):
            f.write(f"{code}|{date}\n")

    print("✅ 업데이트 알림 발송 및 기준 데이터 갱신 완료")

else:
    print("ℹ️ 변경 사항 없음")
