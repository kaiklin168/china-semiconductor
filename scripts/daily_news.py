# -*- coding: utf-8 -*-
"""
每日新闻收集脚本
收集中国半导体相关新闻

使用方法:
  python scripts/daily_news.py                    # 收集默认关键字新闻
  python scripts/daily_news.py "半导体设备"        # 收集特定关键字新闻
"""

import sys, os
from datetime import datetime

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from news.news_collector_cn import main as news_main

# 默认关键字列表
DEFAULT_KEYWORDS = [
    ["半导体设备", "国产替代"],
    ["中芯国际", "晶圆代工"],
    ["AI芯片", "GPU"],
    ["半导体材料", "硅片"],
    ["光刻机", "EUV"],
]


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"\n{'='*60}")
    print(f"  中国半导体每日新闻收集")
    print(f"  日期: {today}")
    print(f"{'='*60}\n")
    
    # 从命令行参数获取关键字
    if len(sys.argv) > 1:
        keywords = [sys.argv[1:]]
    else:
        keywords = DEFAULT_KEYWORDS
    
    total = 0
    for kws in keywords:
        print(f"\n{'='*40}")
        print(f"📰 收集关键字: {', '.join(kws)}")
        print(f"{'='*40}")
        
        # 临时修改 argv
        original_argv = sys.argv
        sys.argv = [__file__] + kws
        
        try:
            news_main()
        except Exception as e:
            print(f"❌ 错误: {e}")
        
        sys.argv = original_argv
        total += 1
    
    print(f"\n{'='*60}")
    print(f"✅ 完成！共处理 {total} 组关键字")
    print("="*60)


if __name__ == "__main__":
    main()
