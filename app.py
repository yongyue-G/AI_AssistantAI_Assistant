import streamlit as st
from api import stream_spark_response, get_silent_response
from utils import extract_text_with_pages, chunk_with_metadata, LightRAG
import plotly.express as px
import pandas as pd

st.set_page_config(page_title="AI个性化学习平台", layout="wide", page_icon="🎓")
# --- [新增] 全局配置区 ---
import os
DEFAULT_BOOK_PATH = r"D:\Github Desktop Repository\AI_AssistantAI_Assistant\人工智能导论 3版 (丁世飞 编著) (Z-Library)(1).pdf"
DEFAULT_BOOK_NAME = "《人工智能导论 (第3版)》- 丁世飞"
@st.cache_resource(show_spinner=False)
def load_rag_system(file_source):
    """缓存 RAG 引擎，避免每次 rerun 都重新索引"""
    pages_data = extract_text_with_pages(file_source)
    chunks = chunk_with_metadata(pages_data)
    engine = LightRAG(chunks)
    return pages_data, engine

def get_pedagogical_strategy(profile):
    """将6维画像转化为具体的智能体指令"""
    strategies = []
    
    # 维度1：知识基础
    if profile["知识基础"] < 40:
        strategies.append("使用非专业人士能听懂的通俗语言，解释每一个出现的专业术语。")
    else:
        strategies.append("使用专业术语，侧重于知识点之间的深层联系。")

    # 维度2：认知风格
    if profile["认知风格"] == "视觉型":
        strategies.append("增加思维导图的层级，在讲义中多使用 Markdown 表格和列表来结构化信息。")
    elif profile["认知风格"] == "实践型":
        strategies.append("讲义要精简，迅速过渡到代码实操案例。")

    # 维度3：学习动力
    if profile["学习动力"] < 50:
        strategies.append("在内容开头增加‘为什么要学这个’的应用场景描述，提高趣味性。")

    # 维度4：易错点偏好
    strategies.append(f"针对学生容易‘{profile['易错点偏好']}’的特点，专门设置一个‘注意！避坑指南’板块。")

    # 维度5：逻辑抽象
    if profile["逻辑抽象"] < 50:
        strategies.append("多使用生活中的实物类比（如把内存比作抽屉），少用数学公式。")

    # 维度6：动手能力
    if profile["动手能力"] > 60:
        strategies.append("在代码案例中提供‘进阶挑战’或‘留白练习’，而不是给全所有代码。")
    else:
        strategies.append("提供详尽的每一行代码注释，并解释运行环境要求。")

    return "\n- ".join(strategies)

# ==========================================
# 【1. 状态初始化：升级为六维画像体系】
# ==========================================
if "phase" not in st.session_state:
    st.session_state.phase = "onboarding"  # 初始阶段：特征收集
if "pdf_data" not in st.session_state:
    st.session_state.pdf_data = [] 
if "rag_engine" not in st.session_state:
    st.session_state.rag_engine = None 
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
# --- [修改] 状态初始化 ---
if "current_book_name" not in st.session_state:
    st.session_state.current_book_name = DEFAULT_BOOK_NAME
if "pdf_data" not in st.session_state:
    st.session_state.pdf_data = [] 
# ... 其他初始化保持不变 ...
# 核心：题目要求的不少于6个维度的动态画像
if "student_profile" not in st.session_state:
    st.session_state.student_profile = {
        "知识基础": 30,      # 数值型 (0-100)
        "认知风格": "未确定", # 文本型 (如：视觉型/实践型)
        "学习动力": 50,      # 数值型
        "易错点偏好": "待分析", # 文本型
        "逻辑抽象": 40,      # 数值型
        "动手能力": 40       # 数值型
    }

if "locked_concept" not in st.session_state:
    st.session_state.locked_concept = ""

