# 智能合约产品需求文档 - Polymarket AI 预测金库

## 1. 概述

### 1.1 项目目的

在 Polygon 链上构建一个 USDC 金库智能合约，用于收集用户存款，并允许管理员提取资金用于 Polymarket 预测市场交易。合约支持可升级性、延迟取款和基于份额的透明收益分配。

### 1.2 技术栈

| 组件 | 选型 |
|------|------|
| 语言 | Solidity ^0.8.20 |
| 框架 | Hardhat |
| 链 | Polygon PoS（主网 / Amoy 测试网）|
| 代理模式 | UUPS (EIP-1822) |
| 库 | OpenZeppelin Contracts Upgradeable v5 |
| 代币标准 | ERC-4626（代币化金库）|
| 存款代币 | USDC (Polygon) |

### 1.3 合约地址（Polygon）

| 合约 | 地址 |
|------|------|
| USDC (Polygon PoS) | `0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359` |
| USDC.e (桥接版) | `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174` |

---

## 2. 核心合约

### 2.1 PolyVault（主金库合约）

继承: `ERC4626Upgradeable`, `UUPSUpgradeable`, `AccessControlUpgradeable`, `PausableUpgradeable`, `ReentrancyGuardUpgradeable`

#### 2.1.1 角色

| 角色 | 说明 |
|------|------|
| `DEFAULT_ADMIN_ROLE` | 可授予/撤销角色，升级合约 |
| `STRATEGIST_ROLE` | 可提取资金进行交易，存回利润 |
| `GUARDIAN_ROLE` | 可在紧急情况下暂停/恢复合约 |

#### 2.1.2 状态变量

```solidity
// Delayed withdrawal
uint256 public withdrawalDelay;          // default: 24 hours
mapping(address => WithdrawalRequest) public withdrawalRequests;

struct WithdrawalRequest {
    uint256 shares;
    uint256 requestTimestamp;
    bool pending;
}

// Strategy tracking
uint256 public totalDeposited;           // total USDC ever deposited by users
uint256 public totalWithdrawnByStrategy; // total USDC withdrawn by strategist
uint256 public totalReturnedByStrategy;  // total USDC returned by strategist
uint256 public maxStrategyAllocation;    // max % of vault that strategist can withdraw (e.g. 80%)

// Performance
uint256 public performanceFee;           // fee on profits (e.g. 10%)
address public feeRecipient;
```

#### 2.1.3 核心函数

**存款流程：**

```
用户授权 USDC → 调用 deposit(assets, receiver)
→ 金库按当前汇率铸造对应份额
→ 触发 Deposit 事件
```

| 函数 | 访问权限 | 说明 |
|------|----------|------|
| `deposit(uint256 assets, address receiver)` | 公开 | 存入 USDC，获得金库份额 |
| `mint(uint256 shares, address receiver)` | 公开 | 铸造指定份额，存入所需 USDC |

- 最低存款: 1 USDC (1e6)
- 单笔最高存款: 可配置（默认 100,000 USDC）
- 合约不能处于暂停状态

**延迟取款流程：**

```
用户调用 requestWithdraw(shares)
→ 份额被锁定，创建 WithdrawalRequest
→ 等待 withdrawalDelay（24小时）
→ 用户调用 executeWithdraw()
→ USDC 转出，份额销毁
```

| 函数 | 访问权限 | 说明 |
|------|----------|------|
| `requestWithdraw(uint256 shares)` | 公开 | 发起取款请求，锁定份额 |
| `cancelWithdraw()` | 公开 | 取消待处理的取款请求 |
| `executeWithdraw()` | 公开 | 延迟期过后执行取款 |

- 每个地址同一时间只能有一个待处理请求
- 待取款期间份额被锁定（不可转让）
- 如果金库 USDC 不足（资金已部署到策略中），允许按可用余额进行部分取款

**策略师函数：**

| 函数 | 访问权限 | 说明 |
|------|----------|------|
| `withdrawToStrategy(uint256 amount)` | STRATEGIST_ROLE | 提取 USDC 用于 Polymarket 交易 |
| `depositFromStrategy(uint256 amount)` | STRATEGIST_ROLE | 将 USDC（本金 + 利润）存回金库 |
| `reportProfit(uint256 profit)` | STRATEGIST_ROLE | 报告利润并分配绩效费 |

- `withdrawToStrategy` 受 `maxStrategyAllocation` 百分比上限约束
- 所有策略师操作均会触发详细事件，供链下追踪

**管理员函数：**

