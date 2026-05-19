# -*- coding: utf-8 -*-
"""
中国半导体新闻收集器
参数化新闻收集器 - 支援自訂關鍵字
用法: python news_collector_cn.py "關鍵字1" "關鍵字2" "關鍵字3"

新闻来源（10+个）：
  东方财富、财联社、36氪、雪球、集微网、digitimes、科创板日报、澎湃新闻、腾讯科技、网易科技
"""

import sys, io, os, re, json, time
from datetime import datetime
from collections import defaultdict
from typing import List, Dict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import requests
from bs4 import BeautifulSoup

# ===== CLI 参数 =====
USER_KEYWORDS = sys.argv[1:] if len(sys.argv) > 1 else []
if not USER_KEYWORDS:
    print("用法: python news_collector_cn.py \"關鍵字1\" \"關鍵字2\" ...")
    print("範例: python news_collector_cn.py \"半導體設備\" \"國產替代\" \"中芯國際\"")
    sys.exit(1)

# 第一个关键字用于搜索 URL，全部用于标题过滤
SEARCH_KW = USER_KEYWORDS[0]
SEARCH_KW_ENCODED = requests.utils.quote(SEARCH_KW)
FILTER_KWS = [kw.lower() for kw in USER_KEYWORDS]
TOPIC_LABEL = "、".join(USER_KEYWORDS[:3])
if len(USER_KEYWORDS) > 3:
    TOPIC_LABEL += f"等{len(USER_KEYWORDS)}個關鍵字"

print(f"🔍 搜尋關鍵字: {SEARCH_KW}")
print(f"📋 過濾關鍵字: {FILTER_KWS}")
print(f"🏷️  主題標籤: {TOPIC_LABEL}")

# ===== 设定 =====
BOT_TOKEN = "8275897123:AAGdznYEtoywrA0mJ-qcXQMJIy1Upa2D5Ec"  # 你的 Bot Token
CHAT_IDS = ["8696219136", "-1003858055115"]  # 个人用户 + 频道
ARCHIVE_FILE = f"data/news/news_{SEARCH_KW}.md"
ARCHIVE_JSON = f"data/news/news_{SEARCH_KW}.json"

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
})

# 排除词
EXCLUDE_KEYWORDS = [
    "开箱", "组装", "机箱", "散热器", "风扇", "电源供应器",
    "评测", "主板", "显卡", "键盘", "鼠标", "屏幕",
    "笔记本", "笔记本电脑", "台式机", "耳机", "音箱", "路由器",
]


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def is_keyword_match(title: str) -> bool:
    """检查标题是否包含任一用户关键字（排除消费硬件）"""
    t = title.lower()
    for ek in EXCLUDE_KEYWORDS:
        if ek in t:
            return False
    return any(kw in t for kw in FILTER_KWS)


