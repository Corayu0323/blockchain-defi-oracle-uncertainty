# 实验窗口与机制结果筛选表


说明：本文件只整理实验结果，便于人工筛选和复核；不作为正文方法描述。若后续写入报告，建议同步说明窗口选择规则，避免结果选择和方法描述不一致。


## 一、当前 9 个主实验窗口


### 1.1 窗口清单


| 窗口 | 类型 | 开始 | 结束 | 价格变化 |
| --- | --- | --- | --- | ---: |
| real_normal_1 | normal | 2026-03-15 | 2026-05-25 | 0.08 |
| real_normal_2 | normal | 2025-11-18 | 2026-01-28 | -0.01 |
| real_normal_3 | normal | 2026-02-03 | 2026-04-15 | -0.91 |
| real_drawdown_1 | drawdown | 2025-12-11 | 2026-02-20 | -41.47 |
| real_drawdown_2 | drawdown | 2026-01-16 | 2026-03-28 | -39.97 |
| real_drawdown_3 | drawdown | 2025-09-13 | 2025-11-23 | -41.20 |
| counterfactual_oracle_shock_1 | oracle shock | 2026-03-15 | 2026-05-25 | 0.08 |
| counterfactual_oracle_shock_2 | oracle shock | 2025-11-18 | 2026-01-28 | -0.01 |
| counterfactual_oracle_shock_3 | oracle shock | 2026-02-03 | 2026-04-15 | -0.91 |


### 1.2 9 窗口聚合结果


| 机制 | 偿付违规次数 | TOPSIS | mean rank | 最大坏账 | 坏账 ES95 | 误清算损失 | 用户损失 | 清算次数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| buffer | 0 | 0.5101 | 2.4889 | 0.00 | 0.00 | 432.50 | 536.91 | 16 |
| fixed | 1 | 0.4991 | 2.5000 | 117.32 | 115.96 | 362.18 | 511.17 | 64 |
| USPL | 1 | 0.3602 | 2.8222 | 2.73 | 2.73 | 405.20 | 557.91 | 44 |
| twap | 2 | 0.5665 | 2.1889 | 336.71 | 323.43 | 0.00 | 392.80 | 72 |


### 1.3 按场景类型聚合


| 场景类型 | 机制 | 窗口数 | 偿付违规次数 | 最大坏账 | 坏账 ES95 | 误清算损失 | 用户损失 | 清算次数 | 平均 TOPSIS | 平均 mean rank |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| drawdown | buffer | 3 | 0 | 0.00 | 0.00 | 246.41 | 350.83 | 11 | 0.6599 | 2.4667 |
| drawdown | fixed | 3 | 1 | 117.32 | 115.96 | 176.09 | 325.08 | 59 | 0.6268 | 2.5000 |
| drawdown | twap | 3 | 2 | 336.71 | 323.43 | 0.00 | 313.33 | 70 | 0.3884 | 2.5333 |
| drawdown | USPL | 3 | 1 | 2.73 | 2.73 | 194.72 | 347.43 | 33 | 0.6399 | 2.5000 |
| normal | buffer | 3 | 0 | 0.00 | 0.00 | 39.74 | 39.74 | 1 | 0.5385 | 2.3333 |
| normal | fixed | 3 | 0 | 0.00 | 0.00 | 39.74 | 39.74 | 1 | 0.5385 | 2.3333 |
| normal | twap | 3 | 0 | 0.00 | 0.00 | 0.00 | 39.74 | 1 | 0.4859 | 2.3333 |
| normal | USPL | 3 | 0 | 0.00 | 0.00 | 63.59 | 63.59 | 4 | 0.1808 | 3.0000 |
| oracle shock | buffer | 3 | 0 | 0.00 | 0.00 | 146.35 | 146.35 | 4 | 0.3320 | 2.6667 |
| oracle shock | fixed | 3 | 0 | 0.00 | 0.00 | 146.35 | 146.35 | 4 | 0.3320 | 2.6667 |
| oracle shock | twap | 3 | 0 | 0.00 | 0.00 | 0.00 | 39.74 | 1 | 0.8253 | 1.7000 |
| oracle shock | USPL | 3 | 0 | 0.00 | 0.00 | 146.89 | 146.89 | 7 | 0.2598 | 2.9667 |


