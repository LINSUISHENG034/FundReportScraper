#!/usr/bin/env python3
"""
平安基金全量数据解析脚本
Complete PingAn Fund data parser from HTML
"""

import sys
import re
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from bs4 import BeautifulSoup

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def parse_pingan_funds_html():
    """解析平安基金HTML数据"""
    
    html_file = Path("data/pingan/平安基金.md")
    
    if not html_file.exists():
        print(f"❌ HTML文件不存在: {html_file}")
        return []
    
    print(f"📂 读取HTML文件: {html_file}")
    
    # 读取HTML内容
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # 移除markdown代码块标记
    html_content = html_content.replace('```', '')
    
    print(f"📄 HTML文件大小: {len(html_content)/1024:.1f} KB")
    
    # 使用BeautifulSoup解析HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 查找所有基金行
    fund_rows = soup.find_all('tr')
    print(f"🔍 找到 {len(fund_rows)} 行数据")
    
    funds_data = []
    
    for row in fund_rows:
        try:
            # 查找基金名称和代码
            fund_name_cell = row.find('td', class_='fund-name')
            if not fund_name_cell:
                continue
            
            # 提取基金名称和代码
            fund_link = fund_name_cell.find('a')
            if not fund_link:
                continue
            
            # 基金名称在<br>标签前
            fund_name_text = fund_link.get_text()
            if '<br>' in str(fund_link):
                # 分离基金名称（去掉<br>后的内容）
                fund_name = fund_name_text.split('\n')[0].strip() if '\n' in fund_name_text else fund_name_text.strip()
            else:
                fund_name = fund_name_text.strip()
            
            # 基金代码在<span>标签内
            code_span = fund_link.find('span')
            if not code_span:
                continue
            
            fund_code = code_span.get_text(strip=True)
            
            # 验证基金代码格式（6位数字）
            if not re.match(r'^\d{6}$', fund_code):
                continue
            
            # 查找所有td元素来提取其他数据
            cells = row.find_all('td')
            if len(cells) < 6:
                continue
            
            # 提取基金净值
            fund_value_span = cells[1].find('span', class_='fund-value')
            unit_nav = None
            nav_date = None
            
            if fund_value_span:
                unit_nav_text = fund_value_span.get_text(strip=True)
                try:
                    unit_nav = float(unit_nav_text)
                except:
                    unit_nav = None
                
                # 提取净值日期
                date_span = cells[1].find('span', title='净值日期')
                if date_span:
                    nav_date = date_span.get_text(strip=True)
            
            # 提取累计净值
            cumulative_nav = None
            if len(cells) > 2:
                cumulative_nav_text = cells[2].get_text(strip=True)
                try:
                    cumulative_nav = float(cumulative_nav_text)
                except:
                    cumulative_nav = None
            
            # 提取日涨跌幅
            daily_change = None
            if len(cells) > 3:
                daily_change_text = cells[3].get_text(strip=True)
                if daily_change_text and daily_change_text != '--':
                    try:
                        daily_change = float(daily_change_text.replace('%', '')) / 100
                    except:
                        daily_change = None
            
            # 提取近一月收益率
            one_month_return = None
            if len(cells) > 4:
                one_month_text = cells[4].get_text(strip=True)
                if one_month_text and one_month_text != '--':
                    try:
                        one_month_return = float(one_month_text.replace('%', '')) / 100
                    except:
                        one_month_return = None
            
            # 提取近一年收益率
            one_year_return = None
            if len(cells) > 5:
                one_year_text = cells[5].get_text(strip=True)
                if one_year_text and one_year_text != '--':
                    try:
                        one_year_return = float(one_year_text.replace('%', '')) / 100
                    except:
                        one_year_return = None
            
            # 提取成立以来收益率
            since_inception_return = None
            if len(cells) > 6:
                inception_text = cells[6].get_text(strip=True)
                if inception_text and inception_text != '--':
                    try:
                        since_inception_return = float(inception_text.replace('%', '')) / 100
                    except:
                        since_inception_return = None
            
            # 判断基金类型（基于基金名称）
            fund_type = determine_fund_type(fund_name)
            
            # 构建基金数据
            fund_data = {
                "fund_code": fund_code,
                "fund_name": fund_name,
                "fund_company": "平安基金管理有限公司",
                "fund_type": fund_type,
                "unit_nav": unit_nav,
                "cumulative_nav": cumulative_nav,
                "nav_date": nav_date,
                "daily_change": daily_change,
                "one_month_return": one_month_return,
                "one_year_return": one_year_return,
                "since_inception_return": since_inception_return,
                "data_collection_time": datetime.now().isoformat(),
                "report_date": "2025-07-11"  # 基于HTML中的净值日期
            }
            
            funds_data.append(fund_data)
            
        except Exception as e:
            # 跳过解析失败的行
            continue
    
    print(f"✅ 成功解析 {len(funds_data)} 只基金")
    return funds_data