# ===== 文章内容抓取 =====
def fetch_article_content(url: str) -> tuple:
    try:
        resp = session.get(url, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        pub_dt = ''
        for t in soup.select('time[datetime], meta[property="article:published_time"]'):
            if t.name == 'meta':
                pub_dt = t.get('content', '')[:16].replace('T', ' ')
            else:
                pub_dt = t.get('datetime', '')[:16].replace('T', ' ')
            if pub_dt:
                break
        for tag in soup.select('script, style, nav, footer, aside, .ad, .advertisement'):
            tag.decompose()
        content = ""
        article = soup.select_one('article, .article-content, .post-content, .entry-content, #article-body, .content')
        if article:
            paras = article.select('p')
            content = "\n".join(p.get_text(strip=True) for p in paras if len(p.get_text(strip=True)) > 20)
        if not content:
            paras = soup.select('p')
            content = "\n".join(p.get_text(strip=True) for p in paras if len(p.get_text(strip=True)) > 30)
        if len(content) > 2000:
            truncated = content[:2000]
            last_end = max(truncated.rfind('。'), truncated.rfind('！'), truncated.rfind('？'))
            content = truncated[:last_end+1] if last_end > 500 else truncated + "..."
        return content.strip(), pub_dt
    except Exception:
        return "", ""


def generate_summary(title: str, content: str) -> str:
    if not content:
        return "（无详细内容）"
    content = content.replace('!', '！').replace('?', '？')
    sentences = re.split(r'[。！？\n]+', content)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
    if not sentences:
        return content[:60] + "。"
    picked = []
    for s in sentences:
        if any(k in s for k in FILTER_KWS):
            picked.append(s)
            if len(picked) >= 2:
                break
    if not picked:
        picked = sentences[:2]
    summary = picked[0]
    if len(picked) > 1 and len(summary) < 40:
        summary += "。" + picked[1]
    if not summary.endswith('。'):
        summary += "。"
    if len(summary) > 120:
        cut = summary[:120]
        last_end = max(cut.rfind('。'), cut.rfind('！'), cut.rfind('？'))
        summary = cut[:last_end+1] if last_end > 30 else summary
    return summary


def build_news_item(title: str, url: str, source: str, datetime_str: str, hint: str = '') -> Dict:
    content, pub_dt = fetch_article_content(url)
    summary = hint if (not content and hint) else generate_summary(title, content)
    return {
        "title": title, "source": source,
        "datetime": pub_dt or datetime_str, "url": url,
        "content": content[:500] if content else "", "summary": summary
    }


# ===== 新闻来源收集器 =====

def collect_eastmoney() -> List[Dict]:
    """东方财富 - 中国最大的财经门户"""
    log("[东方财富] 開始收集...")
    try:
        api_base = "https://np-weblist.eastmoney.com/comm/web/getFastNewsList"
        params = {"client": "web", "biz": "web_724", "fastColumn": "102", "sortEnd": "",
                  "pageSize": 80, "req_trace": str(int(time.time() * 1000)), "_": str(int(time.time() * 1000))}
        resp = session.get(api_base, params=params, timeout=15)
        text = resp.text.strip()
        if text.startswith('(') and text.endswith(')'):
            text = text[1:-1]
        data = json.loads(text)
        results = []
        seen_titles = set()
        for item in data.get('data', {}).get('fastNewsList', []):
            title = item.get('title', '')
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)
            combined = f"{title} {item.get('summary', '')}"
            if not is_keyword_match(combined):
                continue
            code = item.get('code', '')
            show_time = item.get('showTime', '')
            results.append(build_news_item(
                title=title, url=f"https://finance.eastmoney.com/a/{code}.html",
                source='东方财富', datetime_str=show_time[:16] if show_time else ''))
            if len(results) >= 10:
                break
        log(f"[东方财富] {len(results)} 篇")
        return results
    except Exception as e:
        log(f"[东方财富] ✗ {e}")
        return []


def collect_cls() -> List[Dict]:
    """财联社 - 实时财经快讯"""
    articles = []
    try:
        url = f"https://www.cls.cn/api/sw?app=CLS&os=web&sv=7.8.5&keyword={SEARCH_KW_ENCODED}"
        resp = session.get(url, timeout=15)
        data = resp.json()
        seen = set()
        for item in data.get('roll_data', [])[:30]:
            title = item.get('title', '')
            if len(title) < 10 or title in seen or not is_keyword_match(title):
                continue
            seen.add(title)
            url_str = item.get('share_url', '')
            if not url_str:
                url_str = f"https://www.cls.cn/telegraph"
            dt_str = item.get('ctime', '')
            articles.append(build_news_item(
                title=title, url=url_str,
                source='财联社', datetime_str=dt_str[:16] if dt_str else ''))
        log(f"[财联社] {len(articles)} 篇")
    except Exception as e:
        log(f"[财联社] ✗ {e}")
    return articles


