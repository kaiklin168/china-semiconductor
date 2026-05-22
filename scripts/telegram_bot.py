# -*- coding: utf-8 -*-
"""
中国半导体 Telegram Bot
=======================
监听 Telegram 命令，即时输出新闻摘要

用法:
  python scripts/telegram_bot.py          # 启动 Bot（前台运行）
  nohup python scripts/telegram_bot.py &  # 后台运行

支持命令:
  /ChinaSemi              使用默认关键字
  /ChinaSemi 光刻机 中芯   自定义关键字搜索
  /start                  欢迎信息
  /help                   帮助
"""

import sys, os, time, json
from datetime import datetime

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

# 注册包路径
os.environ.setdefault('PYTHONPATH', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.telegram_notifier import BOT_TOKEN, CHAT_IDS_PERSONAL

# ===== 配置 =====
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"
POLL_INTERVAL = 3             # 轮询间隔（秒）
COLLECTION_TIMEOUT = 120      # 新闻收集最大等待时间（秒）
IS_CLOUD = bool(os.environ.get("RENDER"))  # 是否运行在 Render 云端

# 默认关键字
DEFAULT_KEYWORDS = ["半导体设备", "国产替代", "AI芯片", "中芯国际", "光刻机"]

# 已处理的消息 update_id（避免重复处理）
last_update_id = 0


def send_telegram_msg(chat_id, text, parse_mode="HTML", disable_preview=True):
    """通过 Telegram API 发送消息"""
    try:
        resp = requests.post(f"{API_BASE}/sendMessage", json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_preview
        }, timeout=30)
        return resp.json().get('ok', False)
    except Exception as e:
        print(f"[Bot] 发送失败: {e}")
        return False


def send_typing(chat_id):
    """发送输入中状态"""
    try:
        requests.post(f"{API_BASE}/sendChatAction", json={
            "chat_id": chat_id,
            "action": "typing"
        }, timeout=10)
    except Exception:
        pass


def get_updates(offset=None):
    """获取未处理的更新"""
    params = {"timeout": 30, "allowed_updates": ["message"]}
    if offset:
        params["offset"] = offset
    try:
        resp = requests.get(f"{API_BASE}/getUpdates", params=params, timeout=35)
        data = resp.json()
        if data.get('ok'):
            return data.get('result', [])
    except Exception as e:
        if 'timedout' not in str(e).lower():
            print(f"[Bot] 轮询错误: {e}")
    return []


def build_welcome():
    return (
        f"👋 <b>中国半导体情报助手</b>\n\n"
        f"我是你的半导体产业情报秘书，支持以下指令：\n\n"
        f"/ChinaSemi — 使用默认关键字收集最新新闻\n"
        f"/ChinaSemi 光刻机 中芯国际 — 自定义关键字\n"
        f"/start — 显示此欢迎信息\n"
        f"/help — 查看帮助\n\n"
        f"📡 数据来源：东方财富、财联社、36氪、集微网、华尔街见闻、DIGITIMES、雪球等\n"
        f"🤖 由 CodeBuddy 驱动 | {datetime.now().strftime('%Y/%m/%d')}"
    )


def build_help():
    return (
        f"📖 <b>使用帮助</b>\n\n"
        f"<b>/ChinaSemi [关键字...]</b>\n"
        f"搜索中国半导体相关新闻，支持多个关键字\n\n"
        f"<b>示例：</b>\n"
        f"<code>/ChinaSemi</code>\n"
        f"  → 使用默认关键字\n\n"
        f"<code>/ChinaSemi 光刻机 ASML EUV</code>\n"
        f"  → 搜索光刻机相关新闻\n\n"
        f"<code>/ChinaSemi 中芯国际 先进制程</code>\n"
        f"  → 关注特定公司/主题\n\n"
        f"<b>默认关键字：</b>\n"
        f"{', '.join(DEFAULT_KEYWORDS)}\n\n"
        f"⏱️ 每次查询大约需要 1-2 分钟"
    )


