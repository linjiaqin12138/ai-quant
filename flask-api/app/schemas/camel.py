from pydantic import BaseModel, ConfigDict
from humps import camelize

class CamelModel(BaseModel):
    """支持驼峰命名的基础模型"""
    model_config = ConfigDict(
        alias_generator=camelize,
        populate_by_name=True
    )