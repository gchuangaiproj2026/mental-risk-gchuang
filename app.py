# -*- coding:utf-8 -*-
"""
国创项目：多角色高校心理健康动态监测与智能预警平台【全功能增强版】
布局：左侧边栏导航 + 右侧内容区
启动：streamlit run app.py
"""
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os
from datetime import datetime
import io
import random

# 加载核心筛查算法
try:
    from psycho_screen import psycho_risk_screen
    _ALG_AVAILABLE = True
except ImportError:
    psycho_risk_screen = None
    _ALG_AVAILABLE = False

# ===================== 全局中文字体兼容 =====================
import matplotlib.font_manager as fm
def _setup_cjk_font():
    font_paths = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/msyhbd.ttc",
        "C:/Windows/Fonts/simhei.ttf",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                fm.fontManager.addfont(fp)
            except Exception:
                pass
    candidates = [
        "Noto Sans CJK SC", "Noto Sans SC", "Microsoft YaHei", "SimHei",
        "Noto Sans CJK JP", "WenQuanYi Zen Hei",
    ]
    available = {f.name for f in fm.fontManager.ttflist}
    for name in candidates:
        if name in available:
            plt.rcParams['font.sans-serif'] = [name, 'DejaVu Sans']
            break
    plt.rcParams['axes.unicode_minus'] = False
_setup_cjk_font()

