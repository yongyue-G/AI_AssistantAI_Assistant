import streamlit as st
import PyPDF2
import base64
import hashlib
import hmac
import json
import time
from datetime import datetime
from wsgiref.handlers import format_date_time
from time import mktime
from urllib.parse import urlparse, urlencode
import websocket 

# =======================================================
# 🔐 专属秘钥已自动装填
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

# 核心升级 1：真·流式输出生成器 (解决长时间白屏等待)
def stream_spark_response(prompt, max_tokens=2048):
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
            yield choices['text'][0]['content'] # 逐字推送到网页
            if choices['status'] == 2: 
                break
        ws.close()
    except Exception as e:
        yield f"\n网络连接异常: {str(e)}"

# 核心升级 2：非流式请求 (用于后台默默判断逻辑)
def get_silent_response(prompt):
    full_text = ""
    for chunk in stream_spark_response(prompt, 500):
        full_text += chunk
    return full_text

# --- 初始化应用状态 ---
st.set_page_config(page_title="AI学习空间", layout="wide", page_icon="💡")

if "chat_history" not in st.session_state:
    # 设定面试官的性格和任务
    st.session_state.chat_history = [{"role": "assistant", "content": "你好！我是你的AI学习导师。为了给你量身定制学习方案，我们先聊聊吧。请问你目前学的是什么专业？"}]
if "phase" not in st.session_state:
    st.session_state.phase = "chatting" # 状态机：chatting (聊天中) -> profiling (生成中)
if "pdf_text" not in st.session_state:
    st.session_state.pdf_text = ""

# --- 侧边栏：美化与状态追踪 ---
with st.sidebar:
    st.image("https://api.dicebear.com/7.x/bottts/svg?seed=Felix&backgroundColor=e2e8f0", width=100)
    st.title("👨‍🏫 智能导师中控台")
    st.markdown("---")
    
    st.subheader("📁 第一步：注入灵魂 (教材)")
    uploaded_file = st.file_uploader("请上传本次课程的 PDF", type="pdf")
    if uploaded_file and not st.session_state.pdf_text:
        with st.spinner("正在解析知识库..."):
            reader = PyPDF2.PdfReader(uploaded_file)
            # 提取前3页内容作为知识库基础
            for i in range(min(3, len(reader.pages))):
                st.session_state.pdf_text += reader.pages[i].extract_text()
            st.success("✅ 教材解析完毕！请在右侧与导师对话。")
            
    st.markdown("---")
    st.subheader("🎯 任务进度追踪")
    if st.session_state.phase == "chatting":
        st.info("🔄 当前阶段：智能多轮对话画像中...")
    else:
        st.success("✅ 画像完毕，多智能体已接管系统！")

# --- 主界面逻辑 ---
st.title("🎓 基于大模型的多智能体个性化学习空间")

# 阶段一：动态多轮交互 (面试官)
if st.session_state.phase == "chatting":
    st.markdown("### 💬 导师深度访谈区")
    st.caption("不要拘束，像聊天一样告诉我你的情况。当导师认为足够了解你时，会自动为你开启专属学习通道。")
    
    # 渲染历史对话
    chat_box = st.container(height=400)
    with chat_box:
        for msg in st.session_state.chat_history:
            st.chat_message(msg["role"]).write(msg["content"])
            
    # 用户输入框
    user_input = st.chat_input("输入你的回答 (例：我是计科大二，基础很差，总挂科...)")
    if user_input:
        if not uploaded_file:
            st.toast("⚠️ 请先在左侧上传PDF教材哦！", icon="🚨")
        else:
            # 1. 记录用户话语
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            chat_box.chat_message("user").write(user_input)
            
            # 2. 组装后台判断指令：让AI决定是继续问，还是结束
            history_str = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.chat_history])
            judge_prompt = f"""
            你是一名专业的学习诊断导师。以下是你和学生的对话历史：
            {history_str}
            你的任务是判断是否已经充分了解该学生的：1.专业基础 2.学习痛点/易错点 3.学习目标 4.认知偏好。
            如果信息不足，请提出【一个】针对性的问题继续追问。
            如果以上4点都已明确（通常需要2-3个回合），请直接回复："[评估完成]"，不要说任何多余的话。
            """
            
            with st.spinner("导师思考中..."):
                ai_reply = get_silent_response(judge_prompt)
            
            # 3. 拦截并处理状态切换
            if "[评估完成]" in ai_reply:
                st.session_state.phase = "profiling"
                st.rerun() # 刷新页面进入下一阶段
            else:
                st.session_state.chat_history.append({"role": "assistant", "content": ai_reply})
                chat_box.chat_message("assistant").write(ai_reply)

# 阶段二：多智能体并发生成 (0延迟流式呈现)
elif st.session_state.phase == "profiling":
    st.success("🎉 导师访谈结束！系统已充分掌握您的学习特征。多智能体协作流水线正在为您生成资源...")
    
    # 提取聊天记录作为学生的“灵魂数据”
    student_data = "\n".join([m['content'] for m in st.session_state.chat_history if m['role'] == 'user'])
    book_data = st.session_state.pdf_text[:1000] # 截取1000字教材
    
    # 重新设计的 UI：手风琴式折叠面板 (避免页面拉得无限长)
    with st.expander("🕵️‍♂️ 智能体 1：动态学习画像 (6维度)", expanded=True):
        st.caption("打字机极速输出中...")
        p1 = f"根据学生自述：{student_data}。请构建包含：知识基础、认知风格、易错点偏好、学习目标、驱动力、环境偏好 6个维度的学习画像。要求：Markdown列表结构，专业严谨。"
        # 直接使用流式输出写入界面，速度飞快！
        st.write_stream(stream_spark_response(p1, max_tokens=500))
        
    with st.expander("🧭 智能体 2：个性化学习路径规划", expanded=True):
        p2 = f"结合学生特点：{student_data}，以及教材内容摘要：{book_data[:300]}。为他量身定制一个分为【基础铺垫-核心攻坚-拓展实战】三个阶段的学习路径。列出具体要看哪一章、做什么练习。"
        st.write_stream(stream_spark_response(p2, max_tokens=600))
        
    st.markdown("### 📚 基于教材的专属多模态资源生成区")
    tab1, tab2, tab3 = st.tabs(["📝 核心题库与解析", "💻 实操项目案例", "🎬 微课动画分镜"])
    
    with tab1:
        st.info("💡 考评出题员正在根据您的薄弱点自动生成题目...")
        p3 = f"教材内容：{book_data[:500]}。学生基础较弱。请生成3道难度递进的练习题（含单选、多选、实操应用），必须附带详细解析。"
        st.write_stream(stream_spark_response(p3, max_tokens=800))
        
    with tab2:
        st.info("🛠️ 助教智能体为您匹配的实践项目...")
        p4 = f"教材内容：{book_data[:500]}。针对学生的专业需求，设计一个与该教材相关的实战小项目。说明项目背景、任务步骤，并给出一小段核心代码或流程说明。"
        st.write_stream(stream_spark_response(p4, max_tokens=800))
        
    with tab3:
        st.info("🎥 视觉多模态智能体为您转化了晦涩难懂的概念...")
        p5 = f"为了帮该学生直观理解教材内容：{book_data[:300]}。请策划一个1分钟的科普短视频脚本。包含：【画面分镜】和【旁白词】。帮助他视觉化学习。"
        st.write_stream(stream_spark_response(p5, max_tokens=600))
        
    st.balloons()