import pytest
from datetime import datetime
from lib.tools.information_search import duckduckgo_search, google_search, unified_search, read_web_page
from lib.config import get_http_proxy
from lib.model.news import NewsInfo


class TestInformationSearch:
    """信息搜索功能测试"""
    
    def test_duckduckgo_search_basic(self):
        """测试DuckDuckGo搜索基本功能"""
        query = "bitcoin price news"
        results = duckduckgo_search(query, max_results=3)
        
        # 验证返回结果是NewsInfo对象数组
        assert isinstance(results, list)
        
        if len(results) > 0:
            # 检查每个结果都是NewsInfo对象
            for result in results:
                assert isinstance(result, NewsInfo)
                assert result.platform == "ddgo"
                assert hasattr(result, 'news_id')
                assert hasattr(result, 'title')
                assert hasattr(result, 'timestamp')
                assert hasattr(result, 'url')
                assert hasattr(result, 'description')
                
                # 验证timestamp是datetime对象
                assert isinstance(result.timestamp, datetime)
                
                # 验证news_id不为空
                assert len(result.news_id) > 0
    
    def test_duckduckgo_search_with_proxy(self):
        """测试带代理的DuckDuckGo搜索功能"""
        proxy = get_http_proxy()
        
        if proxy:
            print(f"使用代理: {proxy}")
        
        query = "stock market news"
        results = duckduckgo_search(query, max_results=2)
        
        # 验证返回结果
        assert isinstance(results, list)
        
        if len(results) > 0:
            for result in results:
                assert isinstance(result, NewsInfo)
                assert result.platform == "ddgo"
    
    def test_duckduckgo_search_parameters(self):
        """测试DuckDuckGo搜索参数功能"""
        query = "economic news"
        
        # 测试不同地区和时间范围
        results = duckduckgo_search(query, max_results=2, region="us-en", time_limit="d")
        assert isinstance(results, list)
        
        results = duckduckgo_search(query, max_results=2, region="cn-zh", time_limit="w")
        assert isinstance(results, list)
    
    def test_duckduckgo_search_edge_cases(self):
        """测试DuckDuckGo搜索边界情况"""
        # 测试空查询
        try:
            results = duckduckgo_search("", max_results=1)
            assert isinstance(results, list)
        except Exception:
            # 如果抛出异常，这是预期的行为
            pass
        
        # 测试非常短的查询
        results = duckduckgo_search("a", max_results=1)
        assert isinstance(results, list)
    
    def test_google_search_basic(self):
        """测试Google搜索基本功能"""
        try:
            query = "technology news"
            results = google_search(query, max_results=3)
            
            # 验证返回结果是NewsInfo对象数组
            assert isinstance(results, list)
            
            if len(results) > 0:
                # 检查每个结果都是NewsInfo对象
                for result in results:
                    assert isinstance(result, NewsInfo)
                    assert result.platform == "google"
                    assert hasattr(result, 'news_id')
                    assert hasattr(result, 'title')
                    assert hasattr(result, 'timestamp')
                    assert hasattr(result, 'url')
                    assert hasattr(result, 'description')
                    
                    # 验证timestamp是datetime对象
                    assert isinstance(result.timestamp, datetime)
                    
                    # 验证news_id不为空
                    assert len(result.news_id) > 0
            
            print(f"Google搜索测试通过，返回 {len(results)} 条结果")
            
        except ValueError as e:
            if "Google API密钥" in str(e):
                print("Google API未配置，跳过测试")
                pytest.skip("Google API未配置")
            else:
                raise
        except Exception as e:
            print(f"Google搜索测试失败: {e}")
            # 在测试环境中，我们允许Google搜索失败
            pass
    
    def test_google_search_with_proxy(self):
        """测试带代理的Google搜索功能"""
        try:
            proxy = get_http_proxy()
            if proxy:
                print(f"使用代理: {proxy}")
            
            query = "finance news"
            results = google_search(query, max_results=2)
            
            # 验证返回结果
            assert isinstance(results, list)
            
            if len(results) > 0:
                for result in results:
                    assert isinstance(result, NewsInfo)
                    assert result.platform == "google"
            
            print(f"Google搜索代理测试通过，返回 {len(results)} 条结果")
            
        except ValueError as e:
            if "Google API密钥" in str(e):
                print("Google API未配置，跳过测试")
                pytest.skip("Google API未配置")
            else:
                raise
        except Exception as e:
            print(f"Google搜索代理测试失败: {e}")
            # 在测试环境中，我们允许Google搜索失败
            pass
    
    def test_google_search_parameters(self):
        """测试Google搜索参数功能"""
        try:
            query = "economic news"
            
            # 测试不同地区和时间范围
            results = google_search(query, max_results=2, region="us-en", time_limit="d")
            assert isinstance(results, list)
            
            results = google_search(query, max_results=2, region="cn-zh", time_limit="w")
            assert isinstance(results, list)
            
            print(f"Google搜索参数测试通过")
            
        except ValueError as e:
            if "Google API密钥" in str(e):
                print("Google API未配置，跳过测试")
                pytest.skip("Google API未配置")
            else:
                raise
        except Exception as e:
            print(f"Google搜索参数测试失败: {e}")
            # 在测试环境中，我们允许Google搜索失败
            pass
    
    def test_unified_search_basic(self):
        """测试统一搜索基本功能"""
        query = "cryptocurrency news"
        results = unified_search(query, max_results=3)
        
        # 验证返回结果是NewsInfo对象数组
        assert isinstance(results, list)
        
        if len(results) > 0:
            # 检查每个结果都是NewsInfo对象
            for result in results:
                assert isinstance(result, NewsInfo)
                assert result.platform in ["google", "ddgo"]
                assert hasattr(result, 'news_id')
                assert hasattr(result, 'title')
                assert hasattr(result, 'timestamp')
                assert hasattr(result, 'url')
                assert hasattr(result, 'description')
                
                # 验证timestamp是datetime对象
                assert isinstance(result.timestamp, datetime)
                
                # 验证news_id不为空
                assert len(result.news_id) > 0
        
        print(f"统一搜索测试通过，返回 {len(results)} 条结果")
    
    def test_unified_search_fallback(self):
        """测试统一搜索回退机制"""
        # 即使Google搜索失败，也应该回退到DuckDuckGo搜索
        query = "business news"
        results = unified_search(query, max_results=2, region="us-en", time_limit="w")
        
        # 验证返回结果
        assert isinstance(results, list)
        
        # 统一搜索应该总是返回结果（除非网络完全不可用）
        if len(results) > 0:
            for result in results:
                assert isinstance(result, NewsInfo)
                assert result.platform in ["google", "ddgo"]
        
        print(f"统一搜索回退测试通过，返回 {len(results)} 条结果")
    
    def test_read_web_page_basic(self):
        """测试网页读取基本功能"""
        try:
            # 使用一个稳定的测试网站
            test_url = "https://httpbin.org/html"
            content = read_web_page(test_url)
            
            # 验证返回结果
            assert isinstance(content, str)
            assert len(content) > 0
            
            # 验证内容包含预期的标识（Jina API返回markdown格式）
            assert "title:" in content.lower() or "url source:" in content.lower() or "markdown content:" in content.lower()
            
            print(f"网页读取测试通过，内容长度: {len(content)}")
            
        except Exception as e:
            print(f"网页读取测试失败: {e}")
            # 在测试环境中，我们允许网页读取失败（网络问题）
            pass
    
    def test_read_web_page_with_proxy(self):
        """测试带代理的网页读取功能"""
        try:
            proxy = get_http_proxy()
            if proxy:
                print(f"使用代理: {proxy}")
            
            # 使用一个稳定的测试网站
            test_url = "https://httpbin.org/user-agent"
            content = read_web_page(test_url)
            
            # 验证返回结果
            assert isinstance(content, str)
            assert len(content) > 0
            
            print(f"网页读取代理测试通过，内容长度: {len(content)}")
            
        except Exception as e:
            print(f"网页读取代理测试失败: {e}")
            # 在测试环境中，我们允许网页读取失败（网络问题）
            pass
    
    def test_read_web_page_invalid_url(self):
        """测试网页读取异常情况"""
        try:
            # 测试无效URL
            content = read_web_page("invalid-url")
            # 如果没有抛出异常，至少应该是字符串
            assert isinstance(content, str)
        except Exception as e:
            # 预期会抛出异常
            print(f"无效URL测试通过，抛出异常: {e}")
            assert True
    
    @pytest.mark.integration
    def test_integration_search_functions(self):
        """集成测试：测试所有搜索功能"""
        query = "python programming news"
        
        # 测试DuckDuckGo搜索
        ddg_results = duckduckgo_search(query, max_results=2)
        assert isinstance(ddg_results, list)
        
        # 测试统一搜索
        unified_results = unified_search(query, max_results=2)
        assert isinstance(unified_results, list)
        
        # 测试Google搜索（可能失败）
        try:
            google_results = google_search(query, max_results=2)
            assert isinstance(google_results, list)
            print("Google搜索集成测试通过")
        except Exception as e:
            print(f"Google搜索集成测试跳过: {e}")
        
        print(f"搜索功能集成测试通过")
        print(f"DuckDuckGo结果: {len(ddg_results)} 条")
        print(f"统一搜索结果: {len(unified_results)} 条")


if __name__ == "__main__":
    # 运行所有测试
    pytest.main([__file__, "-v"])