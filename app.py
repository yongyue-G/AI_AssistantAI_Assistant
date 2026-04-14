import streamlit as st
import PyPDF2
import base64
import hashlib
import hmac
import json
from datetime import datetime
from wsgiref.handlers import format_date_time
from time import mktime
from urllib.parse import urlparse, urlencode
import websocket 


APPID = "这里填你的AppID"
API_SECRET = "这里填你的APISecret"
API_KEY = "这里填你的APIKey"


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

def get_spark_response(prompt, max_tokens=1024):
    spark_url = "wss://spark-api.xf-yun.com/v3.5/chat"
    handler = SparkAPI(APPID, API_KEY, API_SECRET, spark_url)
    ws_url = handler.create_url()
    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        data = {
            "header": {"app_id": APPID},
            "parameter": {"chat": {"domain": "generalv3.5", "temperature": 0.5, "max_tokens": max_tokens}},
            "payload": {"message": {"text": [{"role": "user", "content": prompt}]}}
        }
        ws.send(json.dumps(data))
        result = ""
        while True:
            res = ws.recv()
            content = json.loads(res)
            if content['header']['code'] != 0: return f"报错: {content['header']['message']}"
            choices = content['payload']['choices']
            result += choices['text'][0]['content']
            if choices['status'] == 2: break
        ws.close()
        return result
    except Exception as e:
        return f"连接失败: {str(e)}"

# --- 网页界面与逻辑 ---
st.set_page_config(page_title="AI个性化学习平台", layout="wide", page_icon="🎓")
st.title("🎓 基于多智能体协同的个性化学习平台")

# 初始化聊天记录
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "同学你好！👋 我是你的专属学习管家。请在左侧上传教材PDF，然后在这里用一句话告诉我：**你的专业是什么？目前的学习痛点和目标是什么？**"}]

with st.sidebar:
    st.header("📂 课程知识库")
    uploaded_file = st.file_uploader("上传当前课程的PDF教材", type="pdf")
    if uploaded_file:
        st.success("教材已就绪！请在右侧聊天框回复你的情况。")

# --- 对话式画像收集区 (干掉表单，变成聊天) ---
st.subheader("💬 第一阶段：对话式画像收集")
chat_container = st.container()
with chat_container:
    for msg in st.session_state.messages:
        st.chat_message(msg["role"]).write(msg["content"])

user_input = st.chat_input("例如：我是学计算机的大二学生，基础薄弱，想快速掌握实操案例...")
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.chat_message("user").write(user_input)
    # 收到回复后，立刻提示可以开始生成
    st.info("✅ 已收到您的学习诉求！向下滚动，点击按钮启动智能体协作。")

st.divider() # 分割线

# --- 多智能体协作区 (5大资源生成) ---
st.subheader("🤖 第二阶段：多智能体协作生成资源")
start_btn = st.button("🚀 启动【5大智能体】协作处理", use_container_width=True)

if start_btn:
    if not uploaded_file:
        st.error("⚠️ 请先在左侧上传PDF教材哦！")
    elif len(st.session_state.messages) < 2:
        st.error("⚠️ 请先在聊天框里告诉我你的专业和目标哦！")
    else:
        # 读取PDF和聊天记录
        reader = PyPDF2.PdfReader(uploaded_file)
        text_sample = reader.pages[0].extract_text()[:600] # 读取一部分防止超长
        user_chat_history = st.session_state.messages[-1]["content"] # 获取用户最后输入的一句话
        
        # 建立6个标签页 (1个画像 + 5个资源)
        tabs = st.tabs(["🕵️ 画像分析", "🧭 路径规划", "✍️ 核心提炼", "📝 实战测试", "💻 实操案例", "🎬 多模态拓展"])
        
        # 智能体 1：画像分析员 (极简输出)
        with tabs[0]:
            with st.spinner("正在构建 6 维度画像..."):
                p1 = f"你是一名教育画像分析员。根据学生的自述：‘{user_chat_history}’，请构建一个6维度学习画像（包含知识基础、认知风格、易错点偏好、学习目标、痛点、建议）。要求：用Markdown列表输出，极其精炼，总字数不超过200字。"
                res1 = get_spark_response(p1)
                st.markdown("### 📊 动态学生画像\n" + res1)
                
        # 智能体 2：学习规划员 (资源1)
        with tabs[1]:
            with st.spinner("正在规划路径..."):
                p2 = f"你是一名规划员。基于学生画像：{res1[:100]}，结合教材内容：{text_sample[:200]}。请为他规划分3个阶段的学习路径。要求：用表格形式输出，字数不超过200字。"
                st.markdown("### 🗺️ 个性化学习路径\n" + get_spark_response(p2))

        # 智能体 3：内容提炼员 (资源2)
        with tabs[2]:
            with st.spinner("正在提炼知识点..."):
                p3 = f"你是一名内容提炼员。根据教材内容：{text_sample[:300]}。请用Markdown代码块生成一份该章节的‘知识点思维导图结构’。要求：层级清晰，简明扼要。"
                st.markdown("### 🧠 核心知识网络\n" + get_spark_response(p3))

        # 智能体 4：考评出题员 (资源3)
        with tabs[3]:
            with st.spinner("正在生成题库..."):
                p4 = f"你是一名考评员。根据教材内容：{text_sample[:300]}。请生成3道不同类型的练习题（1道单选，1道判断，1道简答），并附带答案解析。要求：直接输出题目和解析，废话少说。"
                st.markdown("### 🎯 针对性题库\n" + get_spark_response(p4))

        # 智能体 5：代码/实操教练 (资源4)
        with tabs[4]:
            with st.spinner("正在编写实操案例..."):
                p5 = f"你是一名实操教练。结合学生的专业和教材内容：{text_sample[:200]}。请提供一个非常具体的实操案例（如果涉及编程请给一段简单的代码演示；如果是文科请给一个场景应用案例）。要求：配有简单的文字说明。"
                st.markdown("### 🛠️ 实战演练\n" + get_spark_response(p5))
                
        # 智能体 6：多模态拓展专员 (资源5 - 解决视频生成痛点)
        with tabs[5]:
            with st.spinner("正在设计多模态视频分镜..."):
                p6 = f"你是一名多模态内容导演。为了帮助该学生理解教材重点：{text_sample[:200]}。请为他设计一个1分钟的‘微课视频分镜脚本’。要求包含：镜头画面描述、旁白文案、背景音效提示。字数不超过250字。"
                st.markdown("### 🎬 多模态微课脚本与拓展\n" + get_spark_response(p6))
                
        st.balloons()
        st.success("🎉 多智能体系统协同完毕！为您生成了 5 大类个性化学习资源。")