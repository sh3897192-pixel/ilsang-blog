"""
일상기록장 블로그 자동 작성·게시 스크립트

사용법 (GitHub Actions가 순서대로 실행):
  python auto_blog.py prepare   # 주제 선정 + 글 작성 + 사진 내려받기 -> out/post.json, images/
  (워크플로가 사진을 저장소에 올림)
  python auto_blog.py publish   # 블로거에 게시 + 기록 저장
"""
import json
import os
import re
import sys
import datetime as dt
from pathlib import Path

import feedparser
import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

ROOT = Path(__file__).parent
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
HISTORY_FILE = ROOT / "used_topics.json"
OUT_DIR = ROOT / "out"
IMG_DIR = ROOT / "images"
KST = dt.timezone(dt.timedelta(hours=9))


# ---------- 공통 ----------
def load_history():
    if HISTORY_FILE.exists():
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    return {"topics": [], "pixabay_ids": []}


def save_history(h):
    HISTORY_FILE.write_text(json.dumps(h, ensure_ascii=False, indent=2), encoding="utf-8")


def get_trends():
    try:
        feed = feedparser.parse("https://trends.google.com/trending/rss?geo=KR")
        return [e.title for e in feed.entries][:25]
    except Exception:
        return []


def extract_json(text):
    m = re.search(r"<json>\s*(.*?)\s*</json>", text, re.S)
    raw = m.group(1) if m else text[text.find("{"): text.rfind("}") + 1]
    return json.loads(raw)


# ---------- 1단계: 글 작성 ----------
def build_prompt(trends, used_topics, today, topic=None, news=None):
    cats = "\n".join(f"   - {c}" for c in CONFIG["categories"])
    if topic:
        topic_part = f"""[주제]
- 오늘의 주제는 "{topic}"입니다. 이 주제로 쓰세요."""
    else:
        topic_part = f"""[주제 고르기]
- 주제는 반드시 아래 생활 정보 분야 안에서만 고르세요.
{cats}
- 오늘 한국 구글 트렌드 인기 검색어: {', '.join(trends) if trends else '(가져오지 못함)'}
  이 중 위 분야와 연결되는 것이 있으면 그것을 고르고, 없으면 지금 계절에 맞는 생활 정보 주제를 고르세요.
- 사건·사고, 연예인, 특정 인물, 정치 주제는 피하세요.
- 이미 쓴 주제와 겹치면 안 됩니다: {', '.join(used_topics)}"""

    if news is not None:
        news_list = "\n".join(f"- {n['title']} ({n['date']}) {n['link']}" for n in news) or "- (없음)"
        fact_part = f"""- 웹 검색은 할 수 없습니다. 최신 소식은 아래 뉴스 목록(제목)만 참고하세요.
{news_list}
- 위 목록 제목에 나온 것 외의 구체적인 숫자·금액·날짜·제도 내용은 절대 지어내지 마세요. 대신 "공식 발표를 확인해 보세요"처럼 안내하고, 누구나 아는 일반적인 생활 요령 중심으로 쓰세요.
- 참고 자료 링크는 반드시 위 목록에 있는 링크만 쓰세요. 목록이 비어 있으면 참고 자료 문단은 빼세요.
- 의학적 진단·치료 조언은 하지 마세요."""
    else:
        fact_part = """- 웹 검색으로 최신 공식 자료(정부·공공기관 발표, 주요 언론)를 확인한 뒤 쓰세요.
- 숫자·날짜·제도 내용은 확인한 것만 쓰고, 확인되지 않은 내용은 단정하지 마세요. 의학적 진단·치료 조언은 하지 마세요."""

    return f"""오늘은 {today}입니다. 당신은 한국어 생활 정보 블로그 "{CONFIG['blog_name']}"의 글을 씁니다.

{topic_part}

[글 쓰기]
{fact_part}
- 독자에게 실제로 도움이 되는 1500자 이상, 존댓말(~해요체), 소제목은 <h2>로 3~5개.
- 본문은 HTML로만 쓰세요(<p>, <h2>, <ul>, <li>, <b>, <a>). 마크다운 금지.
- 사진 자리 3곳에 정확히 <!--IMG1-->, <!--IMG2-->, <!--IMG3--> 를 넣으세요. IMG1은 첫 문단 바로 아래, IMG2와 IMG3은 서로 다른 소제목 바로 아래.
- 글 끝에 참고한 공식 자료 링크 1~2개를 <p>참고 자료: <a href="...">...</a></p> 형태로 넣으세요.
- 그 다음에 블로그 주인의 1인칭 문단(2~3문장)을 넣으세요. 이 주제를 정리하며 느낀 점과 앞으로 해 보려는 일을 편한 말투로. "해 보니"처럼 이미 해 본 것처럼 쓰지 말고, 실제로 겪은 구체적인 일은 지어내지 마세요.
- 맨 끝에 <p><i>※ 이 글은 {today} 기준 공개 자료를 바탕으로 정리했으며, 이후 달라질 수 있어요.</i></p>

[출력 형식]
마지막에 아래 두 부분만 출력하세요.
1) 글 정보 JSON을 <json></json> 태그로 감싸서:
<json>
{{
  "topic": "짧은 주제명(한국어)",
  "title": "검색에 잘 걸리는 자연스러운 제목",
  "labels": ["생활정보", "키워드1", "키워드2", "키워드3"],
  "images": [
    {{"query": "사진에 실제로 보일 물건·장면을 영어 2~3단어로 (예: radiator heating)", "caption": "그 query 그대로를 묘사한 짧은 한국어 설명"}},
    {{"query": "...", "caption": "..."}},
    {{"query": "...", "caption": "..."}}
  ]
}}
</json>
2) 본문 HTML 전체를 <article></article> 태그로 감싸서."""