def determine_fund_type(fund_name: str) -> str:
    """根据基金名称判断基金类型"""
    
    if any(keyword in fund_name for keyword in ["股票", "行业", "主题", "精选", "成长", "价值"]):
        return "股票型"
    elif any(keyword in fund_name for keyword in ["混合", "配置", "策略", "均衡", "稳健", "灵活"]):
        return "混合型"
    elif any(keyword in fund_name for keyword in ["债券", "纯债", "金融债", "信用债", "可转债"]):
        return "债券型"
    elif any(keyword in fund_name for keyword in ["指数", "ETF", "300", "500", "创业板", "科创"]):
        return "指数型"
    elif any(keyword in fund_name for keyword in ["货币", "现金", "日增利", "天天"]):
        return "货币型"
    elif any(keyword in fund_name for keyword in ["QDII", "海外", "全球", "美国", "港股"]):
        return "QDII"
    elif any(keyword in fund_name for keyword in ["FOF", "基金中的基金"]):
        return "FOF"
    elif any(keyword in fund_name for keyword in ["REITs", "不动产", "房地产"]):
        return "REITs"
    else:
        # 默认分类逻辑
        if "债" in fund_name:
            return "债券型"
        elif any(keyword in fund_name for keyword in ["平衡", "收益", "增长"]):
            return "混合型"
        else:
            return "其他"


def analyze_fund_distribution(funds_data: List[Dict]):
    """分析基金分布情况"""
    
    print(f"\n📊 平安基金产品分析")
    print("=" * 60)
    
    # 基金类型分布
    type_stats = {}
    total_funds = len(funds_data)
    
    for fund in funds_data:
        fund_type = fund['fund_type']
        type_stats[fund_type] = type_stats.get(fund_type, 0) + 1
    
    print(f"📈 基金类型分布 (总计 {total_funds} 只):")
    for fund_type, count in sorted(type_stats.items(), key=lambda x: x[1], reverse=True):
        percentage = count / total_funds * 100
        print(f"  • {fund_type}: {count} 只 ({percentage:.1f}%)")
    
    # 净值分布分析
    valid_navs = [fund['unit_nav'] for fund in funds_data if fund['unit_nav'] is not None]
    if valid_navs:
        avg_nav = sum(valid_navs) / len(valid_navs)
        max_nav = max(valid_navs)
        min_nav = min(valid_navs)
        print(f"\n💰 基金净值分析:")
        print(f"  • 平均单位净值: {avg_nav:.4f}")
        print(f"  • 最高单位净值: {max_nav:.4f}")
        print(f"  • 最低单位净值: {min_nav:.4f}")
    
    # 收益率分析
    valid_returns = [fund['since_inception_return'] for fund in funds_data 
                    if fund['since_inception_return'] is not None]
    if valid_returns:
        avg_return = sum(valid_returns) / len(valid_returns) * 100
        max_return = max(valid_returns) * 100
        min_return = min(valid_returns) * 100
        print(f"\n📈 成立以来收益率分析:")
        print(f"  • 平均收益率: {avg_return:.2f}%")
        print(f"  • 最高收益率: {max_return:.2f}%")
        print(f"  • 最低收益率: {min_return:.2f}%")
    
    # 找出表现最好的基金
    best_performers = sorted(
        [fund for fund in funds_data if fund['since_inception_return'] is not None],
        key=lambda x: x['since_inception_return'],
        reverse=True
    )[:5]
    
    if best_performers:
        print(f"\n🏆 成立以来收益率前5名:")
        for i, fund in enumerate(best_performers, 1):
            return_rate = fund['since_inception_return'] * 100
            print(f"  {i}. {fund['fund_name']} ({fund['fund_code']})")
            print(f"     收益率: {return_rate:.2f}% | 单位净值: {fund['unit_nav']:.4f}")


def save_complete_fund_data(funds_data: List[Dict]):
    """保存完整的基金数据"""
    
    # 创建目录
    data_dir = Path("data/analysis/pingan_2025")
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存数据
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    data_file = data_dir / f"pingan_funds_complete_2025_{timestamp}.json"
    
    with open(data_file, 'w', encoding='utf-8') as f:
        json.dump(funds_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 数据已保存至: {data_file}")
    print(f"📊 文件大小: {data_file.stat().st_size / 1024:.1f} KB")
    
    return data_file


def main():
    """主函数"""
    print("🎯 平安基金全量数据解析")
    print("=" * 70)
    
    try:
        # 解析HTML数据
        funds_data = parse_pingan_funds_html()
        
        if not funds_data:
            print("❌ 没有解析到基金数据")
            return False
        
        # 分析基金分布
        analyze_fund_distribution(funds_data)
        
        # 保存数据
        data_file = save_complete_fund_data(funds_data)
        
        print(f"\n🎉 解析完成！")
        print(f"📊 总计解析: {len(funds_data)} 只基金")
        print(f"📁 数据文件: {data_file}")
        
        return True
        
    except Exception as e:
        print(f"❌ 解析失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)