from typing import Dict, List

from ..model.news import NewsInfo
from .list import group_by, map_by

platform_name_map = {
    'baidu': '百度',
    'huxiu': '虎嗅',
    'qq-news': '腾讯新闻',
    'toutiao': '今日头条',
    'netease-news': '网易新闻',
    'zhihu': '知乎',
    'sina': '新浪',
    'sina-news': '新浪新闻',
    '36kr': '36氪',
    'caixin': '财新数据',
    'cointime': 'Cointime',
    'eastmoney': '东方财富'
}

def get_platform_display_name(platform: str) -> str:
    return platform_name_map.get(platform, platform)

def render_news_list(news_list: List[NewsInfo]) -> str:
    """
    Mainly for debug use
    """
    def news_item_text(news: NewsInfo) -> str:
        res = f"[{news.timestamp.isoformat()}] [{news.title}] "
        if news.description:
            res += (news.description[:32] + '...') if len(news.description) > 35 else news.description
        
        return res

    news_in_text = map_by(news_list, news_item_text)
    return '\n'.join(news_in_text)

def render_news_in_markdown_group_by_platform(news_list_per_platform: Dict[str, List[NewsInfo]]) -> str:
    def news_to_section(news: NewsInfo) -> str:
        temp = f"### [{news.title}]({news.url})\n"
        if news.description:
            temp += f"{news.description}\n"
        return temp
    
    def platform_to_section(platform: str) -> str:
        return f"\n## {get_platform_display_name(platform)}\n" + '\n'.join(map_by(news_list_per_platform[platform], news_to_section))
    return "# 各大平台新闻\n" + '\n'.join(map_by(news_list_per_platform.keys(), platform_to_section))

def render_news_in_markdown_group_by_time_for_each_platform(news_list_per_platform: Dict[str, List[NewsInfo]]) -> str:
    def get_hour_key(news: NewsInfo) -> str:
        return news.timestamp.strftime("%Y-%m-%d %H:00")
    
    result = []
    platforms = list(news_list_per_platform.keys())
    
    # 如果有多个平台，添加一级标题
    if len(platforms) > 1:
        result.append("# 各平台每小时新闻\n")
    
    for platform in platforms:
        news_list = news_list_per_platform[platform]
        
        # 添加平台标题（多平台时为二级标题，单平台时为一级标题）
        platform_title = f"{'##' if len(platforms) > 1 else '#'} {get_platform_display_name(platform)}\n"
        result.append(platform_title)
        
        # 按小时分组新闻
        news_by_hour = group_by(news_list, get_hour_key)
        
        # 对时间进行排序（从小到大）
        sorted_hours = sorted(news_by_hour.keys(), reverse=False)
        
        for hour in sorted_hours:
            hour_news = news_by_hour[hour]
            result.append(f"{'###' if len(platforms) > 1 else '##'} {hour}\n")
            
            # 添加该小时的所有新闻
            for news in hour_news:
                title_line = f"{'####' if len(platforms) > 1 else '###'} [{news.title}]({news.url})\n"
                result.append(title_line)
                # 如果有描述，添加描述
                if news.description:
                    result.append(f"{news.description}\n")
                
                result.append("\n")
            
        result.append("\n")
    
    return "".join(result)