def claude_generate(prompt):
    import anthropic

    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=CONFIG["claude_model"],
        max_tokens=16000,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 6}],
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")


def gemini_generate(prompt):
    """제미나이 무료 API. 설정한 모델이 없으면 다음 모델로 넘어가요."""
    import time

    last_err = None
    for model in CONFIG["gemini_models"]:
        for attempt in range(4):
            try:
                r = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"].strip()},
                    json={
                        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 16000},
                    },
                    timeout=240,
                )
            except requests.RequestException as e:
                last_err = f"{model}: {e}"
                time.sleep(20)
                continue
            if r.status_code == 200:
                try:
                    parts = r.json()["candidates"][0]["content"]["parts"]
                except (KeyError, IndexError):
                    last_err = f"{model}: 빈 응답"
                    time.sleep(10)
                    continue
                print("사용 모델:", model)
                return "".join(p.get("text", "") for p in parts)
            last_err = f"{model}: {r.status_code} {r.text[:200]}"
            if r.status_code in (404, 400, 403):
                break  # 이 모델은 못 씀 -> 다음 모델로
            if r.status_code == 503 and attempt >= 1:
                break  # 계속 바쁘면 오래 기다리지 말고 다음 모델로
            # 503(바쁨), 429(잠시 한도), 500 등은 기다렸다가 다시 시도
            wait = 20 * (attempt + 1)
            print(f"{model} 응답 {r.status_code}, {wait}초 뒤 다시 시도")
            time.sleep(wait)
    raise RuntimeError(f"제미나이를 쓸 수 없어요 ({last_err})")


def get_news(query, n=8):
    """구글 뉴스 RSS에서 최근 기사 제목·링크·날짜를 가져와요 (무료)."""
    url = (
        "https://news.google.com/rss/search?q="
        + requests.utils.quote(query + " when:14d")
        + "&hl=ko&gl=KR&ceid=KR:ko"
    )
    try:
        feed = feedparser.parse(url)
    except Exception:
        return []
    return [
        {"title": e.title, "link": e.link, "date": e.get("published", "")}
        for e in feed.entries[:n]
    ]


def pick_topic(trends, used_topics, today):
    cats = "\n".join(f"- {c}" for c in CONFIG["categories"])
    prompt = f"""오늘은 {today}입니다. 한국어 생활 정보 블로그의 오늘 글 주제를 하나 고르세요.
분야(이 안에서만):
{cats}
오늘 한국 구글 트렌드 인기 검색어: {', '.join(trends) if trends else '(없음)'}
이 중 위 분야와 연결되는 것이 있으면 그것을, 없으면 지금 계절에 맞는 생활 정보 주제를 고르세요.
사건·사고, 연예인, 특정 인물, 정치는 피하고, 이미 쓴 주제와 겹치지 마세요: {', '.join(used_topics)}
아래 형식의 JSON만 <json></json> 태그로 감싸서 출력하세요.
<json>{{"topic": "짧은 주제명", "news_query": "구글 뉴스 검색어(한국어 2~4단어)"}}</json>"""
    return extract_json(gemini_generate(prompt))


