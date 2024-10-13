import abc
import json
import traceback
from dataclasses import dataclass
from typing import Dict, List, TypedDict, Optional

from ..model import NewsInfo
from ..logger import logger
from ..utils.string import extract_json_string
from ..utils.object import remove_none
from ..utils.list import filter_by
from ..adapter.news import news, NewsAbstract, HotNewsPlatform, ALL_SUPPORTED_PLATFORMS
from ..adapter.database.news_cache import HotNewsCache, HotNewsCacheAbstract
from ..adapter.database.session import SessionAbstract ,SqlAlchemySession
from ..adapter.gpt import GptAgentAbstract, G4fAgent, BaiChuanAgent

GPT_SYSTEM_PROMPT_FOR_BASIC_FILTERING = """
我希望你充当一个可以筛选出可能影响股票市场或某一特定板块的热门新闻标题的Agent。在你的分析中，你需要关注那些具有显著经济影响力的政治新闻.
例如: 一个国家开始大规模战争的报告可能导致股市产生恐慌情绪。此外，你还需要注意政策类的新闻，例如政府针对某一行业出台的监管政策，可能会直接影响到该行业的股市表现。然而，你应该筛选掉与股市或投资机会无关的新闻，比如娱乐新闻、体育新闻、无关紧要的民生新闻、领导人的例行讲话、新闻标题模糊的新闻等。
我会以JSON形式提供数据，例如：
```json
{
    "platform": "sina",
    "start_from": 0,
    "news": [
        {
            "id": "abcd...",
            "title": "欧盟对华电车征税提议通过",
            "description": "法新社援引来自欧洲外交官的最新消息称，欧盟当地时间10月4日表决通过对华电动汽车加征关税案。欧洲多个国家政要、业界代表等此前已对欧委会有关调查表达了反对意见，中方也斥责欧盟欲对中国电动汽车加征关税的举动是典型的保护主义..."
        },
        {
            "id": "qwewqe...",
            "title": "一家人患病查出血液中老鼠药成分高"
        }
        ...
    ]
}
```
其中，news数组排在前面的新闻，相对排在数组后面的新闻，会具有更高的热度
此外，我一次只会给你发送不超过10条新闻，start_from代表有多少条热度更高的新闻排在前面并已经经过分析。所以start_from参数越大，代表在当下热度排名上越靠后。
在判断是否应该过滤出来以及给出mood数值可以通过start_from参数以及新闻在news数组中的相对位置作为参考。
你需要以一个特定的JSON形式来回应，例如：
```json
{
    "result": [
        {
            "id": "abcd...",
            "reason": "欧盟对华电车征税提议有可能导致国产新能源汽车海外销售，进而影响相关公司股价",
            "mood": -0.3
        }
     ]
}
```
在你的回应中，"id"应与所分析的新闻条目的"id"完全一致，"reason"应概括你的分析结果，而"mood"则应反映该新闻对投资者情绪的影响，范围在-1（最负面）到1（最积极)，0表示态度中立需要进一步观察。
注意：
1. 任何解释性的内容都必须一律排除在你回应的JSON之外。
2. 过滤结果尽可能准确，如果没有有价值的新闻，请直接输出一个空结果: { "result": [] }，而不是从这些新闻中挑出一两个相对有价值的。
"""

