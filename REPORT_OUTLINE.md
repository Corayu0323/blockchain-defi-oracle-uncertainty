# 课程报告大纲：基于预言机不确定性的 DeFi 分区清算机制设计

## 题目
**基于预言机不确定性的 DeFi 抵押借贷分区清算机制设计与风险分析**

## 一、背景与痛点
- DeFi 抵押借贷通过智能合约实现无中心化中介的借贷服务。
- 借款人通常需要超额抵押资产，例如抵押 ETH 借出 USDC。
- 抵押品价格波动会导致账户抵押不足，协议需要通过清算机制避免坏账。
- 清算判断依赖预言机提供的链上价格，但预言机价格可能存在：
  - 更新延迟；
  - 短时异常；
  - 与真实市场价格偏离；
  - 极端行情下反应不足。
- 因此，固定阈值清算机制可能面临两类相反风险：
  - 预言机价格滞后导致清算过晚，产生坏账；
  - 预言机价格短时异常导致清算过早，产生误清算。

本报告核心问题：

> 当预言机价格存在不确定性时，DeFi 借贷协议如何在保护协议偿付能力和保护借款人之间做出更稳健的清算决策？

## 二、相关技术综述
### 2.1 智能合约
- 智能合约是部署在区块链上的自动执行程序。
- 在 DeFi 借贷中，智能合约负责：
  - 记录抵押资产；
  - 记录借款余额；
  - 计算账户健康因子；
  - 判断是否允许清算；
  - 执行资产转移和事件记录。

### 2.2 DeFi 抵押借贷机制
- 借款人抵押资产并借出稳定币。
- 协议通过超额抵押降低信用风险。
- 当抵押品价值下降时，账户可能进入清算状态。

### 2.3 预言机 Oracle
- 区块链本身无法直接获取链下价格。
- 预言机负责将 ETH/USD 等链下价格输入链上合约。
- 预言机风险包括：
  - 价格更新延迟；
  - 数据源异常；
  - 短时价格操纵；
  - 极端行情下价格偏离。

### 2.4 健康因子 Health Factor
- 健康因子用于判断账户是否安全。

```text
Health Factor = 抵押品价值 × 清算阈值 / 借款价值
```

- `Health Factor > 1`：账户安全。
- `Health Factor < 1`：账户可被清算。

### 2.5 清算机制 Liquidation
- 当账户健康因子低于清算边界时，清算人可以替借款人偿还部分债务，并获得折价抵押品。
- 清算机制通过经济激励维护协议偿付能力。
- 但清算过晚会产生坏账，清算过早会损害借款人。

## 三、方案设计
### 3.1 系统目标
设计一个简化的 DeFi 抵押借贷清算系统，用于展示：

- 预言机价格如何影响健康因子计算；
- 固定阈值清算机制在预言机不确定性下的风险；
- 如何通过预言机不确定性区间和分区清算机制改善清算决策。

### 3.2 系统参与方
- 借款人 Borrower：抵押 ETH，借出 USDC。
- 预言机 Oracle：向合约提供 ETH/USD 价格。
- 智能合约 Smart Contract：计算健康因子并执行清算规则。
- 清算人 Liquidator：在账户可清算时偿还债务并获得折价抵押品。

### 3.3 基准机制：固定阈值清算
基准机制使用单点预言机价格：

```text
P_oracle,t
```

合约根据该价格计算健康因子：

```text
if Health Factor < 1:
    allow liquidation
else:
    no liquidation
```

该 baseline 用于抽象 oracle-driven liquidation 的核心逻辑，不代表完整复刻真实 DeFi 协议。

### 3.4 对照机制
- 价格过滤机制：
  - 使用 TWAP 或 median price 减少短时异常价格影响。
  - 优点：降低误清算风险。
  - 缺点：真实快速下跌时可能反应变慢。
- 简单安全缓冲机制：
  - 在高波动或预言机延迟时提前增加安全边界。
  - 优点：降低坏账风险。
  - 缺点：可能增加提前清算和用户损失。

### 3.5 Proposed：USPL 不确定性缩放部分清算机制
USPL 的核心思想：

> 不把预言机价格看作完全确定的单点，而是构造价格不确定区间，并让清算强度随不确定性大小动态变化。

第一步：构造价格区间。

```text
P_t ∈ [P_low,t, P_high,t]
```

课程阶段可用简化公式：

```text
P_low,t  = P_oracle,t × (1 - u_t)
P_high,t = P_oracle,t × (1 + u_t)
```

