# 论文大纲：基于预言机不确定性的 DeFi 不确定性缩放部分清算机制

## 备选题目
**基于预言机不确定性的 DeFi 不确定性缩放部分清算机制研究**

英文题目可暂定为：

**Uncertainty-Scaled Partial Liquidation for Oracle-Driven DeFi Lending**

或：

**Oracle Price Uncertainty and Partial Liquidation Design in DeFi Lending**

## 一、引言
- DeFi 抵押借贷协议依靠超额抵押和自动清算机制维持协议偿付能力。
- 清算判断依赖预言机价格，但预言机价格可能存在滞后、噪声、短时异常或与真实市场价格偏离。
- 预言机不确定性会带来两类方向相反的风险：
  - **坏账风险 Bad debt risk**：真实价格持续下跌，但预言机价格滞后，导致清算触发过晚。
  - **误清算风险 False liquidation risk**：短时异常价格或预言机短时偏离导致账户被过早清算。
- 固定阈值、TWAP/median 价格过滤、安全缓冲、部分清算、延迟确认等已有机制能够缓解部分问题，但通常没有显式建立“预言机不确定性”和“清算强度”之间的函数关系。
- 研究问题：

> 如何量化预言机价格不确定性，并将其传导到清算决策中，使 DeFi 借贷协议在协议偿付保护和借款人保护之间取得更稳健的平衡？

- 核心思路：

> 估计预言机价格不确定区间，将其映射为 Health Factor 区间，并根据不确定性强度动态缩放最大清算比例。

## 二、相关研究
### 2.1 DeFi 抵押借贷与清算机制
- 已有研究关注 DeFi 清算事件、清算人激励、借款人损失、清算级联和协议偿付风险。
- 本文不重复做大规模清算事件实证，而是聚焦 oracle-driven liquidation 中的机制设计问题。

### 2.2 预言机风险与预言机操纵
- 相关研究包括预言机准确性、价格偏离、操纵攻击、价格滞后和异常恢复。
- 常见防护机制包括 TWAP、median oracle、deviation filter、circuit breaker 和 oracle security module。
- 本文不声称首次研究预言机风险，而是研究预言机不确定性如何影响清算强度。

### 2.3 清算机制设计
- 真实协议和已有研究中存在固定阈值、close factor、拍卖清算、部分清算、延迟确认等机制。
- 本文不把 partial liquidation 或 delayed confirmation 本身作为创新。
- 本文的差异化在于：建立预言机不确定性到清算强度的映射机制。

## 三、问题建模
### 3.1 简化的预言机驱动借贷模型
- 抵押资产：ETH。
- 借出资产：USDC。
- 预言机价格：`P_oracle,t`。
- 市场参考价格：`P_market,t`。
- 抵押数量：`C`。
- 借款数量：`D`。
- 清算阈值：`LT`。

健康因子：

```text
HF_t = C * P_t * LT / D
```

基准清算规则：

```text
if HF_t < 1:
    allow liquidation
```

说明：该简化模型用于抽象 oracle-driven liquidation 的核心逻辑，不完整复刻 Aave、Compound 等真实协议。

### 3.2 失效模式定义
- **坏账**：真实抵押品价值已经不足以覆盖债务，但清算未及时执行。
- **误清算**：基于预言机价格触发清算，但在市场参考价格下账户仍然安全。
- **清算延迟**：账户真实进入危险状态到链上清算发生之间的时间差。

### 3.3 评价目标
- 协议侧目标：
  - 降低坏账率和坏账规模。
- 借款人侧目标：
  - 降低误清算率和用户损失。
- 执行效率目标：
  - 降低过度清算、清算延迟和无效清算次数。

## 四、提出方法：USPL
USPL 全称：

> **Uncertainty-Scaled Partial Liquidation**  
> 不确定性缩放的部分清算机制

### 4.1 预言机价格不确定区间
传统 baseline 使用单点预言机价格：

```text
P_oracle,t
```