| 函数 | 访问权限 | 说明 |
|------|----------|------|
| `setWithdrawalDelay(uint256 delay)` | DEFAULT_ADMIN_ROLE | 更新取款延迟（最短 1 小时，最长 7 天）|
| `setMaxStrategyAllocation(uint256 bps)` | DEFAULT_ADMIN_ROLE | 设置最大分配比例（基点）|
| `setPerformanceFee(uint256 bps)` | DEFAULT_ADMIN_ROLE | 设置绩效费（最高 20%）|
| `setFeeRecipient(address)` | DEFAULT_ADMIN_ROLE | 设置费用接收地址 |
| `pause()` | GUARDIAN_ROLE | 暂停所有存取款操作 |
| `unpause()` | GUARDIAN_ROLE | 恢复合约 |

**升级函数：**

| 函数 | 访问权限 | 说明 |
|------|----------|------|
| `_authorizeUpgrade(address)` | DEFAULT_ADMIN_ROLE | UUPS 升级授权 |

#### 2.1.4 事件

```solidity
event WithdrawalRequested(address indexed user, uint256 shares, uint256 timestamp);
event WithdrawalExecuted(address indexed user, uint256 shares, uint256 assets);
event WithdrawalCancelled(address indexed user, uint256 shares);
event StrategyWithdrawal(address indexed strategist, uint256 amount);
event StrategyDeposit(address indexed strategist, uint256 amount);
event ProfitReported(uint256 profit, uint256 fee);
event PerformanceFeeUpdated(uint256 oldFee, uint256 newFee);
event WithdrawalDelayUpdated(uint256 oldDelay, uint256 newDelay);
```

#### 2.1.5 安全考虑

- 所有状态变更函数加重入锁
- 支持紧急暂停
- USDC 先授权后转账模式（不涉及原生 ETH）
- 防止份额价格操纵：最低存款金额 + 初始化时铸造死份额
- 策略师提取不能超过 `maxStrategyAllocation`
- 取款延迟防止基于闪电贷的份额价格攻击

---

## 3. 部署架构

```
Proxy (ERC1967Proxy)
  └── Implementation (PolyVault)
        ├── ERC4626 (份额记账)
        ├── UUPS (升级逻辑)
        ├── AccessControl (角色管理)
        ├── Pausable (紧急暂停)
        └── ReentrancyGuard (安全防护)
```

### 3.1 初始化参数

```solidity
function initialize(
    address _usdc,              // USDC token address
    address _admin,             // admin address (gets DEFAULT_ADMIN_ROLE)
    address _strategist,        // strategist address (gets STRATEGIST_ROLE)
    address _guardian,          // guardian address (gets GUARDIAN_ROLE)
    address _feeRecipient,      // performance fee recipient
    uint256 _withdrawalDelay,   // initial withdrawal delay in seconds
    uint256 _maxAllocation,     // max strategy allocation in basis points
    uint256 _performanceFee     // performance fee in basis points
) external initializer;
```

---

## 4. 测试要求

| 类别 | 测试用例 |
|------|----------|
| 存款 | 正常存款、最低/最高限额、暂停状态拒绝 |
| 取款 | 请求 → 等待 → 执行、取消、余额不足、延迟未满 |
| 份额 | 正确的份额计算、收益/亏损后的汇率变化 |
| 策略师 | 提取到策略、带利润返还、分配上限 |
| 权限控制 | 基于角色的函数访问、未授权拒绝 |
| 升级 | UUPS 升级流程、存储布局保持 |
| 边界情况 | 零金额、最大 uint256、重入攻击尝试 |

---

## 5. 部署计划

| 阶段 | 网络 | 说明 |
|------|------|------|
| 1 | Hardhat 本地 | 单元测试 + 集成测试 |
| 2 | Polygon Amoy | 测试网部署 + 端到端测试 |
| 3 | Polygon 主网 | 生产环境部署（时间允许的话）|

### 5.1 部署脚本

1. `deploy-vault.ts` — 部署代理 + 实现合约
2. `upgrade-vault.ts` — 通过 UUPS 升级实现合约
3. `setup-roles.ts` — 部署后配置角色
4. `verify.ts` — 在 Polygonscan 上验证合约

---

## 6. 目录结构

```
contracts/
├── src/
│   ├── PolyVault.sol            # Main vault contract
│   └── interfaces/
│       └── IPolyVault.sol       # Vault interface
├── test/
│   ├── PolyVault.test.ts        # Unit tests
│   └── PolyVault.upgrade.test.ts # Upgrade tests
├── scripts/
│   ├── deploy-vault.ts
│   ├── upgrade-vault.ts
│   └── setup-roles.ts
├── hardhat.config.ts
└── package.json
```
