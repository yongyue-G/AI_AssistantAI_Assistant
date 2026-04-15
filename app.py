import streamlit as st
from api import stream_spark_response, get_silent_response
from utils import extract_text_with_pages, chunk_with_metadata, LightRAG
import plotly.express as px
import pandas as pd
import re
# app.py 顶部初始化
if "practice_completed" not in st.session_state:
    st.session_state.practice_completed = False # 初始状态为未完成
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
    """🧠 7维全数值画像策略引擎：精简指令版"""
    strategies = []
    
    # 维度1：知识基础
    if profile["知识基础"] < 40:
        strategies.append("用通俗类比解释术语，降级难度。")
    else:
        strategies.append("用专业术语探讨深层原理。")

    # 维度2：概念理解深度 (替换 认知风格)
    if profile["概念理解深度"] < 50:
        strategies.append("侧重‘是什么’的基础定义，多给直观例子。")
    else:
        strategies.append("侧重‘为什么’和数学推导，探讨底层逻辑。")

    # 维度3：学习动力
    if profile["学习动力"] < 50:
        strategies.append("开头强调该知识点的实战高薪应用场景。")

    # 维度5：逻辑抽象
    if profile["逻辑抽象"] < 50:
        strategies.append("禁用长公式，用流程图或实物类比（如抽屉原理）。")

    # 维度6：动手能力
    if profile["动手能力"] > 60:
        strategies.append("代码案例提供核心缺省的‘进阶挑战’。")
    else:
        strategies.append("提供详细代码及环境注释。")
        
    # 维度7：进阶速度
    if profile["进阶速度"] > 70:
        strategies.append("增加扩展阅读或跨知识点串联。")

    return "\n- ".join(strategies)

# ==========================================
# 【1. 状态初始化：升级为画像体系】
# ==========================================
if "student_profile" not in st.session_state:
    st.session_state.student_profile = {
        "知识基础": 50, "学习动力": 50, "进阶速度": 50, 
        "逻辑抽象": 50, "动手能力": 50, "概念理解深度": 50
    }

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- 报错的核心就在这里：必须初始化这个字典 ---
if "generated_resources" not in st.session_state:
    st.session_state.generated_resources = {} 

if "locked_concept" not in st.session_state:
    st.session_state.locked_concept = ""

if "practice_completed" not in st.session_state:
    st.session_state.practice_completed = False

if "pdf_data" not in st.session_state:
    st.session_state.pdf_data = None
if "current_book_name" not in st.session_state:
    # 设置一个默认值，比如你正在使用的教材名称
    st.session_state.current_book_name = "《人工智能导论》（第3版）- 丁世飞" 



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