def write_post():
    history = load_history()
    today = dt.datetime.now(KST).strftime("%Y년 %m월 %d일")
    trends = get_trends()

    if CONFIG["ai"] == "claude":
        text = claude_generate(build_prompt(trends, history["topics"], today))
    else:
        chosen = pick_topic(trends, history["topics"], today)
        news = get_news(chosen["news_query"])
        print("주제 후보:", chosen["topic"], "/ 뉴스", len(news), "건")
        text = gemini_generate(
            build_prompt(trends, history["topics"], today, topic=chosen["topic"], news=news)
        )

    post = extract_json(text)
    m = re.search(r"<article>(.*)</article>", text, re.S)
    if m:
        post["html"] = m.group(1).strip()
    for key in ("topic", "title", "labels", "images", "html"):
        if key not in post:
            raise ValueError(f"응답에 {key} 항목이 없어요")
    post["html"] = review_post(post["html"])
    return post, history


def review_post(html):
    """다 쓴 글을 한 번 더 검토해서, 근거 없는 주장과 지어낸 경험을 고쳐요."""
    prompt = f"""아래는 한국어 생활 정보 블로그 글의 HTML입니다. 편집자로서 검토하고 고친 HTML 전체를 돌려주세요.

고칠 것:
1. 과학적·사실적 근거가 약하거나 틀릴 수 있는 문장은 빼거나, 누구나 아는 일반적인 표현으로 바꾸세요.
2. 숫자·금액·날짜·비율 중 출처가 분명하지 않은 것은 빼세요.
3. 글쓴이가 실제로 해 봤다는 과거 경험 표현("해 보니", "해봤더니", "써 보니" 등)은 "해 보려고 해요"처럼 앞으로의 계획으로 바꾸세요.
4. 어색한 문장, 맞춤법, 중복 내용을 다듬으세요.

반드시 지킬 것:
- <!--IMG1-->, <!--IMG2-->, <!--IMG3--> 표시와 모든 <a href> 링크, <h2> 소제목 구조는 그대로 두세요.
- 분량은 원래와 비슷하게 유지하세요 (1500자 이상).
- 설명 없이 고친 HTML만 <article></article> 태그로 감싸서 출력하세요.

<article>
{html}
</article>"""
    try:
        gen = claude_generate if CONFIG["ai"] == "claude" else gemini_generate
        out = gen(prompt)
        m = re.search(r"<article>(.*)</article>", out, re.S)
        fixed = m.group(1).strip() if m else ""
        ok = (
            len(fixed) >= max(1500, int(len(html) * 0.7))
            and all(f"<!--IMG{i}-->" in fixed for i in (1, 2, 3))
            and fixed.count("<h2>") >= 2
        )
        if ok:
            print("검토 완료: 글을 다듬었어요")
            return fixed
        print("검토 결과가 형식에 맞지 않아 원래 글을 써요")
    except Exception as e:
        print("검토 단계를 건너뛰어요:", str(e)[:100])
    return html


# ---------- 1단계: 사진 ----------
def fetch_image(query, used_ids, save_as):
    """사진은 꼭 넣어야 해요. 검색어를 조금씩 바꿔 가며, 내용과 맞는 사진만 골라요."""
    words = query.split()
    keywords = [w.lower() for w in words if len(w) > 2] or [w.lower() for w in words]
    tries = [query, " ".join(words[:3]), " ".join(words[:2]), words[0] if words else query]
    for q in dict.fromkeys(t for t in tries if t):
        try:
            hit = _fetch_image(q, used_ids, save_as, keywords)
            if hit:
                if q != query:
                    print(f"사진 검색어를 '{query}' -> '{q}'로 바꿔서 찾았어요")
                return hit
        except Exception as e:
            print(f"사진 검색 실패 ({q}): {str(e).split('?')[0]}")
    return None


