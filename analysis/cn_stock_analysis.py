# -*- coding: utf-8 -*-
"""
中国A股/港股半导体股票分析器
资料来源：Akshare + Yahoo Finance
支援A股（688/002/300开头）和港股（0开头）

使用方法:
  python cn_stock_analysis.py 688256          # 分析单支A股
  python cn_stock_analysis.py 688256 688981   # 分析多支A股
  python cn_stock_analysis.py --watchlist     # 分析关注列表所有股票
"""

import sys, io, os, re, json
from datetime import datetime
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import requests
import yfinance as yf
import pandas as pd
import numpy as np
import urllib3

urllib3.disable_warnings()
requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS = 'ALL:@SECLEVEL=1'

# ===== Telegram 配置 =====
BOT_TOKEN = "8275897123:AAGdznYEtoywrA0mJ-qcXQMJIy1Upa2D5Ec"
CHAT_IDS = ["8696219136", "-1003858055115"]

# ===== A股/港股半导体关注列表 =====
WATCHLIST = {
    # A股 - 科创板
    "688256": {"name": "寒武纪", "market": "CNSZ", "sector": "AI芯片"},
    "688981": {"name": "中芯国际", "market": "CNSZ", "sector": "晶圆代工"},
    "688012": {"name": "中微公司", "market": "CNSZ", "sector": "半导体设备"},
    "688396": {"name": "华润微", "market": "CNSZ", "sector": "IDM"},
    "688008": {"name": "澜起科技", "market": "CNSZ", "sector": "内存接口"},
    "688047": {"name": "龙芯中科", "market": "CNSZ", "sector": "CPU"},
    "688099": {"name": "晶晨股份", "market": "CNSZ", "sector": "多媒体芯片"},
    "688126": {"name": "沪硅产业", "market": "CNSZ", "sector": "硅片"},
    "688521": {"name": "芯原股份", "market": "CNSZ", "sector": "IP/设计服务"},
    "688369": {"name": "致远互联", "market": "CNSZ", "sector": "EDA"},
    "688223": {"name": "晶科能源", "market": "CNSZ", "sector": "光伏"},
    "688561": {"name": "奇安信", "market": "CNSZ", "sector": "网络安全"},
    "688111": {"name": "金山办公", "market": "CNSZ", "sector": "软件"},
    "688036": {"name": "传音控股", "market": "CNSZ", "sector": "手机"},
    "688072": {"name": "拓荆科技", "market": "CNSZ", "sector": "半导体设备"},
    "688082": {"name": "盛美上海", "market": "CNSZ", "sector": "半导体设备"},
    "688396": {"name": "华润微", "market": "CNSZ", "sector": "功率半导体"},
    
    # A股 - 主板
    "600745": {"name": "闻泰科技", "market": "SH", "sector": "ODM/半导体"},
    "603986": {"name": "兆易创新", "market": "SH", "sector": "MCU/NOR Flash"},
    "002230": {"name": "科大讯飞", "market": "SZ", "sector": "AI"},
    "002241": {"name": "歌尔股份", "market": "SZ", "sector": "消费电子"},
    "000725": {"name": "京东方A", "market": "SZ", "sector": "面板"},
    "002185": {"name": "华天科技", "market": "SZ", "sector": "封装测试"},
    "600584": {"name": "长电科技", "market": "SH", "sector": "封装测试"},
    "002049": {"name": "紫光国微", "market": "SZ", "sector": "IC设计"},
    "603160": {"name": "汇顶科技", "market": "SH", "sector": "IC设计"},
    "688799": {"name": "华纳德", "market": "CNSZ", "sector": "半导体设备"},
    
    # 港股
    "0981": {"name": "中芯国际-H", "market": "HK", "sector": "晶圆代工"},
    "1347": {"name": "华虹半导体", "market": "HK", "sector": "晶圆代工"},
    "0968": {"name": "信越光能", "market": "HK", "sector": "光伏"},
    "0023": {"name": "ASM太平洋", "market": "HK", "sector": "封装设备"},
    "0522": {"name": "ASMPT", "market": "HK", "sector": "封装设备"},
    "0988": {"name": "海尔智家-H", "market": "HK", "sector": "消费"},
}


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def get_akshare_quote(stock_code):
    """使用 Akshare 获取A股实时行情"""
    try:
        import akshare as ak
        
        # 判断市场
        if stock_code.startswith("6"):
            symbol = f"sh{stock_code}"
        else:
            symbol = f"sz{stock_code}"
        
        df = ak.stock_zh_a_spot_em()
        row = df[df['代码'] == stock_code]
        
        if not row.empty:
            return {
                'code': stock_code,
                'name': row.iloc[0]['名称'],
                'price': float(row.iloc[0]['最新价']),
                'change': float(row.iloc[0]['涨跌幅']),
                'volume': float(row.iloc[0]['成交量']),
                'amount': float(row.iloc[0]['成交额']),
                'high': float(row.iloc[0]['最高']),
                'low': float(row.iloc[0]['最低']),
                'open': float(row.iloc[0]['今开']),
                'prev_close': float(row.iloc[0]['昨收']),
            }
    except Exception as e:
        log(f"[Akshare] ✗ {e}")
    return None