# ==========================================
# 【2. 侧边栏：教材注入】
# ==========================================
with st.sidebar:
    st.title("👨‍🏫 智能学习管家")
    st.caption("✨ **教材使用提示**")
    st.caption(f"当前系统默认加载：\n{st.session_state.current_book_name}")
    
    uploaded_file = st.file_uploader("📂 更换教材", type="pdf", label_visibility="collapsed")
    
    # 确定数据源
    target_pdf = None
    if uploaded_file is not None:
        if st.session_state.current_book_name != uploaded_file.name:
            st.session_state.current_book_name = uploaded_file.name
            st.session_state.pdf_data = [] # 标记需要重载
        target_pdf = uploaded_file
    else:
        if st.session_state.current_book_name != DEFAULT_BOOK_NAME:
            st.session_state.current_book_name = DEFAULT_BOOK_NAME
            st.session_state.pdf_data = []
        target_pdf = DEFAULT_BOOK_PATH

    # 执行加载
    if not st.session_state.pdf_data:
        # 注意：这里我们不在 sidebar 里阻塞主界面
        # 我们把加载提示移到主界面或侧边栏下方
        with st.status(f"🚀 正在索引：{st.session_state.current_book_name}...", expanded=False):
            st.write("正在读取 PDF 文本...")
            pdf_data, rag_engine = load_rag_system(target_pdf)
            st.session_state.pdf_data = pdf_data
            st.session_state.rag_engine = rag_engine
            
            st.write("正在唤醒 AI 导师...")
            if not st.session_state.chat_history:
                welcome_prompt = f"当前教材：{st.session_state.current_book_name}。请根据教材内容简介给学生打个招呼，限50字。"
                st.session_state.chat_history = [{"role": "assistant", "content": get_silent_response(welcome_prompt)}]
            
        st.rerun()

    st.success(f"✅ 正在使用：{st.session_state.current_book_name}")
# ==========================================
# 【3. 主界面布局：由单流转向 Tabs 空间】
# ==========================================
st.title("🎓 基于多智能体协同的个性化学习系统")

# 定义四个功能选项卡，对应赛题的核心功能
tab_profile, tab_resource, tab_practice, tab_eval = st.tabs([
    "👤 动态学情画像", 
    "📚 多模态资源生成", 
    "💻 实验实操空间", 
    "📈 学习效果评估"
])

# --- TAB 1: 画像构建 (当前重点) ---
# --- TAB 1: 画像构建 ---
with tab_profile:
    col_chat, col_radar = st.columns([1, 1])
    
    with col_chat:
        st.markdown("### 💬 对话式特征抽取")
        chat_container = st.container(height=450)
        with chat_container:
            for msg in st.session_state.chat_history:
                st.chat_message(msg["role"]).write(msg["content"])
        
        # --- 核心修复：确保输入逻辑在 tab 内部且变量先定义后使用 ---
        if user_input := st.chat_input("告诉导师你的情况..."):
            if not st.session_state.pdf_data:
                st.warning("⚠️ 请先确保教材已成功装载")
            else:
                # 1. 立即显示用户输入
                st.session_state.chat_history.append({"role": "user", "content": user_input})
                with chat_container:
                    st.chat_message("user").write(user_input)

                # 2. 准备历史字符串
                history_str = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.chat_history])
                
                # --- [重点：先定义变量] ---
                profile_extract_prompt = f"""
                你是学情分析智能体。请分析以下对话，提取并更新学生的6维画像。
                对话历史：{history_str}
                当前画像：{st.session_state.student_profile}
                
                任务要求：严格输出JSON格式，包含：知识基础(0-100), 学习动力(0-100), 进阶速度(0-100), 逻辑抽象(0-100), 动手能力(0-100), 认知风格, 易错点偏好。
                """
                
                with st.spinner("🧠 智能体正在分析您的特征..."):
                    import json
                    import re
                    # 现在调用就不会报 NameError 了
                    raw_json = get_silent_response(profile_extract_prompt)
                    
                    match = re.search(r'\{.*\}', raw_json, re.DOTALL)
                    if match:
                        try:
                            new_profile = json.loads(match.group())
                            st.session_state.student_profile.update(new_profile)
                        except Exception as e:
                            print(f"JSON解析异常: {e}")
                
                # --- 智能体 2：导师回复 ---
                reply_prompt = f"""
                你是AI导师。基于画像{st.session_state.student_profile}和教材《{st.session_state.current_book_name}》，
                热情鼓励学生并引导知识点，限60字。
                """
                with chat_container.chat_message("assistant"):
                    ai_reply = st.write_stream(stream_spark_response(reply_prompt, max_tokens=150))
                
                st.session_state.chat_history.append({"role": "assistant", "content": ai_reply})
                st.rerun()

    # 右侧雷达图（保持原样，注意缩进要在 with tab_profile 下）
    with col_radar:
        st.markdown("### 📊 实时学生画像 (6D)")
        plot_data = {k: v for k, v in st.session_state.student_profile.items() if isinstance(v, (int, float))}
        df_radar = pd.DataFrame(dict(r=list(plot_data.values()), theta=list(plot_data.keys())))
        
        fig = px.line_polar(df_radar, r='r', theta='theta', line_close=True)
        fig.update_traces(fill='toself', line_color='#1f77b4')
        fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])))
        st.plotly_chart(fig, use_container_width=True)
        
        st.info(f"**当前认知风格偏好**：{st.session_state.student_profile['认知风格']}")
        st.info(f"**易错点分析**：{st.session_state.student_profile['易错点偏好']}")