# ===================== 页面基础配置 =====================
st.set_page_config(
    page_title="高校心理健康智能监测平台",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===================== 全局自定义CSS（美化，适配侧边栏） =====================
st.markdown("""
<style>
.block-container {
    padding-top: 1rem;
    padding-left: 2rem;
    padding-right: 2rem;
}
.hero-title {
    background: linear-gradient(90deg, #364fc7, #7950f2);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    color: transparent;
    text-align: center;
    font-size: 38px;
    font-weight: bold;
    margin-bottom: 0.2rem;
    display: inline-block;
    width: 100%;
}
.hero-sub {
    text-align: center;
    color: #666;
    font-size: 17px;
    margin-bottom: 2rem;
}
/* 角色卡片与功能卡片 */
.role-card, .feature-card {
    background: white;
    border-radius: 16px;
    padding: 1.5rem 1rem;
    box-shadow: 0 4px 16px rgba(0,0,0,0.06);
    border: 1px solid #edf2f7;
    text-align: center;
    height: 100%;
    transition: all 0.3s ease;
}
.role-card:hover, .feature-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 24px rgba(54, 79, 199, 0.12);
    border-color: #7950f2;
}
.role-card h2 {
    margin-top: 0.2rem;
    font-size: 24px;
}
.role-card p {
    color: #555;
    font-size: 15px;
    line-height: 1.5;
}
.feature-card h3 {
    font-size: 20px;
    margin-bottom: 0.3rem;
}
.feature-card p {
    color: #666;
    font-size: 14px;
}
/* 模块内容卡片 */
.module-card {
    background: white;
    border-radius: 16px;
    padding: 1.5rem 1.8rem;
    box-shadow: 0 2px 12px rgba(0,0,0,0.05);
    border: 1px solid #edf2f7;
    margin-bottom: 1.5rem;
    overflow: auto;
}
/* 侧边栏美化 */
.css-1d391kg, .css-163i55w {
    background-color: #f8faff;
}
.sidebar-title {
    font-size: 22px;
    font-weight: bold;
    color: #364fc7;
    text-align: center;
    margin-bottom: 0.5rem;
}
</style>
""", unsafe_allow_html=True)

# ===================== Session状态初始化 =====================
def init_session():
    if "page_root" not in st.session_state:
        st.session_state["page_root"] = "home"
    if "role" not in st.session_state:
        st.session_state["role"] = ""
    if "username" not in st.session_state:
        st.session_state["username"] = ""
    if "current_module" not in st.session_state:
        st.session_state["current_module"] = ""
    # 算法全局缓存
    if "df_screen_result" not in st.session_state:
        st.session_state["df_screen_result"] = None
    if "tau_cache" not in st.session_state:
        st.session_state["tau_cache"] = None
    if "trace_cache" not in st.session_state:
        st.session_state["trace_cache"] = None
    if "copula_score" not in st.session_state:
        st.session_state["copula_score"] = None
    if "batch_note" not in st.session_state:
        st.session_state["batch_note"] = ""
    # 学生自评存档
    if "student_self_history" not in st.session_state:
        st.session_state["student_self_history"] = []
    # 全局风险阈值
    if "global_high_thr" not in st.session_state:
        st.session_state["global_high_thr"] = 1.5
    if "global_mid_thr" not in st.session_state:
        st.session_state["global_mid_thr"] = 0.5
    # 模拟多批次历史数据
    if "multi_batch_history" not in st.session_state:
        st.session_state["multi_batch_history"] = {
            "批次": [f"2026-0{i}" for i in range(1,9)],
            "高危": [random.randint(2,12) for _ in range(8)],
            "中危": [random.randint(5,18) for _ in range(8)],
            "低危": [random.randint(20,40) for _ in range(8)]
        }
init_session()

# ===================== 侧边栏导航（恢复经典布局） =====================
def render_sidebar():
    role = st.session_state["role"]
    username = st.session_state["username"]
    with st.sidebar:
        st.markdown('<div class="sidebar-title">🧠 心理健康监测平台</div>', unsafe_allow_html=True)
        st.markdown("---")
        st.markdown(f"**用户：** {username}")
        role_map = {"student":"学生端", "teacher":"教师端", "admin":"管理端"}
        st.markdown(f"**当前角色：** {role_map[role]}")
        st.markdown("---")
        st.markdown("#### 功能导航")
        module_list = []
        if role == "student":
            module_list = ["心理普查（自评问卷）", "个人状态画像雷达图", "历史自评存档", "个性化心理建议库"]
        elif role == "teacher":
            module_list = ["心理普查批量筛查", "风险分级统计看板", "高危预警管理", "学生个案追踪档案", "班级趋势分析图表"]
        elif role == "admin":
            module_list = ["全校数据决策总看板", "全校多批次趋势对比", "学校综合报告生成", "平台账号权限管理", "全局算法参数配置"]
        selected = st.selectbox("选择模块", module_list, label_visibility="collapsed")
        if selected != st.session_state["current_module"]:
            st.session_state["current_module"] = selected
            st.rerun()
        st.markdown("---")
        st.caption("底层算法：贝叶斯变点 + Copula")
        if st.button("🚪 退出登录", use_container_width=True):
            st.session_state["page_root"] = "home"
            st.session_state["role"] = ""
            st.session_state["username"] = ""
            st.rerun()

# ===================== 门户首页（三角色选择 + 快捷功能） =====================
def render_home_page():
    st.markdown('<div class="hero-title">高校心理健康智能监测与预警平台</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-sub">底层算法：贝叶斯在线变点检测 + Copula相依结构 | 多角色协同心理健康管理系统</div>', unsafe_allow_html=True)
    st.divider()
    
    st.subheader("🚀 快捷功能入口")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        with st.container():
            st.markdown("""
            <div class="feature-card">
                <h3>📝 心理普查</h3>
                <p>学生自评问卷 / 批量筛查</p>
            </div>
            """, unsafe_allow_html=True)
            if st.button("进入普查", key="quick_survey", use_container_width=True):
                st.session_state["page_root"] = "role_login"
                st.session_state["role"] = "student"
                st.rerun()
    with col2:
        with st.container():
            st.markdown("""
            <div class="feature-card">
                <h3>📊 风险分析</h3>
                <p>智能分级与Copula异常检测</p>
            </div>
            """, unsafe_allow_html=True)
            if st.button("查看风险", key="quick_risk", use_container_width=True):
                st.session_state["page_root"] = "role_login"
                st.session_state["role"] = "teacher"
                st.rerun()
    with col3:
        with st.container():
            st.markdown("""
            <div class="feature-card">
                <h3>📈 数据决策</h3>
                <p>全校看板与趋势报告</p>
            </div>
            """, unsafe_allow_html=True)
            if st.button("数据决策", key="quick_dashboard", use_container_width=True):
                st.session_state["page_root"] = "role_login"
                st.session_state["role"] = "admin"
                st.rerun()
    with col4:
        with st.container():
            st.markdown("""
            <div class="feature-card">
                <h3>🧑‍🏫 个案追踪</h3>
                <p>学生档案与预警管理</p>
            </div>
            """, unsafe_allow_html=True)
            if st.button("追踪档案", key="quick_case", use_container_width=True):
                st.session_state["page_root"] = "role_login"
                st.session_state["role"] = "teacher"
                st.rerun()
    
    st.divider()
    st.markdown("### 请选择您的登录角色进入对应系统")
    col1, col2, col3 = st.columns(3, gap="large")
    with col1:
        with st.container():
            st.markdown("""
            <div class="role-card">
                <h2>👨‍🎓 学生端</h2>
                <p>心理普查自评、多维度状态雷达画像、历史存档、个性化心理疏导建议、自评数据导出</p>
            </div>
            """, unsafe_allow_html=True)
            if st.button("进入学生端系统", use_container_width=True, key="home_student"):
                st.session_state["page_root"] = "role_login"
                st.session_state["role"] = "student"
                st.rerun()
    with col2:
        with st.container():
            st.markdown("""
            <div class="role-card">
                <h2>👩‍🏫 教师端</h2>
                <p>批量贝叶斯-Copula风险筛查、全套算法可视化图表、预警管理、个案追踪、班级趋势、多报表导出</p>
            </div>
            """, unsafe_allow_html=True)
            if st.button("进入教师端系统", use_container_width=True, key="home_teacher"):
                st.session_state["page_root"] = "role_login"
                st.session_state["role"] = "teacher"
                st.rerun()
    with col3:
        with st.container():
            st.markdown("""
            <div class="role-card">
                <h2>🏛️ 管理端</h2>
                <p>全校数据决策看板、多批次趋势对比、年级分层统计、全校综合报告、账号权限、全局算法参数配置</p>
            </div>
            """, unsafe_allow_html=True)
            if st.button("进入管理端系统", use_container_width=True, key="home_admin"):
                st.session_state["page_root"] = "role_login"
                st.session_state["role"] = "admin"
                st.rerun()

# ===================== 登录页 =====================
def render_role_login():
    role_map = {"student": "学生端", "teacher": "教师端", "admin": "管理端"}
    role_cn = role_map[st.session_state["role"]]
    st.markdown(f'<div class="hero-title">{role_cn}登录</div>', unsafe_allow_html=True)
    col1, col_mid, col2 = st.columns([1,2,1])
    with col_mid:
        with st.container():
            user = st.text_input("账号", placeholder="输入账号")
            pwd = st.text_input("密码", type="password", placeholder="输入密码")
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("返回首页", use_container_width=True):
                    st.session_state["page_root"] = "home"
                    st.rerun()
            with col_b:
                if st.button("登录系统", type="primary", use_container_width=True):
                    if user.strip() and pwd.strip():
                        st.session_state["username"] = user
                        mod_map = {
                            "student": "心理普查（自评问卷）",
                            "teacher": "心理普查批量筛查",
                            "admin": "全校数据决策总看板"
                        }
                        st.session_state["current_module"] = mod_map[st.session_state["role"]]
                        st.session_state["page_root"] = "main"
                        st.rerun()
                    else:
                        st.error("账号密码不能为空")
            st.caption("测试权限：任意账号密码均可登录对应角色")

# ===================== 主系统（带侧边栏） =====================
def render_main_system():
    render_sidebar()
    role = st.session_state["role"]
    curr_mod = st.session_state["current_module"]
    with st.container():
        st.markdown('<div class="module-card">', unsafe_allow_html=True)
        if role == "student":
            render_student_module(curr_mod)
        elif role == "teacher":
            render_teacher_module(curr_mod)
        elif role == "admin":
            render_admin_module(curr_mod)
        st.markdown('</div>', unsafe_allow_html=True)

# ===================== 学生端模块（完整） =====================
def render_student_module(module):
    history = st.session_state["student_self_history"]
    if module == "心理普查（自评问卷）":
        st.header("📝 学生心理自评普查问卷")
        st.info("填写量表完成自评，自动存档历史记录，生成多维心理画像")
        with st.form("self_form", clear_on_submit=True):
            anxiety = st.slider("焦虑维度得分（0-40）",0,40,10)
            depression = st.slider("抑郁维度得分（0-40）",0,40,8)
            stress = st.slider("压力维度得分（0-40）",0,40,12)
            sleep = st.slider("睡眠障碍（0-30）",0,30,5)
            social = st.slider("社交回避（0-30）",0,30,4)
            submit = st.form_submit_button("提交自评并存档")
        if submit:
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            self_data = pd.DataFrame({
                "自评时间":[now],
                "焦虑":[anxiety],"抑郁":[depression],"压力":[stress],
                "睡眠障碍":[sleep],"社交回避":[social],
                "总分":[anxiety+depression+stress+sleep+social]
            })
            history.append(self_data)
            st.session_state["student_self_history"] = history
            st.success(f"自评提交成功，已保存至历史存档，提交时间：{now}")
    elif module == "个人状态画像雷达图":
        st.header("📊 个人多维度心理状态雷达画像")
        if len(history) == 0:
            st.warning("请先完成心理普查自评问卷生成数据")
        else:
            latest = history[-1]
            dims = ["焦虑","抑郁","压力","睡眠障碍","社交回避"]
            values = latest[dims].iloc[0].values
            st.subheader("最新自评数据")
            st.dataframe(latest, hide_index=True, use_container_width=True)
            fig = plt.figure(figsize=(8,8))
            ax = fig.add_subplot(111, polar=True)
            angles = np.linspace(0, 2*np.pi, len(dims), endpoint=False).tolist()
            values_plot = np.concatenate((values, [values[0]]))
            angles_plot = np.concatenate((angles, [angles[0]]))
            ax.plot(angles_plot, values_plot, color="#5c7cfa", linewidth=2)
            ax.fill(angles_plot, values_plot, color="#5c7cfa", alpha=0.25)
            ax.set_xticks(angles)
            ax.set_xticklabels(dims)
            ax.set_title("个人心理五维度雷达画像", fontsize=14)
            st.pyplot(fig)
            st.metric("当前心理总分", value=int(latest["总分"].iloc[0]))
            all_history = pd.concat(history, ignore_index=True)
            csv = all_history.to_csv(index=False, encoding="utf_8_sig")
            st.download_button("📥 导出全部自评历史CSV", data=csv, file_name="学生自评历史记录.csv")
    elif module == "历史自评存档":
        st.header("🗃️ 个人自评历史存档记录")
        if len(history) == 0:
            st.info("暂无自评记录，请前往普查问卷提交数据")
        else:
            all_df = pd.concat(history, ignore_index=True)
            st.dataframe(all_df, use_container_width=True)
            fig, ax = plt.subplots(figsize=(12,5))
            ax.plot(all_df["自评时间"], all_df["总分"], marker="o", color="#7950f2")
            ax.set_title("历次自评总分变化趋势")
            ax.tick_params(axis='x', rotation=30)
            st.pyplot(fig)
    elif module == "个性化心理建议库":
        st.header("💡 分级个性化心理疏导建议库")
        if len(history) == 0:
            st.warning("请先完成自评获取分析建议")
        else:
            latest = history[-1]
            a = latest["焦虑"].iloc[0]
            d = latest["抑郁"].iloc[0]
            s = latest["压力"].iloc[0]
            slp = latest["睡眠障碍"].iloc[0]
            soc = latest["社交回避"].iloc[0]
            st.subheader("智能分级疏导建议")
            suggest_list = []
            if a >=25:
                st.error("🔴 焦虑指标偏高：每日20分钟正念呼吸训练，每周预约心理中心一对一咨询")
                suggest_list.append("焦虑偏高：坚持冥想放松，减少长期独处")
            elif a >=15:
                st.warning("🟡 轻度焦虑：睡前减少刷手机，增加户外散步")
                suggest_list.append("轻度焦虑：调整作息，增加运动")
            if d >=22:
                st.error("🔴 抑郁倾向明显：主动参与班级社团活动，避免熬夜封闭自己")
                suggest_list.append("抑郁倾向：多与人交流，必要时线下心理咨询")
            if s >=28:
                st.error("🔴 学业压力过载：拆分学习目标，每日保证30分钟运动")
                suggest_list.append("压力过高：合理规划任务，劳逸结合")
            if slp >=18:
                st.warning("🟡 睡眠质量较差：固定作息，睡前不使用电子设备")
            if soc >=16:
                st.warning("🟡 社交回避轻微：从小型集体活动逐步适应社交")
            if not suggest_list:
                st.success("🟢 各项心理指标状态良好，保持现有生活节奏")
            st.divider()
            st.info("线下咨询渠道：学校大学生心理健康教育中心，工作日8:30-17:00免费预约")

# ===================== 教师端模块 =====================
def render_teacher_module(module):
    df_cache = st.session_state["df_screen_result"]
    tau_cache = st.session_state["tau_cache"]
    trace_cache = st.session_state["trace_cache"]
    copula_cache = st.session_state["copula_score"]
    high_thr = st.session_state["global_high_thr"]
    mid_thr = st.session_state["global_mid_thr"]
    batch_note = st.session_state["batch_note"]
    if module == "心理普查批量筛查":
        st.header("📤 批量学生普查数据筛查（贝叶斯‑Copula完整算法）")
        st.info("上传班级Excel量表数据，自动执行风险分级、变点检测、Copula相依异常识别，支持自定义阈值、交互式筛选、双报表导出")
        with st.expander("⚙️ 本次筛查独立参数配置", expanded=False):
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                local_high = st.slider("本次高危风险阈值", min_value=0.8, max_value=2.5, value=high_thr, step=0.05)
            with col_p2:
                local_mid = st.slider("本次中危风险阈值", min_value=0.2, max_value=1.2, value=mid_thr, step=0.05)
            batch_note_input = st.text_input("本批次普查备注", placeholder="例如：2026秋季大一计算机班普查")
        upload = st.file_uploader("上传普查Excel(xlsx)", type=["xlsx","xls"])
        if upload:
            df_raw = pd.read_excel(upload)
            st.subheader("原始数据预览")
            st.dataframe(df_raw.head(10), hide_index=True)
            dims = st.multiselect("选择量表维度列（至少2个维度用于Copula相依建模）", df_raw.columns.tolist())
            if len(dims)>=2 and st.button("🚀启动智能风险筛查", type="primary"):
                if not _ALG_AVAILABLE:
                    st.error("算法包 psycho_screen 加载失败，请检查文件与依赖环境")
                else:
                    if df_raw.shape[0]>1000:
                        st.warning("云端运行限制，仅处理前1000行样本，完整数据建议本地Anaconda运行")
                        df_raw = df_raw.head(1000)
                    with st.spinner("贝叶斯MCMC采样、Copula相依结构建模计算中，请等待..."):
                        df_out, trace, tau_mean, copula_abnormal_score = psycho_risk_screen(df_raw, dims, local_high, local_mid)
                    st.session_state["df_screen_result"] = df_out
                    st.session_state["tau_cache"] = tau_mean
                    st.session_state["trace_cache"] = trace
                    st.session_state["copula_score"] = copula_abnormal_score
                    st.session_state["batch_note"] = batch_note_input
                    st.success(f"✅计算完成，检测到总分变点位置：{tau_mean:.1f} | 批次备注：{batch_note_input if batch_note_input else '无'}")
                    risk_cnt = df_out["风险等级"].value_counts()
                    c1,c2,c3,c4 = st.columns(4)
                    c1.metric("高危人数", risk_cnt.get("高危",0), delta_color="inverse")
                    c2.metric("中危人数", risk_cnt.get("中危",0))
                    c3.metric("低危人数", risk_cnt.get("低危",0))
                    c4.metric("本次总样本", len(df_out))
                    # 第一行双图
                    fig1,(ax1,ax2)=plt.subplots(1,2,figsize=(17,6))
                    total_score=df_out["总分"].values
                    sample_idx=np.arange(len(total_score))
                    ax1.plot(sample_idx,total_score,color="#5486c0",linewidth=1.4)
                    ax1.axvline(x=tau_mean,color="red",linestyle="--",linewidth=1.8,label=f"变点:{tau_mean:.1f}")
                    ax1.set_title("心理普查总分序列与贝叶斯变点",fontsize=13)
                    ax1.set_xlabel("样本编号")
                    ax1.set_ylabel("总分")
                    ax1.legend()
                    ax1.grid(alpha=0.25)
                    tau_sample=trace.posterior["tau"].values.flatten()
                    ax2.hist(tau_sample,bins=20,color="#628ec7",edgecolor="#2b4870",alpha=0.85)
                    ax2.axvline(x=tau_mean,color="red",linestyle="--",linewidth=1.8)
                    ax2.set_title("变点位置后验分布",fontsize=13)
                    ax2.set_xlabel("变点位置")
                    ax2.grid(alpha=0.25)
                    st.pyplot(fig1)
                    # 第二行双图
                    fig2,(ax3,ax4)=plt.subplots(1,2,figsize=(17,6))
                    ax3.hist(copula_abnormal_score,bins=18,color="#f7bc42",edgecolor="#b48620",alpha=0.88)
                    ax3.set_title("Copula相依异常分分布",fontsize=13)
                    ax3.set_xlabel("异常分")
                    ax3.grid(alpha=0.25)
                    risk_pie = df_out["风险等级"].value_counts()
                    color_map={"高危":"#ff6b6b","中危":"#ffcc44","低危":"#62bd69"}
                    pie_color=[color_map[k] for k in risk_pie.index]
                    ax4.pie(risk_pie.values,labels=risk_pie.index,colors=pie_color,autopct="%.1f%%",textprops={"fontsize":11})
                    ax4.set_title("样本风险分级占比",fontsize=13)
                    st.pyplot(fig2)
                    # 统计明细
                    st.markdown("### 📋风险统计明细")
                    stat_df = pd.DataFrame({
                        "风险等级":["高危","中危","低危"],
                        "样本数量":[risk_cnt.get("高危",0),risk_cnt.get("中危",0),risk_cnt.get("低危",0)],
                        "占比(%)":[
                            round(risk_cnt.get("高危",0)/len(df_out)*100,2),
                            round(risk_cnt.get("中危",0)/len(df_out)*100,2),
                            round(risk_cnt.get("低危",0)/len(df_out)*100,2)
                        ]
                    })
                    st.dataframe(stat_df, hide_index=True, use_container_width=True)
                    # Copula筛选
                    st.markdown("### 🔍Copula高异常样本筛选")
                    filter_score = st.slider("筛选大于该异常分的样本",min_value=float(np.min(copula_abnormal_score)),max_value=float(np.max(copula_abnormal_score)),value=np.percentile(copula_abnormal_score,80))
                    mask = copula_abnormal_score>filter_score
                    st.info(f"异常分高于{filter_score:.2f}的样本数量：{np.sum(mask)}")
                    st.dataframe(df_out.loc[mask,:],use_container_width=True)
                    # 全部结果
                    st.markdown("### 📃全部筛查结果表")
                    show_high_only = st.checkbox("仅展示高危预警学生")
                    display_df = df_out[df_out["风险等级"]=="高危"] if show_high_only else df_out
                    st.dataframe(display_df, use_container_width=True)
                    # 导出
                    csv_full = df_out.to_csv(index=False, encoding="utf_8_sig")
                    csv_stat = stat_df.to_csv(index=False, encoding="utf_8_sig")
                    col_d1,col_d2 = st.columns(2)
                    with col_d1:
                        st.download_button("📥导出完整筛查结果CSV", data=csv_full, file_name=f"班级筛查_{batch_note_input}.csv")
                    with col_d2:
                        st.download_button("📥导出风险统计汇总CSV", data=csv_stat, file_name=f"统计报表_{batch_note_input}.csv")
    elif module == "风险分级统计看板":
        st.header("📈 班级风险分级综合统计看板")
        if df_cache is None:
            st.info("请先在【批量筛查】模块上传并计算普查数据")
        else:
            risk_cnt = df_cache["风险等级"].value_counts()
            c1,c2,c3 = st.columns(3)
            c1.metric("高危", risk_cnt.get("高危",0))
            c2.metric("中危", risk_cnt.get("中危",0))
            c3.metric("低危", risk_cnt.get("低危",0))
            st.subheader("风险等级柱状分布图")
            st.bar_chart(risk_cnt, use_container_width=True)
            st.subheader("统计明细表格")
            stat_df = pd.DataFrame({
                "等级":risk_cnt.index,
                "人数":risk_cnt.values,
                "占比%": [round(x/len(df_cache)*100,2) for x in risk_cnt.values]
            })
            st.dataframe(stat_df, hide_index=True)
    elif module == "高危预警管理":
        st.header("🚨 高危学生预警管理台账")
        if df_cache is None:
            st.info("请先完成批量筛查生成预警数据")
        else:
            high_df = df_cache[df_cache["风险等级"]=="高危"].copy()
            st.subheader(f"高危预警名单（共{len(high_df)}人）")
            st.dataframe(high_df, use_container_width=True)
            st.text_area("批量干预记录填写", placeholder="记录约谈、疏导、回访、转介心理中心情况")
            csv_high = high_df.to_csv(index=False, encoding="utf_8_sig")
            st.download_button("导出高危预警台账", data=csv_high, file_name="高危学生预警名单.csv")
    elif module == "学生个案追踪档案":
        st.header("👤 学生个案长期追踪档案")
        if df_cache is None:
            st.info("请先完成批量筛查")
        else:
            id_list = sorted(df_cache["编号"].unique())
            sel_id = st.selectbox("选择学生编号查看完整个案", id_list)
            stu_data = df_cache[df_cache["编号"]==sel_id]
            st.dataframe(stu_data, hide_index=True)
            st.text_area("个案追踪记录", placeholder="历次沟通、干预、心理变化记录存档")
    elif module == "班级趋势分析图表":
        st.header("📉 班级心理总分时序趋势分析")
        if df_cache is None:
            st.info("请先完成批量筛查")
        else:
            fig, ax = plt.subplots(figsize=(12,5))
            ax.plot(df_cache["编号"], df_cache["总分"], alpha=0.7, color="#4263eb")
            ax.axvline(x=tau_cache, color="red", linestyle="--", label=f"风险变点位置：{tau_cache}")
            ax.set_title("全班学生总分序列与贝叶斯风险变点")
            ax.set_xlabel("学生编号")
            ax.set_ylabel("心理总分")
            ax.legend()
            ax.grid(alpha=0.2)
            st.pyplot(fig)

# ===================== 管理端模块（含趋势图） =====================
def render_admin_module(module):
    df_cache = st.session_state["df_screen_result"]
    global_high = st.session_state["global_high_thr"]
    global_mid = st.session_state["global_mid_thr"]
    if module == "全校数据决策总看板":
        st.header("🏫 全校心理健康数据决策总看板")
        if df_cache is None:
            st.info("暂无普查汇总数据，请教师端上传班级筛查数据")
        else:
            total = len(df_cache)
            high = len(df_cache[df_cache["风险等级"]=="高危"])
            mid = len(df_cache[df_cache["风险等级"]=="中危"])
            low = len(df_cache[df_cache["风险等级"]=="低危"])
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("全校总样本", total)
            c2.metric("高危人数", high, delta_color="inverse")
            c3.metric("中危人数", mid)
            c4.metric("低危人数", low)
            
            col_chart1, col_chart2 = st.columns(2)
            with col_chart1:
                st.subheader("全校风险分布")
                fig, ax = plt.subplots(figsize=(7,6))
                risk_counts = df_cache["风险等级"].value_counts()
                colors = {"高危": "#ff6b6b", "中危": "#ffcc44", "低危": "#62bd69"}
                ax.pie(
                    risk_counts.values,
                    labels=risk_counts.index,
                    colors=[colors[k] for k in risk_counts.index],
                    autopct="%.1f%%",
                    textprops={"fontsize": 12}
                )
                ax.set_title("当前批次风险分布", fontsize=14)
                st.pyplot(fig)
            with col_chart2:
                st.subheader("全校多批次趋势（模拟）")
                hist = st.session_state["multi_batch_history"]
                df_hist = pd.DataFrame(hist)
                fig2, ax2 = plt.subplots(figsize=(7,6))
                ax2.plot(df_hist["批次"], df_hist["高危"], marker='o', label="高危", color="#ff6b6b")
                ax2.plot(df_hist["批次"], df_hist["中危"], marker='s', label="中危", color="#ffcc44")
                ax2.plot(df_hist["批次"], df_hist["低危"], marker='^', label="低危", color="#62bd69")
                ax2.set_title("全校风险人数变化趋势（模拟）")
                ax2.set_xlabel("批次")
                ax2.set_ylabel("人数")
                ax2.legend()
                ax2.grid(alpha=0.2)
                st.pyplot(fig2)
            
            st.subheader("全校风险汇总统计表")
            stat_df = pd.DataFrame({
                "风险等级":["高危","中危","低危"],
                "人数":[high,mid,low],
                "全校占比(%)":[round(high/total*100,2), round(mid/total*100,2), round(low/total*100,2)]
            })
            st.dataframe(stat_df, hide_index=True, use_container_width=True)
    elif module == "全校多批次趋势对比":
        st.header("📊 全校多批次普查长期趋势对比")
        st.info("基于模拟数据展示风险趋势，实际部署可接入数据库")
        hist = st.session_state["multi_batch_history"]
        df_hist = pd.DataFrame(hist)
        st.dataframe(df_hist, use_container_width=True)
        fig, ax = plt.subplots(figsize=(10,5))
        ax.plot(df_hist["批次"], df_hist["高危"], marker='o', label="高危", color="#ff6b6b", linewidth=2)
        ax.plot(df_hist["批次"], df_hist["中危"], marker='s', label="中危", color="#ffcc44", linewidth=2)
        ax.plot(df_hist["批次"], df_hist["低危"], marker='^', label="低危", color="#62bd69", linewidth=2)
        ax.set_title("全校多批次风险人数趋势")
        ax.set_xlabel("批次")
        ax.set_ylabel("人数")
        ax.legend()
        ax.grid(alpha=0.3)
        st.pyplot(fig)
        csv_trend = df_hist.to_csv(index=False, encoding="utf_8_sig")
        st.download_button("📥导出趋势数据CSV", data=csv_trend, file_name="全校多批次趋势.csv")
    elif module == "学校综合报告生成":
        st.header("📑 全校心理健康综合报告生成与导出")
        if df_cache is None:
            st.info("无筛查汇总数据无法生成报告")
        else:
            st.markdown("## 报告摘要（可直接复制至国创/学校汇报文档）")
            total = len(df_cache)
            high = len(df_cache[df_cache["风险等级"]=="高危"])
            mid = len(df_cache[df_cache["风险等级"]=="中危"])
            high_rate = round(high/total*100,2)
            mid_rate = round(mid/total*100,2)
            st.write(f"""
本次全校心理普查样本总量：{total}人
高危风险学生：{high}人，占比 {high_rate}%
中危风险学生：{mid}人，占比 {mid_rate}%
低危正常学生：{total-high-mid}人
平台底层采用贝叶斯在线变点检测+Copula相依结构算法，自动识别多维量表异常样本，精准划分心理风险等级，为学校心理干预、辅导员帮扶提供数据支撑。
            """)
            full_csv = df_cache.to_csv(index=False, encoding="utf_8_sig")
            st.download_button("导出全校完整普查汇总表", data=full_csv, file_name="全校心理普查汇总.csv")
    elif module == "平台账号权限管理":
        st.header("👥 平台三角色账号权限批量管理")
        st.subheader("权限说明")
        st.markdown("- 学生账号：仅自评问卷、个人画像、历史记录、自我建议，无法查看他人数据")
        st.markdown("- 教师账号：班级批量筛查、预警、个案、班级趋势，仅可见本班学生")
        st.markdown("- 管理员账号：全校汇总、系统配置、账号管理、全局算法参数")
        st.divider()
        col1,col2 = st.columns(2)
        with col1:
            st.text_input("新增账号用户名")
            st.text_input("账号密码")
        with col2:
            st.selectbox("分配角色", ["student","teacher","admin"])
            st.button("保存新增账号配置")
        st.text_area("批量导入账号文本框", placeholder="多行输入：用户名,密码,角色")
    elif module == "全局算法参数配置":
        st.header("⚙️ 全局贝叶斯-Copula算法阈值配置（全平台生效）")
        st.info("修改后学生/教师端所有筛查任务默认使用该套阈值，教师端单次筛查可独立覆盖")
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            new_high = st.slider("全局高危风险阈值", min_value=1.0, max_value=2.5, value=global_high, step=0.05)
        with col_p2:
            new_mid = st.slider("全局中危风险阈值", min_value=0.2, max_value=1.2, value=global_mid, step=0.05)
        if st.button("保存全局算法配置", type="primary"):
            st.session_state["global_high_thr"] = new_high
            st.session_state["global_mid_thr"] = new_mid
            st.success("全局风险阈值已保存，后续所有筛查默认生效")

# ===================== 页面总路由控制 =====================
root_page = st.session_state["page_root"]
if root_page == "home":
    render_home_page()
elif root_page == "role_login":
    render_role_login()
elif root_page == "main":
    render_main_system()