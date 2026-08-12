# -*- coding: utf-8 -*-
"""
基于贝叶斯在线变点检测与Copula相依结构的高校心理普查数据筛查算法包
国创项目 psycho_screen.py
"""
import numpy as np
import pandas as pd
import pymc as pm
import arviz as az
from scipy import stats
from scipy.stats import multivariate_normal, norm


def psycho_risk_screen(df_raw, dims_list, seed=42):
    """
    :param df_raw: 原始DataFrame，只包含量表维度列
    :param dims_list: list，量表维度名字，例如 ["焦虑", "抑郁", "压力", "睡眠障碍", "社交回避", "躯体化"]
    :param seed: 随机种子
    :return: df_out(带全部风险指标), trace(贝叶斯采样结果), tau_mean(估计变点位置)
    """
    np.random.seed(seed)
    df = df_raw.copy()
    df["总分"] = df[dims_list].sum(axis=1)
    n = df.shape[0]

    # ========== 贝叶斯变点检测 ==========
    total_scores = df["总分"].values
    T = len(total_scores)
    with pm.Model() as model:
        tau = pm.DiscreteUniform("tau", lower=0, upper=T - 1)
        mu1 = pm.Normal("mu1", mu=total_scores.mean(), sigma=2)
        mu2 = pm.Normal("mu2", mu=total_scores.mean(), sigma=2)
        sigma = pm.HalfNormal("sigma", sigma=2)
        mu = pm.math.switch(tau >= np.arange(T), mu1, mu2)
        obs = pm.Normal("obs", mu=mu, sigma=sigma, observed=total_scores)
        trace = pm.sample(600, tune=300, cores=1, return_inferencedata=True)

    tau_samples = trace.posterior["tau"].values.flatten()
    tau_mean = int(tau_samples.mean())

    # ========== Copula相依结构，计算异常分 ==========
    data_mat = df[dims_list].values
    u_data = norm.cdf(stats.zscore(data_mat))
    kendall_corr = pd.DataFrame(data_mat, columns=dims_list).corr(method="kendall")
    copula_corr = np.sin(np.pi * kendall_corr.values / 2)
    np.fill_diagonal(copula_corr, 1.0)

    # ----------------修复非正定矩阵报错----------------
    cov_mat = copula_corr.copy()
    epsilon = 1e-6
    min_eig = np.min(np.real(np.linalg.eigvals(cov_mat)))
    if min_eig < 0:
        cov_mat += (abs(min_eig) + epsilon) * np.eye(cov_mat.shape[0])

    mv_norm = multivariate_normal(mean=np.zeros(len(dims_list)), cov=cov_mat, allow_singular=True)
    # ---------------------------------------------------

    z_vals = norm.ppf(np.clip(u_data, 1e-6, 1 - 1e-6))
    log_density = mv_norm.logpdf(z_vals)
    df["Copula异常分"] = -log_density

    # ========== 综合风险评分 ==========
    df["总分Z"] = stats.zscore(df["总分"])
    df["CopulaZ"] = stats.zscore(df["Copula异常分"])
    df["综合风险分"] = 0.6 * df["总分Z"] + 0.4 * df["CopulaZ"]

    def risk_level(score):
        if score >= 1.5:
            return "高危"
        elif score >= 0.5:
            return "中危"
        else:
            return "低危"

    df["风险等级"] = df["综合风险分"].apply(risk_level)
    df.reset_index(drop=True, inplace=True)
    df["编号"] = np.arange(1, n + 1)
    return df, trace, tau_mean