import os

import requests

from .interface import PushMessage, Result
# from ....src.utils.logger import logger

PUSH_PLUS_SERVER = 'http://www.pushplus.plus/send'

def send_push(kwargs: PushMessage) -> Result:
    if not os.environ.get('PUSH_PLUS_TOKEN'):
        raise Exception('PUSH_PLUS_TOKEN_MISSED', 'Push plus token is not set')
 
    try:
    # TODO Support Retry
        res = requests.post(PUSH_PLUS_SERVER, {
            'token': os.environ.get('PUSH_PLUS_TOKEN'),
            'content': kwargs['content'],
            'title': kwargs['title'],
            # 'channel': 'wechat',
            # 'callbackUrl': None
        })

        return {
            'success': res.json()['code'] == 200
        }
    except:
        return { 'success': False }