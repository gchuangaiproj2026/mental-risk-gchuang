# db.py
import sqlite3
import pandas as pd
import json
import numpy as np
from datetime import datetime
DB_PATH = 'mental_health.db'
def get_conn():
    return sqlite3.connect(DB_PATH)
def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password_hash TEXT,
        role TEXT,
        college TEXT,
        fullname TEXT,
        email TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS self_assess (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        college TEXT,
        time TEXT,
        anxiety INTEGER,
        depression INTEGER,
        stress INTEGER,
        sleep INTEGER,
        social INTEGER,
        total INTEGER
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS screen_batches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_name TEXT,
        teacher TEXT,
        college TEXT,
        time TEXT,
        tau REAL,
        df_json TEXT,
        copula_json TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        name TEXT,
        college TEXT,
        risk_level TEXT,
        time TEXT,
        status TEXT,
        handler TEXT,
        note TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS interventions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        college TEXT,
        plan TEXT,
        start_time TEXT,
        end_time TEXT,
        status TEXT,
        handler TEXT,
        result TEXT
    )''')
    conn.commit()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username='admin'")
    if not cursor.fetchone():
        from auth import hash_password
        admin_hash = hash_password("admin123")
        cursor.execute('''INSERT INTO users (username, password_hash, role, college, fullname)
                          VALUES (?, ?, ?, ?, ?)''',
                       ("admin", admin_hash, "admin", "全校", "系统管理员"))
        teacher_hash = hash_password("123456")
        cursor.execute('''INSERT INTO users (username, password_hash, role, college, fullname)
                          VALUES (?, ?, ?, ?, ?)''',
                       ("teacher", teacher_hash, "teacher", "计算机学院", "张老师"))
        student_hash = hash_password("123456")
        cursor.execute('''INSERT INTO users (username, password_hash, role, college, fullname)
                          VALUES (?, ?, ?, ?, ?)''',
                       ("student", student_hash, "student", "计算机学院", "李同学"))
    conn.commit()
    conn.close()
# ===== 用户查询 =====
def get_user_by_username(username):
    conn = get_conn()
    df = pd.read_sql(f"SELECT * FROM users WHERE username='{username}'", conn)
    conn.close()
    if len(df)==0:
        return None
    return df.iloc[0].to_dict()
def get_user_college(username):
    user = get_user_by_username(username)
    return user["college"] if user else None
def create_user(username, password, role, college, fullname):
    from auth import hash_password
    conn = get_conn()
    c = conn.cursor()
    hashed = hash_password(password)
    try:
        c.execute('''INSERT INTO users (username, password_hash, role, college, fullname)
                     VALUES (?, ?, ?, ?, ?)''',
                  (username, hashed, role, college, fullname))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()
# ===== 学生自评（自动转换列名） =====
def save_self_assess(username, df, college):
    df = df.copy()
    # 将中文列名映射为数据库字段
    df.rename(columns={
        "自评时间": "time",
        "焦虑": "anxiety",
        "抑郁": "depression",
        "压力": "stress",
        "睡眠障碍": "sleep",
        "社交回避": "social",
        "总分": "total"
    }, inplace=True)
    df["username"] = username
    df["college"] = college
    conn = get_conn()
    df.to_sql('self_assess', conn, if_exists='append', index=False)
    conn.close()
def load_self_assess(username, college=None):
    conn = get_conn()
    sql = f"SELECT * FROM self_assess WHERE username='{username}'"
    if college:
        sql += f" AND college='{college}'"
    df = pd.read_sql(sql, conn)
    conn.close()
    if not df.empty:
        # 将数据库字段映射回中文列名
        df.rename(columns={
            "time": "自评时间",
            "anxiety": "焦虑",
            "depression": "抑郁",
            "stress": "压力",
            "sleep": "睡眠障碍",
            "social": "社交回避",
            "total": "总分"
        }, inplace=True)
    return df
# ===== 筛查批次 =====
def save_screen_batch(batch_name, teacher, college, tau, df, copula_scores):
    conn = get_conn()
    df_json = df.to_json(orient='records')
    copula_json = json.dumps(copula_scores.tolist())
    c = conn.cursor()
    c.execute('''INSERT INTO screen_batches (batch_name, teacher, college, time, tau, df_json, copula_json)
                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
              (batch_name, teacher, college, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), tau, df_json, copula_json))
    conn.commit()
    conn.close()
def load_latest_screen_batch(college=None):
    conn = get_conn()
    sql = 'SELECT * FROM screen_batches'
    if college:
        sql += f" WHERE college='{college}' OR college='全校'"
    sql += ' ORDER BY id DESC LIMIT 1'
    df = pd.read_sql(sql, conn)
    conn.close()
    if len(df) == 0:
        return None, None, None, None
    row = df.iloc[0]
    return row['batch_name'], row['tau'], pd.read_json(row['df_json']), np.array(json.loads(row['copula_json']))
# ===== 预警台账 =====
def save_alert(student_id, name, college, risk_level, status='待跟进', handler='', note=''):
    conn = get_conn()
    c = conn.cursor()
    c.execute('''INSERT INTO alerts (student_id, name, college, risk_level, time, status, handler, note)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (student_id, name, college, risk_level, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), status, handler, note))
    conn.commit()
    conn.close()
def load_alerts(risk_level=None, status=None, college=None):
    conn = get_conn()
    sql = 'SELECT * FROM alerts'
    conds = []
    if risk_level:
        conds.append(f"risk_level='{risk_level}'")
    if status:
        conds.append(f"status='{status}'")
    if college:
        conds.append(f"college='{college}' OR college='全校'")
    if conds:
        sql += ' WHERE ' + ' AND '.join(conds)
    sql += ' ORDER BY id DESC'
    df = pd.read_sql(sql, conn)
    conn.close()
    return df
def update_alert_status(alert_id, status, note=''):
    conn = get_conn()
    c = conn.cursor()
    c.execute('UPDATE alerts SET status=?, note=? WHERE id=?', (status, note, alert_id))
    conn.commit()
    conn.close()
# ===== 干预任务 =====
def save_intervention(student_id, college, plan, start_time, end_time, handler):
    conn = get_conn()
    c = conn.cursor()
    c.execute('''INSERT INTO interventions (student_id, college, plan, start_time, end_time, status, handler)
                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
              (student_id, college, plan, start_time, end_time, '待执行', handler))
    conn.commit()
    conn.close()
def load_interventions(status=None, college=None):
    conn = get_conn()
    sql = 'SELECT * FROM interventions'
    conds = []
    if status:
        conds.append(f"status='{status}'")
    if college:
        conds.append(f"college='{college}' OR college='全校'")
    if conds:
        sql += ' WHERE ' + ' AND '.join(conds)
    sql += ' ORDER BY id DESC'
    df = pd.read_sql(sql, conn)
    conn.close()
    return df
def update_intervention_status(interv_id, status, result=''):
    conn = get_conn()
    c = conn.cursor()
    c.execute('UPDATE interventions SET status=?, result=? WHERE id=?', (status, result, interv_id))
    conn.commit()
    conn.close()