def get_yf_quote(symbol):
    """使用 Yahoo Finance 获取行情"""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        return {
            'price': info.get('currentPrice') or info.get('regularMarketPrice'),
            'change': info.get('regularMarketChangePercent', 0),
            'volume': info.get('regularMarketVolume'),
            'high': info.get('dayHigh'),
            'low': info.get('dayLow'),
            'open': info.get('regularMarketOpen'),
            'prev_close': info.get('previousClose'),
            'market_cap': info.get('marketCap'),
        }
    except Exception as e:
        log(f"[Yahoo Finance] ✗ {e}")
    return None


def get_cn_stock_history(stock_code, period='3mo'):
    """获取A股历史数据"""
    try:
        # 尝试多种格式
        symbols = []
        if stock_code.startswith("688"):
            symbols = [f"{stock_code}.SS"]  # 科创板
        elif stock_code.startswith("6"):
            symbols = [f"{stock_code}.SS"]  # 上证
        elif stock_code.startswith(("000", "002", "003", "300")):
            symbols = [f"{stock_code}.SZ"]  # 深证
        elif stock_code.isdigit() and len(stock_code) == 4:
            symbols = [f"{stock_code}.HK"]  # 港股
        
        for sym in symbols:
            try:
                ticker = yf.Ticker(sym)
                df = ticker.history(period=period)
                if len(df) > 10:
                    return df, sym
            except:
                continue
    except Exception as e:
        log(f"[历史数据] ✗ {e}")
    return None, None


def calculate_tech_indicators(df):
    """计算技术指标"""
    close = df['Close']
    results = {}
    
    # 均线
    for period in [5, 10, 20, 60]:
        if len(close) >= period:
            ma = close.rolling(period).mean().iloc[-1]
            results[f'MA{period}'] = ma
    
    # RSI
    if len(close) >= 14:
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta).where(delta < 0, 0).rolling(14).mean()
        rs = gain / loss
        results['RSI14'] = (100 - 100 / (1 + rs)).iloc[-1]
    
    # MACD
    if len(close) >= 26:
        ema12 = close.ewm(span=12).mean()
        ema26 = close.ewm(span=26).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9).mean()
        results['MACD_DIF'] = macd.iloc[-1]
        results['MACD_SIGNAL'] = signal.iloc[-1]
        results['MACD_HIST'] = macd.iloc[-1] - signal.iloc[-1]
    
    # 布林带
    if len(close) >= 20:
        bb = close.rolling(20).mean()
        bb_std = close.rolling(20).std()
        results['BB_Upper'] = bb.iloc[-1] + 2 * bb_std.iloc[-1]
        results['BB_Mid'] = bb.iloc[-1]
        results['BB_Lower'] = bb.iloc[-1] - 2 * bb_std.iloc[-1]
    
    # 量价分析
    if 'Volume' in df.columns and len(df) >= 5:
        vol = df['Volume']
        results['Vol_MA5'] = vol.rolling(5).mean().iloc[-1]
        results['Vol_Ratio'] = vol.iloc[-1] / results['Vol_MA5'] if results['Vol_MA5'] > 0 else 1
        results['Price_Momentum'] = ((close.iloc[-1] - close.iloc[-5]) / close.iloc[-5] * 100)
        results['Support'] = df['Low'].rolling(5).min().iloc[-1]
        results['Resistance'] = df['High'].rolling(5).max().iloc[-1]
    
    return results


