# -*- coding:utf-8 -*-
"""
国创项目：多角色高校心理健康动态监测与智能预警平台
【最终版】顶栏下移 + 圆图一排布局 + 修复DOM报错
启动：streamlit run app.py
"""
import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os
import io
import random
import math
import json
from datetime import datetime, timedelta
import bcrypt
import smtplib
import requests
from email.mime.text import MIMEText

# ===== 本地模块 =====
from db import (
    init_db, get_conn,
    save_self_assess, load_self_assess,
    save_screen_batch, load_latest_screen_batch,
    save_alert, load_alerts, update_alert_status,
    save_intervention, load_interventions, update_intervention_status,
    get_user_by_username, create_user, get_user_college
)
from auth import hash_password, check_password, login_user

# ===== 算法包 =====
try:
    from psycho_screen import psycho_risk_screen
    _ALG_AVAILABLE = True
except ImportError:
    psycho_risk_screen = None
    _ALG_AVAILABLE = False

# ===== 报告导出 =====
try:
    from docx import Document
    from docx.shared import Inches
    _DOCX_AVAILABLE = True
except ImportError:
    _DOCX_AVAILABLE = False

# ===== 中文字体兼容 =====
import matplotlib.font_manager as fm
def _setup_cjk_font():
    font_paths = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                fm.fontManager.addfont(fp)
            except Exception:
                pass
    candidates = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "WenQuanYi Zen Hei"]
    available = {f.name for f in fm.fontManager.ttflist}
    for name in candidates:
        if name in available:
            plt.rcParams['font.sans-serif'] = [name, 'DejaVu Sans']
            break
    plt.rcParams['axes.unicode_minus'] = False
_setup_cjk_font()

# ===== 页面配置 =====
st.set_page_config(
    page_title="高校心理健康智能监测平台",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ===== 全局CSS =====
st.markdown("""
<style>
.block-container {
    padding-top: 1rem !important;
    padding-left: 1rem;
    padding-right: 1rem;
    max-width: 1450px;
}
.dash-title { font-size:26px; font-weight:bold; color:#0F4C99; margin-bottom:20px; }
.sub-title { font-size: 20px; font-weight: 700; color: #1e293b; margin: .8rem 0 1rem; }
.alert-item { display:flex; align-items:center; padding:.7rem .8rem; border-radius:10px; background:#f8fafc; margin-bottom:.6rem; font-size:15px; border-left:5px solid #ff6b6b; }
.tag { font-size:13px; padding:3px 11px; border-radius:12px; color:#fff; white-space:nowrap; }
.tag-red { background:#ff6b6b; } .tag-yellow { background:#f7bc42; } .tag-green { background:#62bd69; }
.progress-row { margin-bottom:1rem; }
.progress-label { display:flex; justify-content:space-between; font-size:15px; color:#475569; margin-bottom:.35rem; }
.progress-track { height:12px; border-radius:10px; background:#eef2f7; overflow:hidden; }
.progress-fill { height:100%; border-radius:10px; transition: width .6s ease; }
.res-card { background:#fff; border:1px solid #eef2f7; border-radius:16px; padding:1.4rem 1.5rem; box-shadow:0 3px 10px rgba(0,0,0,.05); height:100%; margin-bottom:1rem; }
.res-icon { font-size: 34px; margin-bottom: .6rem; }
.res-card h5 { margin:.4rem 0 .4rem; font-size:17px; color:#334155; }
.res-card p { margin:0; font-size:15px; color:#64748b; line-height:1.75; }
.res-tag { display:inline-block; font-size:13px; padding:3px 12px; border-radius:12px; margin-bottom:.4rem; }
.res-tag.blue { background:#e7f0ff; color:#3b5bdb; }
.res-tag.green { background:#e6fcf5; color:#0ca678; }
.res-tag.orange { background:#fff4e6; color:#f76707; }
.res-tag.red { background:#ffe3e3; color:#ff6b6b; }
/* 顶栏：margin-top下移，解决标题被遮挡 */
.top-bar-wrap{margin-top:28px;margin-bottom:12px;}
.top-bar{background:linear-gradient(135deg,#0F4C99,#1a6bc4);color:white;padding:14px 24px;border-radius:14px;display:flex;justify-content:space-between;align-items:center;box-shadow:0 4px 14px rgba(15,76,153,0.2);}
.top-logo{font-size:22px;font-weight:bold;display:flex;align-items:center;gap:10px;}
.top-user-info{display:flex;gap:18px;align-items:center;font-size:15px;}
.logout-btn{background:rgba(255,255,255,0.2);border:1px solid rgba(255,255,255,0.28);color:white;padding:7px 18px;border-radius:8px;cursor:pointer;text-decoration:none;}
.logout-btn:hover{background:rgba(255,255,255,0.32);}
@media (max-width: 768px) {
    .block-container { padding-left: 0.6rem; padding-right: 0.6rem; padding-top:1.2rem !important; }
    .top-bar{flex-direction:column;gap:10px;padding:12px 16px;}
}
</style>
""", unsafe_allow_html=True)

# ===== 通用卡片辅助 =====
def _metric_card_html(title, value, delta="", color="#0F4C99", icon=""):
    return f"""
    <div style="background:{color};border-radius:14px;padding:20px 24px;color:white;box-shadow:0 6px 16px rgba(0,0,0,0.16);height:100%;">
        <div style="font-size:15px;opacity:0.88;display:flex;justify-content:space-between;">
            <span>{title}</span>
            <span style="font-size:28px;">{icon}</span>
        </div>
        <div style="font-size:34px;font-weight:bold;margin:8px 0;">{value}</div>
        <div style="font-size:14px;opacity:0.92;">{delta}</div>
    </div>
    """

def _suggestion_card_html(title, desc, action, color="#4f6ef7"):
    return f"""
    <div style="background:{color};border-radius:14px;padding:20px 24px;color:white;margin-bottom:16px;box-shadow:0 4px 12px rgba(0,0,0,0.12);">
        <div style="font-weight:bold;font-size:18px;display:flex;align-items:center;gap:10px;">{title}</div>
        <div style="font-size:16px;opacity:0.95;margin:6px 0;">{desc}</div>
        <div style="font-size:15px;opacity:0.85;margin-top:6px;">💡 {action}</div>
    </div>
    """

# ===== 消息推送 =====
def send_email(recipient, subject, body):
    try:
        sender = os.getenv("SMTP_USER", "alert@school.edu")
        password = os.getenv("SMTP_PASS", "")
        if not password:
            st.warning("未配置邮件密码，消息未发送")
            return
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = recipient
        server = smtplib.SMTP(os.getenv("SMTP_HOST", "smtp.qq.com"), int(os.getenv("SMTP_PORT", 587)))
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, [recipient], msg.as_string())
        server.quit()
        st.success("邮件已发送")
    except Exception as e:
        st.error(f"邮件发送失败: {e}")

def send_wechat_robot(webhook_url, content):
    try:
        data = {"msgtype": "text", "text": {"content": content}}
        response = requests.post(webhook_url, json=data)
        if response.status_code == 200:
            st.success("企业微信通知已发送")
        else:
            st.error(f"通知失败: {response.text}")
    except Exception as e:
        st.error(f"通知异常: {e}")

# ===== 示例数据生成（函数内部不调用 st.rerun） =====
def generate_student_example():
    history = []
    base_date = datetime.now() - timedelta(days=10)
    for i in range(3):
        date_str = (base_date + timedelta(days=i*3)).strftime("%Y-%m-%d %H:%M")
        data = pd.DataFrame({
            "自评时间": [date_str],
            "焦虑": [random.randint(5, 25)],
            "抑郁": [random.randint(5, 20)],
            "压力": [random.randint(8, 30)],
            "睡眠障碍": [random.randint(2, 20)],
            "社交回避": [random.randint(2, 18)],
        })
        data["总分"] = data[["焦虑","抑郁","压力","睡眠障碍","社交回避"]].sum(axis=1)
        history.append(data)
    st.session_state["student_self_history"] = history

def generate_teacher_example():
    np.random.seed(42)
    n = 100
    total_scores = np.random.normal(50, 15, n).astype(int)
    total_scores = np.clip(total_scores, 10, 80)
    risk_scores = np.random.normal(0, 1, n)
    risk_scores = np.clip(risk_scores, -1.5, 3.0)
    def level(s):
        if s >= 1.5: return "高危"
        elif s >= 0.5: return "中危"
        else: return "低危"
    levels = [level(s) for s in risk_scores]
    copula_scores = np.random.exponential(1, n) + 0.5
    df_sim = pd.DataFrame({
        "编号": np.arange(1, n+1),
        "总分": total_scores,
        "综合风险分": risk_scores,
        "风险等级": levels,
        "Copula异常分": copula_scores,
    })
    st.session_state["df_screen_result"] = df_sim
    st.session_state["tau_cache"] = int(n * 0.6)
    st.session_state["copula_score"] = copula_scores
    st.session_state["trace_cache"] = None

