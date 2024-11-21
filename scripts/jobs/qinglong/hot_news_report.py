import dataclasses
import argparse
import traceback
from typing import  Dict, List

from lib.adapter.notification import PushPlus, NotificationAbstract
from lib.adapter.gpt import get_agent_by_model
from lib.model.news import NewsInfo
from lib.modules.news_proxy import news_proxy
from lib.logger import logger
from lib.utils.list import map_by
from lib.utils.retry import with_retry
from lib.utils.news import render_news_in_markdown_group_by_platform

GPT_SYSTEM_PROMPT_FOR_SUMMARY = """
你是一位专业的金融分析师,擅长总结和分析来自不同新闻平台的市场和政策动态。请根据提供的新闻列表,总结出当前最值得关注的市场趋势和政策变化。
你的总结应该:
1. 聚焦于可能影响金融市场的重要事件和政策。
2. 分析这些事件和政策可能对不同行业或市场产生的影响。
3. 提供简洁明了的洞见,帮助投资者理解当前市场环境。
4. 如果发现多个新闻源报道了同一事件,请整合信息并提供更全面的分析。

请以下面的格式提供你的总结:

<h2>市场动态:</h2>
<ol>
  <li>[动态1]: [简要分析] <a href="[新闻链接]">[新闻标题]</a></li>
  <li>[动态2]: [简要分析] <a href="[新闻链接]">[新闻标题]</a></li>
  ...
</ol>

<h2>政策变化:</h2>
<ol>
  <li>[政策1]: [可能的影响] <a href="[新闻链接]">[新闻标题]</a></li>
  <li>[政策2]: [可能的影响] <a href="[新闻链接]">[新闻标题]</a></li>
  ...
</ol>

<h2>总体展望:</h2>
<p>[基于以上分析的市场整体展望]</p>
<p>[投资品的看涨看空]</p>

请确保你的回答简洁、客观, 并聚焦于最重要的信息, 区分和过滤掉那些跟市场、政策、投资机会无关的新闻, 比如民生、体育或娱乐新闻, 如果没有需要关注的信息, 直接说明即可。

输出格式: HTML
"""

class SilentPush(NotificationAbstract):
    def send(self, content: str, title: str = ''):
        logger.info(f"Skip Push notification {title} {content}")
        pass

class GptReplyErrror(Exception):
    pass 

@dataclasses.dataclass(frozen=True)
class JobOptions:
    platforms: List[str]
    models: List[str]
    no_push: bool

class JobContext:
    def __init__(self, options: JobOptions):
        self.platforms = options.platforms
        self.push = SilentPush() if options.no_push else PushPlus()
        self.news_fetcher = news_proxy
        self.agents = map_by(options.models, get_agent_by_model)
        self.curr_agents_index = 0

    def get_news_of_all_platform(self) -> Dict[str, List[NewsInfo]]:
        all_news = {}
        for platform in self.platforms:
            platform_news = self.news_fetcher.get_current_hot_news(platform)
            all_news.update({ platform: platform_news })
        return all_news

    @with_retry((GptReplyErrror), 3)
    def ask_ai(self, text: str) -> str:
        agent = self.agents[self.curr_agents_index]
        self.curr_agents_index = (self.curr_agents_index + 1) % len(self.agents)
        agent.clear()
        agent.set_system_prompt(GPT_SYSTEM_PROMPT_FOR_SUMMARY)
        gpt_reply = agent.ask(text)
        if gpt_reply.find('<') == -1:
            raise GptReplyErrror(gpt_reply)
        return gpt_reply

    def run(self):
        try:
            all_news = self.get_news_of_all_platform()
            news_text = render_news_in_markdown_group_by_platform(all_news)
            logger.info(news_text)
            gpt_report = self.ask_ai(news_text)
            self.push.send(title='今日新闻', content=gpt_report)
        except Exception as err:
            logger.error(f"Unknown error: {err}")
            self.push.send(title="获取今日新闻失败", content=traceback.format_exc())

def parse_option() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument('--platforms', nargs='+', type=str, help='平台列表 baidu/huxiu/qq-news/toutiao/netease-news/zhihu/sina/sina-news/36kr')
    parser.add_argument('--no-push', action='store_true', help='不推送消息')
    parser.add_argument('--models', nargs='+', type=str, help='尝试使用的大模型列表', default=['Baichuan3-Turbo-128k'])

    args = parser.parse_args()
    if getattr(args, 'help', False):
        parser.print_help()
        exit(0)

    return args

if __name__ == '__main__':
    option = parse_option()
    JobContext(option).run()