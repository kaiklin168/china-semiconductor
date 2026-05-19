# -*- coding: utf-8 -*-
"""
Telegram 通知工具
用于发送各类通知到 Telegram
"""

import requests
from datetime import datetime

# ===== 配置 =====
BOT_TOKEN = "8275897123:AAGdznYEtoywrA0mJ-qcXQMJIy1Upa2D5Ec"

# 频道配置（好朋友投资资讯快报暂时静默）
CHAT_IDS_PERSONAL = "8696219136"      # 个人用户
CHAT_IDS_FRIENDS = "-1003858055115"   # 好朋友投资资讯快报（暂时静默）
CHAT_IDS = [CHAT_IDS_PERSONAL]        # 当前仅发送个人频道


def send_message(text, chat_id=None, parse_mode="HTML", disable_preview=True):
    """发送 Telegram 消息"""
    targets = [chat_id] if chat_id else CHAT_IDS
    results = []
    
    for cid in targets:
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": cid,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": disable_preview
                },
                timeout=30
            )
            if resp.json().get('ok'):
                results.append((cid, True, "发送成功"))
            else:
                results.append((cid, False, resp.json()))
        except Exception as e:
            results.append((cid, False, str(e)))
    
    return results


def send_market_summary(data):
    """发送市场总结"""
    lines = [
        f"📊 <b>A股半导体行情总结</b>",
        f"📅 {datetime.now().strftime('%Y/%m/%d %H:%M')}",
        f"",
    ]
    
    for item in data:
        code = item.get('code', '')
        name = item.get('name', '')
        price = item.get('price', 0)
        change = item.get('change', 0)
        
        arrow = "▲" if change > 0 else ("▼" if change < 0 else "─")
        color = "🔴" if change > 0 else ("🟢" if change < 0 else "⚪")
        
        lines.append(f"{color} <b>{name}({code})</b>")
        lines.append(f"   价格: {price} ({arrow}{abs(change):.2f}%)")
    
    lines.extend([
        f"",
        f"⚠️ 仅供参考，不构成投资建议",
    ])
    
    return send_message("\n".join(lines))


def send_news_alert(news_list, topic="半导体"):
    """发送新闻提醒"""
    lines = [
        f"📰 <b>{topic} 最新新闻</b>",
        f"📅 {datetime.now().strftime('%Y/%m/%d %H:%M')}",
        f"",
        f"━━━━━━━━━━━━━━━━━━━━━━",
    ]
    
    for i, news in enumerate(news_list[:5], 1):
        title = news.get('title', '')[:50]
        source = news.get('source', '')
        url = news.get('url', '')
        
        lines.append(f"\n{i}. {title}")
        lines.append(f"   来源: {source}")
    
    lines.extend([
        f"",
        f"━━━━━━━━━━━━━━━━━━━━━━",
        f"🤖 CodeBuddy",
    ])
    
    return send_message("\n".join(lines))


def send_alert(code, name, message, level="info"):
    """发送告警"""
    icons = {
        "info": "ℹ️",
        "warning": "⚠️",
        "error": "🔴",
        "success": "🟢",
    }
    icon = icons.get(level, "ℹ️")
    
    text = f"{icon} <b>告警通知</b>\n\n"
    text += f"股票: {name}({code})\n"
    text += f"内容: {message}\n"
    text += f"时间: {datetime.now().strftime('%Y/%m/%d %H:%M')}"
    
    return send_message(text)


if __name__ == "__main__":
    # 测试
    test_msg = f"🤖 <b>中国半导体分析系统测试</b>\n\n"
    test_msg += f"时间: {datetime.now().strftime('%Y/%m/%d %H:%M:%S')}\n"
    test_msg += f"状态: 运行正常 ✅"
    
    results = send_message(test_msg)
    for cid, success, msg in results:
        print(f"[{'✅' if success else '❌'}] {cid}: {msg}")
