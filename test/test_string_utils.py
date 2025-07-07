import pytest
from lib.utils.string import extract_json_string, has_json_features


class TestHasJsonFeatures:
    """测试 has_json_features 函数"""
    
    def test_has_json_features_with_object(self):
        """测试包含JSON对象特征的字符串"""
        test_cases = [
            '{"name": "John"}',
            'This has JSON {"key": "value"} content',
            '{"incomplete": "json"',
            '{name: "John"}',  # 缺少引号但有JSON特征
        ]
        
        for test_string in test_cases:
            assert has_json_features(test_string) == True
    
    def test_has_json_features_with_array(self):
        """测试包含JSON数组特征的字符串"""
        test_cases = [
            '[1, 2, 3]',
            'Array: [{"id": 1}, {"id": 2}]',
            '[incomplete array',
            '["string", "array"]',
        ]
        
        for test_string in test_cases:
            assert has_json_features(test_string) == True
    
    def test_has_json_features_with_colon_and_quotes(self):
        """测试包含冒号和引号特征的字符串"""
        test_cases = [
            '"key": "value"',
            '":"',
            'Some "quoted" text with : colon',
        ]
        
        for test_string in test_cases:
            assert has_json_features(test_string) == True
    
    def test_has_json_features_with_comma(self):
        """测试包含逗号特征的字符串"""
        test_cases = [
            '"name", "age"',
            'key1, key2, key3',
            'Array with, comma',
        ]
        
        for test_string in test_cases:
            assert has_json_features(test_string) == True
    
    def test_has_json_features_without_features(self):
        """测试不包含JSON特征的字符串"""
        test_cases = [
            'plain text without json features',
            'just a normal sentence',
            'no special characters here',
            '12345',
            'some text with spaces',
        ]
        
        for test_string in test_cases:
            assert has_json_features(test_string) == False
    
    def test_has_json_features_empty_string(self):
        """测试空字符串"""
        assert has_json_features('') == False
    
    def test_has_json_features_mixed_content(self):
        """测试混合内容"""
        # 包含JSON特征的混合内容
        mixed_with_json = 'This is some text with {"json": "content"} and more text'
        assert has_json_features(mixed_with_json) == True
        
        # 不包含JSON特征的混合内容
        mixed_without_json = 'This is just plain text with numbers 123 and symbols !@#'
        assert has_json_features(mixed_without_json) == False


class TestExtractJsonString:
    """测试 extract_json_string 函数"""
    
    def test_extract_valid_json_object(self):
        """测试提取有效的JSON对象"""
        test_string = 'This is some text {"name": "John", "age": 30, "city": "New York"} and more text'
        result = extract_json_string(test_string)
        expected = {"name": "John", "age": 30, "city": "New York"}
        assert result == expected
    
    def test_extract_valid_json_array(self):
        """测试提取有效的JSON数组"""
        test_string = 'Here is an array [1, 2, 3, "hello", true, {"age": 18}] in the middle'
        result = extract_json_string(test_string)
        expected = [1, 2, 3, "hello", True,  {"age": 18}]
        assert result == expected
    
    def test_extract_invalid_json(self):
        """测试提取无效的JSON格式"""
        test_string = 'This contains invalid JSON {name: "John", age: 30} without quotes'
        result = extract_json_string(test_string)
        assert result is None
    
    def test_no_json_content(self):
        """测试不包含JSON内容的字符串"""
        test_string = 'This is just a plain text without any JSON content'
        result = extract_json_string(test_string)
        assert result is None
    
    def test_multiple_json_objects_returns_first(self):
        """测试包含多个JSON对象时返回第一个"""
        test_string = 'First {"id": 1, "name": "first"} and second {"id": 2, "name": "second"}'
        result = extract_json_string(test_string)
        expected = {"id": 1, "name": "first"}
        assert result == expected

    def test_multiple_json_objects_in_array(self):
        """测试包含多个JSON对象的数组能够解析"""
        test_string = """[
    {
        "author": "执念投资",
        "time": "2小时前",
        "content": "回复[@未来智能](https://xueqiu.com/n/%E6%9C%AA%E6%9D%A5%E6%99%BA%E8%83%BD): 人家永安药业要成为宇宙减肥龙头了![捂脸]//[@未来智能](https://xueqiu.com/n/%E6%9C%AA%E6%9D%A5%E6%99%BA%E8%83%BD):[该内容已被作者删除]",
        "likes": 2,
        "replies": 1
    }
]"""
        result = extract_json_string(test_string)
        print(result)
        assert result is not None
    
    def test_extract_json_with_nested_structures(self):
        """测试提取包含嵌套结构的JSON"""
        test_string = 'Complex JSON: {"users": [{"name": "Alice", "data": {"age": 25}}, {"name": "Bob", "data": {"age": 30}}]}'
        result = extract_json_string(test_string)
        expected = {
            "users": [
                {"name": "Alice", "data": {"age": 25}},
                {"name": "Bob", "data": {"age": 30}}
            ]
        }
        assert result == expected
    
    def test_extract_json_with_escaped_quotes(self):
        """测试提取包含转义引号的JSON"""
        test_string = 'JSON with quotes: {"message": "He said \\"Hello\\" to me"}'
        result = extract_json_string(test_string)
        expected = {"message": 'He said "Hello" to me'}
        assert result == expected
    
    def test_extract_json_empty_object(self):
        """测试提取空JSON对象"""
        test_string = 'Empty object: {}'
        result = extract_json_string(test_string)
        expected = {}
        assert result == expected
    
    def test_extract_json_empty_array(self):
        """测试提取空JSON数组"""
        test_string = 'Empty array: []'
        result = extract_json_string(test_string)
        expected = []
        assert result == expected