# --- TAB 1: 画像构建 (修正版：解决雷达不刷新与智能体胡说八道) ---
with tab_profile:
    col_chat, col_radar = st.columns([1, 1])
    
    with col_chat:
        st.markdown("### 💬 对话式特征抽取")
        chat_container = st.container(height=450)
        with chat_container:
            for msg in st.session_state.chat_history:
                st.chat_message(msg["role"]).write(msg["content"])
        
        if user_input := st.chat_input("告诉导师你的情况..."):
            if not st.session_state.pdf_data:
                st.warning("⚠️ 请先确保教材已成功装载")
            else:
                # 步骤 A: 立即显示用户输入
                st.session_state.chat_history.append({"role": "user", "content": user_input})
                with chat_container:
                    st.chat_message("user").write(user_input)

                # 步骤 B: 准备历史上下文
                history_str = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.chat_history[-5:]]) # 取最近5轮
                
                # 步骤 C: 【画像抽取智能体】优先执行，确保后续导师能拿到最新数据
                profile_extract_prompt = f"""
                你是学情分析智能体。请分析对话并更新学生的6维画像数值（0-100）：
                对话历史：{history_str}
                当前画像：{st.session_state.student_profile}

                【维度定义】:
                1. 概念理解深度：学生是问“是什么”（低深度）还是问“为什么/怎么做”（高深度）。

                任务要求：严格输出 JSON，禁止废话：
                {{
                "知识基础": 数字, "学习动力": 数字, "进阶速度": 数字, 
                "逻辑抽象": 数字, "动手能力": 数字,  "概念理解深度": 数字
                }}
                """
                
                with st.spinner("🧠 智能体正在解析特征..."):
                    import json, re
                    raw_json = get_silent_response(profile_extract_prompt, max_tokens=250)
                    match = re.search(r'\{.*\}', raw_json, re.DOTALL)
                    if match:
                        try:
                            # 更新本地状态
                            new_data = json.loads(match.group())
                            st.session_state.student_profile.update(new_data)
                        except: pass

                # 步骤 D: 【导师智能体】根据“已经更新”的画像进行回复
                # 增加“拒绝同学们”指令，改用私人对话语气
                reply_prompt = f"""
                角色：你是《{st.session_state.current_book_name}》的专属陪伴式导师。
                上下文：{history_str}
                当前学情数据：{st.session_state.student_profile}

                指令要求：
                1. 【拒绝模板化】：严禁使用“同学们”、“欢迎来到”等客套废话。
                2. 【深度互动】：不要直接给出结论。如果学生说了一个模糊的情况（如“我基础一般”），你必须针对【概念理解深度】或【逻辑抽象】等维度抛出一个具体的小问题来“试探”他。
                - 示例：如果他说想学深度学习，你可以问：“你之前接触过线性代数吗，还是更喜欢从直观的图形逻辑开始？”
                3. 【画像驱动】：根据当前最低的维度进行针对性补捞。如果他“动手能力”数值不详，请问他是否写过 Python 代码。
                4. 【任务挂钩】：在对话末尾，自然地引导他：“如果你准备好了，我们可以去‘资源工厂’针对这个点生成一份专属你的特训包。”
                5. 【拒绝长输出】：如果学生索要长篇代码或复杂讲义，请给出核心的一两行预览，
                然后礼貌且专业地告知他：‘为了提供更沉浸的学习体验，请移步 [多模态资源生成] 标签页，
                我会为你准备好完整的实验环境和深度讲义。’
                要求：语气自然、口语化，像真人在微信聊天。字数严格控制在 100 字以内。
                """
                
                with chat_container.chat_message("assistant"):
                    ai_reply = st.write_stream(stream_spark_response(reply_prompt, max_tokens=400))
                
                st.session_state.chat_history.append({"role": "assistant", "content": ai_reply})

                # 步骤 E: 【关键】强制刷新页面，让右侧雷达图重新绘制
                st.rerun()

    # 右侧雷达图区
    with col_radar:
        st.markdown("### 📊 实时学生画像 (6D)")
        # 自动筛选所有数值类型的键
        plot_data = {k: v for k, v in st.session_state.student_profile.items() if isinstance(v, (int, float))}
        
        df_radar = pd.DataFrame(dict(
            r=list(plot_data.values()),
            theta=list(plot_data.keys())
        ))
        
        fig = px.line_polar(df_radar, r='r', theta='theta', line_close=True)
        fig.update_traces(fill='toself', line_color='#00CC96') # 换个颜色区分
        fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])))
        updated_dims = [v for v in st.session_state.student_profile.values() if v != 50]
        confidence = len(updated_dims) / 6
        st.sidebar.markdown(f"**画像识别完成度**: {confidence:.0%}")
        st.sidebar.progress(confidence)
        st.plotly_chart(fig, use_container_width=True)
    
        
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
                
                # 1. RAG 检索官 (防幻觉核心)
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
                字数不超过500字。
                要求：使用 Markdown 格式，包含标题、正文、避坑指南。
                """
                st.session_state.generated_resources['doc'] = get_silent_response(doc_prompt)
                
                # 3. 视觉智能体 (Mermaid 图表生成)
                st.write("🎨 [视觉智能体] 正在根据讲义逻辑绘制思维导图...")
                mindmap_prompt = f"""
                基于以下讲义内容，生成一段 Mermaid 格式的思维导图代码 (graph TD)。
                讲义内容：{st.session_state.generated_resources['doc']}
                注意：只输出代码，严禁任何废话。短一点
                """
                raw_mermaid = get_silent_response(mindmap_prompt)
                st.session_state.generated_resources['mindmap'] = raw_mermaid.replace("```mermaid", "").replace("```", "").strip()
                
                # 4. 实操智能体 (代码案例定制)
                st.write("💻 [实操智能体] 正在根据您的动手能力准备案例...")
                code_prompt = f"""
                为知识点【{target_concept}】准备一个 Python 案例。
                策略要求：{current_strategy}
                注意：重点关注代码注释的详尽程度和挑战性设置，尽量简短。
                """
                st.session_state.generated_resources['code'] = get_silent_response(code_prompt)
                
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
            
            st.caption(f"🔗 **溯源信息**：本资源包由多智能体协作生成。核心知识点提取自：{st.session_state.current_book_name}")

with tab_practice:
    st.markdown("### 💻 实验实操空间")
    
    # 1. 检查是否有生成的代码参考
    if 'code' not in st.session_state.generated_resources:
        st.info("💡 请先在 [📚 多模态资源生成] 页面生成案例代码。")
    else:
        st.markdown(f"#### 🎯 挑战课题：{st.session_state.locked_concept}")
        
        col_ref, col_edit = st.columns(2)
        with col_ref:
            st.caption("📜 标准参考代码 (或逻辑框架)")
            st.code(st.session_state.generated_resources['code'], language="python")
            
        with col_edit:
            st.caption("✍️ 你的实现 (请在此处编写或修正代码)")
            user_code = st.text_area("Python Sandbox", height=400, placeholder="在此输入你的代码...", key="sandbox_area")
            
            if st.button("🛠️ 呼叫代码审查 (Code Review)", type="primary", use_container_width=True):
                if not user_code.strip():
                    st.warning("请先输入代码！")
                else:
                    # --- 核心逻辑开始 ---
                    with st.status("🕵️ 智能体集群正在协作...", expanded=True) as status:
                        
                        # A. 定义审查指令 (修复 NameError 的关键：先定义再使用)
                        st.write("1. 代码逻辑与数学一致性分析...")
                        current_ability = st.session_state.student_profile['动手能力']
                        review_prompt = f"""
                        你是代码审查专家。对比以下内容：
                        参考标准：{st.session_state.generated_resources['code']}
                        学生实现：{user_code}
                        
                        任务：
                        1. 指出逻辑错误（尤其是数学公式或算法实现）。
                        2. 结合学生当前动手能力({current_ability})给出针对性改进建议。
                        3. 严禁直接给出全量正确代码，要启发式引导。
                        限 150 字以内。
                        """
                        
                        # B. 调用接口获取结果
                        review_result = get_silent_response(review_prompt, max_tokens=512)
                        st.session_state.last_review_report = review_result # 存入 session 防止丢失
                        
                        # C. 核心闭环：根据代码对错更新画像
                        st.write("2. 正在评估实操表现并进化画像...")
                        practice_update_prompt = f"""
                        你是画像分析官。分析此审查报告：{review_result}。
                        根据学生代码的正确性、逻辑严密性，更新 6 维画像数值。
                        如果是明显的逻辑炸弹，大幅降低“动手能力”和“逻辑抽象”。
                        仅输出 JSON：{{ "知识基础":x, "学习动力":x, "进阶速度":x, "逻辑抽象":x, "动手能力":x, "概念理解深度":x }}
                        """
                        raw_json = get_silent_response(practice_update_prompt, max_tokens=200)
                        
                        # 尝试解析并更新全局画像
                        try:
                            import re, json
                            match = re.search(r'\{.*\}', raw_json, re.DOTALL)
                            if match:
                                new_profile = json.loads(match.group())
                                st.session_state.student_profile.update(new_profile)
                        except: pass
                        
                        # D. 解锁门禁
                        st.session_state.practice_completed = True
                        status.update(label="✅ 审查与画像同步完成！", state="complete", expanded=False)

    # 5. 结果展示区（在按钮外，确保不会因为 rerun 消失）
    if "last_review_report" in st.session_state:
        st.markdown(st.session_state.last_review_report)

# --- TAB 4: 学习效果评估与动态闭环 (加分项核心) ---
with tab_eval:
    if not st.session_state.practice_completed:
        st.info("请先前往 [💻 实验实操空间] 完成代码编写并通过 AI 审查，以证明您已具备实操基础。")
    else:
        # 2. 测评生成触发器
        with st.status("🧑‍🏫 测评智能体正在根据您的 6D 画像出题...", expanded=True) as status:
            # 检索背景知识防止幻觉
            st.write("1. 检索教材标准定义...")
            contexts = st.session_state.rag_engine.search(st.session_state.locked_concept, top_k=2)
            context_text = "\n".join([c["text"] for c in contexts]) if contexts else ""
            
            st.write("2. 针对性生成题目...")
            current_level = "零基础入门" if st.session_state.student_profile["知识基础"] < 50 else "进阶专家"
            quiz_prompt = f"""
            你是测评智能体。目标：【{st.session_state.locked_concept}】。依据：{context_text}。
            学生画像：{st.session_state.student_profile}
            
            任务：生成1道极具代表性的深度单选题。
            要求：
            1. 必须根据“概念理解深度”调整题目难度。
            2. 严禁解析，仅输出题目和选项。
            """
            # 存储到 session 供后续判卷
            st.session_state.generated_resources['quiz'] = get_silent_response(quiz_prompt, max_tokens=300)
            status.update(label="✅ 题目已就绪！", state="complete")

        # 3. 渲染题目与答题区
        if 'quiz' in st.session_state.generated_resources:
            st.markdown("---")
            st.markdown("#### 📝 随堂小测")
            st.info(st.session_state.generated_resources['quiz'])
            
            with st.form("eval_quiz_form"):
                user_answer = st.text_area("请输入您的答案及简要解析：", height=100)
                submit_eval = st.form_submit_button("提交并更新画像", use_container_width=True)
                
                if submit_eval and user_answer.strip():
                    with st.status("🧠 正在交叉比对并重塑您的画像...", expanded=True) as status:
                        # 再次获取上下文用于批改
                        contexts = st.session_state.rag_engine.search(st.session_state.locked_concept, top_k=2)
                        context_text = "\n".join([c["text"] for c in contexts]) if contexts else ""
                        
                        # A. 判卷智能体
                        st.write("1. 执行深度批改...")
                        grade_prompt = f"""
                        你是铁面无私的判卷官。题目：{st.session_state.generated_resources['quiz']}
                        学生答案：{user_answer}。参考标准：{context_text}。
                        任务：给出评分(0-100)并简述错因，严禁废话，限80字。
                        """
                        grading_feedback = get_silent_response(grade_prompt, max_tokens=300)
                        
                        # B. 画像进化智能体
                        st.write("2. 计算 6D 能力漂移...")
                        update_prompt = f"""
                        你是学情分析智能体。基于测验结果更新 6 维数值画像（0-100）。
                        旧画像：{st.session_state.student_profile}
                        批改反馈：{grading_feedback}
                        
                        任务：输出最新的 JSON，包含以下 6 个键：
                        知识基础, 学习动力, 进阶速度, 逻辑抽象, 动手能力, 概念理解深度。
                        """
                        raw_json = get_silent_response(update_prompt, max_tokens=250)
                        match = re.search(r'\{.*\}', raw_json, re.DOTALL)
                        if match:
                            try:
                                new_profile = json.loads(match.group())
                                st.session_state.student_profile.update(new_profile)
                            except: pass
                        
                        status.update(label="✅ 闭环反馈完成！", state="complete")
                    
                    # 结果展示
                    st.success(f"**批改报告**：\n{grading_feedback}")
                    st.warning("🔄 画像已实时同步至【动态学情画像】标签页。")