其中 `u_t` 表示预言机价格不确定性宽度。

第二步：计算健康因子区间。

```text
HF_min,t = health_factor(P_low,t)
HF_max,t = health_factor(P_high,t)
```

第三步：划分清算状态。

```text
if HF_min,t > 1:
    safe zone
    no liquidation

elif HF_max,t < 1:
    liquidation zone
    normal liquidation

else:
    uncertainty zone
    partial liquidation with uncertainty-scaled cap
```

第四步：在不确定区中动态限制最大清算比例。

```text
U_t = (P_high,t - P_low,t) / P_oracle,t
cap_t = clip(cap_max - gamma × U_t, cap_min, cap_max)
```

含义：

- 预言机越不确定，允许清算比例越低；
- 预言机越确定，清算比例越接近正常清算；
- `cap_min` 避免完全不清算导致坏账扩大；
- `cap_max` 对应正常部分清算上限。

### 3.6 系统流程
```text
Borrower deposits ETH
        ↓
Borrower borrows USDC
        ↓
Oracle updates ETH/USD price
        ↓
Contract constructs price interval
        ↓
Contract computes Health Factor interval
        ↓
Contract determines safe / uncertainty / liquidation zone
        ↓
Liquidator executes no liquidation / capped partial liquidation / normal liquidation
```

## 四、风险与安全分析
### 4.1 市场价格风险
- ETH 价格快速下跌会使抵押品价值下降。
- 如果清算触发滞后，协议可能产生坏账。

### 4.2 预言机风险
- 预言机更新延迟会导致链上价格高于真实市场价格。
- 短时异常价格可能导致账户被错误清算。
- 价格过滤机制可以缓解短时异常，但可能降低反应速度。

### 4.3 清算机制风险
- 固定阈值清算对预言机价格高度敏感。
- 安全缓冲可能保护协议，但会增加用户损失。
- USPL 在不确定区中限制清算比例，可以减少完全误清算，但若参数设置过保守，也可能增加坏账风险。

### 4.4 链上执行风险
- gas 拥堵可能导致清算交易延迟。
- 清算人竞争可能引发抢跑或 MEV。
- 合约逻辑错误可能导致错误清算或资金损失。

## 五、价值评估与可行性
### 5.1 课程价值
- 体现区块链技术视角：
  - 智能合约自动执行；
  - 预言机链下数据输入；
  - 链上健康因子计算；
  - 自动清算与事件记录。
- 不是单纯使用链上数据做预测，而是研究清算机制本身。

### 5.2 机制价值
- 将预言机不确定性显式纳入清算决策。
- 将二元清算判断扩展为分区清算。
- 在不确定区中通过动态清算比例平衡坏账与误清算。

### 5.3 MVP 可行性
- Solidity 合约：
  - 抵押；
  - 借款；
  - 预言机价格更新；
  - 健康因子区间计算；
  - 分区判断；
  - 不确定区部分清算；
  - 事件日志。
- Python 仿真：
  - 正常波动、快速下跌、闪崩场景；
  - 预言机延迟和异常价格；
  - baseline 与 USPL 对比；
  - 输出坏账、误清算、用户损失和清算延迟。
- Streamlit 展示：
  - 选择价格场景；
  - 设置 `u_t`、`gamma`、`cap_min`、`cap_max`；
  - 展示价格区间、健康因子区间和清算事件。

### 5.4 评价指标
- Bad debt rate。
- Average bad debt size。
- False liquidation rate。
- Average user loss。
- Liquidation delay。
- Liquidation count。

## 六、局限与展望
### 6.1 局限
- 本报告使用简化单资产抵押模型，不完整复刻 Aave、Compound 等真实协议。
- 课程阶段可使用合成价格路径和人工设定的不确定区间，真实数据支撑有限。
- 未完整模拟多资产抵押、动态利率、真实清算人竞争、MEV、mempool 和跨协议联动。
- USPL 参数如 `u_t`、`gamma`、`cap_min`、`cap_max` 需要进一步校准。
- 不确定区中限制清算比例可能降低误清算损失，但也可能在持续暴跌时增加坏账。

### 6.2 展望
- 使用真实 Chainlink 预言机更新记录校准价格不确定区间。
- 使用 Aave 或 Compound 清算事件验证高风险窗口。
- 引入真实 ETH 极端行情 case 进行反事实压力测试。
- 扩展到多资产抵押和不同清算参数。
- 对 USPL 与固定阈值、TWAP、median、简单安全缓冲做更系统的统计检验。