def generate_admin_example():
    if "admin_student_df" not in st.session_state:
        rng = np.random.default_rng(2024)
        names = ["张伟","李娜","王芳","刘洋","陈静","杨帆","赵磊","孙悦","周婷","吴昊"]
        schools = ["计算机学院","外国语学院","经济管理学院","机械工程学院","文学院","艺术学院"]
        n = 80
        stu_df = pd.DataFrame({
            "学号": [f"2024{1000+i}" for i in range(n)],
            "姓名": [rng.choice(names) for _ in range(n)],
            "学院": [rng.choice(schools) for _ in range(n)],
            "年级": [rng.choice(["大一","大二","大三","大四"], p=[0.3,0.3,0.25,0.15]) for _ in range(n)],
            "心理状态": [rng.choice(["良好","良好","良好","关注","预警"], p=[0.6,0.2,0.1,0.06,0.04]) for _ in range(n)],
            "最近测评": [f"2024-09-{rng.integers(1,21):02d}" for _ in range(n)],
        })
        st.session_state["admin_student_df"] = stu_df
    if "admin_alert_df" not in st.session_state:
        rng = np.random.default_rng(9)
        names = ["张伟","李娜","王芳","刘洋","陈静","杨帆","赵磊","孙悦","周婷","吴昊","郑爽","钱进"]
        alert_df = pd.DataFrame({
            "学号": [f"2024{1000+i}" for i in range(1, 13)],
            "姓名": [rng.choice(names) for _ in range(12)],
            "学院": [rng.choice(["计算机学院","外国语学院","经济管理学院","机械工程学院"]) for _ in range(12)],
            "风险等级": [rng.choice(["高危","高危","中危"]) for _ in range(12)],
            "综合风险分": [round(rng.uniform(1.5, 3.2), 2) for _ in range(12)],
            "预警时间": [f"2024-09-{rng.integers(1, 13):02d}" for _ in range(12)],
            "处置状态": [rng.choice(["待跟进","干预中","已转介","已结案"], p=[0.3,0.4,0.2,0.1]) for _ in range(12)],
        })
        st.session_state["admin_alert_df"] = alert_df
    if "admin_intervention_df" not in st.session_state:
        rng = np.random.default_rng(21)
        names = ["张伟","李娜","王芳","刘洋","陈静","杨帆","赵磊","孙悦"]
        inter_df = pd.DataFrame({
            "学生": [rng.choice(names) for _ in range(8)],
            "风险等级": [rng.choice(["高危","高危","中危"]) for _ in range(8)],
            "干预方式": [rng.choice(["一对一咨询","正念减压","团体辅导","家校联动","转介中心"]) for _ in range(8)],
            "负责人": [rng.choice(["张老师","李老师","王老师","刘老师"]) for _ in range(8)],
            "开始时间": [f"2024-09-{rng.integers(1, 15):02d}" for _ in range(8)],
            "状态": [rng.choice(["干预中","干预中","已结案"], p=[0.5,0.3,0.2]) for _ in range(8)],
        })
        st.session_state["admin_intervention_df"] = inter_df

def generate_word_report(batch_name, tau, df, stat_df, fig_pie):
    if not _DOCX_AVAILABLE:
        st.error("请安装 python-docx：pip install python-docx")
        return
    doc = Document()
    doc.add_heading('心理普查筛查报告', 0)
    doc.add_heading(f'批次：{batch_name}', level=1)
    doc.add_paragraph(f'检测变点位置：{tau:.1f}')
    doc.add_heading('风险统计表', level=2)
    table = doc.add_table(rows=stat_df.shape[0]+1, cols=stat_df.shape[1])
    for i, col in enumerate(stat_df.columns):
        table.cell(0, i).text = col
    for i, row in stat_df.iterrows():
        for j, val in enumerate(row):
            table.cell(i+1, j).text = str(val)
    doc.add_heading('风险占比图', level=2)
    img_stream = io.BytesIO()
    fig_pie.savefig(img_stream, format='png')
    img_stream.seek(0)
    doc.add_picture(img_stream, width=Inches(5))
    doc.add_heading('高危学生名单', level=2)
    high_df = df[df['风险等级']=='高危']
    if len(high_df)>0:
        table2 = doc.add_table(rows=len(high_df)+1, cols=len(high_df.columns))
        for i, col in enumerate(high_df.columns):
            table2.cell(0, i).text = col
        for i, row in high_df.iterrows():
            for j, val in enumerate(row):
                table2.cell(i+1, j).text = str(val)
    else:
        doc.add_paragraph('无高危学生')
    doc.save('筛查报告.docx')
    with open('筛查报告.docx', 'rb') as f:
        st.download_button('📄 下载Word报告', data=f, file_name='筛查报告.docx')

# ===== Session初始化 =====
def init_session():
    init_db()
    if "page_root" not in st.session_state:
        st.session_state["page_root"] = "home"
    if "role" not in st.session_state:
        st.session_state["role"] = ""
    if "username" not in st.session_state:
        st.session_state["username"] = ""
    if "user_college" not in st.session_state:
        st.session_state["user_college"] = None
    if "current_module" not in st.session_state:
        st.session_state["current_module"] = ""
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
    if "student_self_history" not in st.session_state:
        st.session_state["student_self_history"] = []
    if "global_high_thr" not in st.session_state:
        st.session_state["global_high_thr"] = 1.5
    if "global_mid_thr" not in st.session_state:
        st.session_state["global_mid_thr"] = 0.5
    if "multi_batch_history" not in st.session_state:
        st.session_state["multi_batch_history"] = {
            "批次": [f"2026-0{i}" for i in range(1,9)],
            "高危": [random.randint(2,12) for _ in range(8)],
            "中危": [random.randint(5,18) for _ in range(8)],
            "低危": [random.randint(20,40) for _ in range(8)]
        }
init_session()

# ===== 加载用户数据 =====
def load_user_data(username, role, college):
    hist_df = load_self_assess(username, college=college if role=="student" else None)
    if not hist_df.empty:
        st.session_state["student_self_history"] = [hist_df.iloc[[i]] for i in range(len(hist_df))]
    if role in ["teacher", "admin"]:
        batch_name, tau, df_data, copula = load_latest_screen_batch(college=college if role=="teacher" else None)
        if df_data is not None:
            st.session_state["df_screen_result"] = df_data
            st.session_state["tau_cache"] = tau
            st.session_state["copula_score"] = copula
            st.session_state["batch_note"] = batch_name

# ===== 访客首页顶部导航 =====
def render_top_nav_home():
    nav_html = """
    <style>
        .top-nav-home {
            background: linear-gradient(135deg, #0F4C99, #1a6bc4);
            padding: 0 3rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            height: 84px;
            box-shadow: 0 6px 20px rgba(0,0,0,0.20);
            border-radius: 16px;
            margin-top: 40px;
            margin-bottom:12px;
            border: 1px solid rgba(255,255,255,0.10);
        }
        .nav-brand {
            color: white;
            font-size: 26px;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 14px;
            white-space: nowrap;
        }
        .nav-brand .sub {
            font-size: 15px;
            font-weight: 400;
            opacity: 0.75;
            margin-left: 6px;
        }
        .nav-menu-home {
            display: flex;
            gap:10px;
            flex: 1;
            margin: 0 2.5rem;
        }
        .nav-item-home {
            color: rgba(255,255,255,0.75);
            padding: 12px 22px;
            border-radius:10px;
            font-size:17px;
            white-space: nowrap;
            text-decoration: none;
            transition: all 0.3s;
            font-weight: 500;
        }
        .nav-item-home:hover {
            color: white;
            background: rgba(255,255,255,0.18);
        }
        .nav-item-home.active {
            color: white;
            background: rgba(255,255,255,0.26);
            font-weight: 600;
        }
        .nav-user-home {
            color: rgba(255,255,255,0.92);
            font-size:16px;
            display: flex;
            align-items: center;
            gap:22px;
        }
        .login-btn {
            background: rgba(255,255,255,0.22);
            border: 1px solid rgba(255,255,255,0.30);
            color: white;
            padding:10px 28px;
            border-radius:10px;
            cursor: pointer;
            font-size:16px;
            transition: all 0.3s;
            text-decoration: none;
            font-weight: 500;
        }
        .login-btn:hover {
            background: rgba(255,255,255,0.36);
            transform: translateY(-2px);
            box-shadow:0 6px 16px rgba(0,0,0,0.22);
        }
        .nav-divider {
            color: rgba(255,255,255,0.25);
            font-size:24px;
        }
        @media (max-width: 768px) {
            .top-nav-home {
                padding: 0 1rem;
                flex-wrap: wrap;
                height: auto;
                min-height:70px;
                margin-top:20px;
                border-radius:10px;
                padding:0.8rem 1rem;
            }
            .nav-brand { font-size:20px; }
            .nav-brand .sub { display:none; }
            .nav-item-home { font-size:14px; padding:8px 14px; }
            .nav-user-home { font-size:14px; gap:12px; }
            .login-btn { padding:7px 16px; font-size:14px; }
            .nav-menu-home { margin:0 0.4rem; gap:6px; flex-wrap:wrap; }
            .nav-divider { display:none; }
        }
    </style>
    <div class="top-nav-home">
        <div class="nav-brand">
            🧠 心理监测平台
            <span class="sub">| 健康校园 · 智能预警</span>
        </div>
        <div class="nav-menu-home">
            <span class="nav-item-home active">📊 总览大屏</span>
            <span class="nav-item-home">📝 心理普查</span>
            <span class="nav-item-home">📈 数据分析</span>
            <span class="nav-item-home">📚 资源中心</span>
        </div>
        <div class="nav-user-home">
            <span style="opacity:0.65;">👤 访客</span>
            <span class="nav-divider">|</span>
            <a href="?login=1" class="login-btn">🔑 登录</a>
        </div>
    </div>
    """
    st.markdown(nav_html, unsafe_allow_html=True)
    qp = st.query_params
    if "login" in qp:
        st.session_state["page_root"] = "role_login"
        st.query_params.clear()
        st.rerun()