### 1.4 逐窗口 USPL 对比速览


| 窗口 | 类型 | USPL坏账ES95 | USPL误清算 | USPL用户损失 | USPL清算次数 | 坏账最优 | 误清算最优 | 用户损失最优 | TOPSIS最优 | USPL坏账排名 | USPL误清算排名 | USPL TOPSIS排名 |
| --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| real_normal_1 | normal | 0.00 | 0.00 | 0.00 | 0 | fixed | fixed | fixed | fixed | 2.5 | 2.5 | 2.5 |
| real_normal_2 | normal | 0.00 | 19.51 | 19.51 | 2 | fixed | fixed | fixed | fixed | 2.5 | 4.0 | 4.0 |
| real_normal_3 | normal | 0.00 | 44.08 | 44.08 | 2 | fixed | twap | fixed | fixed | 2.5 | 4.0 | 3.0 |
| real_drawdown_1 | drawdown | 0.00 | 48.48 | 108.88 | 11 | fixed | twap | twap | buffer | 2.0 | 2.0 | 2.0 |
| real_drawdown_2 | drawdown | 2.73 | 42.38 | 110.08 | 11 | buffer | fixed | twap | USPL | 2.0 | 3.0 | 1.0 |
| real_drawdown_3 | drawdown | 0.00 | 103.86 | 128.47 | 11 | fixed | twap | fixed | fixed | 2.5 | 2.0 | 3.0 |
| counterfactual_oracle_shock_1 | oracle shock | 0.00 | 24.15 | 24.15 | 1 | fixed | twap | twap | twap | 2.5 | 2.0 | 2.0 |
| counterfactual_oracle_shock_2 | oracle shock | 0.00 | 60.96 | 60.96 | 3 | fixed | twap | twap | twap | 2.5 | 4.0 | 4.0 |
| counterfactual_oracle_shock_3 | oracle shock | 0.00 | 61.78 | 61.78 | 3 | fixed | twap | twap | fixed | 2.5 | 4.0 | 3.0 |


## 二、固定随机种子 30 窗口补充实验


随机种子：`20260611`。窗口构造：10 个 normal 候选随机窗口、10 个 drawdown 候选随机窗口、10 个在同一 normal 窗口上注入 25% oracle shock 的反事实窗口。


### 2.1 窗口清单