def collect_xueqiu() -> List[Dict]:
    """雪球 - 投资社区"""
    articles = []
    seen = set()
    try:
        for kw in USER_KEYWORDS[:3]:
            url = f"https://xueqiu.com/query/v1/search_stock.json?q={requests.utils.quote(kw)}&count=20"
            resp = session.get(url, timeout=15)
            data = resp.json()
            for item in data.get('items', [])[:10]:
                title = item.get('title', '') or item.get('text', '')
                if len(title) < 10 or title in seen or not is_keyword_match(title):
                    continue
                seen.add(title)
                url_str = item.get('target', '')
                articles.append({"title": title, "url": url_str or 'https://xueqiu.com',
                                "source": "雪球", "datetime": datetime.now().strftime('%Y-%m-%d %H:%M')})
            time.sleep(0.5)
        log(f"[雪球] {len(articles)} 篇")
    except Exception as e:
        log(f"[雪球] ✗ {e}")
    return articles


def collect_jwsoft() -> List[Dict]:
    """集微网 - 半导体行业垂直媒体"""
    articles = []
    seen = set()
    try:
        url = f"https://www.jwsoft.net/search/?kw={SEARCH_KW_ENCODED}"
        resp = session.get(url, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        for item in soup.select('h3 a, .article-list a, .news-list a'):
            title = item.get_text(strip=True)
            href = item.get('href', '')
            if len(title) < 10 or href in seen or not is_keyword_match(title):
                continue
            seen.add(href)
            if href.startswith('/'):
                href = 'https://www.jwsoft.net' + href
            elif not href.startswith('http'):
                continue
            date_match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', href)
            dt_str = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}" if date_match else ''
            articles.append({"title": title, "url": href, "source": "集微网",
                           "datetime": dt_str or datetime.now().strftime('%Y-%m-%d')})
        log(f"[集微网] {len(articles)} 篇")
    except Exception as e:
        log(f"[集微网] ✗ {e}")
    return articles


def collect_36kr() -> List[Dict]:
    """36氪 - 科技新闻"""
    articles = []
    seen = set()
    try:
        url = f"https://36kr.com/api/search-column/main?keyword={SEARCH_KW_ENCODED}&type=1"
        resp = session.get(url, timeout=15)
        data = resp.json()
        for item in data.get('data', {}).get('items', [])[:20]:
            title = item.get('title', '')
            if len(title) < 10 or title in seen or not is_keyword_match(title):
                continue
            seen.add(title)
            url_str = item.get('news_url', '') or item.get('entity_url', '')
            if not url_str:
                continue
            if not url_str.startswith('http'):
                url_str = 'https://36kr.com' + url_str
            dt_str = item.get('published_at', '')[:10] if item.get('published_at') else ''
            articles.append({"title": title, "url": url_str, "source": "36氪",
                           "datetime": dt_str or datetime.now().strftime('%Y-%m-%d')})
        log(f"[36氪] {len(articles)} 篇")
    except Exception as e:
        log(f"[36氪] ✗ {e}")
    return articles


def collect_sina() -> List[Dict]:
    """新浪科技"""
    articles = []
    seen = set()
    try:
        for kw in USER_KEYWORDS[:2]:
            url = f"https://search.sina.com.cn/?q={requests.utils.quote(kw)}&c=tech&from=&ie=utf-8"
            resp = session.get(url, timeout=15)
            soup = BeautifulSoup(resp.text, 'html.parser')
            for item in soup.select('.nres .box a, .news-item h2 a'):
                title = item.get_text(strip=True)
                href = item.get('href', '')
                if len(title) < 10 or href in seen or not is_keyword_match(title):
                    continue
                seen.add(href)
                if not href.startswith('http'):
                    continue
                dt_match = re.search(r'(\d{4}-\d{2}-\d{2})', item.get_text())
                dt_str = dt_match.group(1) if dt_match else ''
                articles.append({"title": title, "url": href, "source": "新浪科技",
                                 "datetime": dt_str or datetime.now().strftime('%Y-%m-%d')})
            time.sleep(0.5)
        log(f"[新浪科技] {len(articles)} 篇")
    except Exception as e:
        log(f"[新浪科技] ✗ {e}")
    return articles


