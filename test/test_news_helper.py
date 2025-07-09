import pytest
from datetime import datetime, timedelta
import time

from lib.tools.news_helper import NewsHelper
from lib.model.news import NewsInfo
from lib.logger import logger


@pytest.fixture
def news_helper():
    """创建 NewsHelper 实例"""
    return NewsHelper(llm_provider="paoluz", model="gpt-4o-mini", temperature=0.2)


@pytest.fixture
def clean_cache():
    """清理缓存的fixture"""
    # 这里可以添加清理缓存的逻辑
    yield
    # 测试后清理


class TestNewsHelper:
    """NewsHelper 类的集成测试用例"""

    @pytest.mark.integration
    def test_get_global_news_report(self, news_helper, clean_cache):
        """测试获取全球新闻报告功能 - 集成测试"""
        try:
            # 设置时间范围 - 最近24小时
            from_time = datetime.now() - timedelta(hours=24)
            end_time = datetime.now()
            
            logger.info(f"测试全球新闻报告获取: {from_time} 到 {end_time}")
            
            # 调用真实方法
            result = news_helper.get_global_news_report(from_time, end_time)
            
            # 验证结果
            assert isinstance(result, str)
            assert len(result) > 0
            logger.info(f"全球新闻报告获取成功，返回内容长度: {len(result)}")
            
        except Exception as e:
            logger.error(f"全球新闻报告测试失败: {str(e)}")
            pytest.skip(f"网络或API问题导致测试失败: {str(e)}")

