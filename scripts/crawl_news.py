"""
AI / AICC 뉴스 크롤러
구글 뉴스 RSS 키워드 검색 + 국내 IT/AI 매체 RSS 구독을 통해 최신 뉴스를 수집하고,
중복 제거 후 카카오톡 발송용 텍스트를 만든다.
"""

import email.utils
import json
import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))

KEYWORD_GROUPS = {
    "AICC/상담센터 AI": [
        "AICC",
        "AI 콜센터",
        "음성봇 상담",
        "컨택센터 AI",
        "에이전틱 AI 컨택센터",
    ],
    "AI 엔진 (LLM/STT/TTS)": [
        "LLM 모델 출시",
        "STT 음성인식 모델",
        "TTS 음성합성 모델",
        "생성형 AI 모델",
    ],
}
ALL_KEYWORDS = [kw for kws in KEYWORD_GROUPS.values() for kw in kws]

# 매체 RSS는 전체 IT 뉴스에서 골라내야 하므로, 구글 검색 키워드보다 넓은 필터를 쓴다.
MEDIA_FILTER_KEYWORDS = list(
    dict.fromkeys(
        ALL_KEYWORDS
        + [
            "AI",
            "인공지능",
            "생성형",
            "챗봇",
            "콜센터",
            "컨택센터",
            "LLM",
            "STT",
            "TTS",
        ]
    )
)

# 국내 IT/AI 매체 자체 RSS (구글 뉴스에 안 잡히는 기사 보강용)
MEDIA_FEEDS = {
    "전자신문": "https://rss.etnews.com/Section901.xml",
    "AI타임스": "https://www.aitimes.com/rss/allArticle.xml",
    "테크M": "https://www.techm.kr/rss/allArticle.xml",
    "블로터": "https://www.bloter.net/rss/allArticle.xml",
    "디지털투데이": "http://www.digitaltoday.co.kr/rss/allArticle.xml",
}

SEEN_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "seen_urls.json")
MAX_PER_KEYWORD = 3
MAX_PER_MEDIA = 3
LOOKBACK_HOURS = 30  # 하루 1회 실행 기준, 여유있게 30시간


def parse_pub_date(pub_date_str):
    try:
        dt = email.utils.parsedate_to_datetime(pub_date_str)
    except (TypeError, ValueError):
        return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_seen(seen):
    os.makedirs(os.path.dirname(SEEN_FILE), exist_ok=True)
    # 최대 500개만 유지 (무한 증가 방지)
    trimmed = list(seen)[-500:]
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(trimmed, f, ensure_ascii=False, indent=2)


def fetch_news_for_keyword(keyword):
    query = urllib.parse.quote(keyword)
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as res:
        data = res.read()
    root = ET.fromstring(data)
    items = []
    now = datetime.now(timezone.utc)
    for item in root.findall(".//item"):
        title = item.findtext("title", default="").strip()
        link = item.findtext("link", default="").strip()
        pub_date = parse_pub_date(item.findtext("pubDate", default=""))
        if pub_date is None or (now - pub_date) > timedelta(hours=LOOKBACK_HOURS):
            continue
        items.append({"title": title, "link": link, "pub_date": pub_date})
    return items[:MAX_PER_KEYWORD]


def fetch_media_feed(feed_url):
    req = urllib.request.Request(feed_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as res:
        data = res.read()
    root = ET.fromstring(data)
    items = []
    now = datetime.now(timezone.utc)
    for item in root.findall(".//item"):
        title = item.findtext("title", default="").strip()
        link = item.findtext("link", default="").strip()
        pub_date = parse_pub_date(item.findtext("pubDate", default=""))
        if pub_date is None or (now - pub_date) > timedelta(hours=LOOKBACK_HOURS):
            continue
        if not any(kw in title for kw in MEDIA_FILTER_KEYWORDS):
            continue
        items.append({"title": title, "link": link, "pub_date": pub_date})
    return items[:MAX_PER_MEDIA]


def build_message():
    seen = load_seen()
    new_seen = set(seen)
    sections = []

    for group_name, keywords in KEYWORD_GROUPS.items():
        group_lines = []
        for kw in keywords:
            try:
                articles = fetch_news_for_keyword(kw)
            except Exception as e:
                print(f"[경고] '{kw}' 크롤링 실패: {e}")
                continue
            for a in articles:
                if a["link"] in seen:
                    continue
                new_seen.add(a["link"])
                group_lines.append(f"· {a['title']}\n  {a['link']}")
        if group_lines:
            sections.append(f"[{group_name}]\n" + "\n".join(group_lines))

    media_lines = []
    for media_name, feed_url in MEDIA_FEEDS.items():
        try:
            articles = fetch_media_feed(feed_url)
        except Exception as e:
            print(f"[경고] '{media_name}' RSS 크롤링 실패: {e}")
            continue
        for a in articles:
            if a["link"] in seen:
                continue
            new_seen.add(a["link"])
            media_lines.append(f"· [{media_name}] {a['title']}\n  {a['link']}")
    if media_lines:
        sections.append("[국내 IT/AI 매체]\n" + "\n".join(media_lines))

    save_seen(new_seen)

    if not sections:
        return None

    now_str = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    header = f"📰 AI/AICC 뉴스 브리핑 ({now_str} KST)\n\n"
    return header + "\n\n".join(sections)


if __name__ == "__main__":
    msg = build_message()
    if msg:
        print(msg)
        # GitHub Actions에서 다음 스텝으로 넘기기 위해 파일로 저장
        with open("news_message.txt", "w", encoding="utf-8") as f:
            f.write(msg)
    else:
        print("새로운 뉴스가 없습니다.")
        with open("news_message.txt", "w", encoding="utf-8") as f:
            f.write("")