def interpret_tech(tech):
    """解读技术指标"""
    tips = []
    
    # 均线系统
    ma5 = tech.get('MA5')
    ma20 = tech.get('MA20')
    ma60 = tech.get('MA60')
    price = close_price = None
    
    if 'Volume' in tech:
        try:
            price = tech.get('MA5', 0) or 0
        except:
            pass
    
    if ma5 and ma20 and ma60:
        if ma5 > ma20 > ma60:
            tips.append("📈 均线多头排列（短>中>长），趋势偏强")
        elif ma5 < ma20 < ma60:
            tips.append("📉 均线空头排列（短<中<长），趋势偏弱")
        else:
            tips.append("➡️ 均线纠结，方向不明")
    
    # RSI
    rsi = tech.get('RSI14')
    if rsi is not None:
        try:
            rv = float(rsi)
            if rv > 80:
                tips.append(f"🔴 RSI {rv:.1f} 严重超买，获利了结压力大")
            elif rv > 70:
                tips.append(f"🟠 RSI {rv:.1f} 偏超买，注意短线回档")
            elif rv < 30:
                tips.append(f"🔵 RSI {rv:.1f} 偏超卖，观察止稳信号")
            elif rv < 20:
                tips.append(f"🟢 RSI {rv:.1f} 严重超卖，抢反弹窗口")
        except:
            pass
    
    # MACD
    dif = tech.get('MACD_DIF')
    sig = tech.get('MACD_SIGNAL')
    hist = tech.get('MACD_HIST')
    if dif is not None and sig is not None and hist is not None:
        try:
            dv, sv, hv = float(dif), float(sig), float(hist)
            if hv > 0 and dv > sv:
                tips.append("🟢 MACD 柱状体为正且 DIF>SIGNAL，多方动能增强")
            elif hv < 0 and dv < sv:
                tips.append("🔴 MACD 柱状体负值扩大，空方动能持续")
            if dv > 0:
                tips.append("✅ MACD 在零轴上方，中期偏多")
            else:
                tips.append("❌ MACD 在零轴下方，中期偏空")
        except:
            pass
    
    # 量价
    vr = tech.get('Vol_Ratio')
    pm = tech.get('Price_Momentum')
    if vr is not None:
        try:
            vrf = float(vr)
            pmt = float(pm) if pm else 0
            if vrf > 2 and pmt > 3:
                tips.append(f"🚀 放量大涨（量比{vrf:.1f}x +{pmt:.1f}%），强势信号")
            elif vrf > 2 and pmt < -3:
                tips.append(f"💥 放量大跌（量比{vrf:.1f}x {pmt:.1f}%），恐慌性杀出")
            elif vrf < 0.5:
                tips.append("😴 缩量，观望情绪浓厚")
        except:
            pass
    
    return tips


def get_financial_data(stock_code):
    """获取财务数据（A股）"""
    try:
        import akshare as ak
        # 尝试获取季报
        df = ak.stock_financial_analysis_indicator(symbol=stock_code, start_year="2024")
        if df is not None and len(df) > 0:
            return df.head(4)
    except Exception as e:
        log(f"[财务数据] ✗ {e}")
    return None


