# 基于链上压力残差校正的 AMM 短时极端波动预测计划

## Summary
本项目聚焦一个清晰任务：**预测 Uniswap v3 ETH/USDC 池下一小时是否进入极端波动状态**。

核心方法：

> 传统波动模型解释常规波动，链上压力变量校正其未解释残差。

项目输出是短时波动状态预测模型。量化应用只在动机或展望中提及：该预测可作为未来择时或仓位过滤模块；本文不做策略回测。

## Research Design & Inputs/Outputs
- 研究对象：Uniswap v3 `ETH/USDC 0.05%` 单池。
- 数据周期：默认 `2024-01-01` 至 `2025-01-01`，小时级聚合。
- 输入数据：
  - `PoolHourData`：价格、成交量、流动性、tick、小时级池状态。
  - `Swap`：成交额、成交次数、大额成交、方向不平衡、价格冲击。
  - `Mint/Burn`：流动性增加、流动性撤出、净流动性变化。
  - `Transaction/Block/Gas`：gas price 或 gas proxy、交易拥堵 proxy。
- 输入变量组：
  - **Baseline market variables**：过去 1h/6h/24h 收益率、realized volatility、成交量。
  - **Swap pressure**：swap volume、swap count、large swap ratio、direction imbalance、volume per liquidity。
  - **Liquidity pressure**：mint volume、burn volume、net liquidity change、burn-to-mint ratio。
  - **Blockspace pressure**：median gas price、gas volatility、transaction count/congestion proxy。
- 监督标签：
  - `HighVol_{t+1}`：下一小时 realized volatility 或绝对收益率超过训练窗口内滚动 75% 或 80% 分位。
  - 阈值只在训练窗口内计算，避免时间泄漏。
- 模型输出：
  - `baseline_vol_pred(t+1)`：传统波动模型预测值。
  - `residual_correction(t+1)`：链上压力变量对 baseline 残差的校正项。
  - `p_high_vol(t+1)`：下一小时进入高波动状态的概率。
  - `calibrated_threshold(t+1)`：在线校准后的动态预警阈值。
  - `warning_label(t+1)`：基于动态阈值生成的最终高波动预警标签。

## Method
- Baseline 1：传统波动模型
  - HAR-RV / rolling volatility regression。
  - 只使用历史收益率、历史波动率、成交量等市场变量。
- Baseline 2：直接全特征机器学习模型
  - LightGBM 或 XGBoost。
  - 输入 baseline market variables + 全部链上压力变量。
  - 用于检验“直接把链上特征输入模型”的效果。
- Proposed：链上压力残差校正框架
  - 第一步：传统波动模型得到 `baseline_vol_pred`。
  - 第二步：计算训练期残差 `residual = realized_vol - baseline_vol_pred`。
  - 第三步：用 Swap pressure、Liquidity pressure、Blockspace pressure 建模残差或高残差状态。
  - 第四步：合成校正后的波动预测或高波动概率。
- Proposed：压力加权在线校准算法（PWOC）
  - 动机：固定分位数阈值在 AMM 市场状态切换时可能不稳定；同样的预测分数在高 Swap 冲击、流动性撤出或 Gas 拥堵状态下可能对应更高的尾部风险。
  - 定义链上压力指数 `CPI_t = w1 * SwapPressure_t + w2 * LiquidityPressure_t + w3 * BlockspacePressure_t`。
  - 在每个滚动窗口内，根据近期样本与当前 `CPI_t` 的压力状态相似度分配校准权重。
  - 使用压力加权分位数更新动态阈值 `calibrated_threshold(t+1)`。
  - 预警规则：若 `p_high_vol(t+1) >= calibrated_threshold(t+1)`，则输出 `warning_label(t+1)=1`。
  - 对照阈值方案：固定训练集分位数阈值、普通滚动分位数阈值、PWOC 压力加权在线校准阈值。
- 滚动窗口验证：
  - 按时间顺序训练、验证、测试。
  - 每个窗口重新计算标签阈值、模型参数和特征重要性。
  - 不使用随机划分。

## Evaluation
- 预测指标：
  - AUC、PR-AUC、F1、Recall、Precision@high-volatility。
- 极端波动解释指标：
  - High-volatility capture rate：真实高波动时段被捕获比例。
  - False alarm rate：错误预警比例。
  - Tail coverage：前 5% 或前 10% 极端波动时段覆盖率。
  - Tail miss rate：真实极端波动时段未被预警的比例。
  - Average realized volatility under warning：预警时段真实平均波动率。
- 校准指标：
  - Rolling tail coverage deviation：不同滚动窗口中 tail coverage 偏离目标覆盖率的程度。
  - Calibration error：动态阈值下预警概率与真实高波动频率的偏差。
  - Missed extreme event count：未捕获的极端波动事件数量。
- 消融实验：
  - 去掉 Swap pressure。
  - 去掉 Liquidity pressure。
  - 去掉 Blockspace pressure。
  - 去掉在线校准，仅使用固定分位数阈值。
  - 去掉压力加权，仅使用普通滚动阈值。
  - 去掉滚动窗口，改为固定时间切分，检验时间稳健性。
- 可解释分析：
  - SHAP 或特征重要性。
  - 比较不同滚动窗口中 Gas、Swap、Mint/Burn 变量的重要性变化。
  - 分析链上压力变量主要解释哪些极端残差时段。

## Demo & Deliverables
- Python 实验代码：
  - 数据抓取/读取；
  - 小时级聚合；
  - 标签构造；
  - baseline 模型；
  - 残差校正模型；
  - PWOC 在线校准；
  - 滚动窗口评估；
  - 图表输出。
- Streamlit 展示系统：
  - 时间区间选择；
  - 真实波动率与预测概率曲线；
  - 高波动预警区间标注；
  - 模型与阈值校准方案对比表；
  - 特征重要性展示；
  - 典型高波动窗口案例分析。
- 可选链上存证模块：
  - 存储数据版本哈希、模型版本、预测结果哈希。
  - 只作为课程技术补充，不作为研究贡献主体。
- 报告图表：
  - 残差校正框架图；
  - 输入变量分组表；
  - 模型性能对比表；
  - 阈值校准方案对比表；
  - 消融实验表；
  - 高波动预警曲线；
  - SHAP/特征重要性图。

## Blockchain Relevance
- 核心研究对象来自 Uniswap v3 智能合约事件：
  - `Swap` 对应 AMM 交易冲击；
  - `Mint/Burn` 对应 LP 流动性再配置；
  - `PoolHourData` 对应池状态变化。
- `Gas / Blockspace pressure` 是区块链系统执行层变量：
  - 反映区块空间竞争、交易确认成本和链上拥堵状态；
  - 是传统中心化市场数据中不存在的机制变量。
- 安全性与系统分析：
  - subgraph/RPC 数据依赖与索引延迟；
  - Gas 拥堵导致交易执行不确定性；
  - 公链地址匿名但可关联分析；
  - 模型预警信号若公开可能造成策略泄露或被利用。

## Boundaries
- 不做真实交易。
- 不做策略回测。
- 不报告收益率、Sharpe、最大回撤等交易绩效指标。
- 不把项目写成“量化策略论文”。
- 仅在动机或展望中说明：高波动状态预测可作为未来量化择时或仓位过滤模块。
- Temporal GNN 删除。
- 多分类删除。
- 多池不进入 MVP，只作为后续外部有效性验证。
