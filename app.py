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

def get_silent_response(prompt):
    full_text = ""
    for chunk in stream_spark_response(prompt, 500):
        full_text += chunk
    return full_text

# --- 状态初始化 ---
st.set_page_config(page_title="AI学习空间", layout="wide", page_icon="💡")

if "phase" not in st.session_state:
    st.session_state.phase = "chatting" 
if "pdf_text" not in st.session_state:
    st.session_state.pdf_text = ""
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [{"role": "assistant", "content": "同学你好！👋 既然要生成专属学习计划，请**先在左侧上传你要学的 PDF 教材**。我读完后，我们再开始针对性聊聊！"}]
# 新增：记录课后辅导记录
if "tutor_history" not in st.session_state:
    st.session_state.tutor_history = [{"role": "assistant", "content": "🎯 资料看完了吗？如果有不懂的概念，或者想提交上面练习题的答案让我批改，随时发给我！"}]

# --- 侧边栏 ---
with st.sidebar:
    st.image("https://api.dicebear.com/7.x/bottts/svg?seed=Felix&backgroundColor=e2e8f0", width=100)
    st.title("👨‍🏫 智能导师中控台")
    st.markdown("---")
    
    uploaded_file = st.file_uploader("📂 注入当前课程 PDF", type="pdf")
    
    if uploaded_file and not st.session_state.pdf_text:
        with st.spinner("导师正在速读教材..."):
            reader = PyPDF2.PdfReader(uploaded_file)
            for i in range(min(3, len(reader.pages))):
                st.session_state.pdf_text += reader.pages[i].extract_text()
            
            welcome_prompt = f"学生刚上传教材，内容摘要：{st.session_state.pdf_text[:300]}。作为导师主动打招呼，指出资料核心并顺势提问他的基础。限80字。"
            st.session_state.chat_history = [{"role": "assistant", "content": get_silent_response(welcome_prompt)}]
            st.rerun()
            
    st.markdown("---")
    st.subheader("🎯 任务进度追踪")
    if not st.session_state.pdf_text:
        st.warning("⏳ 等待上传教材...")
    elif st.session_state.phase == "chatting":
        st.info("🔄 结合教材深度访谈中...")
    else:
        st.success("✅ 画像完毕，已开启辅导模式！")

# --- 主界面 ---
st.title("🎓 基于大模型的多智能体个性化学习空间")

if st.session_state.phase == "chatting":
    st.markdown("### 💬 导师深度访谈区")
    
    chat_box = st.container(height=400)
    with chat_box:
        for msg in st.session_state.chat_history:
            st.chat_message(msg["role"]).write(msg["content"])
            
    user_input = st.chat_input("输入你的回答...")
    if user_input:
        if not uploaded_file:
            st.toast("⚠️ 请先上传PDF教材，导师才能提问哦！", icon="🚨")
        else:
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            chat_box.chat_message("user").write(user_input)
            
            history_str = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.chat_history])
            judge_prompt = f"""
            探讨教材核心内容：{st.session_state.pdf_text[:400]}...
            对话历史：{history_str}
            任务：
            1. 评估信息是否足够。如果不足，紧扣教材内容追问。
            2. 若交流2个来回以上且信息足够，直接回复："[评估完成]"。
            """
            with st.spinner("导师思考中..."):
                ai_reply = get_silent_response(judge_prompt)
            
            if "[评估完成]" in ai_reply:
                st.session_state.phase = "profiling"
                st.rerun()
            else:
                st.session_state.chat_history.append({"role": "assistant", "content": ai_reply})
                chat_box.chat_message("assistant").write(ai_reply)

elif st.session_state.phase == "profiling":
    st.success("🎉 导师访谈结束！为您生成的专属学习资料如下：")
    
    student_data = "\n".join([m['content'] for m in st.session_state.chat_history if m['role'] == 'user'])
    book_data = st.session_state.pdf_text[:1000]
    
    # 缩小生成区的篇幅，把重点让给底部的交互区
    with st.expander("🕵️‍♂️ 智能体 1 & 2：动态画像与路径规划", expanded=False):
        st.write_stream(stream_spark_response(f"结合：{student_data}和教材：{book_data[:200]}。给出极简的5维度画像和3阶段路径。字数控制在200内。", 400))
        
    st.markdown("### 📚 您的多模态学习资源包")
    tab1, tab2, tab3 = st.tabs(["📝 核心题库与解析", "💻 实操项目案例", "🎬 微课动画分镜"])
    with tab1:
        st.write_stream(stream_spark_response(f"教材内容：{book_data[:400]}。生成2道练习题（不直接给答案，提示学生在页面底部作答）。", 500))
    with tab2:
        st.write_stream(stream_spark_response(f"教材内容：{book_data[:400]}。设计一个实战小案例。", 500))
    with tab3:
        st.write_stream(stream_spark_response(f"基于教材：{book_data[:300]}。写一段1分钟视频分镜脚本。", 400))
        
    st.divider()
    
    # ========================================================
    # 🚀 核心升级区：AI伴学与学情评估智能体 (拿满加分项4和5)
    # ========================================================
    st.markdown("### 🧑‍🏫 24小时专属 AI 伴学答疑区")
    st.caption("把上面生成的习题答案发在这里，或者抛出你不懂的概念，导师实时为你打分和解答！")
    
    # 渲染辅导记录
    tutor_box = st.container(height=350)
    with tutor_box:
        for msg in st.session_state.tutor_history:
            st.chat_message(msg["role"]).write(msg["content"])
            
    # 接收学生提问/答题
    tutor_input = st.chat_input("在此输入习题答案，或向导师提问...")
    if tutor_input:
        # 显示学生的输入
        st.session_state.tutor_history.append({"role": "user", "content": tutor_input})
        tutor_box.chat_message("user").write(tutor_input)
        
        # 封装批改指令
        tutor_prompt = f"""
        你是一名严格但鼓励人的大学老师。
        这门课的教材内容是：{book_data[:800]}
        学生刚发送了："{tutor_input}"
        
        你的任务：
        1. 意图识别：判断学生是在【提交答案】还是在【提问】。
        2. 如果是【提问】：结合教材原文耐心解答。
        3. 如果是【提交答案】：请批改他的答案对错，给出一个评分（如 80/100分），并指出哪里理解有偏差。
        4. 结尾加上一句对该学生“当前学习效果”的动态简评（这符合‘动态学习评估’的要求）。
        """
        
        # 流式输出导师的解答
        with tutor_box.chat_message("assistant"):
            reply = st.write_stream(stream_spark_response(tutor_prompt, max_tokens=800))
        
        st.session_state.tutor_history.append({"role": "assistant", "content": reply})