def analyze_stock(stock_code, name=None):
    """完整分析单支股票"""
    profile = WATCHLIST.get(stock_code, {})
    display_name = name or profile.get('name') or stock_code
    sector = profile.get('sector', 'N/A')
    
    print(f"\n{'='*60}")
    print(f"  {display_name} ({stock_code}) 基本分析")
    print(f"  细分领域: {sector}")
    print(f"{'='*60}")
    print(f"分析时间: {datetime.now().strftime('%Y/%m/%d %H:%M')}\n")
    
    # ===== 1. 实时行情 =====
    print("【1. 实时行情】")
    quote = get_akshare_quote(stock_code)
    if quote:
        change_pct = quote.get('change', 0)
        arrow = "▲" if change_pct > 0 else ("▼" if change_pct < 0 else "─")
        color = "🔴" if change_pct > 0 else ("🟢" if change_pct < 0 else "⚪")
        print(f"  {color} 最新价: {quote.get('price', 'N/A')} ({arrow}{abs(change_pct):.2f}%)")
        print(f"  今开: {quote.get('open', 'N/A')} | 最高: {quote.get('high', 'N/A')} | 最低: {quote.get('low', 'N/A')}")
        print(f"  成交量: {quote.get('volume', 'N/A'):,}手 | 成交额: {quote.get('amount', 'N/A'):,.0f}元")
    else:
        # 尝试 Yahoo Finance
        if stock_code.isdigit() and len(stock_code) == 4:
            sym = f"{stock_code}.HK"
        else:
            sym = f"{stock_code}"
        yf_quote = get_yf_quote(sym)
        if yf_quote:
            price = yf_quote.get('price', 'N/A')
            change = yf_quote.get('change', 0)
            arrow = "▲" if change > 0 else ("▼" if change < 0 else "─")
            print(f"  价格: {price} ({arrow}{abs(change):.2f}%)")
        else:
            print("  (暂时无法获取行情数据)")
    
    # ===== 2. 历史走势 =====
    print(f"\n【2. 技术分析（近3个月）】")
    df, symbol = get_cn_stock_history(stock_code, '3mo')
    if df is not None and len(df) > 0:
        tech = calculate_tech_indicators(df)
        
        price = df['Close'].iloc[-1]
        date = df.index[-1].strftime('%Y/%m/%d')
        print(f"  最新收盘: {price:.2f} ({date})")
        print(f"  MA5: {tech.get('MA5', 'N/A'):.2f} | MA20: {tech.get('MA20', 'N/A'):.2f} | MA60: {tech.get('MA60', 'N/A'):.2f}")
        
        if 'RSI14' in tech:
            print(f"  RSI(14): {tech['RSI14']:.1f}")
        if 'MACD_DIF' in tech:
            print(f"  MACD: DIF={tech['MACD_DIF']:.2f} SIGNAL={tech['MACD_SIGNAL']:.2f} HIST={tech['MACD_HIST']:.2f}")
        if 'Vol_Ratio' in tech:
            print(f"  量比: {tech['Vol_Ratio']:.2f}x")
        
        # 技术指标解读
        tips = interpret_tech(tech)
        if tips:
            print(f"\n  📊 【技术解读】")
            for t in tips[:5]:
                print(f"    {t}")
    else:
        print("  (暂时无法获取历史数据)")
    
    # ===== 3. 基本面信息 =====
    print(f"\n【3. 基本面信息】")
    if profile:
        print(f"  细分领域: {sector}")
        print(f"  市场: {'科创板' if stock_code.startswith('688') else ('上证' if stock_code.startswith('6') else '深证')}")
    
    # 获取 Yahoo Finance 基本面
    if stock_code.isdigit() and len(stock_code) == 4:
        sym = f"{stock_code}.HK"
    else:
        sym = stock_code
    try:
        ticker = yf.Ticker(sym)
        info = ticker.info
        if info:
            pe = info.get('trailingPE', 'N/A')
            pb = info.get('priceToBook', 'N/A')
            market_cap = info.get('marketCap', 0)
            if market_cap:
                if market_cap > 1e12:
                    mc_str = f"{market_cap/1e12:.2f}万亿"
                else:
                    mc_str = f"{market_cap/1e8:.0f}亿"
            else:
                mc_str = 'N/A'
            print(f"  市盈率(PE): {pe:.2f}" if isinstance(pe, (int, float)) else f"  市盈率(PE): {pe}")
            print(f"  市净率(PB): {pb:.2f}" if isinstance(pb, (int, float)) else f"  市净率(PB): {pb}")
            print(f"  总市值: {mc_str}")
    except Exception as e:
        log(f"[Yahoo] ✗ {e}")
    
    print(f"\n{'='*60}")
    print("[!] 本分析仅供参考，不构成投资建议")
    print("="*60)
    
    return True


def send_to_telegram(stock_code, name=None):
    """发送分析报告到 Telegram"""
    profile = WATCHLIST.get(stock_code, {})
    display_name = name or profile.get('name') or stock_code
    sector = profile.get('sector', 'N/A')
    
    # 获取行情
    quote = get_akshare_quote(stock_code)
    df, symbol = get_cn_stock_history(stock_code, '3mo')
    tech = calculate_tech_indicators(df) if df is not None else {}
    tips = interpret_tech(tech) if tech else []
    
    # 构建消息
    msg = f"📊 <b>{display_name} ({stock_code})</b>\n"
    msg += f"🏷️ 细分领域: {sector}\n"
    msg += f"📅 {datetime.now().strftime('%Y/%m/%d %H:%M')}\n\n"
    
    if quote:
        price = quote.get('price', 'N/A')
        change = quote.get('change', 0)
        arrow = "▲" if change > 0 else ("▼" if change < 0 else "─")
        color = "🔴" if change > 0 else ("🟢" if change < 0 else "⚪")
        msg += f"{color} <b>最新价: {price}</b> ({arrow}{abs(change):.2f}%)\n"
        msg += f"今开: {quote.get('open', '-')} | 最高: {quote.get('high', '-')} | 最低: {quote.get('low', '-')}\n"
    else:
        msg += "(暂时无法获取行情)\n"
    
    if tech:
        price_val = df['Close'].iloc[-1] if df is not None else 0
        msg += f"\n📈 <b>技术指标</b>\n"
        msg += f"收盘: {price_val:.2f}\n"
        msg += f"MA5: {tech.get('MA5', 0):.2f} | MA20: {tech.get('MA20', 0):.2f}\n"
        if 'RSI14' in tech:
            msg += f"RSI: {tech['RSI14']:.1f}\n"
        if 'Vol_Ratio' in tech:
            msg += f"量比: {tech['Vol_Ratio']:.2f}x\n"
    
    if tips:
        msg += f"\n📊 <b>技术解读</b>\n"
        for t in tips[:4]:
            msg += f"• {t}\n"
    
    msg += f"\n⚠️ 仅供参考，不构成投资建议"
    
    # 发送到 Telegram
    for chat_id in CHAT_IDS:
        try:
            resp = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                "chat_id": chat_id, "text": msg, "parse_mode": "HTML",
                "disable_web_page_preview": True
            }, timeout=30)
            if resp.json().get('ok'):
                log(f"[Telegram] ✅ {display_name} → {chat_id}")
            else:
                log(f"[Telegram] ❌ {resp.json()}")
        except Exception as e:
            log(f"[Telegram] ❌ {e}")


