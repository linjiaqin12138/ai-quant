import dataclasses
import argparse
import traceback

from typing import List
from lib.modules.hot_news import news
from lib.adapter.notification import PushPlus, NotificationAbstract
from lib.logger import logger

class SilentPush(NotificationAbstract):
    def send(self, content: str, title: str = ''):
        logger.info(f"Skip Push notification {title} {content}")
        pass
@dataclasses.dataclass(frozen=True)
class JobOptions:
    platforms: List[str]
    no_push: bool

class JobContext:
    def __init__(self, options: JobOptions):
        self.platforms = options.platforms
        self.push = SilentPush() if options.no_push else PushPlus()

    def run(self):
        try:
            report = news.get_hot_news_summary_report(self.platforms)
            self.push.send(title='今日新闻', content=report)
        except Exception as err:
            logger.error(f"Unknown error: {err}")
            self.push.send(title="获取今日新闻失败", content=traceback.format_exc())

def parse_option() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument('--platforms', nargs='+', type=str, help='平台列表 baidu/huxiu/qq-news/toutiao/netease-news/zhihu/sina/sina-news/36kr')
    parser.add_argument('--no-push', action='store_true', help='不推送消息')

    args = parser.parse_args()
    if getattr(args, 'help', False):
        parser.print_help()
        exit(0)

    return args

if __name__ == '__main__':
    option = parse_option()
    JobContext(option).run()