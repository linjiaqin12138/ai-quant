"""
JSON修复工具

使用大模型修复有问题的JSON字符串，处理不完整、格式错误等问题
"""
from typing import Optional, Union
from lib.logger import logger
from lib.utils.string import extract_json_string
from lib.adapter.llm import get_llm, get_llm_direct_ask
from lib.adapter.llm.interface import LlmAbstract

SYS_PROMPT = """
你是一个专业的JSON修复专家。你的任务是修复用户提供的不完整或有问题的JSON字符串。

重要修复规则：
1. **保持数组结构**：如果输入是JSON数组，输出也必须是JSON数组
2. **保留完整元素**：只保留完整的对象，删除任何不完整的元素
3. **处理截断**：如果数组在某个对象中间被截断，删除那个不完整的对象
4. **保持数据完整性**：不要修改完整对象的任何字段值
5. **处理特殊字符**：正确处理文本中的引号、换行符等特殊字符
6. **修复格式错误**：补全缺少的括号、引号、逗号等
7. **保持原始结构**：保持原有的字段名称和数据类型

常见问题处理：
- 缺少右括号 `]` 或 `}`：补全它们
- 多余的逗号：删除多余的逗号
- 缺少引号：为字符串添加引号
- 字符串内的引号：正确转义
- 不完整的对象：完全删除，不要尝试补全

处理示例：
输入：[{"name": "张三", "age": 25}, {"name": "李四", "age": 30}, {"name": "王五"
输出：[{"name": "张三", "age": 25}, {"name": "李四", "age": 30}]

输入：[{"content": "他说："你好""}, {"content": "再见"}]
输出：[{"content": "他说：\"你好\""}, {"content": "再见"}]

请直接返回修复后的有效JSON，不要包含任何解释文字。
"""

# TODO: Try use json-repair
class JsonFixer:
    """JSON修复器，使用大模型修复有问题的JSON字符串"""
    
    def __init__(self, llm: LlmAbstract = None):
        """
        初始化JSON修复器
        
        Args:
            llm: LLM实例
        """
        llm or get_llm('paoluz', 'gpt-4o-mini', temperature=0.2)
        self._json_fixer = get_llm_direct_ask(
            SYS_PROMPT, 
            llm = llm or get_llm('paoluz', 'gpt-4o-mini', temperature=0.2),
            response_format="json_object"
        )

    def fix(self, broken_json: str) -> Optional[Union[dict, list]]:
        """
        修复有问题的JSON字符串
        
        Args:
            broken_json: 有问题的JSON字符串
            
        Returns:
            修复后的JSON对象，如果修复失败返回None
        """
        try:
            # 调用大模型修复JSON
            logger.info("使用大模型修复JSON字符串")
            fixed_json_str = self._json_fixer(f"请修复以下JSON字符串，保持数组结构，只保留完整的元素：\n{broken_json}")
            logger.debug("大模型修复结果: %s", fixed_json_str)
            
            # 尝试解析修复后的JSON
            result = extract_json_string(fixed_json_str)
            logger.debug("提取到的JSON对象: %s", result)
            
            if result:
                logger.info("大模型成功修复JSON字符串")
                return result
            else:
                logger.warning("大模型修复JSON失败")
                return None
                
        except Exception as e:
            logger.warning(f"LLM JSON修复失败: {e}")
            return None


def fix_json_with_llm(broken_json: str, provider: str='paoluz', model: str = 'gpt-4o-mini') -> Optional[Union[dict, list]]:
    """
    使用大模型修复有问题的JSON字符串（兼容性函数）
    
    Args:
        broken_json: 有问题的JSON字符串
        provider: LLM提供商
        model: 使用的模型
        
    Returns:
        修复后的JSON对象，如果修复失败返回None
    """
    fixer = JsonFixer(provider, model)
    return fixer.fix(broken_json)