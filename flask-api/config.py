import os

class Config:
    # 回调认证配置
    _callback_auth = {
        'username': os.getenv('CALLBACK_API_USER', 'username'),
        'password': os.getenv('CALLBACK_API_PASS', 'password')
    }

    @classmethod
    def get_callback_auth(cls) -> tuple:
        """获取回调认证信息"""
        return cls._callback_auth['username'], cls._callback_auth['password']