#!/usr/bin/env python3
"""
Web Page Reader Agent
通过Jina API读取网页内容，并使用大模型分析提取用户指定的内容行范围
"""

import sys
import os

from textwrap import dedent
import traceback
from typing import List, Tuple, Optional
import argparse

import requests

from lib.config import get_http_proxy
from lib.model.error import LlmReplyInvalid
from lib.tools.cache_decorator import use_cache
from lib.utils.decorators import with_retry
from lib.utils.string import extract_json_string

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from lib.modules import get_agent, get_llm_tool
from lib.logger import logger

SYS_PROMPT = """你是一个专业的网页内容分析师，擅长从网页内容中提取用户需要的特定信息。

你的任务是：
1. 分析用户提供的网页内容
2. 根据用户的提取需求（query），找到相关内容在原文中的行范围
3. 返回精确的行号范围，格式为 [开始行号, 结束行号]

**重要规则：**
- 行号从1开始计数
- 必须返回JSON格式：{"start_line": 开始行号, "end_line": 结束行号, "reason": "选择理由"}
- 如果找不到相关内容，返回：{"start_line": -1, "end_line": -1, "reason": "未找到相关内容"}
- 选择范围时要确保包含完整的内容，不要遗漏重要信息
- 如果相关内容分散在多个地方，选择最主要或最完整的部分

**示例：**
用户query: "提取文章正文"
分析：文章正文通常在标题后，排除头部导航和底部信息
返回：{"start_line": 15, "end_line": 89, "reason": "文章正文内容，从标题后开始到参考资料前结束"}
"""

def cache_key_generator(kwargs, *args) -> str:
    """生成缓存键"""
    url = kwargs.get('url', '')
    return f"web_page_reader:{url}"

@use_cache(3600, use_db_cache=True, key_generator=cache_key_generator)
@with_retry(
    retry_errors=(ConnectionError, TimeoutError, OSError),
    max_retry_times=3
)
def read_web_page(url: str) -> str:
    """
    使用Jina API读取网页内容
    
    Args:
        url: 要读取的网页URL
    
    Returns:
        网页内容字符串
    """
    # Jina Reader API端点
    jina_url = f"https://r.jina.ai/{url}"
    
    # 获取代理设置
    proxy = get_http_proxy()
    proxies = None
    if proxy:
        proxies = {
            'http': proxy,
            'https': proxy
        }
    
    # 设置请求头
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    # 发送请求到Jina API
    response = requests.get(jina_url, headers=headers, proxies=proxies, timeout=600)
    response.raise_for_status()
    
    # 返回网页内容
    return response.text

class WebPageReader:
    """网页内容读取和智能提取器"""
    
    def __init__(self, provider: str = "paoluz", model: str = "deepseek-v3"):
        """
        初始化网页阅读器
        
        Args:
            provider: LLM提供商
            model: 使用的模型
        """
        self.provider = provider
        self.model = model
        self.llm_ask = get_llm_tool(
            SYS_PROMPT, 
            provider, 
            model, 
            temperature=0.1,
            response_format='json_object'
        )

    @with_retry((LlmReplyInvalid,), max_retry_times=1)
    def analyze_content_range(self, content: str, query: str) -> Tuple[int, int]:
        """
        分析内容并返回指定query对应的行范围
        
        Args:
            content: 网页内容
            query: 用户的提取需求
            
        Returns:
            (开始行号, 结束行号)
        """
        # 为内容添加行号
        lines = content.split('\n')
        numbered_content = []
        for i, line in enumerate(lines, 1):
            numbered_content.append(f"{i:4d}: {line}")
        
        numbered_text = '\n'.join(numbered_content)
        
        # 构建分析提示
        prompt = dedent(
            f"""
                请分析以下带行号的网页内容，根据用户需求提取相应的行范围。

                用户需求：{query}

                网页内容：
                {numbered_text}

                请返回JSON格式的结果，包含start_line、end_line。
            """
        )
        
        # 调用Agent分析
        response = self.llm_ask(prompt)
        logger.debug(f"LLM分析响应: {response}")
        result = extract_json_string(response)
        if not result or "start_line" not in result or "end_line" not in result:
            raise LlmReplyInvalid("LLM返回的结果格式不正确，缺少start_line或end_line字段", response)
        start_line = result.get("start_line", -1)
        end_line = result.get("end_line", -1)
        if start_line < 1 or end_line < 1 or start_line > end_line:
            raise LlmReplyInvalid("LLM返回的行号不合法", response)

        return start_line, end_line

    
    def extract_content_by_range(self, content: str, start_line: int, end_line: int) -> str:
        """
        根据行范围提取内容
        
        Args:
            content: 原始内容
            start_line: 开始行号（从1开始）
            end_line: 结束行号（从1开始）
            
        Returns:
            提取的内容
        """
        if start_line <= 0 or end_line <= 0:
            return "未找到相关内容"
        
        lines = content.split('\n')
        
        # 转换为0-based索引并确保范围有效
        start_idx = max(0, start_line - 1)
        end_idx = min(len(lines), end_line)
        
        if start_idx >= len(lines):
            return "行号超出范围"
        
        extracted_lines = lines[start_idx:end_idx]
        return '\n'.join(extracted_lines)
    
    def read_and_extract(self, url: str, query: str) -> str:
        """
        读取网页并提取指定内容
        
        Args:
            url: 网页URL
            query: 提取需求, 如 "提取正文"、"提取摘要"等
            
        Returns:
            包含提取结果的字典
        """
        
        try:
            # 读取网页内容
            logger.info(f"📖 正在读取网页: {url}")
            full_content = read_web_page(url)

            if not full_content.strip():
                return "网页内容为空"
            
            logger.info(f"✅ 网页读取成功，内容长度: {len(full_content)} 字符")
            
            # 分析内容范围
            logger.info(f"🔍 正在分析内容，查找: {query}")
            start_line, end_line = self.analyze_content_range(full_content, query)
            
            # 提取指定范围的内容
            extracted_content = self.extract_content_by_range(full_content, start_line, end_line)
            logger.info(f"✅ 提取成功，行范围: [{start_line}, {end_line}]")
            return extracted_content
            
        except Exception as e:
            error_msg = f"处理失败: {str(e)}"
            logger.error(error_msg)
            logger.debug(f"错误详情: {traceback.format_exc()}")
            return error_msg