def handle_chinasemi(chat_id, args):
    """处理 /ChinaSemi 命令"""
    keywords = args.strip().split() if args.strip() else DEFAULT_KEYWORDS

    send_telegram_msg(chat_id, (
        f"🔍 <b>正在收集中國半導體新聞…</b>\n"
        f"关键字：<code>{' '.join(keywords)}</code>\n"
        f"約需 1–2 分鐘，请稍候..."
    ))

    send_typing(chat_id)

    # 导入收集模块
    from news.news_collector_cn import run_collection, init_keywords

    # 进度回调，实时通知用户
    def progress(msg):
        send_telegram_msg(chat_id, f"⏳ {msg}")

    try:
        summarized, text = run_collection(
            keywords=keywords,
            chat_id=chat_id,
            do_archive=not IS_CLOUD,  # 云端不存档（无持久存储）
            do_git=not IS_CLOUD,       # 云端不 git push
            progress_callback=progress
        )

        if summarized:
            count = len(summarized)
            sources = set(a['source'] for a in summarized)
            send_telegram_msg(chat_id,
                f"✅ <b>完成！</b> 共 {count} 篇 | 来源：{', '.join(sources)}"
            )
        else:
            send_telegram_msg(chat_id, (
                f"⚠️ <b>未找到相关新闻</b>\n"
                f"关键字: {', '.join(keywords)}\n"
                f"请尝试更换关键字或稍后再试。"
            ))
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        print(f"[Bot] ChinaSemi 错误: {err_msg}")
        send_telegram_msg(chat_id,
            f"❌ <b>查询失败</b>\n错误：{str(e)[:200]}"
        )


def handle_message(msg):
    """处理单条消息"""
    text = msg.get('text', '').strip()
    chat_id = msg.get('chat', {}).get('id', '')
    chat_type = msg.get('chat', {}).get('type', '')

    if not text or not chat_id:
        return

    # 记录日志
    username = msg.get('from', {}).get('username', '')
    first_name = msg.get('from', {}).get('first_name', '')
    user_tag = f"@{username}" if username else first_name
    print(f"[Bot] {datetime.now().strftime('%H:%M:%S')} [{chat_type}] {user_tag}: {text[:80]}")

    # 解析命令（支持 /ChinaSemi 和 /ChinaSemi@botname）
    cmd_part = text.split()[0].lower()
    args = text[len(text.split()[0]):].strip() if ' ' in text else ''

    # 移除 bot username 后缀
    if '@' in cmd_part:
        cmd_part = cmd_part.split('@')[0]

    if cmd_part == '/start':
        send_telegram_msg(chat_id, build_welcome())

    elif cmd_part == '/help':
        send_telegram_msg(chat_id, build_help())

    elif cmd_part == '/chinasemi':
        handle_chinasemi(chat_id, args)

    else:
        # 未知命令或普通消息，仅在私聊中提示
        if chat_type == 'private':
            send_telegram_msg(chat_id, (
                f"📰 <b>中国半导体情报助手</b>\n\n"
                f"使用方法：\n"
                f"/ChinaSemi — 获取最新新闻摘要\n"
                f"/help — 查看更多指令"
            ))


def main():
    global last_update_id

    print("=" * 55)
    print("🤖 中国半导体 Telegram Bot")
    print(f"   启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Bot: @MemoryTon618_bot")
    print(f"   默认关键字: {', '.join(DEFAULT_KEYWORDS)}")
    print(f"   轮询间隔: {POLL_INTERVAL}s")
    print("=" * 55)
    print("\n按 Ctrl+C 停止\n")

    # 获取初始 offset（跳过旧消息）
    initial_updates = get_updates()
    if initial_updates:
        last_update_id = initial_updates[-1]['update_id'] + 1

    while True:
        try:
            updates = get_updates(offset=last_update_id)

            for update in updates:
                update_id = update.get('update_id', 0)
                if update_id >= last_update_id:
                    last_update_id = update_id + 1

                msg = update.get('message')
                if msg:
                    handle_message(msg)

            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print("\n\n👋 Bot 已停止")
            break
        except Exception as e:
            print(f"[Bot] 主循环异常: {e}")
            time.sleep(POLL_INTERVAL * 2)


if __name__ == "__main__":
    main()
