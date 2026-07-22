"""
저장된 refresh_token으로 access_token을 갱신한 뒤,
'나에게 보내기'로 뉴스 메시지를 발송한다.
소스가 많아 메시지가 카카오 텍스트 템플릿 길이 제한(1000자)을 넘기는 날에는
여러 통으로 나눠 보낸다.

필요한 환경변수 (GitHub Secrets):
- KAKAO_REST_API_KEY
- KAKAO_CLIENT_SECRET
- KAKAO_REFRESH_TOKEN
"""

import datetime
import json
import os
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from crawl_news import load_seen, save_seen  # noqa: E402

REST_API_KEY = os.environ["KAKAO_REST_API_KEY"]
CLIENT_SECRET = os.environ["KAKAO_CLIENT_SECRET"]
REFRESH_TOKEN = os.environ["KAKAO_REFRESH_TOKEN"]

SECTIONS_FILE = "news_sections.json"
KST = datetime.timezone(datetime.timedelta(hours=9))
MAX_CHUNK_LEN = 850  # 카카오 텍스트 템플릿 길이 제한(1000자)에 여유를 둔 청크 크기
MAX_MESSAGES_PER_RUN = 5  # 하루치가 너무 밀려도 카톡이 도배되지 않도록 상한선


def refresh_access_token():
    url = "https://kauth.kakao.com/oauth/token"
    data = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "client_id": REST_API_KEY,
            "client_secret": CLIENT_SECRET,
            "refresh_token": REFRESH_TOKEN,
        }
    ).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=15) as res:
        result = json.loads(res.read().decode())
    return result["access_token"]


def send_to_me(access_token, text):
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    template_object = {
        "object_type": "text",
        "text": text[:1000],  # 카카오 텍스트 템플릿 길이 제한 여유있게 컷
        "link": {
            "web_url": "https://news.google.com",
            "mobile_web_url": "https://news.google.com",
        },
    }
    data = urllib.parse.urlencode(
        {"template_object": json.dumps(template_object, ensure_ascii=False)}
    ).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    with urllib.request.urlopen(req, timeout=15) as res:
        return json.loads(res.read().decode())


def build_chunks(sections, max_len=MAX_CHUNK_LEN):
    """섹션 헤더가 잘리지 않도록, 기사 단위로 묶어서 여러 청크로 나눈다.

    각 청크는 (텍스트, 포함된 기사 link 목록) 튜플로 반환한다.
    이 link 목록은 나중에 "실제로 보낸 기사만" seen 처리하는 데 쓰인다.
    """
    chunks = []
    parts, links, length, section_open = [], [], 0, False

    def flush():
        nonlocal parts, links, length, section_open
        if parts:
            chunks.append(("\n".join(parts), links))
        parts, links, length, section_open = [], [], 0, False

    for group_name, articles in sections:
        section_open = False
        header = f"[{group_name}]"
        for a in articles:
            entry = f"· {a['title']}\n  {a['link']}"
            add_len = len(entry) + 1 + (0 if section_open else len(header) + 1)
            if parts and length + add_len > max_len:
                flush()
            if not section_open:
                parts.append(header)
                length += len(header) + 1
                section_open = True
            parts.append(entry)
            links.append(a["link"])
            length += len(entry) + 1
    flush()
    return chunks


if __name__ == "__main__":
    if not os.path.exists(SECTIONS_FILE):
        print("뉴스 데이터 파일이 없습니다. 크롤링 단계를 먼저 실행하세요.")
        raise SystemExit(0)

    with open(SECTIONS_FILE, "r", encoding="utf-8") as f:
        sections = json.load(f)

    if not sections:
        print("새로운 뉴스가 없어 발송을 건너뜁니다.")
        raise SystemExit(0)

    all_chunks = build_chunks(sections)
    chunks_to_send = all_chunks[:MAX_MESSAGES_PER_RUN]
    skipped = len(all_chunks) - len(chunks_to_send)
    if skipped > 0:
        print(f"[안내] 오늘 분량이 많아 {skipped}개 청크는 이번엔 건너뜁니다 (다음 실행에서 재시도).")

    now_str = datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    total = len(chunks_to_send)

    token = refresh_access_token()
    seen = load_seen()
    for i, (chunk_text, chunk_links) in enumerate(chunks_to_send, 1):
        suffix = f" ({i}/{total})" if total > 1 else ""
        text = f"📰 AI/AICC 뉴스 브리핑{suffix} ({now_str} KST)\n\n{chunk_text}"
        result = send_to_me(token, text)
        print(f"발송 결과 [{i}/{total}]:", result)
        # 실제로 보낸 기사만 seen 처리 (못 보낸 기사는 다음 실행에서 다시 시도됨)
        seen.update(chunk_links)
        save_seen(seen)
        if i < total:
            time.sleep(1)