def save_report(stock_code, name=None):
    """保存分析报告到文件"""
    profile = WATCHLIST.get(stock_code, {})
    display_name = name or profile.get('name') or stock_code
    
    report_file = f"data/reports/{stock_code}_{datetime.now().strftime('%Y%m%d')}.md"
    os.makedirs(os.path.dirname(report_file), exist_ok=True)
    
    # 构建报告内容
    quote = get_akshare_quote(stock_code)
    df, symbol = get_cn_stock_history(stock_code, '3mo')
    tech = calculate_tech_indicators(df) if df is not None else {}
    tips = interpret_tech(tech) if tech else []
    
    content = f"# {display_name} ({stock_code}) 分析报告\n"
    content += f"日期: {datetime.now().strftime('%Y/%m/%d %H:%M')}\n\n"
    
    if quote:
        content += f"## 行情\n"
        content += f"- 最新价: {quote.get('price', 'N/A')} (涨跌幅: {quote.get('change', 0):.2f}%)\n"
        content += f"- 今开: {quote.get('open', '-')} | 最高: {quote.get('high', '-')} | 最低: {quote.get('low', '-')}\n\n"
    
    if tech:
        content += f"## 技术指标\n"
        content += f"- MA5: {tech.get('MA5', 0):.2f}\n"
        content += f"- MA20: {tech.get('MA20', 0):.2f}\n"
        content += f"- MA60: {tech.get('MA60', 0):.2f}\n"
        if 'RSI14' in tech:
            content += f"- RSI(14): {tech['RSI14']:.1f}\n"
        if 'MACD_DIF' in tech:
            content += f"- MACD: DIF={tech['MACD_DIF']:.2f} SIGNAL={tech['MACD_SIGNAL']:.2f}\n"
        content += "\n## 技术解读\n"
        for t in tips:
            content += f"- {t}\n"
    
    content += "\n---\n⚠️ 仅供参考，不构成投资建议\n"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    log(f"[报告] 已保存: {report_file}")
    return report_file


def main():
    # 检查参数
    if len(sys.argv) < 2:
        print("用法:")
        print("  python cn_stock_analysis.py 688256          # 分析单支A股")
        print("  python cn_stock_analysis.py 688256 688981 # 分析多支A股")
        print("  python cn_stock_analysis.py --watchlist    # 分析关注列表所有股票")
        sys.exit(1)
    
    stocks = []
    
    if "--watchlist" in sys.argv:
        stocks = list(WATCHLIST.keys())
    else:
        stocks = [s for s in sys.argv[1:] if not s.startswith("--")]
    
    # 是否发送 Telegram
    send_tg = "--telegram" in sys.argv
    
    print(f"\n{'='*60}")
    print(f"  中国半导体股票分析器")
    print(f"  待分析股票: {', '.join(stocks)}")
    print(f"{'='*60}\n")
    
    for stock in stocks:
        profile = WATCHLIST.get(stock, {})
        name = profile.get('name')
        
        analyze_stock(stock, name)
        
        # 保存报告
        save_report(stock, name)
        
        # 发送 Telegram
        if send_tg:
            send_to_telegram(stock, name)
        
        time.sleep(1)
    
    print(f"\n{'='*60}")
    print(f"✅ 分析完成！已处理 {len(stocks)} 支股票")
    print("="*60)


if __name__ == "__main__":
    main()