# ===== 登录后顶部顶栏 =====
def render_top_bar():
    username = st.session_state.get("username","")
    role = st.session_state.get("role","")
    college = st.session_state.get("user_college","")
    html = f"""
    <div class="top-bar-wrap">
        <div class="top-bar">
            <div class="top-logo">🧠 高校心理健康动态监测与智能预警平台</div>
            <div class="top-user-info">
                <span>👤 {username}｜{role}｜🏫{college if college else '全校'}</span>
                <a href="?logout=1" class="logout-btn">🚪退出登录</a>
            </div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
    qp = st.query_params
    if "logout" in qp:
        st.session_state["page_root"] = "home"
        st.session_state["role"] = ""
        st.session_state["username"] = ""
        st.session_state["user_college"] = None
        st.query_params.clear()
        st.rerun()

# ===== 访客首页（圆图一排布局） =====
def render_home_page():
    render_top_nav_home()
    st.markdown("""
    <div style="text-align:center;padding:0.5rem 0 1rem 0;">
        <span style="font-size:32px;font-weight:bold;color:#0F4C99;">🏠 心理健康监测总览</span>
        <span style="font-size:18px;color:#666;margin-left:20px;">基于贝叶斯在线变点检测与Copula相依结构</span>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    metric_data = [
        {"title":"在校学生总数","value":"28,542","delta":"↑4.2%","color":"#0F4C99"},
        {"title":"已完成测评人数","value":"24,532","delta":"完成率 86.0%","color":"#1967D2"},
        {"title":"当前预警总人数","value":"1,257","delta":"预警占比5.1%","color":"#D93025"},
        {"title":"干预中人数","value":"842","delta":"干预率3.4%","color":"#2E7D32"},
    ]
    for idx, col in enumerate([col1, col2, col3, col4]):
        item = metric_data[idx]
        with col:
            st.markdown(f"""
            <div style="background-color:{item['color']};border-radius:16px;padding:24px;color:white;box-shadow:0 6px 16px #00000022;">
                <div style="font-size:15px;opacity:0.85;">{item['title']}</div>
                <div style="font-size:36px;font-weight:bold;margin:10px 0;">{item['value']}</div>
                <div style="font-size:14px;">{item['delta']}</div>
            </div>
            """, unsafe_allow_html=True)

    st.divider()
    # ===== 第一排：饼图 + 雷达图（圆图一排） =====
    row1_col1, row1_col2 = st.columns(2)
    with row1_col1:
        st.markdown("**📊 预警分层统计**")
        pie_labels = ["高危", "中危", "低风险"]
        pie_vals = [312, 945, 22620]
        pie_colors = ["#D93025", "#F57C00", "#2E7D32"]
        fig_pie, ax_pie = plt.subplots(figsize=(10, 5), dpi=110)
        wedges, texts, autotexts = ax_pie.pie(pie_vals, labels=pie_labels, colors=pie_colors,
                                              autopct="%.1f%%", startangle=90,
                                              textprops={'fontsize': 11})
        wedges[0].set_edgecolor('white')
        wedges[0].set_linewidth(2)
        ax_pie.set_title(f"总测评人数 {sum(pie_vals):,}", fontsize=12)
        st.pyplot(fig_pie)
    with row1_col2:
        st.markdown("**🕸️ 风险维度分布**")
        fig_radar = plt.figure(figsize=(10, 5), dpi=110)
        ax_radar = fig_radar.add_subplot(111, polar=True)
        labels = ["焦虑风险", "睡眠问题", "学业压力", "社交压力", "生活满意度"]
        values = [68, 55, 72, 48, 22]
        N = len(labels)
        angles = [n / float(N) * 2 * math.pi for n in range(N)]
        values_plot = values + [values[0]]
        angles_plot = angles + [angles[0]]
        ax_radar.plot(angles_plot, values_plot, color="#D93025", linewidth=2)
        ax_radar.fill(angles_plot, values_plot, color="#D93025", alpha=0.25)
        ax_radar.set_xticks(angles)
        ax_radar.set_xticklabels(labels, fontsize=10)
        ax_radar.set_yticks([20, 40, 60, 80])
        ax_radar.set_ylim(0, 100)
        st.pyplot(fig_radar)

    # ===== 第二排：折线图 + 柱状图 =====
    row2_col1, row2_col2 = st.columns(2)
    with row2_col1:
        st.markdown("**📈 心理风险趋势（月度）**")
        months = pd.date_range("2024-01-01", "2025-03-01", freq="MS").strftime("%Y-%m").tolist()
        np.random.seed(42)
        trend = np.linspace(35, 25, len(months)) + np.random.normal(0, 2, len(months))
        for i, m in enumerate(months):
            if m >= "2024-06":
                trend[i] += 8 * (1 - np.exp(-0.3 * (i - 5)))
        fig_trend, ax_trend = plt.subplots(figsize=(10, 5), dpi=110)
        ax_trend.plot(months, trend, color="#0F4C99", linewidth=2, marker='o', markersize=4)
        ax_trend.set_xticks(months[::3])
        ax_trend.tick_params(axis='x', rotation=45)
        ax_trend.set_ylabel("风险指数")
        ax_trend.grid(alpha=0.2)
        for sp in ["top", "right"]:
            ax_trend.spines[sp].set_visible(False)
        fig_trend.tight_layout()
        st.pyplot(fig_trend)
    with row2_col2:
        st.markdown("**📊 风险等级人数**")
        risk_levels = ["高危", "中危", "低风险"]
        counts = [312, 945, 22620]
        colors_bar = ["#D93025", "#F57C00", "#2E7D32"]
        fig_bar, ax_bar = plt.subplots(figsize=(10, 5), dpi=110)
        bars = ax_bar.bar(risk_levels, counts, color=colors_bar, width=0.5)
        for bar, count in zip(bars, counts):
            ax_bar.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 100,
                        f"{count:,}", ha='center', fontsize=10, fontweight='bold')
        ax_bar.set_ylabel("人数", fontsize=10)
        ax_bar.tick_params(axis='both', labelsize=10)
        for spine in ['top', 'right']:
            ax_bar.spines[spine].set_visible(False)
        fig_bar.tight_layout()
        st.pyplot(fig_bar)

    st.divider()
    cc1, cc2, cc3 = st.columns([3, 2, 2])
    with cc1:
        st.markdown("**🔍 Copula相依结构分析（抑郁×焦虑风险）**")
        fig_cop, ax_cop = plt.subplots(figsize=(11, 5), dpi=110)
        n_sample = 1200
        cov_mat = [[1, 0.72], [0.72, 1]]
        data_cop = np.random.multivariate_normal([12, 14], cov_mat, size=n_sample)
        sc = ax_cop.scatter(data_cop[:,0], data_cop[:,1], c=data_cop[:,0]+data_cop[:,1],
                            cmap="jet", alpha=0.6, s=14)
        fig_cop.colorbar(sc, ax=ax_cop, label="综合风险分数")
        ax_cop.set_xlabel("抑郁风险得分")
        ax_cop.set_ylabel("焦虑风险得分")
        for sp in ["top", "right"]:
            ax_cop.spines[sp].set_visible(False)
        fig_cop.tight_layout()
        st.pyplot(fig_cop)
    with cc2:
        st.markdown("**📈 干预效果评估（近6个月）**")
        fig_eff, ax_eff = plt.subplots(figsize=(5, 4.5), dpi=110)
        month = ["3月", "4月", "5月", "6月", "7月", "8月"]
        eff_rate = [62, 67, 71, 74, 77, 78.6]
        ax_eff.plot(month, eff_rate, marker="o", color="#0F4C99", linewidth=2)
        ax_eff.set_ylim(50, 90)
        ax_eff.set_ylabel("干预有效率%")
        for sp in ["top", "right"]:
            ax_eff.spines[sp].set_visible(False)
        fig_eff.tight_layout()
        st.pyplot(fig_eff)
    with cc3:
        st.markdown("**🚨 预警动态（最新）**")
        warn_df = pd.DataFrame([
            {"学号":"202201041","姓名":"张同学","学院":"计算机学院","风险等级":"高危预警","时间":"2026-08-10"},
            {"学号":"202203072","姓名":"李同学","学院":"外国语学院","风险等级":"中风险预警","时间":"2026-08-10"},
            {"学号":"202302015","姓名":"王同学","学院":"经济管理学院","风险等级":"高危预警","时间":"2026-08-09"},
            {"学号":"202105033","姓名":"赵同学","学院":"艺术学院","风险等级":"中风险预警","时间":"2026-08-09"},
            {"学号":"202201088","姓名":"孙同学","学院":"文学院","风险等级":"低风险预警","时间":"2026-08-08"},
        ])
        def warn_color(val):
            if "高危" in val:
                return "background-color:#ffe8e8;color:#c00000"
            elif "中风险" in val:
                return "background-color:#fff3e0;color:#e65100"
            else:
                return "background-color:#e8f5e9;color:#2e7d32"
        st.dataframe(warn_df.style.map(warn_color, subset=["风险等级"]),
                     hide_index=True, use_container_width=True, height=320)
    st.divider()
    st.markdown("### 🧩 快捷功能入口")
    b1,b2,b3,b4,b5,b6,b7,b8 = st.columns(8)
    btn_info = [
        ("📝", "心理普查", "student"),
        ("⚠️", "风险分析", "teacher"),
        ("📈", "数据决策", "admin"),
        ("👤", "个案追踪", "teacher"),
        ("🏛️", "管理后台", "admin"),
        ("📊", "统计分析", "admin"),
        ("📚", "资源中心", "admin"),
        ("⚙️", "系统设置", "admin")
    ]
    for idx, col in enumerate([b1,b2,b3,b4,b5,b6,b7,b8]):
        icon, txt, role = btn_info[idx]
        with col:
            if st.button(f"{icon}\n{txt}", key=f"home_quick_{idx}", use_container_width=True):
                st.session_state["page_root"] = "role_login"
                st.session_state["role"] = role
                st.rerun()
            st.caption(f"👤 {role}端")
    st.divider()
    st.caption("📊 数据来源：基于模拟数据展示 | 算法：贝叶斯在线变点检测 + Copula相依结构 | 更新：2026-08-18")

# ===== 登录页 =====
def render_role_login():
    st.markdown("<br>" * 4, unsafe_allow_html=True)
    role_map = {"student": "学生端", "teacher": "教师端", "admin": "管理端"}
    role = st.session_state.get("role", "")
    if not role or role not in role_map:
        st.warning("请先选择登录角色（从首页进入）")
        if st.button("返回首页", use_container_width=True):
            st.session_state["page_root"] = "home"
            st.rerun()
        return
    role_cn = role_map[role]
    st.markdown(f"""
        <div style="text-align:center;font-size:38px;font-weight:900;color:#364fc7;
             text-shadow:0 2px 12px rgba(54,79,199,0.2);margin-bottom:0.2rem;">
            {role_cn}登录
        </div>
    """, unsafe_allow_html=True)
    col1, col_mid, col2 = st.columns([1,2,1])
    with col_mid:
        with st.container():
            user = st.text_input("账号", placeholder="请输入用户名")
            pwd = st.text_input("密码", type="password", placeholder="请输入密码")
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("返回首页", use_container_width=True):
                    st.session_state["page_root"] = "home"
                    st.rerun()
            with col_b:
                if st.button("登录", type="primary", use_container_width=True):
                    if user.strip() and pwd.strip():
                        role_result, college = login_user(user.strip(), pwd.strip())
                        if role_result:
                            st.session_state["username"] = user
                            st.session_state["role"] = role_result
                            st.session_state["user_college"] = college
                            mod_map = {"student": "心理普查（自评问卷）", "teacher": "心理普查批量筛查", "admin": "首页概览"}
                            st.session_state["current_module"] = mod_map[role_result]
                            st.session_state["page_root"] = "main"
                            load_user_data(user, role_result, college)
                            st.rerun()
                        else:
                            st.error("用户名或密码错误")
                    else:
                        st.error("请输入账号和密码")
            st.caption("默认管理员：admin / admin123 | 教师：teacher / 123456 | 学生：student / 123456")