def _fetch_image(query, used_ids, save_as, keywords=()):
    # 붙여넣기할 때 따라 들어간 공백·줄바꿈·따옴표를 지워요
    raw = os.environ["PIXABAY_API_KEY"]
    found = re.search(r"\d+-[0-9a-f]{20,}", raw)  # 다른 글자가 섞여 들어가도 키 부분만 골라내요
    key = found.group(0) if found else raw.strip().strip('"').strip("'").strip()
    r = requests.get(
        "https://pixabay.com/api/",
        params={
            "key": key,
            "q": query[:100],
            "image_type": "photo",
            "safesearch": "true",
            "orientation": "horizontal",
            "per_page": 20,
        },
        timeout=30,
    )
    if r.status_code != 200:
        looks_ok = bool(re.fullmatch(r"\d+-[0-9a-f]+", key))
        raise RuntimeError(
            f"픽사베이 {r.status_code}: {r.text[:80]} "
            f"(키 길이 {len(key)}자, 형식 {'정상' if looks_ok else '이상함'})"
        )
    hits = [h for h in r.json().get("hits", []) if h["id"] not in used_ids]
    # 사진 태그가 검색어와 많이 겹치는 것부터 골라요 (내용과 안 맞는 사진 방지)
    need = 2 if len(keywords) >= 3 else 1

    def score(h):
        tags = h.get("tags", "").lower()
        return sum(1 for k in keywords if k in tags)

    hits = [h for h in hits if not keywords or score(h) >= need]
    hits.sort(key=score, reverse=True)
    for hit in hits:
        img = requests.get(hit.get("largeImageURL") or hit["webformatURL"], timeout=60)
        img.raise_for_status()
        save_as.write_bytes(img.content)
        return hit
    return None


def figure_html(url, caption, page_url):
    return (
        '<div class="separator" style="clear: both; text-align: center;">'
        f'<img src="{url}" alt="{caption}" style="max-width:100%; height:auto;" /></div>'
        '<p style="text-align: center; font-size: 85%; color: #666;">'
        f'{caption} (<a href="{page_url}">이미지 출처: Pixabay</a>)</p>'
    )


def prepare():
    stamp = dt.datetime.now(KST).strftime("%Y%m%d-%H%M")
    try:
        _prepare(stamp)
    except Exception:
        # 실패한 시도에서 받아 둔 사진은 지워서 저장소에 쌓이지 않게 해요
        for f in IMG_DIR.glob(f"{stamp}-*.jpg"):
            f.unlink()
        raise


def _prepare(stamp):
    post, history = write_post()
    IMG_DIR.mkdir(exist_ok=True)
    OUT_DIR.mkdir(exist_ok=True)
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    branch = os.environ.get("GITHUB_REF_NAME", "main")

    html = post["html"]
    new_ids = []
    for i, im in enumerate(post["images"][:3], start=1):
        name = f"{stamp}-{i}.jpg"
        hit = fetch_image(im["query"], set(history["pixabay_ids"]) | set(new_ids), IMG_DIR / name)
        marker = f"<!--IMG{i}-->"
        if hit:
            new_ids.append(hit["id"])
            url = f"https://raw.githubusercontent.com/{repo}/{branch}/images/{name}"
            html = html.replace(marker, figure_html(url, im["caption"], hit["pageURL"]))
        else:
            raise RuntimeError(f"사진 {i}번을 끝내 못 구해서 이번 글은 올리지 않아요 (검색어: {im['query']})")

    post["html"] = html
    post["pixabay_ids"] = new_ids
    (OUT_DIR / "post.json").write_text(json.dumps(post, ensure_ascii=False, indent=2), encoding="utf-8")
    print("주제:", post["topic"])
    print("제목:", post["title"])
    print("사진:", len(new_ids), "장")


# ---------- 2단계: 게시 ----------
def blogger():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["BLOGGER_REFRESH_TOKEN"].strip(),
        client_id=os.environ["BLOGGER_CLIENT_ID"].strip(),
        client_secret=os.environ["BLOGGER_CLIENT_SECRET"].strip(),
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/blogger"],
    )
    creds.refresh(Request())
    return build("blogger", "v3", credentials=creds, cache_discovery=False)


def publish():
    post = json.loads((OUT_DIR / "post.json").read_text(encoding="utf-8"))
    if "<!--IMG" in post["html"] or len(post["html"]) < 1500:
        raise ValueError("본문이 너무 짧거나 사진 자리가 남아 있어서 게시를 멈췄어요")

    service = blogger()
    result = service.posts().insert(
        blogId=CONFIG["blog_id"],
        body={"title": post["title"], "content": post["html"], "labels": post["labels"]},
        isDraft=not CONFIG["publish"],
    ).execute()

    history = load_history()
    history["topics"].append(post["topic"])
    history["pixabay_ids"].extend(post.get("pixabay_ids", []))
    save_history(history)
    status = "게시" if CONFIG["publish"] else "임시저장"
    print(f"{status} 완료: {post['title']}")
    print("주소:", result.get("url", "(임시저장 글은 주소 없음)"))


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else ""
    if step == "prepare":
        prepare()
    elif step == "publish":
        publish()
    else:
        print("사용법: python auto_blog.py prepare | publish")
        sys.exit(1)
