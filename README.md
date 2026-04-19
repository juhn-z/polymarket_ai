# Polymarket AI 预测金库

> 由 GPT-5.4 驱动的 Polymarket 比特币预测市场自动化交易金库

一个完整的 AI 驱动 DeFi 应用：用户将 USDC 存入链上金库，AI 引擎每日扫描 Polymarket 上的 BTC 价格预测市场、聚合多源数据进行预测、自动执行交易并监控止盈止损，收益按份额比例分配给所有存款人。

---

## 目录

- [项目概览](#项目概览)
- [系统架构](#系统架构)
- [资金与数据流](#资金与数据流)
- [仓库结构](#仓库结构)
- [智能合约层](#智能合约层-contracts)
- [后端层](#后端层-backend计划中)
- [前端层](#前端层-frontend计划中)
- [快速开始](#快速开始)
- [部署](#部署)
- [开发路线](#开发路线)

---

## 项目概览

| 维度 | 说明 |
|------|------|
| 链 | Polygon PoS（主网 Chain ID 137 / Amoy 测试网 80002）|
| 存款代币 | USDC（6 decimals）|
| 金库代币 | pvUSDC（ERC-4626 份额）|
| 交易标的 | Polymarket "Bitcoin above ___ on {date}" 系列预测市场 |
| AI 模型 | OpenAI GPT-5.4 |
| 升级模式 | UUPS (EIP-1822) |

**核心价值主张：** 普通用户不需要懂技术分析、链上数据或 Polymarket 操作，只要把 USDC 存入金库，就能跟随 AI 的预测策略获取收益；金库通过份额机制保证按比例公平分配盈亏。

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户 (浏览器)                              │
│              MetaMask / WalletConnect / Coinbase                  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
            ┌──────────────┴──────────────┐
            │                             │
            ▼                             ▼
┌─────────────────────────┐   ┌──────────────────────────┐
│  前端 Next.js 14         │   │  Polygon 链              │
│  ─────────────────────   │   │  ──────────────────────  │
│  • 仪表板 / 金库          │◄─►│  PolyVault (UUPS)        │
│  • 预测历史 / 排行榜      │   │  • ERC-4626 + USDC       │
│  • RainbowKit + wagmi    │   │  • 延迟取款机制           │
│  • TanStack Query        │   │  • 角色管理 (Admin/      │
│                          │   │    Strategist/Guardian)  │
└────────────┬─────────────┘   └────────────▲─────────────┘
             │                              │
             │ REST                         │ withdrawToStrategy /
             │                              │ depositFromStrategy
             ▼                              │
┌─────────────────────────────────────────────────────────────────┐
│              后端 FastAPI 服务（Python 3.11+）                    │
│  ─────────────────────────────────────────────────────────────  │
│   ┌──────────┐  ┌────────────┐  ┌────────────┐  ┌──────────┐   │
│   │ Scanner  │─▶│ Aggregator │─▶│ Predictor  │─▶│Generator │   │
│   │ (Gamma)  │  │ (多源数据)  │  │ (GPT-5.4)  │  │ (Kelly)  │   │
│   └──────────┘  └────────────┘  └────────────┘  └────┬─────┘   │
│                                                       │         │
│   ┌──────────┐  ┌────────────┐                        ▼         │
│   │ Monitor  │◄─│  Executor  │◄────────────────── Strategy      │
│   │ (止盈止损)│  │ (CLOB API) │                                 │
│   └──────────┘  └─────┬──────┘                                  │
│                       │                                          │
│   ┌────────────────────────────────────────────────┐            │
│   │  PostgreSQL (markets / predictions / trades)   │            │
│   └────────────────────────────────────────────────┘            │
└──────────────────────────┬──────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
   ┌─────────┐      ┌─────────────┐      ┌────────┐
   │Polymarket│      │  Binance    │      │OpenAI  │
   │CLOB+Gamma│      │  K线/资金费 │      │GPT-5.4 │
   └─────────┘      └─────────────┘      └────────┘
        ▲                  ▲
        │                  │
   ┌────┴────┐    ┌────────┴────────┐
   │  新闻   │    │  链上数据        │
   │NewsAPI  │    │ Glassnode/      │
   │CryptoPanic│  │ CryptoQuant     │
   └─────────┘    └─────────────────┘
```

---

## 资金与数据流

**每日交易循环（典型时序）：**

```
00:00 UTC  Scanner 扫描 Polymarket → 选出今日 BTC 预测市场
01:00 UTC  Aggregator 聚合 K线/技术指标/情绪/新闻/链上数据
02:00 UTC  Predictor 调 GPT-5.4 → 输出预测概率 + 置信度
02:30 UTC  Generator 计算边际 (edge) + Kelly 仓位 → 生成 Strategy
03:00 UTC  Executor 调 vault.withdrawToStrategy(amount)
           → USDC 转入策略钱包 → CLOB API 下限价单
持续      Monitor 通过 WebSocket 监控持仓
           → 触及止盈/止损/临近结算 → 自动平仓
结算后    Executor 调 vault.depositFromStrategy(amount)
           → 利润自动按 performanceFee (10%) 分配给 feeRecipient
           → 剩余收益反映在份额价格 (pvUSDC) 上涨
```

**用户资金循环：**

```
用户 USDC ──approve──▶ PolyVault ──deposit──▶ 铸造 pvUSDC
                                                    │
                                                    ▼
                       (份额价格随策略盈亏变化)
                                                    │
                                                    ▼
用户 ──requestWithdraw(shares)──▶ 锁定份额 → 等待 24h
                                                    │
                                                    ▼
用户 ──executeWithdraw()──▶ 销毁份额 → 收回 USDC（含收益/亏损）
```

---

## 仓库结构

```
polymarket_ai/
├── contracts/             # ✅ 已实现 — Hardhat + Solidity
│   ├── src/
│   │   ├── PolyVault.sol         # 主金库合约
│   │   ├── interfaces/IPolyVault.sol
│   │   └── mocks/MockUSDC.sol    # 测试用
│   ├── scripts/
│   │   ├── deploy-vault.ts       # UUPS 代理部署
│   │   └── upgrade-vault.ts      # 实现合约升级
│   ├── test/PolyVault.test.ts
│   └── hardhat.config.ts
│
├── docs/                  # PRD 文档（中文）
│   ├── PRD-smart-contract.md
│   ├── PRD-backend.md
│   └── PRD-frontend.md
│
├── backend/               # ⏳ 待实现 — Python FastAPI
└── frontend/              # ⏳ 待实现 — Next.js 14
```

---

## 智能合约层 (`contracts/`)

**已完整实现并通过测试。**

### 合约：PolyVault

ERC-4626 标准的 USDC 金库，部署在 UUPS 代理之后。

| 维度 | 配置 |
|------|------|
| Solidity | `^0.8.28`，optimizer 200 runs，evm `cancun` |
| 基础库 | OpenZeppelin Contracts Upgradeable v5 |
| 继承 | `ERC4626Upgradeable` + `UUPSUpgradeable` + `AccessControlUpgradeable` + `PausableUpgradeable` + `ReentrancyGuardTransient` |
| 名称 / 符号 | `PolyVault USDC` / `pvUSDC` |

### 三大角色

| 角色 | 权限 |
|------|------|
| `DEFAULT_ADMIN_ROLE` | 调整参数、授权 UUPS 升级 |
| `STRATEGIST_ROLE` | `withdrawToStrategy` / `depositFromStrategy` |
| `GUARDIAN_ROLE` | `pause` / `unpause` 紧急暂停 |

### 关键设计

1. **延迟取款机制（防闪电贷攻击）**
   - 直接 `withdraw()` / `redeem()` **被禁用**（强制 revert）
   - 用户必须走三步：`requestWithdraw(shares)` → 等待 `withdrawalDelay`（默认 24h）→ `executeWithdraw()`
   - 待取款期间份额被托管在合约自身

2. **策略资金追踪**
   - `totalAssets() = vault USDC 余额 + strategyDebt`
   - 策略师提取受 `maxStrategyAllocation`（基点）上限约束
   - `depositFromStrategy` 检测到利润时自动扣除 `performanceFee`（最高 20%）

3. **流动性不足时的部分取款**
   - 若执行取款时金库 USDC 不足（已部署到 Polymarket），自动按可用余额比例支付
   - 剩余份额返还给用户，可稍后再次申请

### 默认参数

| 参数 | 默认值 | 上下限 |
|------|--------|--------|
| `withdrawalDelay` | 24 小时 | 1 小时 ~ 7 天 |
| `maxStrategyAllocation` | 8000 bps (80%) | ≤ 10000 bps |
| `performanceFee` | 1000 bps (10%) | ≤ 2000 bps |
| `minDeposit` | 1 USDC | — |
| `maxDeposit` | 100,000 USDC | — |

详见 `docs/PRD-smart-contract.md` 与 `CLAUDE.md`。

---

## 后端层 (`backend/`，计划中)

按 `docs/PRD-backend.md` 规划，由 6 个核心服务组成：

| 模块 | 职责 | 调度 |
|------|------|------|
| **Market Scanner** | 通过 Polymarket Gamma API 扫描 BTC 预测事件，筛选概率 35%-65% 且流动性最高的市场 | 每日 00:00 UTC |
| **Data Aggregator** | 收集 Binance K线、RSI/MACD/布林带、恐慌贪婪指数、资金费率、新闻、链上数据 | 每日 01:00 UTC |
| **AI Predictor** | 调用 GPT-5.4，输入 `MarketDataBundle`，输出概率/置信度/方向/推理 | 每日 02:00 UTC |
| **Strategy Generator** | 计算 edge = AI概率 − 市场价格，用简化 Kelly 决定仓位（上限 10%），设置止盈/止损 | 每日 02:30 UTC |
| **Trade Executor** | 调 `vault.withdrawToStrategy` 取资金，通过 Polymarket CLOB API 下限价单 | 每日 03:00 UTC |
| **Position Monitor** | WebSocket 实时监控价格，触发止盈 / 止损 / 临近结算（30min）自动平仓 | 持续运行 |

### 技术栈

- Python 3.11+ / FastAPI
- PostgreSQL + SQLAlchemy + Alembic
- APScheduler（或 Celery + Redis）
- `py-clob-client` 官方 SDK
- Docker + Docker Compose

### 数据模型

`Market` → `Prediction` → `Strategy` → `Trade`，附 `VaultSnapshot`（每小时记录 TVL / 份额价格）和 `User`（钱包地址）。

### 主要 REST 接口

```
GET  /api/v1/markets/today           # 今日选定市场
GET  /api/v1/predictions/today       # 今日 AI 预测（含完整推理）
GET  /api/v1/predictions/history     # 历史预测分页
GET  /api/v1/strategies/active       # 活跃策略
GET  /api/v1/trades/history          # 交易记录
GET  /api/v1/stats/overview          # 胜率 / 总盈亏 / TVL
GET  /api/v1/stats/leaderboard       # 存款人排行
GET  /api/v1/stats/daily             # 每日盈亏图表
POST /api/v1/system/pause            # 管理员暂停交易
```

### 风控参数（默认）

| 参数 | 值 | 说明 |
|------|-----|------|
| `min_edge` | 0.05 | 边际 < 5% 则跳过 |
| `min_confidence` | 0.6 | AI 置信度 < 60% 则跳过 |
| `max_position_pct` | 0.10 | 单笔最多动用 10% 金库 |
| `take_profit_factor` | 0.7 | 止盈 = 边际 × 70% |
| `stop_loss_factor` | 0.5 | 止损 = 边际 × 50% |
| `pre_resolution_minutes` | 30 | 结算前 30 分钟强制平仓 |

完整规格见 `docs/PRD-backend.md`。

---

## 前端层 (`frontend/`，计划中)

按 `docs/PRD-frontend.md` 规划。

### 技术栈

| 层 | 选型 |
|----|------|
| 框架 | Next.js 14 (App Router) + TypeScript |
| 样式 | Tailwind CSS + shadcn/ui |
| Web3 | wagmi v2 + viem + RainbowKit |
| 状态 | TanStack Query（服务端）+ Zustand（客户端）|
| 图表 / 动画 | Recharts + Framer Motion |
| 包管理 | pnpm |

### 页面结构

| 路径 | 用途 |
|------|------|
| `/` | 仪表板（TVL / 胜率 / 总盈亏 / 份额价格 + 今日预测 + 30 天 PnL）|
| `/vault` | 存款 / 取款 / 待处理取款（含倒计时）/ 份额价格历史 |
| `/predictions` | 历史预测列表（可筛选盈利/亏损）|
| `/predictions/[id]` | 单条预测详情（完整 AI 推理 + 数据快照 + 价格图）|
| `/leaderboard` | 存款人排行榜（按存款额 / 利润 / 利润率）|
| `/admin` | 管理员面板（手动触发扫描、暂停交易、查看日志）|

### Web3 交互

读取：`vault.totalAssets()` / `convertToShares` / `convertToAssets` / `balanceOf` / `withdrawalRequests`
写入：`USDC.approve` / `vault.deposit` / `vault.requestWithdraw` / `vault.cancelWithdraw` / `vault.executeWithdraw`

### 实时数据

- TVL & 份额价格：30s 轮询
- 今日策略状态：15s 轮询（活跃时）
- BTC 行情：Binance WebSocket

完整布局、组件、设计系统（配色、字体、断点）见 `docs/PRD-frontend.md`。

---

## 快速开始

目前只有 `contracts/` 子项目可运行。

### 智能合约

```bash
cd contracts
npm install

# 编译并生成 typechain
npm run compile

# 运行测试
npm test
npm run test:coverage

# 本地开发节点
npm run node
# 在另一个终端：
npm run deploy:local
```

### 环境变量（`contracts/.env`）

```env
PRIVATE_KEY=部署账户私钥
POLYGON_RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/your_key
AMOY_RPC_URL=https://rpc-amoy.polygon.technology
POLYGONSCAN_API_KEY=用于合约验证
```

### 后端 / 前端

待实现。请参考 `docs/PRD-backend.md` 和 `docs/PRD-frontend.md` 中的目录结构与配置文件示例。

---

## 部署

| 阶段 | 网络 | 命令 |
|------|------|------|
| 1. 本地 | Hardhat | `npm run deploy:local` |
| 2. 测试网 | Polygon Amoy (80002) | `USDC_ADDRESS=0x... npm run deploy:amoy` |
| 3. 主网 | Polygon PoS (137) | `USDC_ADDRESS=0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359 npm run deploy:polygon` |

升级（仅 admin）：

```bash
VAULT_PROXY_ADDRESS=0x... npx hardhat run scripts/upgrade-vault.ts --network polygon
```

### Polygon USDC 地址

| 代币 | 地址 |
|------|------|
| USDC（原生）| `0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359` |
| USDC.e（桥接）| `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174` |

---

## 开发路线

| 阶段 | 状态 | 内容 |
|------|------|------|
| Phase 1 | ✅ 已完成 | PolyVault 合约 + 单元测试 |
| Phase 2 | 🚧 进行中 | Polygon Amoy 测试网部署与端到端验证 |
| Phase 3 | ⏳ 待启动 | 后端 FastAPI 服务（按 PRD-backend）|
| Phase 4 | ⏳ 待启动 | 前端 Next.js 仪表板（按 PRD-frontend）|
| Phase 5 | ⏳ 待启动 | Polygon 主网部署 + 公开 Beta |

---

## 文档索引

- [`CLAUDE.md`](./CLAUDE.md) — Claude Code 工作时的项目导航
- [`docs/PRD-smart-contract.md`](./docs/PRD-smart-contract.md) — 合约规格
- [`docs/PRD-backend.md`](./docs/PRD-backend.md) — 后端规格
- [`docs/PRD-frontend.md`](./docs/PRD-frontend.md) — 前端规格

---

## License

MIT