# ========================== 学生端模块 ==========================
def render_student_module(module):
    history = st.session_state["student_self_history"]
    college = st.session_state["user_college"]
    if module == "心理普查（自评问卷）":
        st.header("📝 学生心理自评普查问卷")
        st.info("填写量表完成自评，自动存档历史记录，生成多维心理画像")
        if not history:
            st.warning("📭 暂无自评数据，请填写问卷提交，或点击下方按钮加载示例数据体验")
            if st.button("📥 加载示例自评数据", type="primary"):
                generate_student_example()
                st.rerun()
        with st.container(border=True):
            st.markdown("#### 📋 填写量表")
            with st.form("self_form", clear_on_submit=True):
                anxiety = st.slider("焦虑维度得分（0-40）",0,40,10)
                depression = st.slider("抑郁维度得分（0-40）",0,40,8)
                stress = st.slider("压力维度得分（0-40）",0,40,12)
                sleep = st.slider("睡眠障碍（0-30）",0,30,5)
                social = st.slider("社交回避（0-30）",0,30,4)
                submit = st.form_submit_button("✅ 提交自评并存档", type="primary")
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
                save_self_assess(st.session_state["username"], self_data, college)
                st.success(f"✅ 自评提交成功，已保存至历史存档，提交时间：{now}")
                st.rerun()
    elif module == "个人状态画像雷达图":
        st.header("📊 个人多维度心理状态雷达画像")
        if not history:
            st.warning("📭 暂无自评数据，请先前往【心理普查（自评问卷）】提交数据或加载示例数据")
            if st.button("📥 加载示例自评数据", type="primary"):
                generate_student_example()
                st.rerun()
            return
        latest = history[-1]
        dims = ["焦虑","抑郁","压力","睡眠障碍","社交回避"]
        values = latest[dims].iloc[0].values
        st.subheader("📌 最新自评数据")
        with st.container(border=True):
            st.dataframe(latest, hide_index=True, use_container_width=True)
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown(_metric_card_html("当前心理总分", int(latest["总分"].iloc[0]), color="#4f6ef7"), unsafe_allow_html=True)
            all_history = pd.concat(history, ignore_index=True)
            csv = all_history.to_csv(index=False, encoding="utf_8_sig")
            st.download_button("📥 导出全部自评历史CSV", data=csv, file_name="学生自评历史记录.csv", use_container_width=True)
        with col2:
            with st.container(border=True):
                fig = plt.figure(figsize=(8, 6))
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
    elif module == "历史自评存档":
        st.header("🗃️ 个人自评历史存档记录")
        if not history:
            st.warning("📭 暂无自评记录，请先前往【心理普查（自评问卷）】提交数据或加载示例数据")
            if st.button("📥 加载示例自评数据", type="primary"):
                generate_student_example()
                st.rerun()
            return
        all_df = pd.concat(history, ignore_index=True)
        with st.container(border=True):
            st.dataframe(all_df, use_container_width=True)
        with st.container(border=True):
            fig, ax = plt.subplots(figsize=(12, 5))
            ax.plot(all_df["自评时间"], all_df["总分"], marker="o", color="#7950f2", linewidth=2)
            ax.tick_params(axis='x', rotation=30)
            ax.set_ylabel("总分")
            ax.grid(alpha=0.2)
            st.pyplot(fig)
    elif module == "个性化心理建议库":
        st.header("💡 分级个性化心理疏导建议库")
        if not history:
            st.warning("📭 暂无自评数据，请先前往【心理普查（自评问卷）】提交数据或加载示例数据")
            if st.button("📥 加载示例自评数据", type="primary"):
                generate_student_example()
                st.rerun()
            return
        latest = history[-1]
        a = latest["焦虑"].iloc[0]
        d = latest["抑郁"].iloc[0]
        s = latest["压力"].iloc[0]
        slp = latest["睡眠障碍"].iloc[0]
        soc = latest["社交回避"].iloc[0]
        st.subheader("🧠 智能分级疏导建议")
        has_advice = False
        if a >= 25:
            st.markdown(_suggestion_card_html("🔴 焦虑指标偏高", "每日20分钟正念呼吸训练，每周预约心理中心一对一咨询", "减少长期独处，坚持冥想放松", color="#D93025"), unsafe_allow_html=True)
            has_advice = True
        elif a >= 15:
            st.markdown(_suggestion_card_html("🟡 轻度焦虑", "睡前减少刷手机，增加户外散步", "调整作息，增加运动", color="#F57C00"), unsafe_allow_html=True)
            has_advice = True
        if d >= 22:
            st.markdown(_suggestion_card_html("🔴 抑郁倾向明显", "主动参与班级社团活动，避免熬夜封闭自己", "多与人交流，必要时线下心理咨询", color="#D93025"), unsafe_allow_html=True)
            has_advice = True
        if s >= 28:
            st.markdown(_suggestion_card_html("🔴 学业压力过载", "拆分学习目标，每日保证30分钟运动", "合理规划任务，劳逸结合", color="#D93025"), unsafe_allow_html=True)
            has_advice = True
        if slp >= 18:
            st.markdown(_suggestion_card_html("🟡 睡眠质量较差", "固定作息，睡前不使用电子设备", "尝试助眠音乐或冥想", color="#F57C00"), unsafe_allow_html=True)
            has_advice = True
        if soc >= 16:
            st.markdown(_suggestion_card_html("🟡 社交回避轻微", "从小型集体活动逐步适应社交", "勇敢迈出第一步", color="#F57C00"), unsafe_allow_html=True)
            has_advice = True
        if not has_advice:
            st.markdown(_suggestion_card_html("🟢 各项心理指标状态良好", "保持现有生活节奏，继续积极心态", "规律作息，适度运动", color="#2E7D32"), unsafe_allow_html=True)
        st.divider()
        st.info("🏥 线下咨询渠道：学校大学生心理健康教育中心，工作日 8:30-17:00 免费预约")