| 窗口 | 类型 | 开始 | 结束 | 价格变化 | 最大回撤 |
| --- | --- | --- | --- | ---: | ---: |
| random_normal_01 | normal | 2026-03-15 | 2026-05-25 | 0.08 | -15.65 |
| random_normal_02 | normal | 2026-03-23 | 2026-06-02 | -2.42 | -17.25 |
| random_normal_03 | normal | 2026-03-11 | 2026-05-21 | 4.52 | -15.65 |
| random_normal_04 | normal | 2025-11-19 | 2026-01-29 | -3.54 | -16.16 |
| random_normal_05 | normal | 2026-03-22 | 2026-06-01 | -3.56 | -17.23 |
| random_normal_06 | normal | 2026-03-14 | 2026-05-24 | 1.08 | -15.65 |
| random_normal_07 | normal | 2026-03-13 | 2026-05-23 | -0.58 | -15.65 |
| random_normal_08 | normal | 2026-03-16 | 2026-05-26 | -2.94 | -15.65 |
| random_normal_09 | normal | 2025-11-18 | 2026-01-28 | -0.01 | -16.16 |
| random_normal_10 | normal | 2026-03-12 | 2026-05-22 | 3.90 | -15.65 |
| random_drawdown_01 | drawdown | 2026-01-20 | 2026-04-01 | -33.93 | -42.85 |
| random_drawdown_02 | drawdown | 2025-12-15 | 2026-02-24 | -39.53 | -45.76 |
| random_drawdown_03 | drawdown | 2025-12-14 | 2026-02-23 | -37.27 | -45.76 |
| random_drawdown_04 | drawdown | 2025-10-11 | 2025-12-21 | -22.38 | -34.89 |
| random_drawdown_05 | drawdown | 2025-09-09 | 2025-11-19 | -27.67 | -35.84 |
| random_drawdown_06 | drawdown | 2025-09-17 | 2025-11-27 | -32.79 | -41.04 |
| random_drawdown_07 | drawdown | 2025-10-04 | 2025-12-14 | -31.01 | -41.04 |
| random_drawdown_08 | drawdown | 2025-09-16 | 2025-11-26 | -34.68 | -41.04 |
| random_drawdown_09 | drawdown | 2026-01-06 | 2026-03-18 | -28.19 | -45.76 |
| random_drawdown_10 | drawdown | 2025-11-01 | 2026-01-11 | -19.87 | -29.29 |
| random_oracle_shock_01 | oracle shock | 2026-03-15 | 2026-05-25 | 0.08 | -15.65 |
| random_oracle_shock_02 | oracle shock | 2026-03-23 | 2026-06-02 | -2.42 | -17.25 |
| random_oracle_shock_03 | oracle shock | 2026-03-11 | 2026-05-21 | 4.52 | -15.65 |
| random_oracle_shock_04 | oracle shock | 2025-11-19 | 2026-01-29 | -3.54 | -16.16 |
| random_oracle_shock_05 | oracle shock | 2026-03-22 | 2026-06-01 | -3.56 | -17.23 |
| random_oracle_shock_06 | oracle shock | 2026-03-14 | 2026-05-24 | 1.08 | -15.65 |
| random_oracle_shock_07 | oracle shock | 2026-03-13 | 2026-05-23 | -0.58 | -15.65 |
| random_oracle_shock_08 | oracle shock | 2026-03-16 | 2026-05-26 | -2.94 | -15.65 |
| random_oracle_shock_09 | oracle shock | 2025-11-18 | 2026-01-28 | -0.01 | -16.16 |
| random_oracle_shock_10 | oracle shock | 2026-03-12 | 2026-05-22 | 3.90 | -15.65 |


### 2.2 30 窗口聚合结果


| 机制 | 偿付违规次数 | TOPSIS | mean rank | 最大坏账 | 坏账 ES95 | 误清算损失 | 用户损失 | 清算次数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| buffer | 2 | 0.3688 | 2.5667 | 65.49 | 53.22 | 1013.43 | 1462.42 | 111 |
| USPL | 2 | 0.2425 | 2.6100 | 2.20 | 2.20 | 1137.72 | 1453.06 | 122 |
| twap | 4 | 0.5930 | 2.2367 | 393.20 | 350.81 | 0.00 | 1060.09 | 150 |
| fixed | 4 | 0.3965 | 2.5867 | 139.43 | 131.73 | 656.02 | 1450.13 | 165 |


### 2.3 按场景类型聚合


