# -*- coding: utf-8 -*-
"""
基于贝叶斯在线变点检测与Copula相依结构的高校心理普查数据筛查算法包
国创项目 psycho_screen.py
适配多角色平台增强版：支持自定义风险阈值，返回Copula异常分数组用于前端绘图筛选
优化版：降低采样迭代，适应Streamlit Cloud 1GB内存环境
"""
import numpy as np
import pandas as pd
import pymc as pm
import arviz as az
from scipy import stats
from scipy.stats import multivariate_normal, norm
import gc

def psycho_risk_screen(df_raw, dims_list, high_threshold=1.5, mid_threshold=0.5, seed=42):
    """
    心理风险智能筛查主算法
    :param df_raw: 原始DataFrame，包含所有量表维度列
    :param dims_list: list，量表维度字段名
    :param high_threshold: 高危综合风险分阈值（前端可自定义）
    :param mid_threshold: 中危综合风险分阈值（前端可自定义）
    :param seed: 随机种子，保证复现结果
    :return: df_out(完整带指标数据表), trace(贝叶斯采样后验数据), tau_mean(变点均值), copula_abnormal_score(Copula异常分数组)
    """
    np.random.seed(seed)
    df = df_raw.copy()
    # 计算量表总分
    df["总分"] = df[dims_list].sum(axis=1)
    n = df.shape[0]

    # ===================== 1. 贝叶斯离散变点检测 =====================
    total_scores = df["总分"].values
    T = len(total_scores)
    with pm.Model() as model:
        # 变点均匀先验
        tau = pm.DiscreteUniform("tau", lower=0, upper=T - 1)
        # 分段均值先验
        mu1 = pm.Normal("mu1", mu=total_scores.mean(), sigma=2)
        mu2 = pm.Normal("mu2", mu=total_scores.mean(), sigma=2)
        sigma = pm.HalfNormal("sigma", sigma=2)
        # 根据变点切换前后两段均值
        mu = pm.math.switch(tau >= np.arange(T), mu1, mu2)
        # 观测似然
        obs = pm.Normal("obs", mu=mu, sigma=sigma, observed=total_scores)
        # MCMC采样 - 降低迭代次数，减少链数，适应云环境
        trace = pm.sample(300, tune=150, chains=2, cores=1, return_inferencedata=True)
    # 计算变点后验均值
    tau_samples = trace.posterior["tau"].values.flatten()
    tau_mean = int(tau_samples.mean())

    # ===================== 2. Copula相依结构建模，计算异常分 =====================
    data_mat = df[dims_list].values
    # 边缘经验分布转化为均匀分布U(0,1)
    u_data = norm.cdf(stats.zscore(data_mat))
    # Kendall相关系数转换为高斯Copula相关矩阵
    kendall_corr = pd.DataFrame(data_mat, columns=dims_list).corr(method="kendall")
    copula_corr = np.sin(np.pi * kendall_corr.values / 2)
    np.fill_diagonal(copula_corr, 1.0)

    # 修复相关矩阵非正定报错（核心兼容代码）
    cov_mat = copula_corr.copy()
    epsilon = 1e-6
    min_eig = np.min(np.real(np.linalg.eigvals(cov_mat)))
    if min_eig < 0:
        cov_mat += (abs(min_eig) + epsilon) * np.eye(cov_mat.shape[0])

    # 多元高斯Copula
    mv_norm = multivariate_normal(mean=np.zeros(len(dims_list)), cov=cov_mat, allow_singular=True)
    # 分位数逆变换至标准正态
    z_vals = norm.ppf(np.clip(u_data, 1e-6, 1 - 1e-6))
    # 对数密度，取负作为Copula异常分（值越大异常程度越高）
    log_density = mv_norm.logpdf(z_vals)
    copula_abnormal_score = -log_density
    df["Copula异常分"] = copula_abnormal_score

    # ===================== 3. 综合风险评分与分级（支持前端自定义阈值） =====================
    df["总分Z"] = stats.zscore(df["总分"])
    df["CopulaZ"] = stats.zscore(df["Copula异常分"])
    # 加权综合风险分：总分权重0.6，Copula相依异常权重0.4
    df["综合风险分"] = 0.6 * df["总分Z"] + 0.4 * df["CopulaZ"]

    # 动态风险分级函数，接收前端传入阈值
    def risk_level(score):
        if score >= high_threshold:
            return "高危"
        elif score >= mid_threshold:
            return "中危"
        else:
            return "低危"
    df["风险等级"] = df["综合风险分"].apply(risk_level)

    # 生成样本编号
    df.reset_index(drop=True, inplace=True)
    df["编号"] = np.arange(1, n + 1)

    # 建议：如内存紧张，可在此处删除部分中间变量
    # del data_mat, u_data, z_vals, cov_mat, mv_norm
    # gc.collect()

    # 多返回值，供前端绘图、筛选使用
    return df, trace, tau_mean, copula_abnormal_score