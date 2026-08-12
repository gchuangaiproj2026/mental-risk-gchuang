# -*- coding:utf-8 -*-
"""
国创项目：多角色高校心理健康动态监测与智能预警平台
三角色：学生端 / 教师端 / 管理端
核心算法：贝叶斯在线变点检测 + Copula相依结构
启动：streamlit run app.py
"""
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os
from datetime import datetime

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

# ===================== 全局自定义CSS 蓝紫科技风格 =====================
st.markdown("""
<style>
.block-container {
    padding-top: 2rem;
    padding-left: 3rem;
    padding-right: 3rem;
}
.main-title {
    background: linear-gradient(90deg, #364fc7, #7950f2);
    -webkit-background-clip: text;
    color: transparent;
    text-align:center;
    font-size:36px;
    font-weight:bold;
    margin-bottom:10px;
}
.sub-desc {
    text-align:center;
    color:#666;
    font-size:16px;
    margin-bottom:3rem;
}
.role-card {
    padding:2rem;
    border-radius:12px;
    border:1px solid #e0e7ff;
    background:#f8faff;
    text-align:center;
    height:100%;
}
.role-card:hover {
    box-shadow: 0 4px 12px #c7d2fe;
    border-color:#7950f2;
}
.sidebar-title {
    font-size:20px;
    font-weight:bold;
    color:#364fc7;
}
.upload-box{
    max-width:950px;
    margin:0 auto 2rem auto;
}
</style>
""", unsafe_allow_html=True)

# ===================== Session状态初始化 =====================
def init_session():
    if "page_root" not in st.session_state:
        st.session_state["page_root"] = "home"  # home/role_login/main
    if "role" not in st.session_state:
        st.session_state["role"] = ""  # student/teacher/admin
    if "username" not in st.session_state:
        st.session_state["username"] = ""
    if "current_module" not in st.session_state:
        st.session_state["current_module"] = ""
    # 算法缓存数据
    if "df_screen_result" not in st.session_state:
        st.session_state["df_screen_result"] = None
    if "tau_cache" not in st.session_state:
        st.session_state["tau_cache"] = None
    if "trace_cache" not in st.session_state:
        st.session_state["trace_cache"] = None
    # 学生自评缓存
    if "student_self_data" not in st.session_state:
        st.session_state["student_self_data"] = None
init_session()