# ========================== 教师端模块 ==========================
def render_teacher_module(module):
    df_cache = st.session_state["df_screen_result"]
    tau_cache = st.session_state["tau_cache"]
    copula_scores = st.session_state["copula_score"]
    high_thr = st.session_state["global_high_thr"]
    mid_thr = st.session_state["global_mid_thr"]
    batch_note = st.session_state["batch_note"]
    college = st.session_state["user_college"]
    def empty_state_with_load():
        st.warning("📭 暂无筛查数据，请先上传Excel文件进行批量筛查，或点击下方按钮加载示例数据")
        if st.button("📥 加载示例教师数据", type="primary"):
            generate_teacher_example()
            st.rerun()
    if module == "心理普查批量筛查":
        st.header("📤 批量学生普查数据筛查（贝叶斯-Copula完整算法）")
        st.info("上传班级Excel量表数据，自动执行风险分级、变点检测、Copula相依异常识别")
        with st.container(border=True):
            with st.expander("⚙️ 本次筛查独立参数配置", expanded=False):
                col_p1, col_p2 = st.columns(2)
                with col_p1:
                    local_high = st.slider("本次高危风险阈值", min_value=0.8, max_value=2.5, value=high_thr, step=0.05)
                with col_p2:
                    local_mid = st.slider("本次中危风险阈值", min_value=0.2, max_value=1.2, value=mid_thr, step=0.05)
                batch_note_input = st.text_input("本批次普查备注", placeholder="例如：2026秋季大一计算机班普查")
        with st.container(border=True):
            upload = st.file_uploader("上传普查Excel(xlsx)", type=["xlsx","xls"])
            if upload:
                df_raw = pd.read_excel(upload)
                st.subheader("📄 原始数据预览")
                st.dataframe(df_raw.head(10), hide_index=True)
                dims = st.multiselect("选择量表维度列（至少2个维度用于Copula相依建模）", df_raw.columns.tolist())
                if len(dims)>=2 and st.button("🚀 启动智能风险筛查", type="primary"):
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
                        save_screen_batch(batch_note_input, st.session_state["username"], college, tau_mean, df_out, copula_abnormal_score)
                        high_risk_df = df_out[df_out['风险等级']=='高危']
                        for _, row in high_risk_df.iterrows():
                            save_alert(str(row['编号']), f"学生{row['编号']}", college, '高危', status='待跟进')
                        webhook = os.getenv("WECHAT_WEBHOOK")
                        if webhook:
                            send_wechat_robot(webhook, f"预警通知：{len(high_risk_df)}名学生触发高危，请登录平台查看。")
                        st.success(f"✅ 计算完成，检测到总分变点位置：{tau_mean:.1f} | 批次备注：{batch_note_input if batch_note_input else '无'}")
                        st.rerun()
            else:
                empty_state_with_load()
        if df_cache is not None:
            risk_cnt = df_cache["风险等级"].value_counts()
            c1,c2,c3,c4 = st.columns(4)
            with c1: st.markdown(_metric_card_html("高危人数", risk_cnt.get("高危",0), color="#D93025"), unsafe_allow_html=True)
            with c2: st.markdown(_metric_card_html("中危人数", risk_cnt.get("中危",0), color="#F57C00"), unsafe_allow_html=True)
            with c3: st.markdown(_metric_card_html("低危人数", risk_cnt.get("低危",0), color="#2E7D32"), unsafe_allow_html=True)
            with c4: st.markdown(_metric_card_html("本次总样本", len(df_cache), color="#0F4C99"), unsafe_allow_html=True)
            trace = st.session_state.get("trace_cache")
            if trace is not None:
                with st.container(border=True):
                    fig1,(ax1,ax2)=plt.subplots(1,2,figsize=(17,6))
                    total_score=df_cache["总分"].values
                    sample_idx=np.arange(len(total_score))
                    ax1.plot(sample_idx,total_score,color="#5486c0",linewidth=1.4)
                    ax1.axvline(x=tau_cache,color="red",linestyle="--",linewidth=1.8,label=f"变点:{tau_cache:.1f}")
                    ax1.set_title("心理普查总分序列与贝叶斯变点",fontsize=13)
                    ax1.set_xlabel("样本编号")
                    ax1.set_ylabel("总分")
                    ax1.legend()
                    ax1.grid(alpha=0.25)
                    tau_sample=trace.posterior["tau"].values.flatten()
                    ax2.hist(tau_sample,bins=20,color="#628ec7",edgecolor="#2b4870",alpha=0.85)
                    ax2.axvline(x=tau_cache,color="red",linestyle="--",linewidth=1.8)
                    ax2.set_title("变点位置后验分布",fontsize=13)
                    ax2.set_xlabel("变点位置")
                    ax2.grid(alpha=0.25)
                    st.pyplot(fig1)
            with st.container(border=True):
                fig2,(ax3,ax4)=plt.subplots(1,2,figsize=(17,6))
                if copula_scores is not None:
                    ax3.hist(copula_scores,bins=18,color="#f7bc42",edgecolor="#b48620",alpha=0.88)
                    ax3.set_title("Copula相依异常分分布",fontsize=13)
                    ax3.set_xlabel("异常分")
                    ax3.grid(alpha=0.25)
                risk_pie = df_cache["风险等级"].value_counts()
                color_map={"高危":"#ff6b6b","中危":"#ffcc44","低危":"#62bd69"}
                pie_color=[color_map[k] for k in risk_pie.index]
                ax4.pie(risk_pie.values,labels=risk_pie.index,colors=pie_color,autopct="%.1f%%",textprops={"fontsize":11})
                ax4.set_title("样本风险分级占比",fontsize=13)
                st.pyplot(fig2)
                stat_df = pd.DataFrame({
                    "风险等级":["高危","中危","低危"],
                    "样本数量":[risk_cnt.get("高危",0),risk_cnt.get("中危",0),risk_cnt.get("低危",0)],
                    "占比(%)":[
                        round(risk_cnt.get("高危",0)/len(df_cache)*100,2),
                        round(risk_cnt.get("中危",0)/len(df_cache)*100,2),
                        round(risk_cnt.get("低危",0)/len(df_cache)*100,2)
                    ]
                })
                if st.button("📄 生成Word报告"):
                    generate_word_report(batch_note, tau_cache, df_cache, stat_df, fig2)
            with st.container(border=True):
                st.markdown("### 📋 风险统计明细")
                st.dataframe(stat_df, hide_index=True, use_container_width=True)
            with st.container(border=True):
                st.markdown("### 🔍 Copula高异常样本筛选")
                if copula_scores is not None:
                    filter_score = st.slider("筛选大于该异常分的样本",min_value=float(np.min(copula_scores)),max_value=float(np.max(copula_scores)),value=np.percentile(copula_scores,80))
                    mask = copula_scores>filter_score
                    st.info(f"异常分高于{filter_score:.2f}的样本数量：{np.sum(mask)}")
                    st.dataframe(df_cache.loc[mask,:],use_container_width=True)
            with st.container(border=True):
                st.markdown("### 📃 全部筛查结果表")
                show_high_only = st.checkbox("仅展示高危预警学生")
                display_df = df_cache[df_cache["风险等级"]=="高危"] if show_high_only else df_cache
                st.dataframe(display_df, use_container_width=True)
            csv_full = df_cache.to_csv(index=False, encoding="utf_8_sig")
            csv_stat = stat_df.to_csv(index=False, encoding="utf_8_sig")
            col_d1,col_d2 = st.columns(2)
            with col_d1:
                st.download_button("📥 导出完整筛查结果CSV", data=csv_full, file_name=f"班级筛查_{batch_note}.csv", use_container_width=True)
            with col_d2:
                st.download_button("📥 导出风险统计汇总CSV", data=csv_stat, file_name=f"统计报表_{batch_note}.csv", use_container_width=True)
    elif module == "风险分级统计看板":
        st.header("📈 班级风险分级综合统计看板")
        if df_cache is None:
            empty_state_with_load()
            return
        risk_cnt = df_cache["风险等级"].value_counts()
        c1,c2,c3 = st.columns(3)
        with c1: st.markdown(_metric_card_html("高危", risk_cnt.get("高危",0), color="#D93025"), unsafe_allow_html=True)
        with c2: st.markdown(_metric_card_html("中危", risk_cnt.get("中危",0), color="#F57C00"), unsafe_allow_html=True)
        with c3: st.markdown(_metric_card_html("低危", risk_cnt.get("低危",0), color="#2E7D32"), unsafe_allow_html=True)
        with st.container(border=True):
            st.subheader("📊 风险等级柱状分布图")
            st.bar_chart(risk_cnt, use_container_width=True)
        with st.container(border=True):
            st.subheader("📋 统计明细表格")
            stat_df = pd.DataFrame({
                "等级":risk_cnt.index,
                "人数":risk_cnt.values,
                "占比%": [round(x/len(df_cache)*100,2) for x in risk_cnt.values]
            })
            st.dataframe(stat_df, hide_index=True)
    elif module == "高危预警管理":
        st.header("🚨 高危学生预警管理台账")
        if df_cache is None:
            empty_state_with_load()
            return
        high_df = df_cache[df_cache["风险等级"]=="高危"].copy()
        with st.container(border=True):
            st.subheader(f"⚠️ 高危预警名单（共 {len(high_df)} 人）")
            st.dataframe(high_df, use_container_width=True)
        with st.container(border=True):
            st.text_area("📝 批量干预记录填写", placeholder="记录约谈、疏导、回访、转介心理中心情况", height=100)
        csv_high = high_df.to_csv(index=False, encoding="utf_8_sig")
        st.download_button("📥 导出高危预警台账", data=csv_high, file_name="高危学生预警名单.csv", use_container_width=True)
        with st.expander("➕ 创建干预任务"):
            if len(high_df) > 0:
                student_id = st.selectbox("选择学生编号", high_df['编号'].astype(str).tolist())
                plan = st.text_area("干预计划")
                start_date = st.date_input("开始日期")
                end_date = st.date_input("预计完成日期")
                handler = st.text_input("负责人")
                if st.button("创建任务", key="create_task"):
                    if plan and handler:
                        save_intervention(student_id, college, plan, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"), handler)
                        st.success("干预任务已创建")
                        st.rerun()
                    else:
                        st.error("请填写完整信息")
            else:
                st.info("当前无高危学生")
        with st.expander("📧 发送预警通知"):
            recipient = st.text_input("辅导员邮箱")
            if st.button("发送测试通知"):
                if recipient:
                    send_email(recipient, "心理预警通知", f"学生{student_id}触发高危预警，请及时处理。")
                else:
                    st.error("请输入邮箱")
    elif module == "学生个案追踪档案":
        st.header("👤 学生个案长期追踪档案")
        if df_cache is None:
            empty_state_with_load()
            return
        id_list = sorted(df_cache["编号"].unique())
        sel_id = st.selectbox("选择学生编号查看完整个案", id_list)
        stu_data = df_cache[df_cache["编号"]==sel_id]
        with st.container(border=True):
            st.dataframe(stu_data, hide_index=True)
        with st.container(border=True):
            st.text_area("📝 个案追踪记录", placeholder="历次沟通、干预、心理变化记录存档", height=150)
    elif module == "班级趋势分析图表":
        st.header("📉 班级心理总分时序趋势分析")
        if df_cache is None:
            empty_state_with_load()
            return
        with st.container(border=True):
            fig, ax = plt.subplots(figsize=(12, 5))
            ax.plot(df_cache["编号"], df_cache["总分"], alpha=0.7, color="#4263eb", marker='o', markersize=3)
            if tau_cache is not None:
                ax.axvline(x=tau_cache, color="red", linestyle="--", linewidth=2, label=f"风险变点位置：{tau_cache:.1f}")
            ax.set_title("全班学生总分序列与贝叶斯风险变点", fontsize=14)
            ax.set_xlabel("学生编号")
            ax.set_ylabel("心理总分")
            ax.legend()
            ax.grid(alpha=0.2)
            st.pyplot(fig)

# ========================== 管理端模块 ==========================
def render_admin_dashboard():
    st.markdown('<div class="dash-title">🏠 首页概览 · 心理健康监测大屏</div>', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
    metric_data = [
        {"title":"在校学生总数","value":"28,542","delta":"↑4.2%","color":"#0F4C99"},
        {"title":"已完成测评人数","value":"24,532","delta":"完成率 86.0%","color":"#1967D2"},
        {"title":"当前预警总人数","value":"1,257","delta":"预警占比5.1%","color":"#D93025"},
        {"title":"干预中人数","value":"842","delta":"干预率3.4%","color":"#2E7D32"},
    ]
    for idx, col in enumerate([col1, col2, col3, col4]):
        item = metric_data[idx]
        with col:
            st.markdown(f"""
            <div style="background-color:{item['color']};border-radius:16px;padding:24px;color:white;box-shadow:0 6px 16px #00000022;">
                <div style="font-size:15px;opacity:0.85;">{item['title']}</div>
                <div style="font-size:36px;font-weight:bold;margin:10px 0;">{item['value']}</div>
                <div style="font-size:14px;">{item['delta']}</div>
            </div>
            """, unsafe_allow_html=True)
    st.divider()
    # ===== 第一排：饼图 + 雷达图（圆图一排） =====
    row1_col1, row1_col2 = st.columns(2)
    with row1_col1:
        st.markdown("**📊 预警分层统计**")
        pie_labels = ["高危", "中危", "低风险"]
        pie_vals = [312, 945, 22620]
        pie_colors = ["#D93025", "#F57C00", "#2E7D32"]
        fig_pie, ax_pie = plt.subplots(figsize=(10, 5), dpi=110)
        wedges, texts, autotexts = ax_pie.pie(pie_vals, labels=pie_labels, colors=pie_colors,
                                              autopct="%.1f%%", startangle=90,
                                              textprops={'fontsize': 11})
        wedges[0].set_edgecolor('white')
        wedges[0].set_linewidth(2)
        ax_pie.set_title(f"总测评人数 {sum(pie_vals):,}", fontsize=12)
        st.pyplot(fig_pie)
    with row1_col2:
        st.markdown("**🕸️ 风险维度分布**")
        fig_radar = plt.figure(figsize=(10, 5), dpi=110)
        ax_radar = fig_radar.add_subplot(111, polar=True)
        labels = ["生活满意度", "焦虑风险", "睡眠问题", "学业压力", "社交压力"]
        values = [22, 68, 55, 72, 48]
        N = len(labels)
        angles = [n / float(N) * 2 * math.pi for n in range(N)]
        values_plot = values + [values[0]]
        angles_plot = angles + [angles[0]]
        ax_radar.plot(angles_plot, values_plot, color="#D93025", linewidth=2)
        ax_radar.fill(angles_plot, values_plot, color="#D93025", alpha=0.25)
        ax_radar.set_xticks(angles)
        ax_radar.set_xticklabels(labels, fontsize=10)
        ax_radar.set_yticks([20, 40, 60, 80])
        ax_radar.set_ylim(0, 100)
        st.pyplot(fig_radar)

    # ===== 第二排：折线图 + 柱状图 =====
    row2_col1, row2_col2 = st.columns(2)
    with row2_col1:
        st.markdown("**📈 心理风险趋势（月度）**")
        months = pd.date_range("2024-01-01", "2025-03-01", freq="MS").strftime("%Y-%m").tolist()
        np.random.seed(42)
        trend = np.linspace(35, 25, len(months)) + np.random.normal(0, 2, len(months))
        for i, m in enumerate(months):
            if m >= "2024-06":
                trend[i] += 8 * (1 - np.exp(-0.3 * (i - 5)))
        fig_trend, ax_trend = plt.subplots(figsize=(10, 5), dpi=110)
        ax_trend.plot(months, trend, color="#0F4C99", linewidth=2, marker='o', markersize=4)
        ax_trend.set_xticks(months[::3])
        ax_trend.tick_params(axis='x', rotation=45)
        ax_trend.set_ylabel("风险指数")
        ax_trend.grid(alpha=0.2)
        for sp in ["top", "right"]:
            ax_trend.spines[sp].set_visible(False)
        fig_trend.tight_layout()
        st.pyplot(fig_trend)
    with row2_col2:
        st.markdown("**📊 风险等级人数**")
        risk_levels = ["高危", "中危", "低风险"]
        counts = [312, 945, 22620]
        colors_bar = ["#D93025", "#F57C00", "#2E7D32"]
        fig_bar, ax_bar = plt.subplots(figsize=(10, 5), dpi=110)
        bars = ax_bar.bar(risk_levels, counts, color=colors_bar, width=0.5)
        for bar, count in zip(bars, counts):
            ax_bar.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 100,
                        f"{count:,}", ha='center', fontsize=10, fontweight='bold')
        ax_bar.set_ylabel("人数", fontsize=10)
        ax_bar.tick_params(axis='both', labelsize=10)
        for spine in ['top', 'right']:
            ax_bar.spines[spine].set_visible(False)
        fig_bar.tight_layout()
        st.pyplot(fig_bar)

    st.divider()
    cc1, cc2, cc3 = st.columns([3, 2, 2])
    with cc1:
        st.markdown("**🔍 Copula相依结构分析（抑郁×焦虑风险）**")
        fig_cop, ax_cop = plt.subplots(figsize=(11, 5), dpi=110)
        n_sample = 1200
        cov_mat = [[1, 0.72], [0.72, 1]]
        data_cop = np.random.multivariate_normal([12, 14], cov_mat, size=n_sample)
        sc = ax_cop.scatter(data_cop[:,0], data_cop[:,1], c=data_cop[:,0]+data_cop[:,1],
                            cmap="jet", alpha=0.6, s=14)
        fig_cop.colorbar(sc, ax=ax_cop, label="综合风险分数")
        ax_cop.set_xlabel("抑郁风险得分")
        ax_cop.set_ylabel("焦虑风险得分")
        for sp in ["top", "right"]:
            ax_cop.spines[sp].set_visible(False)
        fig_cop.tight_layout()
        st.pyplot(fig_cop)
    with cc2:
        st.markdown("**📈 干预效果评估（近6个月）**")
        fig_eff, ax_eff = plt.subplots(figsize=(5, 4.5), dpi=110)
        month = ["3月", "4月", "5月", "6月", "7月", "8月"]
        eff_rate = [62, 67, 71, 74, 77, 78.6]
        ax_eff.plot(month, eff_rate, marker="o", color="#0F4C99", linewidth=2)
        ax_eff.set_ylim(50, 90)
        ax_eff.set_ylabel("干预有效率%")
        for sp in ["top", "right"]:
            ax_eff.spines[sp].set_visible(False)
        fig_eff.tight_layout()
        st.pyplot(fig_eff)
    with cc3:
        st.markdown("**🚨 预警动态（最新）**")
        warn_df = pd.DataFrame([
            {"学号":"202201041","姓名":"张同学","学院":"计算机学院","风险等级":"高危预警","时间":"2026-08-10"},
            {"学号":"202203072","姓名":"李同学","学院":"外国语学院","风险等级":"中风险预警","时间":"2026-08-10"},
            {"学号":"202302015","姓名":"王同学","学院":"经济管理学院","风险等级":"高危预警","时间":"2026-08-09"},
            {"学号":"202105033","姓名":"赵同学","学院":"艺术学院","风险等级":"中风险预警","时间":"2026-08-09"},
        ])
        def warn_color(val):
            if "高危" in val:
                return "background-color:#ffe8e8;color:#c00000"
            else:
                return "background-color:#fff3e0;color:#e65100"
        st.dataframe(warn_df.style.map(warn_color, subset=["风险等级"]),
                     hide_index=True, use_container_width=True, height=300)
    st.divider()
    st.markdown("### 🧩 平台快捷功能")
    b1,b2,b3,b4,b5,b6,b7,b8 = st.columns(8)
    btn_info = [
        ("📝", "智能评估"), ("⚠️", "精准预警"), ("🔗", "关联分析"),
        ("🤝", "个性干预"), ("🔒", "数据安全"), ("📊", "可视化大屏"),
        ("📄", "学校报告"), ("👥", "个案追踪")
    ]
    for idx, col in enumerate([b1,b2,b3,b4,b5,b6,b7,b8]):
        icon,txt = btn_info[idx]
        with col:
            st.markdown(f"""
            <div style="text-align:center;padding:14px 4px;background:#f0f4f9;border-radius:12px;height:95px">
                <div style="font-size:28px;margin-bottom:8px">{icon}</div>
                <div style="font-size:13px">{txt}</div>
            </div>
            """, unsafe_allow_html=True)

def render_admin_students():
    st.markdown('<div class="dash-title">🧑‍🎓 学生管理</div>', unsafe_allow_html=True)
    if "admin_student_df" not in st.session_state:
        st.warning("📭 暂无学生数据，请点击下方按钮加载示例数据")
        if st.button("📥 加载示例学生数据", type="primary"):
            generate_admin_example()
            st.rerun()
        return
    stu_df = st.session_state["admin_student_df"]
    with st.container(border=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            grade_sel = st.multiselect("年级", options=stu_df['年级'].unique(), default=stu_df['年级'].unique())
        with col2:
            college_sel = st.multiselect("学院", options=stu_df['学院'].unique(), default=stu_df['学院'].unique())
        with col3:
            status_sel = st.multiselect("心理状态", options=stu_df['心理状态'].unique(), default=stu_df['心理状态'].unique())
        keyword = st.text_input("🔍 搜索姓名/学号", placeholder="输入关键词")
    mask = stu_df['年级'].isin(grade_sel) & stu_df['学院'].isin(college_sel) & stu_df['心理状态'].isin(status_sel)
    if keyword:
        mask &= (stu_df['姓名'].str.contains(keyword) | stu_df['学号'].str.contains(keyword))
    show = stu_df[mask]
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.markdown(_metric_card_html("筛选学生数", len(show), color="#0F4C99"), unsafe_allow_html=True)
    with col2: st.markdown(_metric_card_html("其中预警", int((show["心理状态"] == "预警").sum()), color="#D93025"), unsafe_allow_html=True)
    with col3: st.markdown(_metric_card_html("其中关注", int((show["心理状态"] == "关注").sum()), color="#F57C00"), unsafe_allow_html=True)
    with col4: st.markdown(_metric_card_html("涉及学院", show["学院"].nunique() if len(show) else 0, color="#2E7D32"), unsafe_allow_html=True)
    with st.container(border=True):
        st.dataframe(show, hide_index=True, use_container_width=True)

def _chart_monthly_assess():
    months = ["2024-05","2024-06","2024-07","2024-08","2024-09"]
    done = [1880, 2010, 2150, 2230, 2318]
    fig, ax = plt.subplots(figsize=(7, 3.2), dpi=110)
    ax.bar(months, done, color="#4f6ef7", alpha=0.85, width=0.55)
    for i, v in enumerate(done):
        ax.text(i, v + 30, f"{v:,}", ha="center", fontsize=10, fontweight="bold", color="#364fc7")
    ax.set_ylabel("完成人数"); ax.grid(axis="y", alpha=0.25)
    for s in ("top","right"): ax.spines[s].set_visible(False)
    fig.tight_layout(); return fig

def _chart_dim_means():
    dims = ["焦虑","抑郁","压力","睡眠障碍","社交回避"]
    means = [42.5, 41.2, 38.8, 8.4, 7.9]
    colors = ["#4f6ef7","#9775fa","#f7bc42","#20c997","#ff922b"]
    fig, ax = plt.subplots(figsize=(7, 3.2), dpi=110)
    bars = ax.bar(dims, means, color=colors, width=0.5)
    for b, v in zip(bars, means):
        ax.text(b.get_x()+b.get_width()/2, v+0.6, f"{v:.1f}", ha="center", fontsize=10, fontweight="bold")
    ax.set_ylabel("平均分"); ax.grid(axis="y", alpha=0.25)
    for s in ("top","right"): ax.spines[s].set_visible(False)
    fig.tight_layout(); return fig

def render_admin_assessment():
    st.markdown('<div class="dash-title">📝 心理评估</div>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    col1.metric("本月完成评估", "2,318", "较上月 +12.4%")
    col2.metric("平均完成率", "86.0%", "较上月 +3.2%")
    col3.metric("平均心理总分", "63.4", "较上月 -2.1")
    with st.container(border=True):
        st.markdown("**📋 评估量表管理**")
        scales = pd.DataFrame({
            "量表名称": ["SAS 焦虑自评量表","SDS 抑郁自评量表","SCL-90 症状自评量表","PSQI 睡眠质量量表","UPI 大学生人格问卷"],
            "已测人数": [24532, 24105, 18930, 15204, 11022],
            "完成率(%)": [86.0, 84.5, 66.3, 53.3, 38.6],
            "状态": ["启用中","启用中","启用中","启用中","启用中"],
        })
        st.dataframe(scales, hide_index=True, use_container_width=True)
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.markdown("**📈 月度评估完成趋势**")
            st.pyplot(_chart_monthly_assess())
    with c2:
        with st.container(border=True):
            st.markdown("**📊 各维度平均得分**")
            st.pyplot(_chart_dim_means())

def _alert_list_html():
    alerts = [
        ("2024-09-10", "计算机学院 · 张同学", "高风险预警", "tag-red"),
        ("2024-09-09", "外国语学院 · 李同学", "中风险预警", "tag-yellow"),
        ("2024-09-08", "经济管理学院 · 王同学", "高风险预警", "tag-red"),
        ("2024-09-07", "机械工程学院 · 赵同学", "中风险预警", "tag-yellow"),
        ("2024-09-06", "文学院 · 刘同学", "已转介干预", "tag-green"),
    ]
    items = []
    for date, name, tag, cls in alerts:
        items.append(
            f'<div class="alert-item"><span style="color:#94a3b8;font-size:12px">{date}</span>'
            f'<span style="flex:1;margin:0 8px;color:#334155">{name}</span>'
            f'<span class="tag {cls}">{tag}</span></div>'
        )
    return '<div class="alert-list">' + "".join(items) + "</div>"

def _chart_risk_levels():
    segs = [("高风险", 312, "#ff6b6b"), ("中风险", 945, "#f7bc42"), ("低风险", 23275, "#62bd69")]
    total = sum(v for _, v, _ in segs)
    fig, ax = plt.subplots(figsize=(7, 2.9), dpi=110)
    left = 0
    for name, v, c in segs:
        ax.barh(0, v, left=left, color=c, height=0.5)
        if v / total > 0.08:
            ax.text(left + v / 2, 0, f"{v:,}（{v/total*100:.1f}%）",
                    ha="center", va="center", fontsize=10, color="white", fontweight="bold")
        left += v
    ax.set_yticks([]); ax.set_xlim(0, total); ax.set_xticks([])
    ax.set_title(f"已完成测评 {total:,} 人 · 预警分层统计", fontsize=11, pad=10)
    ax.legend([f"{n} {v:,}" for n, v, _ in segs], loc="upper center",
              bbox_to_anchor=(0.5, -0.12), ncol=3, fontsize=9, frameon=False)
    for s in ("top", "right", "left", "bottom"): ax.spines[s].set_visible(False)
    fig.tight_layout(); return fig

def render_admin_alert():
    st.markdown('<div class="dash-title">🚨 预警监测</div>', unsafe_allow_html=True)
    if "admin_alert_df" not in st.session_state:
        st.warning("📭 暂无预警数据，请点击下方按钮加载示例数据")
        if st.button("📥 加载示例预警数据", type="primary"):
            generate_admin_example()
            st.rerun()
        return
    alert_df = st.session_state["admin_alert_df"]
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.markdown(_metric_card_html("当前预警人数", "1,257", "↑1.2%", color="#0F4C99"), unsafe_allow_html=True)
    with col2: st.markdown(_metric_card_html("高风险", 312, color="#D93025"), unsafe_allow_html=True)
    with col3: st.markdown(_metric_card_html("中风险", 945, color="#F57C00"), unsafe_allow_html=True)
    with col4: st.markdown(_metric_card_html("本月新增", 86, "↑12", color="#2E7D32"), unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.markdown("**📊 预警分层统计**")
            st.pyplot(_chart_risk_levels())
    with c2:
        with st.container(border=True):
            st.markdown("**🔔 最新预警动态**")
            st.markdown(_alert_list_html(), unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown("**🗂️ 高危预警台账**")
        st.dataframe(alert_df, hide_index=True, use_container_width=True)
        csv = alert_df.to_csv(index=False, encoding="utf_8_sig")
        st.download_button("📥 导出预警台账CSV", data=csv, file_name="预警台账.csv")

def _intervention_progress_html():
    items = [
        ("干预后症状改善率", 78.6, "#4f6ef7"),
        ("高危个案转介完成率", 32.4, "#f7bc42"),
        ("复测风险回落率", 12.7, "#62bd69"),
    ]
    parts = []
    for label, val, color in items:
        parts.append(f"""
        <div class="progress-row">
            <div class="progress-label"><span>{label}</span><span style="font-weight:700;color:{color}">{val:.1f}%</span></div>
            <div class="progress-track"><div class="progress-fill" style="width:{val}%;background:{color}"></div></div>
        </div>""")
    return "".join(parts)

def _chart_intervention_compare():
    groups = ["认知行为干预","正念减压","团体辅导","心理讲座"]
    before = [2.8, 2.6, 2.4, 2.1]
    after = [1.9, 1.8, 1.7, 1.6]
    x = np.arange(len(groups)); w = 0.32
    fig, ax = plt.subplots(figsize=(7, 3.4), dpi=110)
    b1 = ax.bar(x - w/2, before, w, label="干预前", color="#ff6b6b")
    b2 = ax.bar(x + w/2, after, w, label="干预后", color="#62bd69")
    for b, v in zip(b1, before):
        ax.text(b.get_x()+b.get_width()/2, v+0.05, f"{v:.1f}", ha="center", fontsize=9)
    for b, v in zip(b2, after):
        ax.text(b.get_x()+b.get_width()/2, v+0.05, f"{v:.1f}", ha="center", fontsize=9)
    ax.set_xticks(x); ax.set_xticklabels(groups)
    ax.set_ylabel("平均风险分")
    ax.legend(fontsize=9, frameon=False)
    ax.grid(axis="y", alpha=0.25)
    for s in ("top","right"): ax.spines[s].set_visible(False)
    fig.tight_layout(); return fig

def render_admin_intervention():
    st.markdown('<div class="dash-title">🛟 干预管理</div>', unsafe_allow_html=True)
    interv_df = load_interventions()
    if interv_df.empty:
        st.warning("📭 暂无干预任务，可加载示例数据")
        if st.button("📥 加载示例干预数据", type="primary"):
            generate_admin_example()
            st.rerun()
        return
    col1, col2, col3 = st.columns(3)
    total = len(interv_df)
    doing = len(interv_df[interv_df['status'] == '进行中'])
    done = len(interv_df[interv_df['status'] == '已完成'])
    with col1: st.markdown(_metric_card_html("总任务", total, color="#0F4C99"), unsafe_allow_html=True)
    with col2: st.markdown(_metric_card_html("进行中", doing, color="#F57C00"), unsafe_allow_html=True)
    with col3: st.markdown(_metric_card_html("已完成", done, color="#2E7D32"), unsafe_allow_html=True)
    st.subheader("📋 所有干预任务")
    for idx, row in interv_df.iterrows():
        with st.expander(f"任务 {row['id']}：{row['student_id']} - {row['plan'][:20]}..."):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**学生**：{row['student_id']}")
                st.write(f"**计划**：{row['plan']}")
                st.write(f"**负责人**：{row['handler']}")
            with col2:
                st.write(f"**开始**：{row['start_time']}")
                st.write(f"**结束**：{row['end_time']}")
                st.write(f"**状态**：{row['status']}")
            new_status = st.selectbox("更新状态", ['待执行', '进行中', '已完成'], key=f"status_{row['id']}")
            result = st.text_area("结果/备注", key=f"result_{row['id']}")
            if st.button("更新", key=f"update_{row['id']}"):
                update_intervention_status(row['id'], new_status, result)
                st.success("状态已更新")
                st.rerun()

def _chart_batch_trend(hist):
    x = np.arange(len(hist["批次"]))
    fig, ax = plt.subplots(figsize=(7, 3.4), dpi=110)
    ax.plot(x, hist["低危"], marker="o", color="#62bd69", linewidth=2, label="低危")
    ax.plot(x, hist["中危"], marker="s", color="#f7bc42", linewidth=2, label="中危")
    ax.plot(x, hist["高危"], marker="^", color="#ff6b6b", linewidth=2, label="高危")
    ax.set_xticks(x); ax.set_xticklabels(hist["批次"])
    ax.set_ylabel("人数")
    ax.legend(fontsize=9, frameon=False)
    ax.grid(alpha=0.25)
    for s in ("top","right"): ax.spines[s].set_visible(False)
    fig.tight_layout(); return fig

def _chart_grade_risk():
    grades = ["大一","大二","大三","大四"]
    high = [85, 70, 60, 55]
    mid = [120, 100, 90, 80]
    x = np.arange(len(grades)); w = 0.32
    fig, ax = plt.subplots(figsize=(7, 3.4), dpi=110)
    ax.bar(x - w/2, high, w, label="高危", color="#ff6b6b")
    ax.bar(x + w/2, mid, w, label="中危", color="#f7bc42")
    ax.set_xticks(x); ax.set_xticklabels(grades)
    ax.set_ylabel("人数")
    ax.legend(fontsize=9, frameon=False)
    ax.grid(axis="y", alpha=0.25)
    for s in ("top","right"): ax.spines[s].set_visible(False)
    fig.tight_layout(); return fig

def _chart_gender_risk():
    labels = ["男生", "女生"]
    sizes = [612, 645]
    colors = ["#4f6ef7", "#f783ac"]
    fig, ax = plt.subplots(figsize=(7, 3.4), dpi=110)
    wedges, _, _ = ax.pie(sizes, colors=colors, autopct="%.1f%%", startangle=90,
                          textprops={"fontsize": 11}, wedgeprops=dict(edgecolor="white"))
    ax.legend(wedges, [f"{l} {v:,}人" for l, v in zip(labels, sizes)],
              loc="center left", bbox_to_anchor=(0.9, 0.5), fontsize=9, frameon=False)
    ax.set_aspect("equal"); fig.subplots_adjust(right=0.72); return fig

def _chart_dim_contribution():
    dims = ["学业压力","社交压力","情绪波动","睡眠问题","就业焦虑"]
    vals = [30, 25, 20, 15, 10]
    colors = ["#4f6ef7","#f7bc42","#ff6b6b","#62bd69","#9775fa"]
    fig, ax = plt.subplots(figsize=(7, 3.4), dpi=110)
    y = np.arange(len(dims))[::-1]
    ax.barh(y, vals, color=colors, height=0.55)
    ax.set_yticks(y)
    ax.set_yticklabels(dims)
    for yi, v in zip(y, vals):
        ax.text(v + 0.4, yi, f"{v}%", va="center", fontsize=10, fontweight="bold", color="#334155")
    ax.set_xlim(0, 38); ax.set_xlabel("占比(%)")
    for s in ("top","right"): ax.spines[s].set_visible(False)
    fig.tight_layout(); return fig

def render_admin_stats():
    st.markdown('<div class="dash-title">📈 统计分析</div>', unsafe_allow_html=True)
    hist = st.session_state["multi_batch_history"]
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.markdown("**📉 全校多批次风险人数趋势**")
            st.pyplot(_chart_batch_trend(hist))
    with c2:
        with st.container(border=True):
            st.markdown("**🎓 年级风险分层对比**")
            st.pyplot(_chart_grade_risk())
    c3, c4 = st.columns(2)
    with c3:
        with st.container(border=True):
            st.markdown("**⚧ 性别预警对比**")
            st.pyplot(_chart_gender_risk())
    with c4:
        with st.container(border=True):
            st.markdown("**🧩 风险维度贡献度**")
            st.pyplot(_chart_dim_contribution())
    st.markdown("### 🔮 未来风险人数预测（Prophet）")
    try:
        from prophet import Prophet
        df_ts = pd.DataFrame({
            'ds': pd.to_datetime(hist['批次']),
            'y': hist['高危']
        })
        model = Prophet()
        model.fit(df_ts)
        future = model.make_future_dataframe(periods=3, freq='MS')
        forecast = model.predict(future)
        fig_forecast = model.plot(forecast)
        st.pyplot(fig_forecast)
    except ImportError:
        st.warning("请安装 prophet 库：pip install prophet")
    except Exception as e:
        st.error(f"预测失败：{e}")

def render_admin_resources():
    st.markdown('<div class="dash-title">📚 资源中心</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">🏥 线下咨询与热线</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    res_cards = [
        ("🏥", "心理咨询中心", "工作日 8:30-17:00 免费预约", "校内", "res-tag blue", "预约电话：010-8888 6666"),
        ("📞", "24小时心理援助热线", "全国统一心理援助热线", "热线", "res-tag green", "12356 / 400-161-9995"),
        ("🏫", "团体心理辅导", "每周三下午 14:00 团体室", "活动", "res-tag orange", "报名请到心理中心前台登记"),
    ]
    for col, (icon, title, desc, tag_text, tag_cls, extra) in zip([c1, c2, c3], res_cards):
        with col:
            st.markdown(f"""
            <div class="res-card">
                <div class="res-icon">{icon}</div>
                <span class="{tag_cls}">{tag_text}</span>
                <h5>{title}</h5>
                <p>{desc}<br>{extra}</p>
            </div>
            """, unsafe_allow_html=True)
    st.markdown('<div class="sub-title">📖 自助学习与资料</div>', unsafe_allow_html=True)
    c4, c5, c6 = st.columns(3)
    study_cards = [
        ("🧘", "正念减压课程", "10 节线上音频课程，每日 10 分钟", "课程", "res-tag green", "配套练习：呼吸锚定、身体扫描"),
        ("📕", "情绪管理手册", "认知行为疗法自助学习电子书", "资料", "res-tag blue", "涵盖 6 大情绪调节技术"),
        ("🎧", "放松减压音频", "白噪音与渐进式肌肉放松", "音频", "res-tag orange", "睡前聆听效果更佳"),
    ]
    for col, (icon, title, desc, tag_text, tag_cls, extra) in zip([c4, c5, c6], study_cards):
        with col:
            st.markdown(f"""
            <div class="res-card">
                <div class="res-icon">{icon}</div>
                <span class="{tag_cls}">{tag_text}</span>
                <h5>{title}</h5>
                <p>{desc}<br>{extra}</p>
            </div>
            """, unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown("**📥 资料下载**")
        text1 = """大学生心理危机干预工作手册（2024版）
一、预警信号识别
二、分级处置流程
三、转介与回访规范
四、家校沟通要点"""
        text2 = """心理健康教育年度报告模板
一、总体概况
二、风险分析
三、干预成效
四、改进计划"""
        col_a, col_b = st.columns(2)
        with col_a:
            st.download_button("📄 下载《危机干预工作手册》", data=text1.encode("utf-8"), file_name="危机干预工作手册.txt")
        with col_b:
            st.download_button("📄 下载《年度报告模板》", data=text2.encode("utf-8"), file_name="年度报告模板.txt")

def render_admin_settings():
    st.markdown('<div class="dash-title">⚙️ 系统设置</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.markdown("**🧮 全局算法参数配置**")
            high = st.slider("全局高危风险阈值", 0.8, 2.5, st.session_state["global_high_thr"], 0.05)
            mid = st.slider("全局中危风险阈值", 0.2, 1.2, st.session_state["global_mid_thr"], 0.05)
            w_total = st.slider("总分维度权重", 0.0, 1.0, 0.6, 0.05)
            w_copula = round(1.0 - w_total, 2)
            if st.button("💾 保存全局参数", type="primary", use_container_width=True):
                st.session_state["global_high_thr"] = high
                st.session_state["global_mid_thr"] = mid
                st.success(f"参数已保存：高危≥{high}，中危≥{mid}，权重 总分{w_total:.2f} / Copula{w_copula:.2f}")
            st.caption("保存后作为教师端批量筛查、预警分级的全局默认阈值")
    with c2:
        with st.container(border=True):
            st.markdown("**👥 平台账号权限管理**")
            accounts = pd.DataFrame({
                "账号": ["admin01","teacher_zhang","teacher_li","stu_wang","stu_liu"],
                "姓名": ["系统管理员","张老师","李老师","王同学","刘同学"],
                "角色": ["管理端","教师端","教师端","学生端","学生端"],
                "所属": ["学工部","心理健康中心","外国语学院","计算机学院","文学院"],
                "最近登录": ["2024-09-12 09:15","2024-09-11 16:40","2024-09-10 11:02","2024-09-09 20:18","2024-09-08 14:33"],
                "状态": ["正常","正常","正常","正常","正常"],
            })
            st.dataframe(accounts, hide_index=True, use_container_width=True)
            st.markdown("**➕ 新增账号**")
            with st.form("add_account_form"):
                a1, a2 = st.columns(2)
                new_user = a1.text_input("新账号")
                new_name = a2.text_input("姓名")
                new_role = st.selectbox("角色权限", ["学生端","教师端","管理端"])
                if st.form_submit_button("创建账号", type="primary"):
                    if new_user.strip() and new_name.strip():
                        st.success(f"账号 {new_user.strip()}（{new_name.strip()}）创建成功，角色：{new_role}")
                    else:
                        st.error("账号与姓名不能为空")

def render_admin_module(module):
    if module == "首页概览":
        render_admin_dashboard()
    elif module == "学生管理":
        render_admin_students()
    elif module == "心理评估":
        render_admin_assessment()
    elif module == "预警监测":
        render_admin_alert()
    elif module == "干预管理":
        render_admin_intervention()
    elif module == "统计分析":
        render_admin_stats()
    elif module == "资源中心":
        render_admin_resources()
    elif module == "系统设置":
        render_admin_settings()

# ===== 登录后主系统：顶栏 + 左侧侧边栏 =====
def render_main_system():
    render_top_bar()
    role = st.session_state["role"]
    if role == "admin":
        menu_items = ["首页概览", "学生管理", "心理评估", "预警监测", "干预管理", "统计分析", "资源中心", "系统设置"]
        menu_icons = ["house-fill","people-fill","clipboard2-check-fill","exclamation-triangle-fill","heart-pulse-fill","bar-chart-fill","book-fill","gear-fill"]
    elif role == "teacher":
        menu_items = ["心理普查批量筛查", "风险分级统计看板", "高危预警管理", "学生个案追踪档案", "班级趋势分析图表"]
        menu_icons = ["upload","bar-chart","bell","person-lines-fill","graph-up"]
    elif role == "student":
        menu_items = ["心理普查（自评问卷）", "个人状态画像雷达图", "历史自评存档", "个性化心理建议库"]
        menu_icons = ["pencil-square","radar","clock-history","lightbulb"]
    else:
        return

    with st.sidebar:
        try:
            default_idx = menu_items.index(st.session_state["current_module"])
        except ValueError:
            default_idx = 0
        selected = option_menu(
            menu_title="📋 功能导航",
            options=menu_items,
            icons=menu_icons,
            default_index=default_idx,
            styles={
                "container":{"background":"#f7f8fa","border-radius":"12px","padding":"8px"},
                "nav-link":{"font-size":"15px","padding":"12px 14px"},
                "nav-link-selected":{"background":"#0F4C99","color":"white"}
            }
        )
    if selected != st.session_state["current_module"]:
        st.session_state["current_module"] = selected
        st.rerun()

    curr_mod = st.session_state["current_module"]
    if role == "student":
        render_student_module(curr_mod)
    elif role == "teacher":
        render_teacher_module(curr_mod)
    elif role == "admin":
        render_admin_module(curr_mod)

# ===== 路由总入口 =====
root_page = st.session_state["page_root"]
if root_page == "home":
    render_home_page()
elif root_page == "role_login":
    render_role_login()
elif root_page == "main":
    render_main_system()