# --- TAB 2: 多模态资源生成 ---
with tab_resource:
    st.markdown("### 🤖 多智能体协同工作台")
    
    # 顶部状态卡片：展示当前适配策略
    with st.expander("🎯 查看当前的个性化适配策略", expanded=False):
        current_strategy = get_pedagogical_strategy(st.session_state.student_profile)
        st.write(f"系统已根据您的 6D 画像制定了以下策略：\n\n- {current_strategy}")

    # 输入区域
    target_concept = st.text_input("🎯 请输入要攻克的知识点：", value=st.session_state.locked_concept)
    
    # 启动按钮
    if st.button("🚀 启动多智能体协作生成", type="primary"):
        if not st.session_state.pdf_data:
            st.error("⚠️ 请先在左侧侧边栏加载教材知识库！")
        elif not target_concept:
            st.warning("⚠️ 请输入具体的知识点名称。")
        else:
            # 锁定当前目标
            st.session_state.locked_concept = target_concept
            st.session_state.generated_resources = {} # 清空缓存

            # --- [进度追踪机制] 满足非功能性需求4 ---
            with st.status(f"🌐 正在为【{target_concept}】编排多智能体工作流...", expanded=True) as status:
                
                # 1. RAG 检索官 (import streamlit as st
from api import stream_spark_response, get_silent_response
from utils import extract_text_with_pages, chunk_with_metadata, LightRAG
import plotly.express as px
import pandas as pd
import os
import json
import re

# ==========================================
# 全局配置与缓存加载
# ==========================================
st.set_page_config(page_title="AI 个性化学习引擎", layout="wide")

DEFAULT_BOOK_PATH = r"D:\Github Desktop Repository\AI_AssistantAI_Assistant\人工智能导论 3版 (丁世飞 编著) (Z-Library)(1).pdf"
DEFAULT_BOOK_NAME = "《人工智能导论 (第3版)》"

@st.cache_resource(show_spinner=False)
def load_rag_system(file_source):
    pages_data = extract_text_with_pages(file_source)
    chunks = chunk_with_metadata(pages_data)
    engine = LightRAG(chunks)
    return pages_data, engine

def get_pedagogical_strategy(profile):
    strategies = []
    if profile["知识基础"] < 40:
        strategies.append("使用非专业人士能听懂的通俗语言，解释每一个出现的专业术语。")
    else:
        strategies.append("使用专业术语，侧重于知识点之间的深层联系。")
    if profile["认知风格"] == "视觉型":
        strategies.append("增加思维导图的层级，多使用表格和列表来结构化信息。")
    elif profile["认知风格"] == "实践型":
        strategies.append("讲义要精简，迅速过渡到实操案例。")
    if profile["学习动力"] < 50:
        strategies.append("在内容开头增加应用场景描述，提高趣味性。")
    strategies.append(f"针对学生容易‘{profile['易错点偏好']}’的特点，设置‘避坑指南’板块。")
    if profile["逻辑抽象"] < 50:
        strategies.append("多使用生活中的实物类比，少用数学公式。")
    if profile["动手能力"] > 60:
        strategies.append("在代码案例中提供‘进阶挑战’，不提供全量保姆级代码。")
    else:
        strategies.append("提供详尽的逐行代码注释。")
    return "\n- ".join(strategies)

