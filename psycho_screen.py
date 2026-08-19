# psycho_screen.py
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
    np.random.seed(seed)
    df = df_raw.copy()
    df["总分"] = df[dims_list].sum(axis=1)
    n = df.shape[0]
    total_scores = df["总分"].values
    T = len(total_scores)
    with pm.Model() as model:
        tau = pm.DiscreteUniform("tau", lower=0, upper=T - 1)
        mu1 = pm.Normal("mu1", mu=total_scores.mean(), sigma=2)
        mu2 = pm.Normal("mu2", mu=total_scores.mean(), sigma=2)
        sigma = pm.HalfNormal("sigma", sigma=2)
        mu = pm.math.switch(tau >= np.arange(T), mu1, mu2)
        obs = pm.Normal("obs", mu=mu, sigma=sigma, observed=total_scores)
        trace = pm.sample(300, tune=150, chains=2, cores=1, return_inferencedata=True)
    tau_samples = trace.posterior["tau"].values.flatten()
    tau_mean = int(tau_samples.mean())
    data_mat = df[dims_list].values
    u_data = norm.cdf(stats.zscore(data_mat))
    kendall_corr = pd.DataFrame(data_mat, columns=dims_list).corr(method="kendall")
    copula_corr = np.sin(np.pi * kendall_corr.values / 2)
    np.fill_diagonal(copula_corr, 1.0)
    cov_mat = copula_corr.copy()
    epsilon = 1e-6
    min_eig = np.min(np.real(np.linalg.eigvals(cov_mat)))
    if min_eig < 0:
        cov_mat += (abs(min_eig) + epsilon) * np.eye(cov_mat.shape[0])
    mv_norm = multivariate_normal(mean=np.zeros(len(dims_list)), cov=cov_mat, allow_singular=True)
    z_vals = norm.ppf(np.clip(u_data, 1e-6, 1 - 1e-6))
    log_density = mv_norm.logpdf(z_vals)
    copula_abnormal_score = -log_density
    df["Copula异常分"] = copula_abnormal_score
    df["总分Z"] = stats.zscore(df["总分"])
    df["CopulaZ"] = stats.zscore(df["Copula异常分"])
    df["综合风险分"] = 0.6 * df["总分Z"] + 0.4 * df["CopulaZ"]
    def risk_level(score):
        if score >= high_threshold:
            return "高危"
        elif score >= mid_threshold:
            return "中危"
        else:
            return "低危"
    df["风险等级"] = df["综合风险分"].apply(risk_level)
    df.reset_index(drop=True, inplace=True)
    df["编号"] = np.arange(1, n + 1)
    gc.collect()
    return df, trace, tau_mean, copula_abnormal_score