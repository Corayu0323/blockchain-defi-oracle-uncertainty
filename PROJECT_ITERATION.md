# 项目版本迭代记录：预言机不确定性下 DeFi 清算机制研究

## 0. 项目定位

当前项目从一个区块链课程报告原型，逐步升级为一个更完整的机制研究框架：

> 在 DeFi 抵押借贷清算场景中，将预言机价格不确定性显式传导到健康因子区间和清算比例调节，并通过真实数据、可解释参数校准、多目标评价和链上可部署性设计，分析协议坏账风险、用户误清算风险与链上执行成本之间的权衡。

核心定位不应是“重新发明清算协议”，而应是：

> oracle uncertainty-aware close factor framework。

即：在已有 Aave/Compound 类清算机制基础上，研究预言机不确定性如何影响清算强度，并提出可解释、可评估、可部署的改进框架。

## 1. 已完成版本

### V0：合成路径机制原型

已完成内容：

- 用 Python 构造 normal、drawdown、flash crash 三类合成价格路径。
- 实现 fixed、TWAP、buffer、USPL 四种机制对比。
- 将单点预言机价格扩展为价格区间。
- 将价格区间传导到 Health Factor 区间。
- 在不确定区中使用 `cap_t = clip(cap_max - gamma * U_t, cap_min, cap_max)` 调节清算比例。
- 输出坏账、误清算损失、总用户损失、清算延迟、清算次数等指标。
- 生成 Word 版结课报告与图表。

当前价值：

- 能说明机制逻辑；
- 有基本可复现实验；
- 能支撑课程报告。

当前不足：

- 主要依赖合成路径；
- `gamma`、`cap_min`、`cap_max` 仍以人工设定和敏感性分析为主；
- 缺少真实清算事件验证；
- 综合评价体系还不够强；
- 链上部署部分仍偏概念化。

### V1：定位升级版报告

已完成内容：

- 题目从“分区清算机制设计”升级为“清算机制的风险权衡与改进研究”。
- 摘要重写，不再把三区域划分本身作为主要创新。
- 明确本文改进点：
  - 动态预言机不确定性宽度；
  - 价格区间到健康因子区间；
  - 边界不确定状态下的清算比例缩放；
  - 多机制对照与参数敏感性。
- 删除“课程级”等削弱正式性的表述。
- 新增“本文改进点与已有机制的区别”。

当前价值：

- 论文叙事更稳；
- 创新定位更准确；
- 避免过度声称“分区”是原创。

## 2. 用户思考过程沉淀

本项目的创新不是突然从模型出发，而是遵循了一条可复用的研究思考路径：

1. **先确定具体场景**
   - 场景：DeFi 抵押借贷清算。
   - 机制冲突：协议需要及时清算以避免坏账，但预言机异常又可能导致用户误清算。

2. **用建模中的常见思想重写关键变量**
   - 常见思想：从点估计/点预测转向区间估计。
   - 场景化改造：将单点 oracle price 改为 oracle price interval。

3. **将变量改造传导到机制状态**
   - 价格区间传导为 Health Factor 区间。
   - 健康因子区间自然产生三类状态：
     - 明确安全；
     - 明确危险；
     - 边界不确定。

4. **在新状态上做机制改进**
   - 不确定区不再二元判断是否清算；
   - 改为根据预言机不确定性调节最大清算比例。

5. **发现新机制带来的现实约束**
   - 连续计算 `U_t`、滚动波动、分位数和动态参数在链上成本高；
   - 参数更新会带来治理、审计和清算人激励问题。

6. **提出二次改进**
   - 将连续 USPL 函数离线校准；
   - 压缩为链上可执行、可审计的分段 close factor 曲线；
   - 链上只做查表或低阶线性插值。

7. **建立可量化评价体系**
   - 不只比较单个指标；
   - 用协议侧风险、用户侧损失、延迟、Expected Shortfall、Pareto frontier 和综合 RiskScore 表达多目标权衡。

可复用范式：

> 场景机制冲突 -> 关键变量重表达 -> 新状态识别 -> 场景约束下的小机制改进 -> 真实数据验证 -> 多目标评价 -> 可部署性分析。

## 3. 后续目标版本

### V2：真实数据升级

目标：

- 从合成路径升级为 Chainlink + Aave 真实数据。

数据设计：

- Chainlink ETH/USD historical rounds：
  - `roundId`
  - `answer`
  - `startedAt`
  - `updatedAt`
  - `answeredInRound`
  - round interval / staleness
- Aave V3 liquidation events：
  - liquidation timestamp
  - collateral asset
  - debt asset
  - user
  - debtToCover
  - liquidatedCollateralAmount
  - liquidator
- 市场参考价格：
  - 可先用 CoinGecko/CEX 小时级价格；
  - 在报告中说明其是 reference market price，不等于完全真实价格。

推荐最小范围：

- Ethereum mainnet；
- ETH/USDC 或 WETH/USDC；
- 2-3 个极端行情窗口；
- 事件窗口：清算前后 `±1h`、`±6h`、`±24h`。

验收标准：

- 至少生成一张真实 oracle price vs reference market price 路径图；
- 至少生成一张 Aave liquidation event overlay 图；
- 能提取 oracle staleness、oracle-market deviation、recent volatility。

### V3：可解释自动调参机制

目标：

- 从人工设定 `gamma` 升级为损失函数驱动的可解释参数校准。

建议目标函数：

