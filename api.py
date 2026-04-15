import base64
import hashlib
import hmac
import json
from datetime import datetime
from wsgiref.handlers import format_date_time
from time import mktime
from urllib.parse import urlparse, urlencode
import websocket 

# =======================================================
# 🔐 你的专属星火秘钥集中管理
# =======================================================
APPID = "a232feea"
API_SECRET = "NWZiYTUwNjY4ZGVjYTIyYjI3ZDFlOTg3"
API_KEY = "4b9e899159084f15bfca10dc0ad489b4"
# =======================================================

class SparkAPI:
    def __init__(self, appid, api_key, api_secret, spark_url):
        self.appid = appid
        self.api_key = api_key
        self.api_secret = api_secret
        self.host = urlparse(spark_url).netloc
        self.path = urlparse(spark_url).path
        self.spark_url = spark_url

    def create_url(self):
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))
        signature_origin = f"host: {self.host}\ndate: {date}\nGET {self.path} HTTP/1.1"
        signature_sha = hmac.new(self.api_secret.encode('utf-8'), signature_origin.encode('utf-8'), digestmod=hashlib.sha256).digest()
        signature_sha_base64 = base64.b64encode(signature_sha).decode(encoding='utf-8')
        authorization_origin = f'api_key="{self.api_key}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature_sha_base64}"'
        v = {"authorization": base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8'),"date": date,"host": self.host}
        return self.spark_url + '?' + urlencode(v)

def stream_spark_response(prompt, max_tokens=2048):
    """供网页前端调用的流式输出发电机"""
    spark_url = "wss://spark-api.xf-yun.com/v3.5/chat"
    handler = SparkAPI(APPID, API_KEY, API_SECRET, spark_url)
    ws_url = handler.create_url()
    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        data = {
            "header": {"app_id": APPID},
            "parameter": {"chat": {"domain": "generalv3.5", "temperature": 0.6, "max_tokens": max_tokens}},
            "payload": {"message": {"text": [{"role": "user", "content": prompt}]}}
        }
        ws.send(json.dumps(data))
        while True:
            res = ws.recv()
            content = json.loads(res)
            if content['header']['code'] != 0: 
                yield f"\n⚠️ 接口报错: {content['header']['message']}"
                break
            choices = content['payload']['choices']
            yield choices['text'][0]['content']
            if choices['status'] == 2: break
        ws.close()
    except Exception as e:
        yield f"\n网络连接异常: {str(e)}"

def get_silent_response(prompt, max_tokens=2048):
    """供后台默默思考用的发电机 (非流式)，默认加大 token 限制防截断"""
    full_text = ""
    for chunk in stream_spark_response(prompt, max_tokens):
        full_text += chunk
    return full_text