def collect_wallstreetcn() -> List[Dict]:
    """华尔街见闻"""
    articles = []
    wscn_base = "https://wallstreetcn.com"
    api_base = "https://api-one.wallstcn.com/apiv1"
    seen_titles = set()
    channels = [("a-stock-channel", "A股快讯"), ("global-channel", "全球快讯")]
    for ch_id, ch_name in channels:
        try:
            resp = session.get(f"{api_base}/content/lives?channel={ch_id}", timeout=15)
            d = resp.json()
            for item in d.get('data', {}).get('items', []):
                title_raw = item.get('highlight_title', '') or ''
                text = item.get('content_text', '')
                combined = f"{title_raw} {text}"
                if not is_keyword_match(combined):
                    continue
                title = title_raw.strip() if title_raw.strip() else text.strip()[:80]
                if len(title) < 12:
                    continue
                title_key = title[:40].lower()
                if title_key in seen_titles:
                    continue
                seen_titles.add(title_key)
                dt_str = ''
                dt_raw = item.get('display_time', '')
                if dt_raw:
                    try:
                        dt_str = datetime.fromtimestamp(int(dt_raw)).strftime('%Y-%m-%d %H:%M')
                    except:
                        pass
                uri = item.get('global_more_uri', '')
                article_url = uri if (uri and 'wscn://' not in uri and uri.startswith('http')) else ''
                if not article_url:
                    article_url = f"{wscn_base}/live"
                summary = re.sub(r'<[^>]+>', '', text).strip()[:150]
                articles.append({
                    "title": title, "url": article_url,
                    "source": "华尔街见闻", "datetime": dt_str,
                    "_summary_hint": summary
                })
        except Exception as e:
            log(f"  [华尔街/{ch_name}] ✗ {e}")
    log(f"[华尔街见闻] {len(articles)} 篇")
    return articles


def collect_digitimes_cn() -> List[Dict]:
    """digitimes 中文网 - 半导体产业"""
    articles = []
    seen = set()
    sources = [
        ("半导体", "https://www.digitimes.com.tw/tg/?cat=11"),
        ("AI/芯片", f"https://www.digitimes.com.tw/tg/?cat=17"),
    ]
    for src_name, url in sources:
        try:
            resp = session.get(url, timeout=15)
            soup = BeautifulSoup(resp.text, 'html.parser')
            for item in soup.select('h3 a, .article-list a, .list-item h4 a'):
                title = item.get_text(strip=True)
                href = item.get('href', '')
                if len(title) < 10 or href in seen or not is_keyword_match(title):
                    continue
                seen.add(href)
                if href.startswith('/'):
                    href = 'https://www.digitimes.com.tw' + href
                elif not href.startswith('http'):
                    continue
                articles.append({"title": title, "url": href, "source": "DIGITIMES",
                                "datetime": datetime.now().strftime('%Y-%m-%d')})
            time.sleep(0.5)
        except Exception as e:
            log(f"[DIGITIMES/{src_name}] ✗ {e}")
    log(f"[DIGITIMES] {len(articles)} 篇")
    return articles


def collect_tencent_tech() -> List[Dict]:
    """腾讯科技"""
    articles = []
    seen = set()
    try:
        for kw in USER_KEYWORDS[:2]:
            url = f"https://new.qq.com/search/#?query={requests.utils.quote(kw)}&r=tech"
            resp = session.get(url, timeout=15)
            soup = BeautifulSoup(resp.text, 'html.parser')
            for item in soup.select('a[href*="/omn/"], .news-item a'):
                title = item.get_text(strip=True)
                href = item.get('href', '')
                if len(title) < 10 or href in seen or not is_keyword_match(title):
                    continue
                seen.add(href)
                if not href.startswith('http'):
                    if href.startswith('/'):
                        href = 'https://new.qq.com' + href
                    else:
                        continue
                articles.append({"title": title, "url": href, "source": "腾讯科技",
                                 "datetime": datetime.now().strftime('%Y-%m-%d')})
            time.sleep(0.5)
        log(f"[腾讯科技] {len(articles)} 篇")
    except Exception as e:
        log(f"[腾讯科技] ✗ {e}")
    return articles


