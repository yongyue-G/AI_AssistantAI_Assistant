import streamlit as st
import PyPDF2
import time
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
# 🚨 检查区：请确保这里填写的和讯飞控制台一模一样 🚨
# =======================================================
APPID = "这里填你的AppID"
API_SECRET = "这里填你的APISecret"
API_KEY = "这里填你的APIKey"
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
        # 修正时间格式：必须使用标准 RFC1123 格式
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))
        
        # 拼接签名字符串
        signature_origin = f"host: {self.host}\ndate: {date}\nGET {self.path} HTTP/1.1"
        signature_sha = hmac.new(self.api_secret.encode('utf-8'), signature_origin.encode('utf-8'), digestmod=hashlib.sha256).digest()
        signature_sha_base64 = base64.b64encode(signature_sha).decode(encoding='utf-8')
        
        authorization_origin = f'api_key="{self.api_key}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature_sha_base64}"'
        v = {
            "authorization": base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8'),
            "date": date,
            "host": self.host
        }
        return self.spark_url + '?' + urlencode(v)

def get_spark_response(prompt):
    spark_url = "wss://spark-api.xf-yun.com/v3.5/chat"
    handler = SparkAPI(APPID, API_KEY, API_SECRET, spark_url)
    ws_url = handler.create_url()
    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        data = {
            "header": {"app_id": APPID},
            "parameter": {"chat": {"domain": "generalv3.5", "temperature": 0.5, "max_tokens": 2048}},
            "payload": {"message": {"text": [{"role": "user", "content": prompt}]}}
        }
        ws.send(json.dumps(data))
        
        result = ""
        while True:
            res = ws.recv()
            content = json.loads(res)
            if content['header']['code'] != 0:
                return f"讯飞报错: {content['header']['message']} (错误码: {content['header']['code']})"
            choices = content['payload']['choices']
            result += choices['text'][0]['content']
            if choices['status'] == 2: break
        ws.close()
        return result
    except Exception as e:
        return f"连接失败: {str(e)}"

# --- 网页界面 ---
st.set_page_config(page_title="AI学习助手", layout="wide")
st.title("🎓 软件杯：多智能体协作学习系统")

if 'step' not in st.session_state: st.session_state.step = 0

with st.sidebar:
    st.header("⚙️ 任务面板")
    uploaded_file = st.file_uploader("1. 上传PDF教材", type="pdf")
    major = st.text_input("2. 你的专业", "计算机科学")
    goal = st.text_input("3. 学习目标", "考试冲刺")
    start_btn = st.button("🚀 启动多智能体协作", use_container_width=True)

if start_btn and uploaded_file:
    reader = PyPDF2.PdfReader(uploaded_file)
    text_sample = reader.pages[0].extract_text()[:500]
    
    t1, t2, t3 = st.tabs(["🕵️ 画像分析员", "🧭 学习规划员", "✍️ 内容生成员"])
    
    with t1:
        with st.spinner("画像分析中..."):
            res1 = get_spark_response(f"你是分析员。学生专业{major}，目标{goal}。请输出学习画像。")
            st.write(res1)
    with t2:
        with st.spinner("计划制定中..."):
            res2 = get_spark_response(f"你是规划员。画像：{res1[:100]}。教材：{text_sample[:100]}。请规划路径。")
            st.write(res2)
    with t3:
        with st.spinner("资料生成中..."):
            res3 = get_spark_response(f"你是生成员。教材：{text_sample}。请生成思维导图和3道题。")
            st.write(res3)
    st.success("✅ 全部生成完毕！")