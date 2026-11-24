"""
처음 한 번만 내 PC에서 실행하는 파일이에요.
구글 로그인 창이 뜨면 블로그 주인 계정(ldh943655 블로그가 있는 계정)으로 로그인하고 허용을 누르세요.
화면에 나오는 세 값을 깃허브 Secrets에 넣으면 됩니다.

준비: 같은 폴더에 client_secret.json (구글 클라우드에서 받은 OAuth 파일)
실행: pip install google-auth-oauthlib
      python get_token.py
"""
import json
from google_auth_oauthlib.flow import InstalledAppFlow

flow = InstalledAppFlow.from_client_secrets_file(
    "client_secret.json", ["https://www.googleapis.com/auth/blogger"]
)
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
info = json.loads(creds.to_json())

lines = [
    "아래 세 값을 깃허브 Secrets에 각각 넣으세요. 다른 사람에게 보여 주지 마세요.",
    "",
    "BLOGGER_CLIENT_ID",
    info["client_id"],
    "",
    "BLOGGER_CLIENT_SECRET",
    info["client_secret"],
    "",
    "BLOGGER_REFRESH_TOKEN",
    info["refresh_token"],
]
with open("깃허브_비밀값.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print("\n완료! 같은 폴더의 '깃허브_비밀값.txt' 파일에 세 값을 저장했어요.")