# ==========================================
# 状态初始化
# ==========================================
if "current_book_name" not in st.session_state:
    st.session_state.current_book_name = DEFAULT_BOOK_NAME
if "pdf_data" not in st.session_state:
    st.session_state.pdf_data = [] 
if "rag_engine" not in st.session_state:
    st.session_state.rag_engine = None 
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "locked_concept" not in st.session_state:
    st.session_state.locked_concept = ""
if "generated_resources" not in st.session_state:
    st.session_state.generated_resources = {}

if "student_profile" not in st.session_state:
    st.session_state.student_profile = {
        "知识基础": 30, "认知风格": "视觉型", "学习动力": 50,
        "易错点偏好": "概念混淆", "逻辑抽象": 40, "动手能力": 40
    }

# ==========================================
# 侧边栏：知识库管理
# ==========================================
with st.sidebar:
    st.subheader("知识库管理")
    st.caption(f"当前挂载：{st.session_state.current_book_name}")
    
    uploaded_file = st.file_uploader("装载新教材 (PDF)", type="pdf", label_visibility="collapsed")
    target_pdf = uploaded_file if uploaded_file else DEFAULT_BOOK_PATH
    
    if uploaded_file and st.session_state.current_book_name != uploaded_file.name:
        st.session_state.current_book_name = uploaded_file.name
        st.session_state.pdf_data = [] 
    elif not uploaded_file and st.session_state.current_book_name != DEFAULT_BOOK_NAME:
        st.session_state.current_book_name = DEFAULT_BOOK_NAME
        st.session_state.pdf_data = []

    if not st.session_state.pdf_data:
        with st.status(f"正在索引知识库...", expanded=False):
            st.write("读取文本特征...")
            pdf_data, rag_engine = load_rag_system(target_pdf)
            st.session_state.pdf_data = pdf_data
            st.session_state.rag_engine = rag_engine
            
            if not st.session_state.chat_history:
                welcome_prompt = f"教材：{st.session_state.current_book_name}。用专业、简洁的语言打招呼，限50字。"
                st.session_state.chat_history = [{"role": "assistant", "content": get_silent_response(welcome_prompt, 100)}]
        st.rerun()

    st.success("知识库引擎已就绪")

# ==========================================
# 主体功能区
# ==========================================
st.title("多智能体协同学习空间")

tab_profile, tab_resource, tab_practice, tab_eval = st.tabs([
    "学情画像建模", "多模态资源生成", "实操沙箱", "动态评测闭环"
])

# --- TAB 1: 画像构建 ---
with tab_profile:
    col_chat, col_radar = st.columns([1, 1])
    
    with col_chat:
        st.markdown("#### 对话式学情诊断")
        chat_container = st.container(height=400)
        with chat_container:
            for msg in st.session_state.chat_history:
                st.chat_message(msg["role"]).write(msg["content"])
        
        if user_input := st.chat_input("描述你的学习困惑或偏好..."):
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            with chat_container:
                st.chat_message("user").write(user_input)

            history_str = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.chat_history])
            
            profile_extract_prompt = f"""
            任务：提取学生6维画像。
            历史：{history_str}
            当前画像：{st.session_state.student_profile}
            严格输出JSON格式，包含：知识基础(0-100), 学习动力(0-100), 进阶速度(0-100), 逻辑抽象(0-100), 动手能力(0-100), 认知风格, 易错点偏好。
            """
            with st.spinner("更新认知模型中..."):
                raw_json = get_silent_response(profile_extract_prompt, 300)
                match = re.search(r'\{.*\}', raw_json, re.DOTALL)
                if match:
                    try:
                        st.session_state.student_profile.update(json.loads(match.group()))
                    except:
                        pass
            
            reply_prompt = f"你是专业导师。基于画像{st.session_state.student_profile}，简洁地回复学生并引导知识点，限60字。"
            with chat_container.chat_message("assistant"):
                ai_reply = st.write_stream(stream_spark_response(reply_prompt, 150))
            
            st.session_state.chat_history.append({"role": "assistant", "content": ai_reply})
            st.rerun()

    with col_radar:
        st.markdown("#### 实时雷达分析")
        plot_data = {k: v for k, v in st.session_state.student_profile.items() if isinstance(v, (int, float))}
        df_radar = pd.DataFrame(dict(r=list(plot_data.values()), theta=list(plot_data.keys())))
        fig = px.line_polar(df_radar, r='r', theta='theta', line_close=True)
        fig.update_traces(fill='toself', line_color='#2E86C1')
        fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)
        
        st.caption(f"**认知风格**：{st.session_state.student_profile['认知风格']} | **易错点特征**：{st.session_state.student_profile['易错点偏好']}")

