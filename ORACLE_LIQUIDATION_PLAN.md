# 基于预言机不确定性的 DeFi 分区清算机制研究计划

## Summary
本项目研究 DeFi 抵押借贷中一个具体机制问题：

> 当预言机价格存在延迟、异常或短时偏离时，智能合约如何在坏账风险与误清算风险之间做更稳健的清算决策？

课程阶段完成一个可解释的机制设计与仿真验证；论文阶段在同一机制上补充真实数据校准、历史 case 验证、更强 baseline 和统计检验。

核心机制从原来的“场景切换”调整为：

> **Uncertainty-Scaled Partial Liquidation, USPL**  
> 即：先估计预言机价格不确定区间，再计算 Health Factor 区间，并在不确定区中根据区间宽度动态缩放最大清算比例。

本项目不做价格预测、不做量化策略、不训练 AI 风控分类器。统计建模和仿真只服务于区块链清算机制评估。

## Core Thesis
- DeFi 清算机制中存在两类方向相反的风险：
  - **Bad debt risk**：真实价格持续下跌，但预言机价格滞后，清算触发过晚。
  - **False liquidation risk**：价格只是短时异常或预言机短时偏离，但合约过早触发清算。
- 现有 baseline 各有偏向：
  - 固定阈值清算规则简单，但依赖单一预言机价格。
  - TWAP/median 价格过滤更适合减少短时异常导致的误清算，但真实快速下跌时可能反应变慢。
  - 简单安全缓冲更适合降低坏账，但可能增加提前清算、用户损失和清算频率。
- 本项目的 proposed 机制不是发明 partial liquidation 或 delayed confirmation；这些在真实协议中已有类似工程做法。
- 真正的创新点是：

> 将预言机价格不确定性量化为价格区间，并把区间宽度传导到 Health Factor 和清算强度，使最大清算比例随 oracle uncertainty 动态缩放。

## Research Design
- 研究对象：单资产抵押 DeFi 借贷清算机制。
- 简化场景：
  - 抵押资产：ETH。
  - 借出资产：USDC。
  - 价格输入：ETH/USD 预言机价格。
  - 清算边界：`Health Factor < 1`。
- 核心参与方：
  - Borrower：抵押 ETH，借出 USDC。
  - Oracle：向合约提供 ETH/USD 价格。
  - Smart Contract：计算健康因子并执行清算规则。
  - Liquidator：在账户可清算时偿还债务并获得折价抵押品。
- 核心输出指标：
  - `bad_debt_event` / `bad_debt_size`
  - `false_liquidation_event`
  - `liquidation_delay`
  - `user_loss`
  - `liquidation_count`

## Proposed Mechanism: USPL
### Step 1: 预言机价格区间
普通 baseline 使用单点价格：

```text
P_oracle,t
```

USPL 使用价格不确定区间：

```text
P_t ∈ [P_low,t, P_high,t]
```

课程阶段可先用简化公式设定：

```text
P_low,t  = P_oracle,t * (1 - u_t)
P_high,t = P_oracle,t * (1 + u_t)
```

其中 `u_t` 可由人工设定，或由 oracle delay、近期波动率、spot-TWAP deviation 简化生成。

论文阶段应升级为 data-calibrated interval：

```text
u_t = q_alpha(
    historical oracle-market deviation
    | staleness bucket,
      volatility bucket,
      market stress bucket
)
```

含义：根据历史上类似预言机延迟、类似波动状态下的 oracle-market deviation 分布，取高分位数作为当前不确定区间宽度。

### Step 2: Health Factor 区间
由价格区间得到健康因子区间：

```text
HF_min,t = health_factor(P_low,t)
HF_max,t = health_factor(P_high,t)
```

### Step 3: 三分区清算状态
```text
if HF_min,t > 1:
    safe zone
    no liquidation

elif HF_max,t < 1:
    liquidation zone
    normal liquidation allowed

else:
    uncertainty zone
    uncertainty-scaled partial liquidation
```

解释：

- `safe zone`：即使用最低可信价格计算，账户仍安全。
- `liquidation zone`：即使用最高可信价格计算，账户仍危险。
- `uncertainty zone`：账户是否危险取决于预言机价格不确定性，不应直接执行完全清算。

### Step 4: 不确定性缩放的部分清算
定义预言机不确定性强度：

```text
U_t = (P_high,t - P_low,t) / P_oracle,t
```

在 uncertainty zone 中，最大允许清算比例随 `U_t` 动态缩放：

```text
cap_t = clip(cap_max - gamma * U_t, cap_min, cap_max)
```

含义：

- `U_t` 越大：预言机越不确定，允许清算比例越低。
- `U_t` 越小：预言机越确定，清算比例越接近正常清算。
- `cap_min` 避免完全不清算导致坏账失控。
- `cap_max` 对应正常部分清算上限。

可选扩展：

```text
confirm_delay_t = ceil(delta * U_t)
```

即不确定性越大，越需要等待更多 oracle update 才允许 full liquidation。课程阶段优先实现 `cap_t`，不必同时实现确认延迟。

## Baselines
- Baseline 1：Fixed-threshold liquidation
  - 根据单点 oracle price 计算 Health Factor。
  - `HF < 1` 时允许清算。
- Baseline 2：Price filtering
  - 使用 TWAP 或 median price。
  - 主要缓解短时异常价格导致的误清算。
- Baseline 3：Simple safety buffer
  - 在高波动或 oracle 延迟时提前增加安全边界。
  - 主要缓解清算滞后和坏账。
- Proposed：USPL
  - 使用价格区间与 Health Factor 区间。
  - 在 uncertainty zone 中根据 `U_t` 缩放清算比例。

