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
# 🔐 1. 核心秘钥配置区 (请替换为你自己的)
# =======================================================
APPID = "a232feea"
API_SECRET = "NWZiYTUwNjY4ZGVjYTIyYjI3ZDFlOTg3"
API_KEY = "4b9e899159084f15bfca10dc0ad489b4"


SPARK_URL = "wss://spark-api.xf-yun.com/v3.5/chat" 
DOMAIN = "max70-32k" # 👈 修改这里，从报错列表选中的精确值
MAX_TOKEN_LIMIT = 32000

# =======================================================
# 🛠️ 3. 鉴权签名引擎
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
        v = {"authorization": base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8'), "date": date, "host": self.host}
        return self.spark_url + '?' + urlencode(v)

# =======================================================
# 🚀 4. 高级调用接口
# =======================================================
def stream_spark_response(prompt, max_tokens=512):
    """
    供前端使用的流式生成器。
    Ultra版支持超长生成，默认设为4096，最高可传32000。
    """
    handler = SparkAPI(APPID, API_KEY, API_SECRET, SPARK_URL)
    ws_url = handler.create_url()
    try:
        # 增加超时时间以应对长文本处理
        ws = websocket.create_connection(ws_url, timeout=30)
        
        # 动态计算安全上限
        safe_max_tokens = min(max_tokens, MAX_TOKEN_LIMIT)
        
        data = {
            "header": {"app_id": APPID},
            "parameter": {
                "chat": {
                    "domain": DOMAIN, 
                    "temperature": 0.5, 
                    "max_tokens": safe_max_tokens,
                    "auditing": "default" # 显式开启合规审计
                }
            },
            "payload": {"message": {"text": [{"role": "user", "content": prompt}]}}
        }
        
        ws.send(json.dumps(data))
        while True:
            res = ws.recv()
            content = json.loads(res)
            
            # 详尽的错误拦截
            code = content['header']['code']
            if code != 0: 
                err_msg = content['header']['message']
                yield f"\n⚠️ [Spark Ultra 错误] 状态码: {code}, 详情: {err_msg}"
                if code == 11200:
                    yield "\n*提示：请检查控制台是否已开通 Ultra-32K 权限并将 DOMAIN 修改正确。*"
                break
                
            choices = content['payload']['choices']
            yield choices['text'][0]['content']
            
            if choices['status'] == 2:
                break
        ws.close()
    except Exception as e:
        yield f"\n⚠️ [WebSocket 连接中断]: {str(e)}"

def get_silent_response(prompt, max_tokens=512):
    """非流式同步接口，专为长讲义生成设计"""
    full_text = ""
    for chunk in stream_spark_response(prompt, max_tokens):
        if "⚠️" in chunk:
            return f"Error: {chunk}"
        full_text += chunk
    return full_text