# --- TAB 2: 多模态资源生成 (排版重大优化) ---
with tab_resource:
    st.markdown("#### 智能体编排与内容生成")
    
    current_strategy = get_pedagogical_strategy(st.session_state.student_profile)
    with st.expander("查看当前个性化生成策略", expanded=False):
        st.write(current_strategy)

    col_input, col_btn = st.columns([4, 1])
    with col_input:
        target_concept = st.text_input("输入学习目标 (知识点)：", value=st.session_state.locked_concept, label_visibility="collapsed", placeholder="例如：反向传播算法")
    with col_btn:
        generate_btn = st.button("生成专属资源包", type="primary", use_container_width=True)

    if generate_btn:
        if not target_concept:
            st.warning("请指定知识点。")
        else:
            st.session_state.locked_concept = target_concept
            st.session_state.generated_resources = {}

            with st.status(f"多智能体工作流执行中：{target_concept}", expanded=True) as status:
                st.write("[RAG引擎] 检索学术背景...")
                contexts = st.session_state.rag_engine.search(target_concept, top_k=3)
                context_text = "\n".join([c["text"] for c in contexts]) if contexts else "无直接参考，启动知识库扩展。"
                
                # 注意：这里我们给讲义和代码传入了 2048 的最大字数，彻底解决截断问题！
                st.write("[教研智能体] 编写讲义...")
                doc_prompt = f"知识点：{target_concept}。教材：{context_text}。策略：{current_strategy}。使用Markdown输出全面详尽的教学文档。"
                st.session_state.generated_resources['doc'] = get_silent_response(doc_prompt, max_tokens=2048)
                
                st.write("[视觉智能体] 提取逻辑树...")
                mindmap_prompt = f"根据讲义生成 Mermaid 思维导图代码 (graph TD)。内容：{st.session_state.generated_resources['doc']}。仅输出代码。"
                raw_mermaid = get_silent_response(mindmap_prompt, max_tokens=800)
                st.session_state.generated_resources['mindmap'] = raw_mermaid.replace("```mermaid", "").replace("```", "").strip()
                
                st.write("[实操智能体] 定制代码沙箱...")
                code_prompt = f"为【{target_concept}】编写 Python 案例。要求：{current_strategy}。务必保证代码完整性。"
                st.session_state.generated_resources['code'] = get_silent_response(code_prompt, max_tokens=2048)
                
                st.write("[评测智能体] 准备检验套件...")
                current_level = "零基础" if st.session_state.student_profile["知识基础"] < 50 else "进阶"
                quiz_prompt = f"知识点：{context_text}。水平：{current_level}。生成2道单选题，不可包含答案或多套对比。"
                st.session_state.generated_resources['quiz'] = get_silent_response(quiz_prompt, max_tokens=600)
                
                status.update(label="资源生成完毕", state="complete", expanded=False)

    # 布局大改造：使用嵌套子标签页，释放空间
    if st.session_state.generated_resources:
        st.divider()
        st.markdown(f"### {target_concept} 学习包")
        
        res_tab_doc, res_tab_code, res_tab_map, res_tab_quiz = st.tabs(["📑 深度讲义", "💻 代码工坊", "🗺️ 思维导图", "📝 快速自测"])
        
        with res_tab_doc:
            st.markdown(st.session_state.generated_resources.get('doc', '生成失败'))
        with res_tab_code:
            st.code(st.session_state.generated_resources.get('code', ''), language='python')
        with res_tab_map:
            m_code = st.session_state.generated_resources.get('mindmap', '')
            if m_code:
                st.markdown(f"```mermaid\n{m_code}\n```")
        with res_tab_quiz:
            st.markdown(st.session_state.generated_resources.get('quiz', ''))
        
        st.caption(f"数据溯源：本资源包核心知识点提取自知识库文件。")

