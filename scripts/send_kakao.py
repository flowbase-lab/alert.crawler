"""
저장된 refresh_token으로 access_token을 갱신한 뒤,
'나에게 보내기'로 뉴스 메시지를 발송한다.

필요한 환경변수 (GitHub Secrets):
- KAKAO_REST_API_KEY
- KAKAO_CLIENT_SECRET
- KAKAO_REFRESH_TOKEN
"""

import json
import os
import urllib.parse
import urllib.request

REST_API_KEY = os.environ["KAKAO_REST_API_KEY"]
CLIENT_SECRET = os.environ["KAKAO_CLIENT_SECRET"]
REFRESH_TOKEN = os.environ["KAKAO_REFRESH_TOKEN"]

MESSAGE_FILE = "news_message.txt"


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


if __name__ == "__main__":
    if not os.path.exists(MESSAGE_FILE):
        print("메시지 파일이 없습니다. 크롤링 단계를 먼저 실행하세요.")
        raise SystemExit(0)

    with open(MESSAGE_FILE, "r", encoding="utf-8") as f:
        message = f.read().strip()

    if not message:
        print("새로운 뉴스가 없어 발송을 건너뜁니다.")
        raise SystemExit(0)

    token = refresh_access_token()
    result = send_to_me(token, message)
    print("발송 결과:", result)
