from typing import Dict, List
from textwrap import dedent
from ..model.news import NewsInfo
from .list import filter_by, group_by, map_by

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
    'eastmoney': '东方财富',
    'jin10': "金十数据",
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
        temp = ''
        if news.title and news.url:
            temp = f"### [{news.title}]({news.url})\n"
        elif news.title:
            temp = f"### {news.title}\n"
        if news.description:
            temp += f"{news.description}\n"
        return temp
    
    def platform_to_section(platform: str) -> str:
        if len(news_list_per_platform[platform]) > 0:
            news_with_title = filter_by(news_list_per_platform[platform], lambda n: n.title)
            news_without_title = filter_by(news_list_per_platform[platform], lambda n: not n.title)
            news_with_title = '\n'.join(map_by(news_with_title, news_to_section))
            news_without_title = '\n'.join(map_by(news_without_title, news_to_section))
            if news_without_title:
                news_without_title = f'### 其它新闻 \n{news_without_title}'
            return dedent(f"""
                ## {get_platform_display_name(platform)}
                {news_with_title}
                {news_without_title}
            """)
        return ''

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
        title_level = '###' if len(platforms) > 1 else '##'
        for hour in sorted_hours:
            hour_news = news_by_hour[hour]
            result.append(f"{title_level} {hour}\n")
            news_have_title = filter_by(hour_news, lambda x: x.title)
            news_have_no_title = filter_by(hour_news, lambda x: not x.title)
            # 添加该小时的所有新闻
            for news in news_have_title:
                title_line = f"{'####' if len(platforms) > 1 else '###'}"
                if news.url:
                    title_line += f" [{news.title}]({news.url})\n"
                else:
                    title_line += f" {news.title}\n"
                
                result.append(title_line)
                # 如果有描述，添加描述
                if news.description:
                    result.append(f"{news.description}\n")
                
                result.append("\n")
            # 添加没有标题的新闻
            if news_have_no_title:
                result.append(f"{title_level} 其它新闻\n")
                for news in news_have_no_title:
                    result.append(f"- {news.description}\n")
        result.append("\n")
    return "".join(result)
