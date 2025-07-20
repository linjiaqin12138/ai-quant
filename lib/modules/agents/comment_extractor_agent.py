#!/usr/bin/env python3
"""
CommentExtractorAgent
负责从网页内容中提取评论数据，包含schema校验、过滤、单URL和多URL评论提取等功能。
"""
from typing import List, Dict, Any, Optional, TypedDict
from datetime import datetime
from textwrap import dedent
import traceback

from lib.adapter.llm import get_llm, get_llm_direct_ask
from lib.modules.agents.json_fixer import JsonFixer
from lib.modules.agents.web_page_reader import WebPageReader
from lib.logger import logger
from lib.utils.string import extract_json_string, has_json_features
from lib.utils.decorators import with_retry
from lib.model.error import LlmReplyInvalid

COMMENT_EXTRACTOR_SYS_PROMPT_TEMPLATE = """
你是一个专业的股票数据分析助手，擅长从网页内容中提取和分析股票相关信息。
现在时间是{curr_time_str}。
请按照以下要求操作：
1. 仔细分析页面内容，找出评论区域
2. 提取过去24小时内的评论，包括：
   - 评论者用户名/昵称
   - 评论时间
   - 评论内容
   - 点赞数、阅读数、回复数等互动数据（如果有）
3. 以JSON数组格式返回所有评论数据

如果页面没有评论区或评论为空，请说明具体情况。

Response Format Example (请严格follow)
[
    {{
        "author": "用户名",
        "time": "评论时间",
        "content": "评论内容",
        "likes": 0,
        "replies": 0
    }},
    ...
]
"""

CommentItem = TypedDict("CommentItem", {
    "author": str,
    "time": str,
    "content": str,
    "likes": int,
    "replies": int
})

class CommentExtractorAgent:
    """
    评论提取Agent，负责从网页内容中提取评论数据
    """
    def __init__(self, llm=None, web_page_reader: Optional[WebPageReader]=None, json_fixer: Optional[JsonFixer]=None):
        self.llm = llm or get_llm("paoluz", "deepseek-v3", temperature=0.2)
        self.comment_extractor = get_llm_direct_ask(
            system_prompt=COMMENT_EXTRACTOR_SYS_PROMPT_TEMPLATE.format(curr_time_str=datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            llm=self.llm,
            response_format="json_object"
        )
        self.web_page_reader = web_page_reader or WebPageReader(llm=self.llm)
        self.fix_json_tool = json_fixer.fix if json_fixer else JsonFixer(llm=self.llm).fix

    def validate_comment_schema(self, comment: Any) -> bool:
        """
        验证评论数据的schema是否符合要求
        """
        if not isinstance(comment, dict):
            return False
        required_fields = ['author', 'time', 'content']
        for field in required_fields:
            if field not in comment:
                return False
            if not isinstance(comment[field], str):
                return False
            if not comment[field].strip():
                return False
        optional_numeric_fields = ['likes', 'replies']
        for field in optional_numeric_fields:
            if field in comment:
                if not isinstance(comment[field], (int, float)):
                    try:
                        comment[field] = int(comment[field])
                    except (ValueError, TypeError):
                        comment[field] = 0
        return True

    def filter_valid_comments(self, json_list: list) -> list:
        valid_comments = []
        invalid_comments = []
        for comment in json_list:
            if self.validate_comment_schema(comment):
                valid_comments.append(comment)
            else:
                invalid_comments.append(comment)
        if invalid_comments:
            logger.warning("发现%d条不符合schema的评论数据, 如%r", len(invalid_comments), invalid_comments[0] if invalid_comments else None)
        if not valid_comments:
            logger.warning("没有有效的评论数据")
        return valid_comments

    def extract_comments_from_url(self, url: str) -> List[CommentItem]:
        logger.info(f"正在获取页面内容: {url}")
        page_content = self.web_page_reader.read_and_extract(url, '提取评论区')
        prompt = dedent(f"""
            请分析以下页面内容，提取其中的评论区信息：

            页面URL: {url}
            页面内容: {page_content[:15000]}

            请提取所有评论并按JSON格式返回。
        """)
        @with_retry((LlmReplyInvalid,), 1)
        def retryable_extract():
            logger.info(f"开始分析页面: {url}")
            response = self.comment_extractor(prompt)
            logger.info("分析页面内容完成：%s...%s", response[:1], response[-1:])
            logger.debug("完整分析结果: %s", response)
            json_or_none = extract_json_string(response)
            logger.debug("提取到的JSON对象: %r", json_or_none)
            if json_or_none and isinstance(json_or_none, list):
                return self.filter_valid_comments(json_or_none)
            else:
                logger.warning("大模型JSON响应错误")
                if has_json_features(response) and json_or_none is None:
                    logger.info("检测到JSON特征字符，尝试使用大模型修复")
                    fixed_json = self.fix_json_tool(response)
                    if fixed_json and isinstance(fixed_json, list):
                        return self.filter_valid_comments(fixed_json)
                    else:
                        logger.warning("大模型修复JSON失败 %s", fixed_json)
                else:
                    logger.error("响应中未检测到JSON特征字符")
                raise LlmReplyInvalid("未找到JSON格式的评论数据", response)
        return retryable_extract()