## Stress Scenarios
不需要穷举所有组合，只保留能揭示机制差异的关键场景。

- 正常波动 + 正常预言机
  - sanity check。
- 快速下跌 + 正常预言机
  - 测试正常清算触发。
- 快速下跌 + 预言机延迟
  - 主要观察 bad debt 和 liquidation delay。
- 闪崩/短时异常 + 即时价格
  - 主要观察 false liquidation。
- 闪崩/短时异常 + price filtering
  - 观察 TWAP/median 对误清算的缓解。
- 快速下跌 + price filtering
  - 观察过滤机制在真实下跌时的反应迟缓。
- 快速下跌/闪崩 + USPL
  - 观察不确定性缩放清算比例是否改善 trade-off。

## Evaluation
- 清算安全：
  - Bad debt rate
  - Average bad debt size
  - Maximum bad debt size
- 用户保护：
  - False liquidation rate
  - Average user loss
- 执行效率：
  - Liquidation delay
  - Liquidation count
  - Missed liquidation count
- 机制权衡：
  - Bad debt vs false liquidation trade-off curve
  - User loss vs protocol loss
  - Sensitivity to `u_t`, `gamma`, `cap_min`, `cap_max`

课程阶段可用均值、表格和曲线展示。论文阶段增加显著性检验：

```text
Outcome_i = risk metric under mechanism i
Difference = Outcome_USPL - Outcome_baseline
```

可用方法：

- paired t-test；
- Wilcoxon signed-rank test；
- bootstrap confidence interval；
- panel regression with scenario fixed effects。

更进一步可检验：

```text
Outcome = β0 + β1 USPL + β2 U + β3 USPL × U + controls
```

若 `β3` 显著，说明 USPL 在高 oracle uncertainty 场景下确实有差异化作用。

## Data Strategy
### 课程阶段
- 可用合成价格路径。
- 可人工设定 oracle delay、异常价格和 `u_t`。
- 目标是完成机制概念验证和课程报告展示。
- 必须实现 USPL 的三分区判断和 `cap_t` 动态清算比例。

### Paper 阶段
不能只依赖自造仿真，需要真实数据校准：

- **ETH/USD market price**：分钟级或小时级 ETH 价格。
- **Chainlink ETH/USD oracle updates**：更新时间、更新间隔、链上价格跳变。
- **Aave or Compound liquidation events**：清算事件时间、清算资产、清算金额。
- **Ethereum gas/block data**：gas price、block timestamp、拥堵 proxy。
- **Protocol parameters**：liquidation threshold、liquidation bonus、close factor 等。

真实数据用途：

- 校准价格冲击、oracle delay 和 oracle-market deviation。
- 校准 `u_t` 的分布和高分位区间。
- 选择 2-3 个历史极端行情窗口做 case study。
- 验证模型识别出的高风险窗口是否与真实清算集中时段一致。

## Demo & Deliverables
- Solidity MVP：
  - 抵押、借款、价格更新；
  - Health Factor 计算；
  - Health Factor interval 计算；
  - safe / uncertainty / liquidation zone 判断；
  - uncertainty zone 中的 `cap_t` 部分清算；
  - 清算事件日志。
- Python 仿真：
  - 价格路径生成；
  - oracle delay / anomaly 生成；
  - uncertainty interval 生成；
  - baseline 与 USPL 对照；
  - bad debt、false liquidation、user loss、delay 指标输出。
- Streamlit 展示：
  - 选择价格场景和预言机状态；
  - 设置 `u_t`、`gamma`、`cap_min`、`cap_max`；
  - 展示价格区间、HF 区间、zone 状态和清算事件；
  - 展示不同机制指标对比。
- 报告图表：
  - Oracle-driven liquidation 流程图；
  - 价格区间与 HF 区间示意图；
  - USPL 机制流程图；
  - baseline 对比表；
  - bad debt / false liquidation trade-off 图；
  - 参数敏感性图。

## Blockchain Relevance
- 智能合约是执行主体：抵押、借款、健康因子、清算都由链上规则完成。
- 预言机是核心技术组件：链上清算判断依赖链下价格输入。
- 清算机制体现 DeFi 协议设计：通过阈值、清算比例、激励和外部清算人维护偿付能力。
- 风险具有区块链特征：预言机延迟、价格操纵、MEV、gas 拥堵和合约自动执行都会影响清算结果。
- MVP 能体现区块链技术：合约自动执行、预言机接口、事件日志和可验证状态变化。

## Related Work Positioning
- 不声称首次研究 DeFi 清算风险。
- 不声称首次研究预言机延迟或操纵。
- 不把 TWAP、median、partial liquidation 或 delayed confirmation 包装成创新。
- 差异化定位：
  - 显式研究 bad debt 与 false liquidation 的 trade-off；
  - 将 oracle uncertainty 量化为价格区间并传播到 Health Factor 区间；
  - 提出清算强度随不确定性缩放的低复杂度机制；
  - 用 data-calibrated counterfactual stress testing 分析机制适用边界。

## Boundaries
- 不做价格预测。
- 不做收益率预测。
- 不做交易策略回测。
- 不报告 Sharpe、最大回撤、年化收益等量化策略指标。
- 不把项目写成 AI 风控模型。
- 不训练分类器判断账户是否应该清算。
- 不追求复杂运筹优化或全局最优清算策略。
- 不完整复刻 Aave、Compound 等真实大型协议。
- 不在课程阶段完整模拟真实 mempool、MEV、跨协议清算和多资产抵押组合。
- 课程阶段以简化仿真和 MVP 为主；论文阶段必须补真实数据校准、历史 case、强 baseline 和稳健性验证。
- USPL 只主张在特定 oracle-driven liquidation 场景下改善 trade-off，必须报告失效边界。
