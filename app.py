# -*- coding:utf‑8 -*-
"""
国创项目：高校心理健康动态监测与智能预警平台
启动命令：streamlit run app.py
【终极修复版】selectbox导航 + session字典存储 + 结果持久展示
"""
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from psycho_screen import psycho_risk_screen

# ========== matplotlib中文设置 ==========
try:
    plt.rcParams['font.sans-serif'] = ['SimHei']
    plt.rcParams['axes.unicode_minus'] = False
except Exception:
    pass

# ========== 页面基础配置 ==========
st.set_page_config(
    page_title="基于贝叶斯在线变点检测与Copula相依结构的高校心理健康动态监测与智能预警平台",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ========== 自定义CSS ==========
st.markdown("""
<style>
.block-container {
    padding-top: 3rem;
    padding-left: 3rem;
    padding-right: 3rem;
}
.title-wrap{
    text-align:center;
    margin-bottom:1rem;
}
.desc-text{
    text-align:center;
    color:#555555;
    font-size:16px;
    margin-bottom:2.5rem;
}
.upload-box{
    max-width:900px;
    margin:0 auto 2rem auto;
}
</style>
""", unsafe_allow_html=True)

# ========== session状态初始化（用字典key方式，最稳） ==========
def init_session():
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False
    if "username" not in st.session_state:
        st.session_state["username"] = ""
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = "数据上传与筛查"
    if "df_out" not in st.session_state:
        st.session_state["df_out"] = None
    if "tau_mean" not in st.session_state:
        st.session_state["tau_mean"] = None

init_session()

# ========== 登录页面 ==========
def login_page():
    col1, col_mid, col2 = st.columns([1, 2.2, 1])
    with col_mid:
        st.markdown("## 🔐 平台登录")
        st.markdown("高校心理健康动态监测与智能预警平台")
        st.divider()

        username = st.text_input("用户名", placeholder="请输入用户名")
        password = st.text_input("密码", type="password", placeholder="请输入密码")

        if st.button("登 录", type="primary", use_container_width=True):
            if username.strip() and password.strip():
                st.session_state["logged_in"] = True
                st.session_state["username"] = username
                st.success("登录成功，正在进入系统...")
                st.rerun()
            else:
                st.error("请输入用户名和密码")

        st.divider()
        st.caption("账号：任意用户名 + 任意密码即可登录")

# ========== 侧边栏渲染【改用selectbox，最稳定】 ==========
def render_sidebar():
    with st.sidebar:
        st.markdown("### 🧠 心理预警平台")
        st.markdown("---")
        st.markdown(f"👤 当前用户：**{st.session_state['username']}**")
        st.markdown("🏫 角色：心理中心老师")
        st.markdown("---")
        st.markdown("#### 📋 功能导航")
        # 改用selectbox，不会触发隐性rerun清空session
        st.session_state["current_page"] = st.selectbox(
            label="选择功能页面",
            options=["数据上传与筛查", "风险分级统计", "结果报告导出"],
            label_visibility="collapsed"
        )
        st.markdown("---")
        st.markdown("#### ℹ️ 关于平台")
        st.caption("底层算法：贝叶斯在线变点检测 + Copula相依结构")
        st.caption("适用场景：高校心理普查批量风险筛查")
        st.markdown("---")
        if st.button("退出登录", use_container_width=True):
            st.session_state["logged_in"] = False
            st.session_state["username"] = ""
            st.session_state["df_out"] = None
            st.session_state["tau_mean"] = None
            st.rerun()

# ========== 结果展示函数（抽出来，切换回来也能直接显示） ==========
def show_results(df_out, tau_mean, trace):
    st.success(f"✅ 计算完成，检测到总分变点位置：{tau_mean}")
    risk_cnt = df_out["风险等级"].value_counts()
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("高危人数", risk_cnt.get("高危", 0), delta_color="inverse")
    with c2:
        st.metric("中危人数", risk_cnt.get("中危", 0))
    with c3:
        st.metric("低危人数", risk_cnt.get("低危", 0))

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes[0,0].plot(df_out["编号"], df_out["总分"], alpha=0.6)
    axes[0,0].axvline(x=tau_mean, color="red", linestyle="--", label=f"变点:{tau_mean}")
    axes[0,0].set_title("心理普查总分序列与贝叶斯变点")
    axes[0,0].set_xlabel("样本编号")
    axes[0,0].set_ylabel("总分")
    axes[0,0].legend()

    tau_samples = trace.posterior["tau"].values.flatten()
    axes[0,1].hist(tau_samples, bins=30, density=True, alpha=0.7, color="steelblue")
    axes[0,1].axvline(tau_mean, color="red", linestyle="--")
    axes[0,1].set_title("变点位置后验分布")
    axes[0,1].set_xlabel("变点位置")

    axes[1,0].hist(df_out["Copula异常分"], bins=30, alpha=0.7, color="orange")
    axes[1,0].set_title("Copula相依异常分分布")
    axes[1,0].set_xlabel("异常分")

    risk_cnt = df_out["风险等级"].value_counts()
    axes[1,1].pie(risk_cnt.values, labels=risk_cnt.index, autopct="%1.1f%%",
                   colors=["#ff6b6b", "#ffd93d", "#6bcb77"])
    axes[1,1].set_title("样本风险分级占比")

    plt.tight_layout()
    st.pyplot(fig, width="stretch")

    st.subheader("📋 筛查输出结果表")
    st.dataframe(df_out, width="stretch")

    csv_data = df_out.to_csv(index=False, encoding="utf_8_sig")
    st.download_button("📥 下载筛查结果CSV", data=csv_data,
                       file_name="心理筛查输出.csv", mime="text/csv")

# ========== 主业务页面 ==========
def main_page():
    render_sidebar()
    page = st.session_state["current_page"]

    if page == "数据上传与筛查":
        st.markdown('<div class="title-wrap">', unsafe_allow_html=True)
        st.markdown("# 基于贝叶斯在线变点检测与Copula相依结构的高校心理健康动态监测与智能预警平台", unsafe_allow_html=True)
        st.markdown('<h4>心理普查数据智能筛查与风险预警工具</h4>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("""
        <div class="desc-text">
        本平台底层封装贝叶斯在线变点检测‑Copula相依结构算法包，对高校心理普查量表数据开展风险识别、异常样本检测、风险分级，输出筛查报告。
        </div>
        """, unsafe_allow_html=True)

        st.info("⚠️线上演示Demo受公有云算力内存限制，**仅支持300行以内小样本Excel测试**，大规模心理普查数据请在本地Anaconda环境运行完整算法。")

        # 如果已经有结果，先展示结果（切换回来不会丢）
        if st.session_state["df_out"] is not None:
            st.warning("⚠️ 当前已有筛查结果，重新上传文件并点击「开始风险筛查」将覆盖旧结果")
            # 注意：trace没存session，所以这里只展示表格和统计，不重绘贝叶斯后验图
            df_show = st.session_state["df_out"]
            tau_show = st.session_state["tau_mean"]
            st.success(f"✅ 上次筛查结果（变点位置：{tau_show}）")
            risk_cnt = df_show["风险等级"].value_counts()
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("高危人数", risk_cnt.get("高危", 0), delta_color="inverse")
            with c2:
                st.metric("中危人数", risk_cnt.get("中危", 0))
            with c3:
                st.metric("低危人数", risk_cnt.get("低危", 0))
            st.dataframe(df_show, width="stretch")
            csv_data = df_show.to_csv(index=False, encoding="utf_8_sig")
            st.download_button("📥 下载筛查结果CSV", data=csv_data,
                               file_name="心理筛查输出.csv", mime="text/csv")

        st.markdown('<div class="upload-box">', unsafe_allow_html=True)
        upload_file = st.file_uploader("📤 上传心理普查Excel文件", type=["xlsx", "xls"])
        st.markdown('</div>', unsafe_allow_html=True)

        if upload_file is not None:
            df_upload = pd.read_excel(upload_file)
            st.subheader("📊 原始数据预览")
            st.dataframe(df_upload.head(), width="stretch")

            dims = st.multiselect("请选择量表维度列（至少选2列）", df_upload.columns.tolist())
            if len(dims) >= 2 and st.button("🚀 开始风险筛查", type="primary"):
                with st.spinner("贝叶斯模型采样计算中，请等待..."):
                    df_out, trace, tau_mean = psycho_risk_screen(df_upload, dims)
                # 存入session
                st.session_state["df_out"] = df_out
                st.session_state["tau_mean"] = tau_mean
                # 展示完整结果（含trace绘图）
                show_results(df_out, tau_mean, trace)

    elif page == "风险分级统计":
        st.title("📈 风险分级统计")
        if st.session_state["df_out"] is None:
            st.info("请先在【数据上传与筛查】页面完成数据筛查")
        else:
            df = st.session_state["df_out"]
            risk_cnt = df["风险等级"].value_counts()
            st.dataframe(risk_cnt, width="stretch")
            st.bar_chart(risk_cnt)

    elif page == "结果报告导出":
        st.title("📑 结果报告导出")
        if st.session_state["df_out"] is None:
            st.info("请先在【数据上传与筛查】页面完成数据筛查")
        else:
            df = st.session_state["df_out"]
            csv_data = df.to_csv(index=False, encoding="utf_8_sig")
            st.download_button("📥 下载筛查结果CSV", data=csv_data,
                               file_name="心理筛查输出.csv", mime="text/csv")
            st.info("PDF报告功能待开发")

# ========== 页面路由 ==========
if st.session_state["logged_in"]:
    main_page()
else:
    login_page()