# --- TAB 3: 实验实操空间 ---
with tab_practice:
    st.markdown("#### 代码审查与优化")
    
    if 'code' not in st.session_state.generated_resources:
        st.info("请先在 [多模态资源生成] 中生成实操案例。")
    else:
        prac_col1, prac_col2 = st.columns([1, 1])
        with prac_col1:
            st.caption("参考实现架构")
            st.code(st.session_state.generated_resources['code'], language="python")
            
        with prac_col2:
            st.caption("沙箱练习环境")
            user_code = st.text_area("在此键入代码：", height=400, label_visibility="collapsed")
            if st.button("发起 Code Review", type="secondary"):
                if user_code.strip():
                    with st.spinner("执行代码规范审查..."):
                        review_prompt = f"参考代码：{st.session_state.generated_resources['code']}。学生代码：{user_code}。指出Bug，评估风格，限150字。"
                        st.markdown(f"> **审查结果**：\n{get_silent_response(review_prompt, 400)}")

# --- TAB 4: 学习效果评估闭环 ---
with tab_eval:
    st.markdown("#### 评估与画像重塑")
    
    if 'quiz' not in st.session_state.generated_resources:
        st.info("请先生成测评套件。")
    else:
        st.markdown(st.session_state.generated_resources['quiz'])
        
        with st.form("quiz_form"):
            user_answer = st.text_area("答题区：", height=100)
            if st.form_submit_button("提交判卷并同步画像"):
                if user_answer.strip():
                    with st.status("执行学情分析...", expanded=True) as status:
                        contexts = st.session_state.rag_engine.search(st.session_state.locked_concept, top_k=2)
                        context_text = "\n".join([c["text"] for c in contexts]) if contexts else ""
                        current_level = "零基础" if st.session_state.student_profile["知识基础"] < 50 else "进阶"
                        
                        grade_prompt = f"水平：{current_level}。题目：{st.session_state.generated_resources['quiz']}。依据：{context_text}。答案：{user_answer}。给出评分和解析，绝不分类讨论，限100字。"
                        grading_feedback = get_silent_response(grade_prompt, 300)
                        
                        update_prompt = f"旧画像：{st.session_state.student_profile}。表现：{grading_feedback}。根据表现好坏调整数值，提取易错点。严格返回完整6维JSON。"
                        raw_json = get_silent_response(update_prompt, 300)
                        match = re.search(r'\{.*\}', raw_json, re.DOTALL)
                        if match:
                            try:
                                st.session_state.student_profile.update(json.loads(match.group()))
                            except:
                                pass
                        status.update(label="画像重塑完成", state="complete", expanded=False)
                    
                    st.success(grading_feedback)
                    st.info(f"系统已更新您的特征数据。当前易错点记录：{st.session_state.student_profile['易错点偏好']}")防幻觉核心)
                st.write("🔍 [RAG 检索官] 正在从《人工智能导论》中检索学术依据...")
                contexts = st.session_state.rag_engine.search(target_concept, top_k=3)
                context_text = "\n".join([c["text"] for c in contexts]) if contexts else "教材中未找到直接定义，转入通用知识增强模式。"
                
                # 2. 教研智能体 (深度定制化讲义)
                st.write("📝 [教研智能体] 正在应用个性化策略撰写讲义...")
                doc_prompt = f"""
                你是教研智能体。目标知识点：{target_concept}。
                教材依据：{context_text}。
                
                请严格遵循以下【个性化适配策略】进行创作：
                {current_strategy}
                
                要求：使用 Markdown 格式，包含标题、正文、避坑指南。
                """
                st.session_state.generated_resources['doc'] = get_silent_response(doc_prompt)
                
                # 3. 视觉智能体 (Mermaid 图表生成)
                st.write("🎨 [视觉智能体] 正在根据讲义逻辑绘制思维导图...")
                mindmap_prompt = f"""
                基于以下讲义内容，生成一段 Mermaid 格式的思维导图代码 (graph TD)。
                认知风格：{st.session_state.student_profile['认知风格']}。如果是视觉型，请增加层级细节。
                讲义内容：{st.session_state.generated_resources['doc']}
                注意：只输出代码，严禁任何废话。
                """
                raw_mermaid = get_silent_response(mindmap_prompt)
                st.session_state.generated_resources['mindmap'] = raw_mermaid.replace("```mermaid", "").replace("```", "").strip()
                
                # 4. 实操智能体 (代码案例定制)
                st.write("💻 [实操智能体] 正在根据您的动手能力准备案例...")
                code_prompt = f"""
                为知识点【{target_concept}】准备一个 Python 案例。
                策略要求：{current_strategy}
                注意：重点关注代码注释的详尽程度和挑战性设置。
                """
                st.session_state.generated_resources['code'] = get_silent_response(code_prompt)
                
                # 5. 测评智能体 (动态题库生成)
                st.write("🧑‍🏫 [测评智能体] 正在生成针对性练习题...")
                current_level = "零基础入门" if st.session_state.student_profile["知识基础"] < 50 else "进阶专家"

                quiz_prompt = f"""
                基于教材原文：{context_text}。
                当前学生水平：{current_level}。
                画像特征：认知风格为{st.session_state.student_profile['认知风格']}。

                任务：请【仅生成一套】适合该水平的练习题（含2道单选题）。
                要求：严禁提供不同版本的对比，直接输出题目内容。
                """
                st.session_state.generated_resources['quiz'] = get_silent_response(quiz_prompt)
                
                status.update(label="✅ 资源包生成完毕！已实现全维度画像适配。", state="complete", expanded=False)

            # --- [卡片化展示展示区] 满足非功能性需求1 ---
            st.divider()
            st.markdown(f"## 🎁 个性化学习包：{target_concept}")
            
            res_col1, res_col2 = st.columns([1.2, 1])
            
            with res_col1:
                with st.container(border=True):
                    st.markdown("### 📑 专属讲义")
                    st.markdown(st.session_state.generated_resources.get('doc', ''))
                
                with st.container(border=True):
                    st.markdown("### 💻 代码工坊")
                    st.code(st.session_state.generated_resources.get('code', ''), language='python')
                    
            with res_col2:
                with st.container(border=True):
                    st.markdown("### 🗺️ 逻辑图谱 (思维导图)")
                    m_code = st.session_state.generated_resources.get('mindmap', '')
                    if m_code:
                        st.markdown(f"```mermaid\n{m_code}\n```")
                    else:
                        st.warning("思维导图生成中或格式暂不支持。")
                
                with st.container(border=True):
                    st.markdown("### 📝 快速自测")
                    st.write(st.session_state.generated_resources.get('quiz', ''))
            
            st.caption(f"🔗 **溯源信息**：本资源包由多智能体协作生成。核心知识点提取自：{st.session_state.current_book_name}")