USPL 使用价格不确定区间：

```text
P_t ∈ [P_low,t, P_high,t]
```

课程/MVP 阶段可用简化公式：

```text
P_low,t  = P_oracle,t * (1 - u_t)
P_high,t = P_oracle,t * (1 + u_t)
```

论文阶段应使用真实数据校准：

```text
u_t = q_alpha(
    historical oracle-market deviation
    | staleness bucket,
      volatility bucket,
      market stress bucket
)
```

含义：根据历史上类似预言机滞后、类似波动状态下的 oracle-market deviation 分布，取高分位数作为当前价格不确定区间宽度。

可选扩展为非对称区间：

```text
P_low,t  = P_oracle,t * (1 - u_down,t)
P_high,t = P_oracle,t * (1 + u_up,t)
```

当快速下跌和向上修复的预言机误差不对称时，非对称区间可能更合理。

### 4.2 Health Factor 区间
将预言机价格不确定性传导到抵押品估值：

```text
HF_min,t = C * P_low,t  * LT / D
HF_max,t = C * P_high,t * LT / D
```

### 4.3 三分区清算状态
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
- `uncertainty zone`：账户是否危险取决于预言机不确定性，此时不宜直接完全清算。

### 4.4 不确定性到清算强度的函数
定义预言机不确定性强度：

```text
U_t = (P_high,t - P_low,t) / P_oracle,t
```

线性形式：

```text
cap_t = clip(cap_max - gamma * U_t, cap_min, cap_max)
```

候选函数族：

```text
Linear:
cap_t = clip(cap_max - gamma * U_t, cap_min, cap_max)

Exponential:
cap_t = cap_min + (cap_max - cap_min) * exp(-gamma * U_t)

Logistic:
cap_t = cap_min + (cap_max - cap_min) / (1 + exp(gamma * (U_t - U0)))
```

含义：

- 预言机不确定性越高，允许清算比例越低。
- 预言机不确定性越低，清算比例越接近正常清算上限。
- `cap_min` 避免在真实暴跌时完全不清算。
- `cap_max` 与正常 close factor 或部分清算上限对齐。

### 4.5 参数校准原则
不能通过反复调参直到显著来确定机制。

推荐流程：

```text
预先定义函数族
→ 预先定义校准目标
→ 在 calibration period 中选择参数
→ 固定参数
→ 在 test period 或历史 case 中做 out-of-sample 检验
```

可选校准目标：

```text
Loss = w1 * BadDebt
     + w2 * FalseLiquidationLoss
     + w3 * UserLoss
     + w4 * DelayPenalty
```

或者使用约束式目标：

```text
minimize FalseLiquidationLoss
subject to BadDebtRate <= baseline_bad_debt_rate + epsilon
```

## 五、数据与校准
### 5.1 数据来源
- **ETH/USD 市场价格**：
  - 分钟级或小时级市场参考价格。
- **Chainlink ETH/USD 预言机更新记录**：
  - 更新时间、预言机价格、更新间隔、价格跳变。
- **Aave 或 Compound 清算事件**：
  - 清算时间、资产、金额、账户状态信息。
- **Ethereum gas/block 数据**：
  - gas price、block timestamp、拥堵 proxy。
- **协议参数**：
  - liquidation threshold、liquidation bonus、close factor、collateral factor 等。

### 5.2 历史压力窗口
选择 2-3 个历史极端行情窗口：

- ETH 快速下跌窗口；
- 短时闪崩或异常偏离窗口；
- gas 拥堵和清算事件集中窗口。

每个窗口记录：

- 市场价格路径；
- 预言机价格路径；
- 预言机更新间隔；
- gas 拥堵 proxy；
- 真实清算事件。

### 5.3 预言机不确定性校准
估计 oracle-market deviation：

```text
dev_t = |P_oracle,t - P_market,t| / P_market,t
```

按以下状态分组：

- oracle staleness bucket；
- recent volatility bucket；
- market stress bucket。