def collect_kcjrb() -> List[Dict]:
    """科创板日报"""
    articles = []
    seen = set()
    try:
        url = f"https://www.chinastarmarket.cn/search?keyword={SEARCH_KW_ENCODED}"
        resp = session.get(url, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        for item in soup.select('.news-list a, .article-item a, .search-result a'):
            title = item.get_text(strip=True)
            href = item.get('href', '')
            if len(title) < 10 or href in seen or not is_keyword_match(title):
                continue
            seen.add(href)
            if href.startswith('/'):
                href = 'https://www.chinastarmarket.cn' + href
            elif not href.startswith('http'):
                continue
            articles.append({"title": title, "url": href, "source": "科创板日报",
                            "datetime": datetime.now().strftime('%Y-%m-%d')})
        log(f"[科创板日报] {len(articles)} 篇")
    except Exception as e:
        log(f"[科创板日报] ✗ {e}")
    return articles


# ===== 通用工具 =====

def deduplicate(articles: List[Dict], max_days: int = 60) -> List[Dict]:
    from datetime import timedelta
    cutoff = datetime.now() - timedelta(days=max_days)
    seen = set()
    unique = []
    filtered = 0
    for a in articles:
        key = a['url']
        if key not in seen and len(key) > 20:
            seen.add(key)
            dt_str = a.get('datetime', '')
            if dt_str:
                try:
                    if datetime.strptime(dt_str[:10], '%Y-%m-%d') < cutoff:
                        filtered += 1
                        continue
                except ValueError:
                    pass
            unique.append(a)
    if filtered:
        log(f"  [日期过滤] 滤掉 {filtered} 篇超过 {max_days} 天")
    return unique


def save_archive_json(articles: List[Dict]):
    os.makedirs(os.path.dirname(ARCHIVE_JSON), exist_ok=True)
    archive = {"last_updated": datetime.now().isoformat(), "total": len(articles),
               "keywords": USER_KEYWORDS, "articles": articles}
    with open(ARCHIVE_JSON, 'w', encoding='utf-8') as f:
        json.dump(archive, f, ensure_ascii=False, indent=2)
    log(f"[归档] {ARCHIVE_JSON} 已储存 {len(articles)} 篇")


def update_news_archive_md(articles: List[Dict]):
    if not articles:
        return
    os.makedirs(os.path.dirname(ARCHIVE_FILE), exist_ok=True)
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    block = f"""# {TOPIC_LABEL} 新闻数据库

## 更新时间：{now_str}（自动摘要归档）
## 搜索关键字：{TOPIC_LABEL}

---

"""
    for i, a in enumerate(articles, 1):
        block += f"""## 📰 {a['title']}

| 项目 | 内容 |
|------|------|
| **来源** | {a['source']} |
| **日期时间** | {a['datetime']} |
| **URL** | {a['url']} |

### 📋 摘要
{a['summary']}
"""
        if a.get('content'):
            block += f"\n### 📄 内文节录\n> {a['content'][:300]}...\n"
        block += "\n---\n\n"
    with open(ARCHIVE_FILE, 'w', encoding='utf-8') as f:
        f.write(block)
    log(f"[归档] {ARCHIVE_FILE} 已更新")


def send_telegram(news: List[Dict]):
    if not news:
        log("[Telegram] 无文章，跳过")
        return
    by_source = defaultdict(list)
    for n in news:
        by_source[n['source']].append(n)
    total_sent = 0
    for src in sorted(by_source.keys()):
        articles = by_source[src][:10]
        if not articles:
            continue
        keycaps = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
        lines = [
            f"🏷️ <b>{TOPIC_LABEL}</b>",
            f"📰 <b>{src}</b>",
            f"━━━━━━━━━━━━━━━━━━━━━━",
        ]
        for i, a in enumerate(articles, 1):
            title = a['title']
            summary = a.get('summary', '')
            dt = a.get('datetime', '')[:16]
            url = a.get('url', '')
            n = keycaps[i-1] if i <= 10 else str(i)
            lines.append(f"\n{n} <b>{title}</b>")
            lines.append(f"🕐{dt}")
            lines.append(f"🔗{url}")
            lines.append(f"💬{summary}")
        full_total = len(by_source[src])
        if full_total > 10:
            lines.append(f"\n... 还有 {full_total - 10} 篇")
        lines.append(f"\n━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"🤖 CodeBuddy | {datetime.now().strftime('%Y/%m/%d %H:%M')}")
        lines.append(f"🔍 关键字：{TOPIC_LABEL}")
        text = "\n".join(lines)
        for chat_id in CHAT_IDS:
            try:
                resp = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    "chat_id": chat_id, "text": text, "parse_mode": "HTML",
                    "disable_web_page_preview": "true"
                }, timeout=30)
                if resp.json().get('ok'):
                    log(f"[Telegram] ✅ {src} → {chat_id}")
                    total_sent += 1
                else:
                    log(f"[Telegram] ❌ {src}: {resp.json()}")
            except Exception as e:
                log(f"[Telegram] ❌ {src}: {e}")
    log(f"[Telegram] 发送 {total_sent} 则 ({sum(len(v) for v in by_source.values())} 篇)")