# --- TAB 3: 实验实操空间 (代码沙箱与Review) ---
with tab_practice:
    st.markdown("### 💻 沉浸式代码实操空间")
    
    if not st.session_state.locked_concept or 'code' not in st.session_state.generated_resources:
        st.info("💡 请先在 [多模态资源生成] 页面锁定知识点并生成专属代码案例。")
    else:
        st.caption(f"当前实操目标：实现【{st.session_state.locked_concept}】的核心逻辑。")
        
        # 个性化展示：根据动手能力决定是“全量代码”还是“填空题”
        practice_col1, practice_col2 = st.columns([1, 1])
        
        with practice_col1:
            st.markdown("#### 👨‍🏫 导师给出的参考架构")
            st.code(st.session_state.generated_resources['code'], language="python")
            
        with practice_col2:
            st.markdown("#### ✍️ 你的实战沙箱")
            user_code = st.text_area("在此编写或粘贴你的代码实现，支持 Python:", height=300, 
                                     placeholder="# 在这里写下你的代码...\n# 写完后点击下方按钮呼叫代码审查智能体")
            
            if st.button("🛠️ 呼叫代码审查 (Code Review)", type="secondary"):
                if not user_code.strip():
                    st.warning("请先输入你的代码！")
                else:
                    with st.spinner("🕵️ [代码审查智能体] 正在逐行分析你的代码..."):
                        review_prompt = f"""
                        你是严厉但友好的代码审查智能体。
                        标准参考代码：{st.session_state.generated_resources['code']}
                        学生的实现：{user_code}
                        
                        请进行 Code Review：
                        1. 找出潜在的 Bug 或逻辑错误。
                        2. 评估代码风格。
                        3. 结合学生的动手能力评分（当前{st.session_state.student_profile['动手能力']}分），给出下一步建议。
                        限 150 字以内。
                        """
                        review_result = get_silent_response(review_prompt)
                        st.success("✅ 审查完成！")
                        st.markdown(f"> **审查报告：**\n{review_result}")