在每个状态组内，用历史偏离分布的高分位数确定 `u_t`。

## 六、实验设计
### 6.1 机制对照
- 固定阈值清算。
- TWAP 或 median 价格过滤。
- 简单安全缓冲。
- 固定比例部分清算。
- USPL-linear。
- USPL-exponential 或 USPL-logistic。

### 6.2 压力测试场景
- 正常波动 + 正常预言机。
- 快速下跌 + 正常预言机。
- 快速下跌 + 预言机滞后。
- 短时异常价格 + 即时预言机响应。
- 快速下跌 + TWAP。
- 短时异常价格 + TWAP。
- 历史 case 校准的压力窗口。

### 6.3 评价指标
- Bad debt rate。
- Average bad debt size。
- Maximum bad debt size。
- False liquidation rate。
- Average user loss。
- Liquidation delay。
- Liquidation count。
- 不同权重下的 composite loss。

### 6.4 敏感性分析
- `u_t` 分位数水平。
- `gamma`。
- `cap_min`。
- `cap_max`。
- 函数形式：linear / exponential / logistic。
- 初始 Health Factor。
- 预言机更新频率。
- 清算阈值和清算奖励。

## 七、统计检验
### 7.1 配对机制比较
对同一批模拟路径或历史 case 校准窗口，比较：

```text
Difference_i = Metric_USPL,i - Metric_Baseline,i
```

可用检验方法：

- paired t-test；
- Wilcoxon signed-rank test；
- bootstrap confidence interval。

### 7.2 回归检验
可构建面板式回归：

```text
Outcome = β0 + β1 USPL + β2 U + β3 USPL × U + controls + scenario FE + error
```

解释：

- `β1` 表示 USPL 的平均效果。
- `β3` 检验 USPL 在高 oracle uncertainty 场景下是否更有效。

### 7.3 防止调参偏差
- 参数只在 calibration data 中选择。
- 显著性检验只在 test windows 中进行。
- composite loss 的权重需要做敏感性分析。

## 八、预期结果
- 固定阈值机制在正常预言机下表现稳定，但对预言机偏差敏感。
- TWAP/median 可以降低短时异常导致的误清算，但在真实快速下跌中可能增加滞后。
- 简单安全缓冲可以降低坏账，但可能增加借款人损失。
- USPL 预期能够在 uncertainty zone 中降低误清算损失，同时通过 `cap_min` 保留一定坏账控制能力。
- USPL 不应被声称在所有场景下都最优，必须报告失效场景。

## 九、讨论
- 机制可解释性：
  - USPL 是规则型机制，可解释性强，适合智能合约或 keeper 逻辑实现。
- 部署考虑：
  - gas 成本；
  - 预言机数据可用性；
  - `cap_min`、`cap_max`、`gamma` 的治理参数设置；
  - 与现有 close factor、liquidation bonus 的兼容性。
- 安全考虑：
  - 不确定性信号本身可能被操纵；
  - 借款人可能在 uncertainty zone 附近进行策略性操作；
  - 清算比例降低可能影响清算人激励。

## 十、局限与未来工作
- 简化单资产模型，不完整复刻 Aave 或 Compound。
- 对 MEV、mempool 竞争和清算人策略建模有限。
- 历史 case 可能无法覆盖所有极端状态。
- 预言机不确定区间依赖市场参考价格质量。
- 后续可扩展：
  - 多资产抵押；
  - 非对称不确定区间；
  - 拍卖式清算；
  - 更真实的清算人竞争；
  - 智能合约形式化验证。

## 贡献表述
本文不声称发明清算、部分清算、延迟确认或预言机风险分析。

建议贡献表述：

> 本文提出一种不确定性缩放清算机制，首先量化预言机价格不确定性并构造价格区间，再将其传导到 Health Factor 区间，最后在不确定区中根据不确定性强度动态调整最大清算比例。通过真实数据校准的压力测试，本文评估该机制如何影响协议偿付保护与借款人保护之间的权衡。