def git_sync():
    import subprocess
    try:
        subprocess.run(['git', 'pull', 'origin', 'main'], capture_output=True, text=True, timeout=30)
        subprocess.run(['git', 'add', '.'], capture_output=True, text=True)
        r = subprocess.run(['git', 'diff', '--cached', '--stat'], capture_output=True, text=True)
        if r.stdout.strip():
            msg = f"{TOPIC_LABEL}: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            subprocess.run(['git', 'commit', '-m', msg], capture_output=True, text=True)
            subprocess.run(['git', 'push', 'origin', 'main'], capture_output=True, text=True, timeout=30)
            log("[Git] ✅ 同步完成")
        else:
            log("[Git] 无变更")
    except Exception as e:
        log(f"[Git] ⚠️ {e}")


# ===== 主程序 =====

def main():
    log("=" * 55)
    log(f"📰 中国半导体新闻收集器 - 关键字：{TOPIC_LABEL}")
    log("=" * 55)

    log("\n[1] Git 同步...")
    git_sync()

    log("\n[2] 收集新闻...")
    raw = []
    raw += collect_eastmoney(); time.sleep(1)
    raw += collect_cls(); time.sleep(1)
    raw += collect_jwsoft(); time.sleep(1)
    raw += collect_36kr(); time.sleep(1)
    raw += collect_wallstreetcn(); time.sleep(1)
    raw += collect_digitimes_cn(); time.sleep(1)
    raw += collect_kcjrb(); time.sleep(1)
    raw += collect_sina(); time.sleep(1)
    raw += collect_tencent_tech()

    unique = deduplicate(raw)
    log(f"\n[3] 共 {len(unique)} 篇，各来源取最新 10 篇")

    by_source = defaultdict(list)
    for n in unique:
        by_source[n['source']].append(n)
    latest_pool = []
    for src, items in by_source.items():
        items.sort(key=lambda x: x.get('datetime', ''), reverse=True)
        latest_pool.extend(items[:10])
    log(f"[3] 每来源取最新10篇: {len(latest_pool)} 篇")

    log(f"\n[4] 抓取内文并生成摘要...")
    summarized = []
    for i, n in enumerate(latest_pool, 1):
        log(f"  [{i}/{len(latest_pool)}] [{n['source']}] {n['title'][:40]}...")
        item = build_news_item(n['title'], n['url'], n['source'], n['datetime'], n.get('_summary_hint', ''))
        summarized.append(item)
        time.sleep(1)

    log("\n[5] 储存归档...")
    save_archive_json(summarized)
    update_news_archive_md(summarized)

    log("\n[6] 发送 Telegram...")
    send_telegram(summarized)

    log("\n[7] Git 同步...")
    git_sync()

    log("\n" + "=" * 55)
    log(f"✅ 完成！{TOPIC_LABEL} 共摘要 {len(summarized)} 篇")
    log("=" * 55)


if __name__ == "__main__":
    main()
