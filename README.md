# 일상기록장 자동 게시 설정 방법

매일 한국 시간 오전 6시 40분쯤 깃허브가 알아서 글을 쓰고 블로그에 게시해요. PC는 꺼 둬도 돼요.

## 들어 있는 파일
- `auto_blog.py` : 주제 선정, 글 작성, 사진, 게시를 하는 본체
- `config.json` : 블로그 ID, 게시/임시저장 선택 (`"publish": false`로 바꾸면 임시저장만 해요)
- `used_topics.json` : 이미 쓴 주제 기록 (자동으로 늘어나요)
- `.github/workflows/daily-post.yml` : 매일 아침 실행 예약
- `get_token.py` : 처음 한 번 블로거 로그인 열쇠를 받는 파일

## 처음 한 번만 하는 설정 (약 30분)

### 1. 키 3가지 받기
1. **제미나이 API 키 (무료)**: aistudio.google.com/apikey → "API 키 만들기". 카드 등록 없이 무료 사용량 안에서 써요.
   - 무료 버전은 웹 검색을 못 해서, 구글 뉴스 제목만 참고하고 구체적인 숫자는 지어내지 않도록 해 뒀어요.
   - 나중에 더 정확한 글을 원하면 `config.json`의 `"ai"`를 `"claude"`로 바꾸고 `ANTHROPIC_API_KEY`를 등록하면 돼요(유료).
2. **Pixabay API 키**: pixabay.com 가입 → pixabay.com/api/docs 페이지 중간에 내 키가 보여요.
3. **구글 OAuth 파일**: console.cloud.google.com
   - 새 프로젝트 만들기 → "Blogger API v3" 검색해서 사용 설정
   - OAuth 동의 화면: 외부, 앱 이름 아무거나, 테스트 사용자에 블로그 계정 추가, 그 다음 **"앱 게시"(프로덕션)** 로 바꾸기 (테스트 상태로 두면 7일마다 열쇠가 만료돼요)
   - 사용자 인증 정보 → OAuth 클라이언트 ID → 유형 "데스크톱 앱" → JSON 다운로드 → 이름을 `client_secret.json`으로 바꾸기

### 2. 블로거 열쇠 받기 (내 PC에서)
`client_secret.json`을 이 폴더에 넣고 명령 프롬프트에서:
```
pip install google-auth-oauthlib
python get_token.py
```
로그인 창이 뜨면 **블로그 주인 계정**으로 로그인 → 허용. 화면에 나온 세 값을 메모해 두세요.

### 3. 깃허브에 올리기
1. github.com 가입 → 새 저장소(New repository) 만들기. **Public**으로 만들어야 사진이 블로그에 보여요. (비밀 키는 Secrets에 들어가서 공개되지 않아요)
2. "uploading an existing file"을 눌러 이 폴더의 파일을 모두 끌어다 놓기. `.github` 폴더도 꼭 포함. **`client_secret.json`은 올리지 마세요.**
3. 저장소 → Settings → Secrets and variables → Actions → New repository secret 에서 5개 등록:
   - `GEMINI_API_KEY`
   - `PIXABAY_API_KEY`
   - `BLOGGER_CLIENT_ID`
   - `BLOGGER_CLIENT_SECRET`
   - `BLOGGER_REFRESH_TOKEN`

### 4. 시험 실행
저장소 → Actions → "매일 아침 블로그 글" → **Run workflow**. 초록 체크가 뜨면 블로그에 글이 올라가 있어요.
지금은 `config.json`의 `"publish"`가 `false`라서 **임시저장**만 돼요. 며칠 글 품질을 확인한 뒤 `true`로 바꾸면 그때부터 자동 게시돼요.

## 알아 두세요
- 비용: 제미나이 무료 사용량 안에서는 0원이에요. 무료 등급에서는 보낸 내용이 구글 서비스 개선에 쓰일 수 있어요.
- 실패하면 Actions 화면에 빨간 X가 뜨고, 깃허브가 가입 이메일로 알려 줘요.
- 시간 바꾸기: `daily-post.yml`의 `cron` 줄. 한국 시간에서 9시간을 뺀 값이에요.
- 사람이 안 보고 매일 게시되니, 가끔 블로그에 들어가서 내용을 확인하고 내 경험 한두 줄을 보태 주세요. 애드센스 승인에 도움이 돼요.
