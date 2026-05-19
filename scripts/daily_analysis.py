# -*- coding: utf-8 -*-
"""
每日股票分析脚本
分析关注列表中的中国半导体股票

使用方法:
  python scripts/daily_analysis.py                 # 分析所有关注股票
  python scripts/daily_analysis.py 688256 688981  # 分析指定股票
"""

import sys, os
from datetime import datetime

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.cn_stock_analysis import WATCHLIST, analyze_stock, save_report, send_to_telegram


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"\n{'='*60}")
    print(f"  中国半导体每日股票分析")
    print(f"  日期: {today}")
    print(f"{'='*60}\n")
    
    # 从命令行参数获取股票代码
    if len(sys.argv) > 1:
        stocks = sys.argv[1:]
    else:
        stocks = list(WATCHLIST.keys())
    
    print(f"待分析股票数: {len(stocks)}\n")
    
    results = []
    for i, stock in enumerate(stocks, 1):
        profile = WATCHLIST.get(stock, {})
        name = profile.get('name', stock)
        
        print(f"[{i}/{len(stocks)}] 分析 {name}({stock})...")
        
        try:
            analyze_stock(stock, name)
            report_file = save_report(stock, name)
            
            # 发送 Telegram
            send_to_telegram(stock, name)
            
            results.append((stock, name, True, report_file))
            print(f"✅ {name} 分析完成")
        except Exception as e:
            print(f"❌ {name} 分析失败: {e}")
            results.append((stock, name, False, str(e)))
        
        print()
    
    # 总结
    success = sum(1 for r in results if r[2])
    failed = sum(1 for r in results if not r[2])
    
    print(f"\n{'='*60}")
    print(f"📊 分析总结")
    print(f"{'='*60}")
    print(f"总计: {len(results)} 支股票")
    print(f"成功: {success}")
    print(f"失败: {failed}")
    
    if failed > 0:
        print(f"\n失败列表:")
        for stock, name, ok, msg in results:
            if not ok:
                print(f"  - {name}({stock}): {msg}")
    
    print("="*60)


if __name__ == "__main__":
    main()