| 场景类型 | 机制 | 窗口数 | 偿付违规次数 | 最大坏账 | 坏账 ES95 | 误清算损失 | 用户损失 | 清算次数 | 平均 TOPSIS | 平均 mean rank |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| drawdown | buffer | 10 | 2 | 65.49 | 53.22 | 627.03 | 1076.01 | 101 | 0.6803 | 2.3700 |
| drawdown | fixed | 10 | 4 | 139.43 | 131.73 | 304.39 | 1098.50 | 156 | 0.6633 | 2.5700 |
| drawdown | twap | 10 | 4 | 393.20 | 350.81 | 0.00 | 1060.09 | 150 | 0.4789 | 2.6700 |
| drawdown | USPL | 10 | 2 | 2.20 | 2.20 | 765.91 | 1081.25 | 101 | 0.5309 | 2.3900 |
| normal | buffer | 10 | 0 | 0.00 | 0.00 | 0.00 | 0.00 | 0 | 0.3000 | 2.4100 |
| normal | fixed | 10 | 0 | 0.00 | 0.00 | 0.00 | 0.00 | 0 | 0.3000 | 2.4100 |
| normal | twap | 10 | 0 | 0.00 | 0.00 | 0.00 | 0.00 | 0 | 0.3000 | 2.4100 |
| normal | USPL | 10 | 0 | 0.00 | 0.00 | 51.90 | 51.90 | 5 | 0.0000 | 2.7700 |
| oracle shock | buffer | 10 | 0 | 0.00 | 0.00 | 386.40 | 386.40 | 10 | 0.1261 | 2.9200 |
| oracle shock | fixed | 10 | 0 | 0.00 | 0.00 | 351.63 | 351.63 | 9 | 0.2261 | 2.7800 |
| oracle shock | twap | 10 | 0 | 0.00 | 0.00 | 0.00 | 0.00 | 0 | 1.0000 | 1.6300 |
| oracle shock | USPL | 10 | 0 | 0.00 | 0.00 | 319.91 | 319.91 | 16 | 0.1965 | 2.6700 |


### 2.4 逐窗口 USPL 对比速览