```text
Loss(theta)
  = lambda_B * BadDebt
  + lambda_F * FalseLiquidationLoss
  + lambda_U * UserLoss
  + lambda_D * DelayPenalty
  + lambda_C * ComputationCost
```

其中：

```text
theta = (gamma, cap_min, cap_max, base_u, max_u)
```

最小可行调参：

- 主调 `gamma`；
- 次调 `cap_min`；
- `cap_max` 可参考现有协议 close factor 上限；
- `base_u`、`max_u` 用历史 oracle uncertainty 分位数确定。

解释逻辑：

- `lambda_B` 越大，协议越重视坏账风险，应降低 `gamma` 或提高 `cap_min`；
- `lambda_F` 越大，协议越重视用户误清算风险，应提高 `gamma` 或降低边界状态 close factor；
- `cap_min` 是防止清算不足的安全下界；
- `cap_max` 是限制用户冲击的清算强度上界。

报告表达：

- 不使用黑盒优化作为主线；
- 使用“目标函数 + 边际损失权衡 + 参数敏感性”作为数学支撑；
- 可以用 train/calibration window 校准，在 holdout stress window 评估。

### V4：评价体系升级

目标：

- 建立一眼能看出 fixed、TWAP、buffer、USPL 谁优谁劣的评价体系。

单项指标：

- Max Bad Debt；
- Expected Shortfall of BadDebt；
- False Liquidation Loss；
- Total User Loss；
- Liquidation Delay；
- Liquidation Count；
- Computation / Update Cost。

综合指标：

```text
RiskScore
  = w_B * normalized_ES_BadDebt
  + w_F * normalized_FalseLoss
  + w_D * normalized_Delay
  + w_C * normalized_Cost
```

图表建议：

- 归一化柱状图：展示每种机制各维度风险；
- 雷达图：展示协议风险、用户风险、延迟、成本；
- Pareto frontier：横轴协议侧风险，纵轴用户侧损失；
- 权重敏感性图：展示不同 `lambda_B / lambda_F` 下最优机制是否变化。

重要表述：

> USPL 不需要在所有单项指标上第一。只要它在协议风险和用户损失之间形成更优或更可解释的 Pareto trade-off，就能构成有效机制改进。

### V5：链上可部署性与计算优化

目标：

- 不使用“链下算 score、链上读三档”作为主方案；
- 改为“离线校准 + 链上可验证分段 close factor 曲线”。

主方案：

```text
U_t in [0, U_max]

cap(U_t) =
  c_0                         if U_t in [0, q_1)
  c_1 - s_1(U_t - q_1)         if U_t in [q_1, q_2)
  c_2 - s_2(U_t - q_2)         if U_t in [q_2, q_3)
  cap_min                     if U_t >= q_3
```

参数来源：

- `q_1, q_2, q_3` 来自历史 oracle uncertainty 分位数；
- `c_i, s_i` 来自目标函数校准；
- `cap_min`、`cap_max` 受治理参数边界约束。

链上实现思想：

- 链上不滚动计算历史波动；
- 链上不求解优化问题；
- 链上只读取当前 `U_t` 或其可验证输入，并执行查表或低阶线性插值；
- 参数表包含版本号、有效期、资产对、分位点、cap 值、最大单次更新幅度和 emergency freeze flag。

优势：

- 保留连续机制的可解释形状；
- 降低链上计算和存储成本；
- 便于审计和治理；
- 比 low/medium/high 三档更强，也比完全链上动态优化更可部署。

## 4. 需要补进论文的关键章节

建议新增或强化以下章节：

1. **真实数据与事件构造**
   - 说明 Chainlink、Aave、reference market price 的来源和对齐方法。

2. **可解释参数校准**
   - 给出损失函数；
   - 解释 `gamma`、`cap_min`、`cap_max` 的经济含义；
   - 做权重敏感性。

3. **综合评价体系**
   - 引入 Expected Shortfall、RiskScore、Pareto frontier。

4. **与现有协议机制的区别**
   - 对标 Aave close factor；
   - 说明 Aave 已有分档 close factor，但主要由健康因子和头寸条件驱动；
   - 本文进一步引入 oracle uncertainty-aware close factor。

5. **为什么现实协议没有直接采用**
   - 审计成本；
   - 治理复杂度；
   - 清算人激励；
   - oracle uncertainty 的客观定义困难；
   - 链上计算与存储成本；
   - 动态参数引入新的信任假设。

6. **链上可部署性优化**
   - 离线校准；
   - 分段 close factor 曲线；
   - 参数表版本化；
   - 参数边界约束；
   - 事件日志可审计。

## 5. 当前优先级

建议优先级：

1. V2 真实数据升级；
2. V3 目标函数与自动调参；
3. V4 评价体系；
4. V5 可部署性优化；
5. 最后再统一重写报告。

不建议优先做：

- 大规模多资产、多协议扩展；
- 黑盒机器学习调参；
- 复杂清算人博弈模型；
- 完整主网级 Solidity 实现。

这些方向会显著增加工作量，但不一定提高当前结课报告或简历项目的单位收益。

## 6. 一句话创新总结

> 本项目的创新不是简单提出“分区清算”，而是在 DeFi 清算这一具体场景中，将统计建模中的区间估计思想引入预言机价格风险表达，并进一步把价格不确定性传导到健康因子区间和清算比例调节；随后针对链上计算和治理约束，将连续调节机制压缩为可验证的分段 close factor 曲线，形成一套兼顾风险控制、解释性、评价体系和可部署性的机制改进框架。
