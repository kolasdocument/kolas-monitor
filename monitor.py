import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

LIST_URL = "https://www.knab.go.kr/inf/bbs/lawrecsroom/LawRecsRoomList.do"

headers = {
    "User-Agent": "Mozilla/5.0"
}

def normalize(s: str) -> str:
    """문서 코드 비교용 문자열 정규화"""
    return re.sub(r"[^A-Z0-9]", "", s.upper())

def parse_title(title_text: str):
    """
    제목에서 문서코드, 문서제목, 개정일 추출
    반환: (doc_code, doc_title, revised_date)
    """

    # 1️⃣ 문서 코드 추출 (KOLAS-R-001 등)
    code_match = re.search(r"KOLAS[-\s]?(?:SR|R|G)[-\s]?\d{3}", title_text, re.IGNORECASE)
    doc_code = code_match.group(0).replace(" ", "").upper() if code_match else None

    # 2️⃣ 개정일 추출 (YYYY.MM.DD)
    date_match = re.search(r"\((20\d{2})\.(\d{2})\.(\d{2})\)", title_text)
    revised_date = None
    if date_match:
        revised_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"

    # 3️⃣ 문서 제목 정리 (코드, 날짜 제거)
    doc_title = title_text
    if doc_code:
        doc_title = re.sub(doc_code, "", doc_title, flags=re.IGNORECASE)
    doc_title = re.sub(r"\(20\d{2}\.\d{2}\.\d{2}\)", "", doc_title)
    doc_title = doc_title.strip(" -()")

    return doc_code, doc_title.strip(), revised_date


def to_date(date_str: str):
    return datetime.strptime(date_str, "%Y-%m-%d")


# -------------------------
# 실제 페이지 요청
# -------------------------
session = requests.Session()
payload = {
    "pageNo": "1",
    "xlsDownloadYn": "N"
}

resp = session.post(LIST_URL, headers=headers, data=payload, timeout=20)
soup = BeautifulSoup(resp.text, "html.parser")

rows = soup.select("table.board_list tbody tr")

print("✅ 파싱 결과:")
print("-" * 60)

for row in rows:
    cols = row.find_all("td")
    if len(cols) < 5:
        continue

    # 게시일 (fallback 용)
    posted_date = cols[3].get_text(strip=True).replace(".", "-")

    # 제목
    title_text = cols[4].get_text(" ", strip=True)

    doc_code, doc_title, revised_date = parse_title(title_text)

    if revised_date is None:
        revised_date = posted_date  # fallback

    print(f"문서코드 : {doc_code}")
    print(f"문서제목 : {doc_title}")
    print(f"개정일   : {revised_date}")
    print("-" * 60)
``