| 窗口 | 类型 | USPL坏账ES95 | USPL误清算 | USPL用户损失 | USPL清算次数 | 坏账最优 | 误清算最优 | 用户损失最优 | TOPSIS最优 | USPL坏账排名 | USPL误清算排名 | USPL TOPSIS排名 |
| --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| random_normal_01 | normal | 0.00 | 0.00 | 0.00 | 0 | fixed | fixed | fixed | fixed | 2.5 | 2.5 | 2.5 |
| random_normal_02 | normal | 0.00 | 0.00 | 0.00 | 0 | fixed | fixed | fixed | fixed | 2.5 | 2.5 | 2.5 |
| random_normal_03 | normal | 0.00 | 0.00 | 0.00 | 0 | fixed | fixed | fixed | fixed | 2.5 | 2.5 | 2.5 |
| random_normal_04 | normal | 0.00 | 23.96 | 23.96 | 2 | fixed | fixed | fixed | fixed | 2.5 | 4.0 | 4.0 |
| random_normal_05 | normal | 0.00 | 0.00 | 0.00 | 0 | fixed | fixed | fixed | fixed | 2.5 | 2.5 | 2.5 |
| random_normal_06 | normal | 0.00 | 0.00 | 0.00 | 0 | fixed | fixed | fixed | fixed | 2.5 | 2.5 | 2.5 |
| random_normal_07 | normal | 0.00 | 0.00 | 0.00 | 0 | fixed | fixed | fixed | fixed | 2.5 | 2.5 | 2.5 |
| random_normal_08 | normal | 0.00 | 8.43 | 8.43 | 1 | fixed | fixed | fixed | fixed | 2.5 | 4.0 | 4.0 |
| random_normal_09 | normal | 0.00 | 19.51 | 19.51 | 2 | fixed | fixed | fixed | fixed | 2.5 | 4.0 | 4.0 |
| random_normal_10 | normal | 0.00 | 0.00 | 0.00 | 0 | fixed | fixed | fixed | fixed | 2.5 | 2.5 | 2.5 |
| random_drawdown_01 | drawdown | 2.20 | 27.32 | 105.03 | 10 | USPL | fixed | twap | buffer | 1.0 | 4.0 | 3.0 |
| random_drawdown_02 | drawdown | 0.59 | 14.60 | 99.82 | 8 | USPL | fixed | twap | fixed | 1.0 | 4.0 | 3.0 |
| random_drawdown_03 | drawdown | 0.00 | 27.38 | 99.63 | 9 | buffer | fixed | twap | buffer | 1.5 | 4.0 | 3.0 |
| random_drawdown_04 | drawdown | 0.00 | 92.84 | 92.84 | 9 | fixed | fixed | USPL | fixed | 2.5 | 3.0 | 4.0 |
| random_drawdown_05 | drawdown | 0.00 | 94.81 | 94.81 | 8 | fixed | twap | twap | buffer | 2.5 | 4.0 | 4.0 |
| random_drawdown_06 | drawdown | 0.00 | 129.28 | 129.28 | 13 | fixed | twap | fixed | fixed | 2.5 | 4.0 | 4.0 |
| random_drawdown_07 | drawdown | 0.00 | 118.58 | 129.86 | 11 | fixed | twap | USPL | buffer | 2.5 | 4.0 | 3.0 |
| random_drawdown_08 | drawdown | 0.00 | 130.37 | 130.37 | 13 | fixed | twap | USPL | buffer | 2.5 | 4.0 | 3.0 |
| random_drawdown_09 | drawdown | 0.00 | 36.97 | 105.85 | 11 | buffer | fixed | buffer | USPL | 1.5 | 3.0 | 1.0 |
| random_drawdown_10 | drawdown | 0.00 | 93.75 | 93.75 | 9 | fixed | fixed | USPL | fixed | 2.5 | 3.0 | 4.0 |
| random_oracle_shock_01 | oracle shock | 0.00 | 24.15 | 24.15 | 1 | fixed | twap | twap | twap | 2.5 | 2.0 | 2.0 |
| random_oracle_shock_02 | oracle shock | 0.00 | 21.74 | 21.74 | 1 | fixed | twap | twap | twap | 2.5 | 2.0 | 2.0 |
| random_oracle_shock_03 | oracle shock | 0.00 | 32.61 | 32.61 | 1 | fixed | twap | twap | twap | 2.5 | 2.0 | 2.0 |
| random_oracle_shock_04 | oracle shock | 0.00 | 64.82 | 64.82 | 3 | fixed | twap | twap | twap | 2.5 | 4.0 | 4.0 |
| random_oracle_shock_05 | oracle shock | 0.00 | 23.57 | 23.57 | 1 | fixed | twap | twap | twap | 2.5 | 2.0 | 2.0 |
| random_oracle_shock_06 | oracle shock | 0.00 | 22.26 | 22.26 | 1 | fixed | twap | twap | twap | 2.5 | 2.0 | 2.0 |
| random_oracle_shock_07 | oracle shock | 0.00 | 24.31 | 24.31 | 1 | fixed | twap | twap | twap | 2.5 | 2.0 | 2.0 |
| random_oracle_shock_08 | oracle shock | 0.00 | 29.79 | 29.79 | 3 | fixed | twap | twap | twap | 2.5 | 2.0 | 4.0 |
| random_oracle_shock_09 | oracle shock | 0.00 | 60.96 | 60.96 | 3 | fixed | twap | twap | twap | 2.5 | 4.0 | 4.0 |
| random_oracle_shock_10 | oracle shock | 0.00 | 15.70 | 15.70 | 1 | fixed | fixed | fixed | fixed | 2.5 | 3.0 | 3.0 |


## 三、文件索引


- `outputs/real_data_windows.csv`：9 个主实验窗口。

- `outputs/real_data_metrics.csv`：9 个主实验逐机制完整指标。

- `outputs/real_group_metrics.csv`：9 个主实验按场景类型聚合。

- `outputs/random_30_windows.csv`：30 个固定随机种子窗口。

- `outputs/random_30_metrics.csv`：30 个窗口逐机制完整指标。

- `outputs/random_30_group_metrics.csv`：30 个窗口按场景类型聚合。

- `outputs/random_30_aggregate.csv`：30 个窗口跨场景聚合。