# --- TAB 4: 学习效果评估与动态闭环 (加分项核心) ---
with tab_eval:
    st.markdown("### 📈 动态评估与画像进化")
    st.caption("完成这里的测试，系统将根据你的表现自动刷新 6D 学习画像。")
    
    if not st.session_state.locked_concept or 'quiz' not in st.session_state.generated_resources:
        st.info("💡 请先在 [多模态资源生成] 页面生成测试题。")
    else:
        st.markdown("#### 📝 随堂测验")
        st.info(st.session_state.generated_resources['quiz'])
        
        # 使用表单管理评测提交
        with st.form("quiz_form"):
            user_answer = st.text_area("请输入你的答案（标明题号）：", height=150)
            submit_eval = st.form_submit_button("批改并更新我的画像 🚀")
            
            if submit_eval:
                if not user_answer.strip():
                    st.warning("答案不能为空哦。")
                else:
                    with st.status("🧑‍🏫 [测评智能体] 正在交叉比对并重塑您的画像...", expanded=True) as status:
                        st.write("1. 正在调取教材标准答案进行批改...")
                        # 获取教材原文作为判卷标准 (防幻觉判卷)
                        contexts = st.session_state.rag_engine.search(st.session_state.locked_concept, top_k=2)
                        context_text = "\n".join([c["text"] for c in contexts]) if contexts else ""
                        
                        grade_prompt = f"""
                        你是铁面无私的测评智能体。
                        当前学生水平判定为：{current_level}。
                        测试题目：{st.session_state.generated_resources['quiz']}
                        原书参考知识点：{context_text}
                        学生答案：{user_answer}

                        任务：
                        1. 给出评分 (0-100)。
                        2. 【仅针对当前学生水平】指出答错的地方并解析。
                        严禁输出“针对小白/专家”的分类讨论，直接给出对该学生的批改结果。
                        要求总字数不超过 100 字。
                        """
                        grading_feedback = get_silent_response(grade_prompt)
                        st.write("2. 正在根据答题表现计算画像漂移量...")
                        
                        # 核心闭环：让大模型根据答题结果直接输出最新的 JSON 画像
                        update_prompt = f"""
                        你是学情分析智能体。学生刚完成了一次测验。
                        他的旧画像：{st.session_state.student_profile}
                        批改结果：{grading_feedback}
                        
                        请判断：如果表现好，请提高“知识基础”和“学习动力”；如果表现差，请降低“进阶速度”，并提取他做错的共性填入“易错点偏好”。
                        严格返回 JSON，格式必须为：
                        {{
                            "知识基础": 分值, "学习动力": 分值, "进阶速度": 分值, 
                            "逻辑抽象": 分值, "动手能力": 分值, 
                            "认知风格": "当前风格", "易错点偏好": "简短描述"
                        }}
                        """
                        import json, re
                        raw_json = get_silent_response(update_prompt)
                        match = re.search(r'\{.*\}', raw_json, re.DOTALL)
                        if match:
                            try:
                                new_profile = json.loads(match.group())
                                st.session_state.student_profile.update(new_profile)
                                st.write("3. 动态画像更新成功！")
                            except Exception as e:
                                pass
                                
                        status.update(label="✅ 评估完成！能力雷达已重构。", state="complete", expanded=False)
                    
                    st.divider()
                    st.markdown("#### 🎯 批改结果")
                    st.success(grading_feedback)
                    st.warning(f"**您的学情画像已产生漂移！**\n系统记录到您最新的易错点为：**{st.session_state.student_profile['易错点偏好']}**。请返回【Tab 1: 动态学情画像】查看最新雷达图，或在下一次生成资源时体验系统为您做出的调整。")