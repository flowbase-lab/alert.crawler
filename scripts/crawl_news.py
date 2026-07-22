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

# 해외(영어권) 뉴스 - LLM/STT/TTS는 해외 발표가 많아 영어 구글 뉴스로 별도 검색
GLOBAL_KEYWORD_GROUPS = {
    "해외 AI 엔진 (LLM/STT/TTS)": [
        "LLM model release",
        "speech-to-text model release",
        "text-to-speech AI model",
        "generative AI model launch",
    ],
    "해외 AICC/컨택센터 AI": [
        "AI contact center",
        "conversational AI customer service",
        "voice AI customer support",
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


def fetch_news_for_keyword(keyword, hl="ko", gl="KR", ceid="KR:ko"):
    query = urllib.parse.quote(keyword)
    url = f"https://news.google.com/rss/search?q={query}&hl={hl}&gl={gl}&ceid={ceid}"
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


def build_sections():
    """섹션별로 (제목, [기사, ...]) 목록을 만든다. 기사는 {"title", "link"}.

    주의: 여기서는 dedup 조회만 하고 seen_urls.json에 기록하지는 않는다.
    실제로 카카오톡 발송에 성공한 기사만 send_kakao.py가 seen 처리한다.
    (안 그러면 발송 개수 제한에 걸려 못 보낸 기사가 "이미 봤음" 처리되어
    영영 다시 안 나오는 버그가 생긴다.)
    """
    seen = load_seen()
    collected = set()  # 이번 실행 안에서 키워드끼리 겹치는 것만 방지
    sections = []

    def collect(group_name, keywords, fetch_fn):
        articles_out = []
        for kw in keywords:
            try:
                articles = fetch_fn(kw)
            except Exception as e:
                print(f"[경고] '{kw}' 크롤링 실패: {e}")
                continue
            for a in articles:
                if a["link"] in seen or a["link"] in collected:
                    continue
                collected.add(a["link"])
                articles_out.append({"title": a["title"], "link": a["link"]})
        if articles_out:
            sections.append((group_name, articles_out))

    for group_name, keywords in KEYWORD_GROUPS.items():
        collect(group_name, keywords, fetch_news_for_keyword)

    for group_name, keywords in GLOBAL_KEYWORD_GROUPS.items():
        collect(
            group_name,
            keywords,
            lambda kw: fetch_news_for_keyword(kw, hl="en-US", gl="US", ceid="US:en"),
        )

    media_articles = []
    for media_name, feed_url in MEDIA_FEEDS.items():
        try:
            articles = fetch_media_feed(feed_url)
        except Exception as e:
            print(f"[경고] '{media_name}' RSS 크롤링 실패: {e}")
            continue
        for a in articles:
            if a["link"] in seen or a["link"] in collected:
                continue
            collected.add(a["link"])
            media_articles.append({"title": f"[{media_name}] {a['title']}", "link": a["link"]})
    if media_articles:
        sections.append(("국내 IT/AI 매체", media_articles))

    return sections


def render_text(sections):
    now_str = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    header = f"📰 AI/AICC 뉴스 브리핑 ({now_str} KST)"
    blocks = [header]
    for group_name, articles in sections:
        lines = [f"[{group_name}]"]
        lines += [f"· {a['title']}\n  {a['link']}" for a in articles]
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


if __name__ == "__main__":
    sections = build_sections()

    # 사람이 읽기 좋은 전체 미리보기 (발송용 청크 분할은 send_kakao.py가 처리)
    text = render_text(sections) if sections else ""
    print(text if text else "새로운 뉴스가 없습니다.")
    with open("news_message.txt", "w", encoding="utf-8") as f:
        f.write(text)

    # GitHub Actions에서 다음 스텝(send_kakao.py)으로 넘기기 위해 구조화된 형태로 저장
    with open("news_sections.json", "w", encoding="utf-8") as f:
        json.dump(sections, f, ensure_ascii=False, indent=2)