GPT_SYSTEM_PROMPT_FOR_FURTHER_FILTERING = """
我希望你充当一个专业的投资舆情分析师，将各大新闻平台的经济局势或特定股票板块相关的新闻标题和描述进行集中管理和智能分析。你需要从这些信息中寻找对股票市场有可能产生影响的情报，并且聚合这些从多个平台得到的相同新闻，确保只传递最准确、最及时的信息。同时，你需要可以区分和过滤掉那些跟股市或其他投资机会无关的新闻，比如民生、体育或娱乐新闻。
你的每一条推荐新闻，都应该附带一小段解释，解释为什么这条新闻对股市或特定股票板块可能产生影响。因此，你应该具备良好的新闻聚合能力，和投资相关新闻的深度解析能力。
我会以JSON形式提供数据，例如：
```json
{
    "news": [
        {
            "id": "abcd...",
            "platform": "sina"
            "title": "欧盟对华电车征税提议通过",
            "description": "法新社援引来自欧洲外交官的最新消息称，欧盟当地时间10月4日表决通过对华电动汽车加征关税案。欧洲多个国家政要、业界代表等此前已对欧委会有关调查表达了反对意见，中方也斥责欧盟欲对中国电动汽车加征关税的举动是典型的保护主义..."
        },
        {
            "id": "cdef...",
            "platform": "qq-news"
            "title": "当地时间4日，欧盟就是否对中国电动汽车征收为期五年的反补贴税举行投票。欧盟委员会发布的声明显示，投票中欧委会对中国进口纯电动汽车征收关税的提议获得了欧盟成员国的必要支持。对此，中国商务部新闻..."
        },
        {
            "id": "qwewqe...",
            "title": "一家人患病查出血液中老鼠药成分高",
            "platform": "weibo"
        }
        ...
    ]
}
```

你需要以一个特定的JSON形式来回应，例如：
```json
{
    "result": [
        {
            "id": ["abcd...", "cdef..."]
            "reason": "欧盟对华电车征税提议有可能导致国产新能源汽车海外销售，进而影响相关公司股价"
        }
     ]
}
在这个例子中聚合了来自sina和qq-new两个新闻平台的同一个新闻，并过滤掉了“一家人患病查出老鼠药”这个无关紧要的民生新闻
注意：
1. 任何解释性的内容都必须一律排除在你回应的JSON之外。
2. 过滤结果尽可能准确，如果没有有价值的新闻，请直接输出一个空结果: { "result": [] }，而不是从这些新闻中挑出一两个相对有价值的。
"""

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

提供给你的数据将是一个JSON, 请确保你的回答简洁、客观, 并聚焦于最重要的信息, 区分和过滤掉那些跟市场、政策、资机会无关的新闻, 比如民生、体育或娱乐新闻, 如果没有需要关注的信息, 直接说明即可。

