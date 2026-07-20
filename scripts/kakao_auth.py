"""
카카오 '나에게 보내기' 최초 1회 인증 스크립트.

로컬 PC에서 딱 한 번만 실행합니다.
실행 후 안내에 따라 브라우저에서 로그인/동의하면
refresh_token이 출력됩니다. 이 값을 GitHub Secrets(KAKAO_REFRESH_TOKEN)에 저장하세요.

사전 준비 (developers.kakao.com):
1. 애플리케이션 추가 -> 앱 이름 아무거나 (예: aicc-news-bot)
2. [내 애플리케이션] > [카카오 로그인] 활성화
3. [앱 설정] > [앱 키] > REST API 키 하단의 "로그인 리다이렉트 URI"에 http://localhost:5000 추가
4. [카카오 로그인] > [동의항목]에서 "카카오톡 메시지 전송" 항목을 '선택 동의'로 설정
   (개인 개발자 앱은 '필수 동의'를 선택할 수 없음 - 비즈니스 인증 필요)
   대신 로그인 시 동의 화면에서 이 항목을 직접 체크해야 함
5. [앱 설정] > [앱 키] > REST API 키 하단의 "클라이언트 시크릿" 활성화 여부 확인
   활성화(ON)라면 코드도 복사해서 아래 CLIENT_SECRET 에 붙여넣기
6. REST API 키 복사 -> 아래 REST_API_KEY 에 붙여넣기
"""

import json
import urllib.parse
import urllib.request

REST_API_KEY = "여기에_REST_API_키_붙여넣기"
CLIENT_SECRET = "여기에_Client_Secret_붙여넣기"
REDIRECT_URI = "http://localhost:5000"


def get_authorize_url():
    params = {
        "client_id": REST_API_KEY,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "talk_message",
    }
    return "https://kauth.kakao.com/oauth/authorize?" + urllib.parse.urlencode(params)


def exchange_code_for_token(code):
    url = "https://kauth.kakao.com/oauth/token"
    data = urllib.parse.urlencode(
        {
            "grant_type": "authorization_code",
            "client_id": REST_API_KEY,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
            "code": code,
        }
    ).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=15) as res:
        return json.loads(res.read().decode())


if __name__ == "__main__":
    if "여기에" in REST_API_KEY or "여기에" in CLIENT_SECRET:
        print("먼저 이 파일 안의 REST_API_KEY, CLIENT_SECRET 값을 실제 값으로 바꿔주세요.")
        raise SystemExit(1)

    print("1) 아래 URL을 브라우저에 붙여넣어 로그인/동의하세요:\n")
    print(get_authorize_url())
    print(
        "\n2) 동의 후 리다이렉트된 주소가 http://localhost:5000/?code=XXXX 형태입니다."
        "\n   그 중 code=이후의 값(XXXX)만 복사해서 아래에 붙여넣으세요.\n"
    )
    code = input("code 값 입력: ").strip()

    token_data = exchange_code_for_token(code)
    print("\n=== 발급 결과 ===")
    print(json.dumps(token_data, ensure_ascii=False, indent=2))

    if "refresh_token" in token_data:
        print("\n✅ 아래 refresh_token 값을 GitHub Secrets(KAKAO_REFRESH_TOKEN)에 저장하세요:")
        print(token_data["refresh_token"])
    else:
        print("\n❌ 실패했습니다. code 값이나 REST_API_KEY, Redirect URI 설정을 다시 확인하세요.")