# ===================== 门户首页（三角色选择入口） =====================
def render_home_page():
    st.markdown('<div class="main-title">高校心理健康智能监测与预警平台</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-desc">底层算法：贝叶斯在线变点检测 + Copula相依结构 | 多角色协同心理健康管理系统</div>', unsafe_allow_html=True)
    st.divider()
    st.markdown("### 请选择您的登录角色进入对应系统")
    col1, col2, col3 = st.columns(3, gap="large")
    with col1:
        st.markdown("""
        <div class="role-card">
            <h2>👨‍🎓 学生端</h2>
            <p>心理普查自评、个人状态画像、个性化心理建议</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("进入学生端系统", use_container_width=True, type="secondary"):
            st.session_state["page_root"] = "role_login"
            st.session_state["role"] = "student"
            st.rerun()
    with col2:
        st.markdown("""
        <div class="role-card">
            <h2>👩‍🏫 教师端</h2>
            <p>批量风险筛查、个案追踪、预警管理、班级趋势分析</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("进入教师端系统", use_container_width=True, type="primary"):
            st.session_state["page_root"] = "role_login"
            st.session_state["role"] = "teacher"
            st.rerun()
    with col3:
        st.markdown("""
        <div class="role-card">
            <h2>🏛️ 管理端</h2>
            <p>全校数据决策、整体趋势报告、账号与系统配置</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("进入管理端系统", use_container_width=True, type="secondary"):
            st.session_state["page_root"] = "role_login"
            st.session_state["role"] = "admin"
            st.rerun()

# ===================== 分角色登录页 =====================
def render_role_login():
    role_map = {
        "student": "学生端",
        "teacher": "教师端",
        "admin": "管理端"
    }
    role_cn = role_map[st.session_state["role"]]
    st.markdown(f'<div class="main-title">{role_cn}登录</div>', unsafe_allow_html=True)
    col1, col_mid, col2 = st.columns([1,2,1])
    with col_mid:
        user = st.text_input("账号", placeholder="输入账号")
        pwd = st.text_input("密码", type="password", placeholder="输入密码")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("返回首页"):
                st.session_state["page_root"] = "home"
                st.rerun()
        with col_b:
            if st.button("登录系统", type="primary"):
                if user.strip() and pwd.strip():
                    st.session_state["username"] = user
                    st.session_state["page_root"] = "main"
                    st.rerun()
                else:
                    st.error("账号密码不能为空")
        st.caption("测试权限：任意账号密码均可登录对应角色")

# ===================== 侧边栏导航（按角色区分模块） =====================
def render_sidebar():
    role = st.session_state["role"]
    username = st.session_state["username"]
    with st.sidebar:
        st.markdown('<div class="sidebar-title">🧠 心理健康监测平台</div>', unsafe_allow_html=True)
        st.markdown("---")
        st.markdown(f"用户：{username}")
        role_map = {"student":"学生","teacher":"教师","admin":"管理员"}
        st.markdown(f"当前角色：{role_map[role]}")
        st.markdown("---")
        st.markdown("#### 功能模块导航")
        module_list = []
        if role == "student":
            module_list = ["心理普查（自评问卷）", "个人状态画像", "个性化心理建议"]
        elif role == "teacher":
            module_list = ["心理普查批量筛查", "风险分析总览", "预警管理", "个案追踪", "班级趋势分析"]
        elif role == "admin":
            module_list = ["全校数据决策", "全校趋势分析", "学校综合报告", "用户账号管理", "系统设置"]
        st.session_state["current_module"] = st.selectbox("选择模块", module_list, label_visibility="collapsed")
        st.markdown("---")
        if st.button("退出登录", use_container_width=True):
            # 清空全部缓存
            st.session_state["page_root"] = "home"
            st.session_state["role"] = ""
            st.session_state["username"] = ""
            st.session_state["df_screen_result"] = None
            st.session_state["student_self_data"] = None
            st.rerun()

# ===================== 学生端全部模块渲染 =====================
def render_student_module(module):
    if module == "心理普查（自评问卷）":
        st.header("📝 学生心理自评普查问卷")
        st.info("填写量表完成自评，系统将生成你的心理状态数据，仅供本人与心理中心查阅")
        with st.form("self_form"):
            anxiety = st.slider("焦虑维度得分（0-40）",0,40,10)
            depression = st.slider("抑郁维度得分（0-40）",0,40,8)
            stress = st.slider("压力维度得分（0-40）",0,40,12)
            sleep = st.slider("睡眠障碍（0-30）",0,30,5)
            social = st.slider("社交回避（0-30）",0,30,4)
            submit = st.form_submit_button("提交自评数据")
        if submit:
            self_data = pd.DataFrame({
                "焦虑":[anxiety],"抑郁":[depression],"压力":[stress],
                "睡眠障碍":[sleep],"社交回避":[social]
            })
            st.session_state["student_self_data"] = self_data
            st.success("自评提交成功！前往【个人状态画像】查看分析结果")
    elif module == "个人状态画像":
        st.header("📊 个人心理状态画像")
        if st.session_state["student_self_data"] is None:
            st.warning("请先完成心理普查自评问卷")
        else:
            df = st.session_state["student_self_data"]
            dim_cols = ["焦虑","抑郁","压力","睡眠障碍","社交回避"]
            st.dataframe(df, hide_index=True)
            fig, ax = plt.subplots(figsize=(8,5))
            ax.bar(dim_cols, df.iloc[0].values, color="#5c7cfa")
            ax.set_title("个人各维度得分分布")
            plt.xticks(rotation=30)
            st.pyplot(fig)
            total = df[dim_cols].sum(axis=1).iloc[0]
            st.metric("心理总分", value=total)
    elif module == "个性化心理建议":
        st.header("💡 个性化心理疏导建议")
        if st.session_state["student_self_data"] is None:
            st.warning("请先完成心理普查自评问卷")
        else:
            df = st.session_state["student_self_data"]
            a = df["焦虑"].iloc[0]
            d = df["抑郁"].iloc[0]
            s = df["压力"].iloc[0]
            st.subheader("智能分析建议")
            if a >=25:
                st.markdown("- 焦虑偏高：建议每日20分钟深呼吸冥想，定期预约心理咨询")
            if d >=22:
                st.markdown("- 抑郁倾向：多参与社团户外活动，减少独处熬夜")
            if s >=28:
                st.markdown("- 学业压力过大：拆分学习目标，增加运动放松时间")
            st.info("若多项指标偏高，可前往学校心理中心线下咨询")

# ===================== 教师端全部模块渲染（复用贝叶斯Copula核心算法） =====================
def render_teacher_module(module):
    df_cache = st.session_state["df_screen_result"]
    tau_cache = st.session_state["tau_cache"]
    trace_cache = st.session_state["trace_cache"]
    if module == "心理普查批量筛查":
        st.header("📤 批量学生普查数据筛查（贝叶斯-Copula算法）")
        st.info("上传班级Excel量表数据，自动执行风险分级、变点检测、Copula异常识别")
        upload = st.file_uploader("上传普查Excel(xlsx)", type=["xlsx","xls"])
        if upload:
            df_raw = pd.read_excel(upload)
            st.subheader("原始数据预览")
            st.dataframe(df_raw.head())
            dims = st.multiselect("选择量表维度列", df_raw.columns.tolist())
            if len(dims)>=2 and st.button("启动智能风险筛查", type="primary"):
                if not _ALG_AVAILABLE:
                    st.error("算法包 psycho_screen 加载失败，请检查依赖")
                else:
                    if df_raw.shape[0]>1000:
                        st.warning("云端限制，仅处理前1000行数据")
                        df_raw = df_raw.head(1000)
                    with st.spinner("贝叶斯模型采样计算中..."):
                        df_out, trace, tau_mean = psycho_risk_screen(df_raw, dims)
                    st.session_state["df_screen_result"] = df_out
                    st.session_state["tau_cache"] = tau_mean
                    st.session_state["trace_cache"] = trace
                    st.success(f"计算完成，总分变点位置：{tau_mean}")
                    risk_cnt = df_out["风险等级"].value_counts()
                    c1,c2,c3 = st.columns(3)
                    c1.metric("高危人数", risk_cnt.get("高危",0), delta_color="inverse")
                    c2.metric("中危人数", risk_cnt.get("中危",0))
                    c3.metric("低危人数", risk_cnt.get("低危",0))
                    st.dataframe(df_out, use_container_width=True)
                    csv = df_out.to_csv(index=False, encoding="utf_8_sig")
                    st.download_button("导出筛查结果CSV", data=csv, file_name="班级心理筛查.csv")
    elif module == "风险分析总览":
        st.header("📈 班级风险分级总览")
        if df_cache is None:
            st.info("请先在批量筛查模块上传数据")
        else:
            risk_cnt = df_cache["风险等级"].value_counts()
            st.dataframe(risk_cnt)
            st.bar_chart(risk_cnt)
    elif module == "预警管理":
        st.header("🚨 高危学生预警管理")
        if df_cache is None:
            st.info("请先完成批量筛查")
        else:
            high_risk = df_cache[df_cache["风险等级"]=="高危"]
            st.subheader(f"高危学生名单（共{len(high_risk)}人）")
            st.dataframe(high_risk, use_container_width=True)
            st.caption("可线下约谈，标记干预记录")
    elif module == "个案追踪":
        st.header("👤 学生个案追踪档案")
        if df_cache is None:
            st.info("请先完成批量筛查")
        else:
            id_list = df_cache["编号"].unique()
            sel_id = st.selectbox("选择学生编号查看个案", id_list)
            one_stu = df_cache[df_cache["编号"]==sel_id]
            st.dataframe(one_stu, hide_index=True)
            st.text_area("干预记录填写", placeholder="记录约谈、疏导、回访情况")
    elif module == "班级趋势分析":
        st.header("📉 班级心理数据趋势分析")
        if df_cache is None:
            st.info("请先完成批量筛查")
        else:
            fig, ax = plt.subplots(figsize=(12,5))
            ax.plot(df_cache["编号"], df_cache["总分"], alpha=0.7, color="#4263eb")
            ax.axvline(x=tau_cache, color="red", linestyle="--", label=f"风险变点：{tau_cache}")
            ax.legend()
            ax.set_title("班级学生总分序列与贝叶斯风险变点")
            st.pyplot(fig)

# ===================== 管理端全部模块渲染 =====================
def render_admin_module(module):
    df_cache = st.session_state["df_screen_result"]
    if module == "全校数据决策":
        st.header("🏫 全校心理健康数据总览")
        st.info("汇总各班级筛查数据，支撑校心理中心决策")
        if df_cache is None:
            st.info("暂无筛查数据，请教师端上传班级数据")
        else:
            total = len(df_cache)
            high = len(df_cache[df_cache["风险等级"]=="高危"])
            mid = len(df_cache[df_cache["风险等级"]=="中危"])
            low = len(df_cache[df_cache["风险等级"]=="低危"])
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("全校统计样本", total)
            c2.metric("高危人数", high)
            c3.metric("中危人数", mid)
            c4.metric("低危人数", low)
    elif module == "全校趋势分析":
        st.header("📊 全校长期心理趋势分析")
        st.info("多批次普查数据对比，观察整体心理变化趋势")
        st.warning("多批次时序对比功能开发中，当前展示单批次分布")
        if df_cache is not None:
            st.pie_chart(df_cache["风险等级"].value_counts())
    elif module == "学校综合报告":
        st.header("📑 全校心理健康综合报告导出")
        if df_cache is None:
            st.info("无筛查数据无法生成报告")
        else:
            st.markdown("### 报告摘要")
            st.write(f"普查样本总量：{len(df_cache)}")
            st.write(f"高危占比：{round(len(df_cache[df_cache['风险等级']=='高危'])/len(df_cache)*100,2)}%")
            st.download_button("导出原始数据报表", data=df_cache.to_csv(index=False, encoding="utf_8_sig"), file_name="全校心理汇总.csv")
            st.caption("PDF图文报告功能迭代中")
    elif module == "用户账号管理":
        st.header("👥 平台账号权限管理")
        st.markdown("- 学生账号：仅自评、查看个人画像")
        st.markdown("- 教师账号：班级筛查、个案预警")
        st.markdown("- 管理员账号：全校数据、系统配置")
        st.text_input("新增账号")
        st.selectbox("分配角色", ["student","teacher","admin"])
        st.button("保存账号配置")
    elif module == "系统设置":
        st.header("⚙️ 系统基础配置")
        st.subheader("算法参数配置")
        st.slider("高危风险分阈值", min_value=1.0, max_value=2.5, value=1.5, step=0.1)
        st.slider("中危风险分阈值", min_value=0.0, max_value=1.2, value=0.5, step=0.1)
        st.divider()
        st.subheader("通知配置")
        st.checkbox("高危学生自动推送预警消息给辅导员")

# ===================== 主业务分发路由 =====================
def render_main_system():
    render_sidebar()
    role = st.session_state["role"]
    curr_mod = st.session_state["current_module"]
    if role == "student":
        render_student_module(curr_mod)
    elif role == "teacher":
        render_teacher_module(curr_mod)
    elif role == "admin":
        render_admin_module(curr_mod)

# ===================== 页面总路由控制 =====================
root_page = st.session_state["page_root"]
if root_page == "home":
    render_home_page()
elif root_page == "role_login":
    render_role_login()
elif root_page == "main":
    render_main_system()