输出格式: HTML
"""

GptBasicAskingNewsItem = TypedDict("GptBasicFilteredItem", {
    "id": str,
    "title": str,
    "description": Optional[float]
})

GptBasicFilteredItem = TypedDict("GptBasicFilteredItem", {
    "id": str,
    "reason": str,
    "mood": float
})

GptFurtherAskingNewsItem = GptBasicAskingNewsItem

GptFurtherFilteredItem = TypedDict("GptFurtherFilteredItem", {
    "id": List[str],
    "reason": str
})

LARGE_CONTEXT_MODEL_THRESHOLD = 30000

def common_rsp_validation_success(rsp_json: Optional[dict]) -> bool:
    if rsp_json is None:
        logger.error("GPT response has no Json output")
        return False
    # if rsp_json.get('error'):
    #     logger.error("GPT response error")
    #     return False
    # if rsp_json.get('code'):
    #     if rsp_json.get('code') != 200 or rsp_json.get('gpt') is None:
    #         logger.error("GPT response miss gpt or code is not 200")
    #         return False
    #     else:
    #         return True
    result_list = rsp_json.get('result')
    if result_list is None or type(result_list) != list:
        logger.error("GPT response miss result or result is not a list")
        return False
    return True

def parse_gpt_basic_filtering_rsp(rsp_text: str) -> Optional[List[GptBasicFilteredItem]]:   
    json_result = extract_json_string(rsp_text)
    if not common_rsp_validation_success(json_result):
        return None
    # if json_result.get('code'):
    #     return parse_gpt_basic_filtering_rsp(json_result.get('gpt'))
    result = []
    for item in json_result.get('result'):
        if type(item) == dict and type(item.get('id')) == str and (type(item.get('reason')) == str and len(item.get('reason')) > 0) and (type(item.get('mood')) == float or type(item.get('mood')) == int):
            result.append(item)
    return result


def parse_gpt_further_filtering_rsp(rsp_text: str) -> Optional[List[GptFurtherFilteredItem]]:   
    json_result = extract_json_string(rsp_text)
    if not common_rsp_validation_success(json_result):
        return None
    # if json_result.get('code'):
    #     return parse_gpt_further_filtering_rsp(json_result.get('gpt'))
    result = []
    for item in json_result.get('result'):
        if (type(item) == dict and type(item.get('id')) == list and len(item.get('id')) > 0) and (type(item.get('reason')) == str and len(item.get('reason')) > 0):
            item["id"] = filter_by(item.get('id'), lambda x: isinstance(x, str))
            result.append(item)
    return result

@dataclass
class ModuleDependencyAbstract(abc.ABC):
    hot_news_cache: HotNewsCacheAbstract
    hot_news_fetcher: NewsAbstract
    basic_gpt_gent: GptAgentAbstract
    gpt_agent_large_context: GptAgentAbstract

class ModuleDependency(ModuleDependencyAbstract):
    def __init__(self, session: SessionAbstract = SqlAlchemySession()):
        self.session = session
        self.hot_news_fetcher = news
        self.hot_news_cache = HotNewsCache(session=session)
        self.basic_gpt_gent = G4fAgent("gpt-4-turbo", '')
        self.gpt_agent_large_context = BaiChuanAgent("Baichuan3-Turbo-128k", '')
    
    def __enter__(self):
        self.session.begin()

    def __exit__(self, exc_type, exc_value, traceback_obj):
        if exc_value is None:
            self.session.commit()
        if exc_type and exc_value and traceback_obj:
            self.session.rollback()
    

class HotNewsOperationsModule:
    def __init__(self, dependency: ModuleDependencyAbstract = ModuleDependency()):
        self.dependency = dependency
    def _further_filter_news_from_different_patform(self, trend_news: List[NewsInfo]) -> List[NewsInfo]:
        if len(trend_news) == 0:
            return []
      
        to_ask_gpt: List[GptFurtherAskingNewsItem] = []
        final_result: List[NewsInfo] = []
        for news in trend_news:
            to_ask_gpt.append(remove_none({
                "id": news.news_id,
                "title": news.title,
                "platform": news.platform,
                "description": news.description
            }))
        question_json = { "news": to_ask_gpt }
        logger.debug(f"GPT request: {json.dumps(question_json, ensure_ascii=False, indent=2)}");
        while True:
            self.dependency.gpt_agent_large_context.set_system_prompt(GPT_SYSTEM_PROMPT_FOR_FURTHER_FILTERING)
            rsp = self.dependency.gpt_agent_large_context.ask(json.dumps(question_json, ensure_ascii=False))
            logger.debug(f"GPT response: {rsp}")
            parsed_results = parse_gpt_further_filtering_rsp(rsp)
            logger.debug(f"parsed_result {parsed_results}")
            if parsed_results is None:
                # 无限重试直到body正常
                continue
            for result in parsed_results:
                for news in trend_news:
                    if news.news_id == result['id'][0]:
                        final_result.append(news)
                    # 防止下次提取到这些重复新闻
                    if news.news_id in result['id']:
                        self.dependency.hot_news_cache.setnx(news)
            return final_result
        
    def _filter_news_from_platform(self, trend_news: List[NewsInfo]) -> List[NewsInfo]:
        if len(trend_news) == 0:
            return []
        to_ask_gpt: List[GptBasicAskingNewsItem] = []
        final_result: List[NewsInfo] = []
        start_from = 0
        for news in trend_news:
            # 防止重复
            if self.dependency.hot_news_cache.get(news.news_id) is None:
                to_ask_gpt.append(remove_none({
                    "id": news.news_id,
                    "title": news.title,
                    "description": news.description
                }))
        
        while start_from < len(to_ask_gpt):
            question_json = {
                "platform": news.platform, 
                "start_from": start_from,
                "news": to_ask_gpt[start_from:start_from+10]
            }
            logger.debug(f"GPT request: {json.dumps(question_json, ensure_ascii=False, indent=2)}");
            try:
                self.dependency.basic_gpt_gent.set_system_prompt(GPT_SYSTEM_PROMPT_FOR_BASIC_FILTERING)
                rsp = self.dependency.basic_gpt_gent.ask(json.dumps(question_json, ensure_ascii=False))
                logger.debug(f"GPT response: {rsp}")
                parsed_result = parse_gpt_basic_filtering_rsp(rsp)
                logger.debug(f"Parsed GPT response: {rsp}")
                if parsed_result is None:
                    # 无限重试直到body正常
                    continue
                # 将GPT过滤出来的新闻，根据ID从trend_news中过滤出来，并填充其reason和mood返回
                for news in trend_news:
                    for filtered_news in parsed_result:
                        if news.news_id == filtered_news["id"]:
                            news.reason = filtered_news['reason']
                            news.mood = filtered_news['mood']
                            final_result.append(news)
            except Exception as err:
                # 模块报错，只能忽略了，毕竟模块也做了重试
                logger.warning(f"Failed to ask GPT for error {err}")
            # 更新下一批次的新闻
            start_from += 10
        return final_result

    def get_hot_news_summary_report(self, platforms: HotNewsPlatform = ALL_SUPPORTED_PLATFORMS, max_records_per_platform: Dict[HotNewsPlatform, int] = {}) -> str:
        all_news: List[Dict] = []
        
        with self.dependency:
            for platform in platforms:
                news_from_platform = self.dependency.hot_news_fetcher.get_hot_news_of_platform(platform)
                if max_records_per_platform.get(platform) is not None:
                    news_from_platform = news_from_platform[:max_records_per_platform.get(platform)]
                
                filtered_count = 0
                total_count = len(news_from_platform)
                for news in news_from_platform:
                    # 过滤去重
                    if self.dependency.hot_news_cache.setnx(news) > 0:
                        all_news.append(remove_none({
                            "platform": platform,
                            "title": news.title,
                            "description": news.description,
                            "url": news.url
                        }))
                    else:
                        filtered_count += 1
                logger.info(f"平台 {platform}: 总新闻数 {total_count}, 过滤掉 {filtered_count} 条重复新闻, 保留 {total_count - filtered_count} 条新闻")
            
            # 准备发送给 GPT 的数据
            gpt_input = json.dumps({"news": all_news}, ensure_ascii=False)
            agent = self.dependency.basic_gpt_gent
            message_len = len(gpt_input + GPT_SYSTEM_PROMPT_FOR_SUMMARY)
            logger.info(f"Message length: {message_len}")
            if message_len >= LARGE_CONTEXT_MODEL_THRESHOLD:
                logger.info("Use large context model")
                agent = self.dependency.gpt_agent_large_context
            try:
                agent.set_system_prompt(GPT_SYSTEM_PROMPT_FOR_SUMMARY)
                return agent.ask(gpt_input)
            except Exception as err:
                logger.warning(f"Failed to use basic gpt agent with error {err} {traceback.format_exc()}")
                if agent != self.dependency.gpt_agent_large_context:
                    logger.warning("Retry by large context model")
                    agent = self.dependency.gpt_agent_large_context
                    agent.set_system_prompt(GPT_SYSTEM_PROMPT_FOR_SUMMARY)
                    return agent.ask(gpt_input)
                raise err
        
    def get_latest_valuable_news(self, platforms: HotNewsPlatform = ALL_SUPPORTED_PLATFORMS, max_records_per_platform: Dict[HotNewsPlatform, int]={}) -> List[NewsInfo]:
        gpt_analysis_result: List[NewsInfo] = []
        with self.dependency:
            for platform in platforms:
                news_from_platform = self.dependency.hot_news_fetcher.get_hot_news_of_platform(platform)
                if max_records_per_platform.get(platform) is not None:
                    news_from_platform = news_from_platform[:max_records_per_platform.get(platform)]
                gpt_analysis_result.extend(self._filter_news_from_platform(news_from_platform))
            logger.info("The first round of news screening is complete.")
            return self._further_filter_news_from_different_patform(gpt_analysis_result)

news = HotNewsOperationsModule()
