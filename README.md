# AICC/AI 뉴스 → 카카오톡 자동 알림

매일 오전 9시(KST), AI 전반 + AICC/컨택센터 AI 뉴스를 아래 소스에서 크롤링해서
카카오톡 "나에게 보내기"로 발송합니다.

- 구글 뉴스 RSS (국내: 한국어/한국 지역, 해외: 영어/미국 지역)
- 국내 IT/AI 매체 RSS 직접 구독 (전자신문, AI타임스, 테크M, 블로터, 디지털투데이)

기사가 많은 날은 카카오 텍스트 메시지 길이 제한(1000자) 때문에 여러 통으로 나눠서 보내며,
한 번에 최대 10통까지만 보내고 나머지는 다음 실행 때 이어서 보냅니다(유실 없음).

## 준비물
- GitHub 계정 (개인 레포 1개)
- 카카오 계정 (developers.kakao.com)

## 설정 순서

### 1. 카카오 앱 등록
1. https://developers.kakao.com 접속 → 로그인
2. [내 애플리케이션] → [애플리케이션 추가하기] → 이름은 아무거나 (예: `aicc-news-bot`)
3. 앱 선택 → [제품 설정] → [카카오 로그인] → 활성화 ON
4. [앱 설정] → [앱 키] → REST API 키 하단 "로그인 리다이렉트 URI" → `http://localhost:5000` 추가 후 저장
5. [카카오 로그인] → [동의항목] → "카카오톡 메시지 전송" 항목을 찾아 **선택 동의**로 설정
   (개인 개발자 앱은 필수 동의를 선택할 수 없습니다 - 대신 아래 2단계 로그인 시 동의 화면에서 이 항목을 직접 체크해야 합니다)
6. [앱 설정] → [앱 키] → **REST API 키** 복사해두기
7. 같은 페이지에서 REST API 키 하단 "클라이언트 시크릿" 상태 확인 → **활성화(ON)**라면 코드도 복사해두기 (5단계 인증 시 필요)

### 2. 최초 1회 로그인 인증 (내 PC에서)
1. 이 프로젝트를 로컬에 다운로드
2. `scripts/kakao_auth.py` 파일을 열어 `REST_API_KEY`, `CLIENT_SECRET` 값을 1단계에서 복사한 값으로 교체
3. 터미널에서 실행:
   ```
   python scripts/kakao_auth.py
   ```
4. 출력된 URL을 브라우저에 붙여넣고 로그인 + 동의 (동의 화면에서 "카카오톡 메시지 전송" 항목을 꼭 체크)
5. 리다이렉트된 주소(`http://localhost:5000/?code=XXXX`)에서 `code=` 뒤의 값 **전체**를 복사 (중간에 잘리지 않게 주의)
6. 터미널에 붙여넣고 Enter
7. 출력되는 `refresh_token` 값을 복사해두기 (이게 제일 중요한 값)

### 3. GitHub 레포 만들고 Secrets 등록
1. GitHub에서 새 레포 생성 (Private 추천) 후 이 프로젝트 폴더 전체를 push
2. 레포 → [Settings] → [Secrets and variables] → [Actions] → [New repository secret]
3. 아래 3개를 등록:
   - `KAKAO_REST_API_KEY` : 1단계에서 복사한 REST API 키
   - `KAKAO_CLIENT_SECRET` : [앱 키] 페이지의 REST API 키 하단 "클라이언트 시크릿" 코드 (활성화되어 있는 경우 필수)
   - `KAKAO_REFRESH_TOKEN` : 2단계 마지막에 얻은 refresh_token

### 4. 동작 확인
- [Actions] 탭 → "AICC/AI 뉴스 크롤링 & 카카오 발송" → [Run workflow]로 수동 실행해서 카톡이 오는지 확인
- 정상 작동하면 이후로는 매일 09:00 KST에 자동 실행됨

## 참고
- 카카오 access_token은 6시간, refresh_token은 최대 2개월까지 유효합니다.
  refresh_token도 갱신 시점에 따라 재발급될 수 있는데, 이 스크립트는 재발급된 refresh_token을
  다시 저장하지는 않으므로 **2개월에 한 번 정도는 2단계 인증을 다시 해줘야 할 수 있습니다.**
  (필요하면 자동 갱신 저장 로직도 추가해드릴 수 있어요.)
- 키워드는 `scripts/crawl_news.py`의 `KEYWORD_GROUPS`(국내)/`GLOBAL_KEYWORD_GROUPS`(해외)에서 자유롭게 수정 가능합니다.
- 국내 매체 RSS 목록은 `scripts/crawl_news.py`의 `MEDIA_FEEDS`에서 추가/삭제할 수 있습니다.
- 하루 발송량 상한은 `scripts/send_kakao.py`의 `MAX_MESSAGES_PER_RUN`(기본 10)에서 조절 가능합니다.
