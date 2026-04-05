# 前端产品需求文档 - Polymarket AI 预测仪表板

## 1. 概述

### 1.1 项目目的

构建一个现代化、响应式的 Web 仪表板，用于 Polymarket AI 预测金库。用户可以连接钱包、存取 USDC、查看每日 AI 预测、追踪策略表现，并查看实时统计数据（包括排行榜和胜率）。

### 1.2 技术栈

| 组件 | 选型 |
|------|------|
| 框架 | Next.js 14 (App Router) |
| 语言 | TypeScript |
| 样式 | Tailwind CSS + shadcn/ui |
| Web3 | wagmi v2 + viem |
| 钱包 | RainbowKit |
| 状态管理 | TanStack Query（服务端状态）+ Zustand（客户端状态）|
| 图表 | Recharts |
| 动画 | Framer Motion |
| 图标 | Lucide React |
| 包管理器 | pnpm |

### 1.3 目标链

| 网络 | Chain ID | RPC |
|------|----------|-----|
| Polygon PoS | 137 | Alchemy / Infura |
| Polygon Amoy（测试网）| 80002 | Alchemy |

---

## 2. 页面结构

```
/                        → 首页 / 仪表板（主页面）
/vault                   → 金库存取款
/predictions             → 预测历史与详情
/predictions/[id]        → 单个预测详情
/leaderboard             → 存款人排行榜
/admin                   → 管理员面板（受保护）
```

---

## 3. 页面规格说明

### 3.1 仪表板页面 (`/`)

主页面，展示系统状态总览。

**布局：**

```
┌─────────────────────────────────────────────────┐
│  顶部导航栏 (Logo + 导航 + 连接钱包)            │
├─────────────────────────────────────────────────┤
│                                                  │
│  ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐       │
│  │  TVL  │ │ 胜率  │ │ 总盈亏│ │ 份额  │       │
│  │$1.2M  │ │ 68%   │ │+$45K  │ │ 价格  │       │
│  │       │ │       │ │       │ │$1.12  │       │
│  └───────┘ └───────┘ └───────┘ └───────┘       │
│                                                  │
│  ┌──────────────────────────────────────────┐   │
│  │  今日预测                                 │   │
│  │                                           │   │
│  │  市场: Bitcoin above 66,000 on Apr 6?    │   │
│  │  Polymarket 赔率: 76% Yes               │   │
│  │  AI 预测: 62% Yes                       │   │
│  │  置信度: 78%                             │   │
│  │  策略: 买入 NO @ 25¢                     │   │
│  │  状态: 执行中 ●                          │   │
│  │                                           │   │
│  │  [关键因素]  [完整分析 →]                │   │
│  └──────────────────────────────────────────┘   │
│                                                  │
│  ┌──────────────────┐ ┌─────────────────────┐   │
│  │  盈亏图表         │ │  最近交易           │   │
│  │  (30 天折线图)    │ │  - 4月5日: +$230 ✅ │   │
│  │                   │ │  - 4月4日: -$80  ❌ │   │
│  │                   │ │  - 4月3日: +$150 ✅ │   │
│  └──────────────────┘ └─────────────────────┘   │
│                                                  │
│  页脚                                           │
└─────────────────────────────────────────────────┘
```

**组件：**

| 组件 | 说明 |
|------|------|
| StatsCards | 4 个 KPI 卡片：TVL、胜率、总盈亏、份额价格 |
| TodayPrediction | 重点展示今日 AI 预测和策略的卡片 |
| PnLChart | 30 天累计盈亏折线图（Recharts）|
| RecentTrades | 最近 10 笔交易及结果标识 |

**数据来源：**

| 数据 | API 接口 |
|------|----------|
| 统计总览 | `GET /api/v1/stats/overview` |
| 今日预测 | `GET /api/v1/predictions/today` |
| 今日市场 | `GET /api/v1/markets/today` |
| 每日盈亏 | `GET /api/v1/stats/daily` |
| 最近交易 | `GET /api/v1/trades/history?limit=10` |

### 3.2 金库页面 (`/vault`)

用户存取款管理。

**布局：**

```
┌─────────────────────────────────────────────────┐
│  顶部导航栏                                      │
├─────────────────────────────────────────────────┤
│                                                  │
│  ┌──────────────────────────────────────────┐   │
│  │  金库信息                                 │   │
│  │  总 TVL: $1,200,000                      │   │
│  │  份额价格: $1.12                         │   │
│  │  你的份额: 1,000 pvUSDC                  │   │
│  │  你的价值: $1,120.00                     │   │
│  │  你的收益: +$120.00 (+12%)              │   │
│  └──────────────────────────────────────────┘   │
│                                                  │
│  ┌────────────────┐  ┌──────────────────────┐   │
│  │  存款            │  │  份额价格历史       │   │
│  │                 │  │  (折线图)            │   │
│  │  金额: [____]   │  │                      │   │
│  │  USDC 余额:     │  │                      │   │
│  │  1,500.00       │  │                      │   │
│  │                 │  │                      │   │
│  │  你将获得:      │  │                      │   │
│  │  892.86 份额    │  │                      │   │
│  │                 │  │                      │   │
│  │  [授权 USDC]    │  │                      │   │
│  │  [存入]         │  │                      │   │
│  ├─────────────────┤  │                      │   │
│  │  取款            │  │                      │   │
│  │                 │  │                      │   │
│  │  份额: [____]   │  │                      │   │
│  │  你将收到:      │  │                      │   │
│  │  ~$1,120 USDC   │  │                      │   │
│  │                 │  │                      │   │
│  │  [申请取款]     │  │                      │   │
│  └────────────────┘  └──────────────────────┘   │
│                                                  │
│  ┌──────────────────────────────────────────┐   │
│  │  待处理取款                               │   │
│  │  ┌─────────────────────────────────┐     │   │
│  │  │ 500 份额 → ~$560 USDC           │     │   │
│  │  │ 申请时间: 4月5日 10:00 AM       │     │   │
│  │  │ 可执行时间: 4月6日 10:00 AM     │     │   │
│  │  │ 剩余时间: 14小时30分             │     │   │
│  │  │ [取消]  [执行] (未到期禁用)     │     │   │
│  │  └─────────────────────────────────┘     │   │
│  └──────────────────────────────────────────┘   │
│                                                  │
│  页脚                                           │
└─────────────────────────────────────────────────┘
```

**组件：**

| 组件 | 说明 |
|------|------|
| VaultInfo | 用户持仓摘要和金库统计 |
| DepositForm | USDC 授权 + 存款表单，实时份额计算 |
| WithdrawForm | 份额取款请求表单 |
| PendingWithdrawals | 待处理取款请求列表，含倒计时 |
| SharePriceChart | 历史份额价格图表 |

**Web3 交互：**

| 操作 | 合约调用 | 说明 |
|------|----------|------|
| 授权 | `USDC.approve(vault, amount)` | 授权 USDC 支出 |
| 存款 | `vault.deposit(amount, receiver)` | 存入 USDC 到金库 |
| 申请取款 | `vault.requestWithdraw(shares)` | 发起取款请求 |
| 取消取款 | `vault.cancelWithdraw()` | 取消待处理的取款 |
| 执行取款 | `vault.executeWithdraw()` | 延迟期过后执行取款 |

**状态检查：**

| 检查项 | 方法 | UI 影响 |
|--------|------|---------|
| USDC 授权额度 | `USDC.allowance(user, vault)` | 显示"授权"或"存入"按钮 |
| USDC 余额 | `USDC.balanceOf(user)` | 显示可用余额 |
| 份额余额 | `vault.balanceOf(user)` | 显示用户份额 |
| 份额价格 | `vault.convertToAssets(1e18)` | 计算当前价值 |
| 待处理取款 | `vault.withdrawalRequests(user)` | 显示待处理区域 |
| 取款延迟 | `vault.withdrawalDelay()` | 显示倒计时 |

### 3.3 预测历史页面 (`/predictions`)

带筛选和排序的历史预测记录。

**布局：**

```
┌─────────────────────────────────────────────────┐
│  顶部导航栏                                      │
├─────────────────────────────────────────────────┤
│                                                  │
│  ┌──────────────────────────────────────────┐   │
│  │  筛选: [全部|盈利|亏损]  排序: [日期 ▼]   │   │
│  └──────────────────────────────────────────┘   │
│                                                  │
│  ┌──────────────────────────────────────────┐   │
│  │ 4月5日│ BTC > 66,000 │ AI: 62%│ 市场:   │   │
│  │       │ 策略: NO     │ 盈亏: +$230│ ✅   │   │
│  ├───────┼──────────────┼──────────┼─────────┤   │
│  │ 4月4日│ BTC > 70,000 │ AI: 35%│ 市场:   │   │
│  │       │ 策略: NO     │ 盈亏: -$80 │ ❌   │   │
│  ├───────┼──────────────┼──────────┼─────────┤   │
│  │ 4月3日│ BTC > 65,000 │ AI: 72%│ 市场:   │   │
│  │       │ 策略: YES    │ 盈亏: +$150│ ✅   │   │
│  └──────────────────────────────────────────┘   │
│                                                  │
│  [加载更多]                                     │
│                                                  │
│  页脚                                           │
└─────────────────────────────────────────────────┘
```

**点击展开** 每行显示：
- 完整的 AI 推理过程
- 关键因素和风险因素
- 入场/出场价格和时间戳
- 数据快照摘要（预测时的 BTC 价格、情绪、指标）

### 3.4 预测详情页面 (`/predictions/[id]`)

**内容板块：**

| 板块 | 内容 |
|------|------|
| 市场信息 | 问题、阈值价格、目标日期、结算状态 |
| AI 分析 | 预测概率、置信度、方向、完整推理 |
| 关键因素 | 看涨/看跌因素标签列表 |
| 数据快照 | 预测时的 BTC 价格、RSI、MACD、恐慌贪婪指数、新闻标题 |
| 交易详情 | 入场价、出场价、仓位大小、盈亏 |
| 价格图表 | Polymarket 代币价格走势，标注入场/出场点 |

### 3.5 排行榜页面 (`/leaderboard`)

**布局：**

```
┌─────────────────────────────────────────────────┐
│  顶部导航栏                                      │
├─────────────────────────────────────────────────┤
│                                                  │
│  ┌──────────────────────────────────────────┐   │
│  │ 排名 │ 地址           │ 存款额  │ 盈亏   │   │
│  │ 🥇 1 │ 0x1234...abcd │ $50,000 │+$5.6K │   │
│  │ 🥈 2 │ 0x5678...efgh │ $30,000 │+$3.2K │   │
│  │ 🥉 3 │ 0xabcd...1234 │ $20,000 │+$2.1K │   │
│  │    4  │ 0xefgh...5678 │ $15,000 │+$1.5K │   │
│  │   ... │               │         │       │   │
│  └──────────────────────────────────────────┘   │
│                                                  │
│  排序: [存款额 | 利润 | 利润率%]                │
│                                                  │
│  页脚                                           │
└─────────────────────────────────────────────────┘
```

**数据说明：**

- 存款人排名基于金库份额持有量计算
- 利润 = 当前份额价值 - 总存入金额
- 数据来源：金库合约事件 + 后端聚合

### 3.6 管理员页面 (`/admin`) - 受保护

仅管理员钱包地址可访问。

**功能：**

| 功能 | 说明 |
|------|------|
| 系统状态 | 调度器、监控器、API 健康指标 |
| 手动控制 | 触发扫描、触发预测、暂停/恢复交易 |
| 金库管理 | 查看已部署金额、待处理取款 |
| 交易覆盖 | 手动平仓、取消订单 |
| 日志 | 最近的系统日志和告警 |

---

## 4. 全局组件

### 4.1 顶部导航栏

```
┌─────────────────────────────────────────────────┐
│  🔮 PolyPredict AI │ 仪表板 │ 金库 │            │
│                     │ 预测   │ 排行榜│            │
│                     │        │ [连接  │            │
│                     │        │ 钱包 🦊]│            │
└─────────────────────────────────────────────────┘
```

- Logo + 品牌名称
- 导航链接（高亮当前页面）
- RainbowKit 连接钱包按钮
- 网络指示器（Polygon 图标）
- 移动端：汉堡菜单

### 4.2 页脚

- 链接：文档、GitHub、Twitter
- 合约地址（链接到 Polygonscan）
- 构建版本号

### 4.3 Toast 通知

| 事件 | 类型 | 消息 |
|------|------|------|
| 存款成功 | 成功 | "已存入 X USDC，获得 Y 份额" |
| 取款已申请 | 信息 | "取款已申请，24 小时后可执行" |
| 取款已执行 | 成功 | "已取出 X USDC" |
| 交易失败 | 错误 | "交易失败: {原因}" |
| 新预测可用 | 信息 | "今日预测已就绪！" |

### 4.4 实时更新

- 金库 TVL 和份额价格：每 30 秒轮询
- 今日策略状态：每 15 秒轮询（活跃时）
- 顶部 BTC 价格行情：通过 Binance WebSocket

---

## 5. 设计系统

### 5.1 配色方案

| 用途 | 浅色模式 | 深色模式 |
|------|----------|----------|
| 背景 | `#FFFFFF` | `#0A0A0B` |
| 卡片背景 | `#F8F9FA` | `#141416` |
| 主色（品牌）| `#6366F1` (Indigo) | `#818CF8` |
| 成功 / 盈利 | `#10B981` | `#34D399` |
| 错误 / 亏损 | `#EF4444` | `#F87171` |
| 警告 | `#F59E0B` | `#FBBF24` |
| 主文字 | `#111827` | `#F9FAFB` |
| 次要文字 | `#6B7280` | `#9CA3AF` |
| 边框 | `#E5E7EB` | `#27272A` |

### 5.2 字体排版

| 元素 | 字体 | 大小 | 粗细 |
|------|------|------|------|
| H1 | Inter | 36px | 700 |
| H2 | Inter | 28px | 600 |
| H3 | Inter | 20px | 600 |
| 正文 | Inter | 16px | 400 |
| 小字 | Inter | 14px | 400 |
| 等宽（地址、数字）| JetBrains Mono | 14px | 400 |

### 5.3 组件库 (shadcn/ui)

使用的预构建组件：
- Button, Card, Badge, Table, Tabs
- Dialog, Sheet（移动端导航）, Tooltip
- Input, Select, Skeleton（加载态）
- Toast (sonner)

---

## 6. 响应式断点

| 断点 | 宽度 | 布局 |
|------|------|------|
| 手机 | < 768px | 单列布局，卡片堆叠 |
| 平板 | 768px - 1024px | 两列网格 |
| 桌面 | > 1024px | 完整布局 |

---

## 7. Web3 集成

### 7.1 钱包连接

```typescript
// wagmi config
const config = createConfig({
  chains: [polygon, polygonAmoy],
  connectors: [
    injected(),
    walletConnect({ projectId }),
    coinbaseWallet({ appName: "PolyPredict AI" }),
  ],
  transports: {
    [polygon.id]: http(POLYGON_RPC),
    [polygonAmoy.id]: http(AMOY_RPC),
  },
});
```

**支持的钱包：**
- MetaMask（注入式）
- WalletConnect v2
- Coinbase Wallet
- Rainbow Wallet

### 7.2 合约 ABI

ABI 从 Hardhat 编译产物自动生成，使用 wagmi CLI 或手动复制。

关键读取函数：
- `vault.totalAssets()` — 金库中的总 USDC
- `vault.convertToShares(assets)` — 预览存款份额
- `vault.convertToAssets(shares)` — 预览取款金额
- `vault.balanceOf(user)` — 用户份额余额
- `vault.withdrawalRequests(user)` — 待处理取款信息

关键写入函数：
- `usdc.approve(vault, amount)`
- `vault.deposit(amount, receiver)`
- `vault.requestWithdraw(shares)`
- `vault.cancelWithdraw()`
- `vault.executeWithdraw()`

### 7.3 交易处理

所有写入操作遵循以下 UX 模式：

1. 用户点击操作按钮
2. 按钮显示"等待钱包确认..."（带加载动画）
3. 钱包弹窗出现
4. 用户在钱包中确认
5. 按钮显示"确认中..."（带交易哈希链接）
6. 等待确认（1 个区块）
7. 显示成功 Toast 通知及详情
8. 自动刷新相关数据

错误状态：
- 用户拒绝：重置按钮，不显示 Toast
- 交易回滚：显示错误 Toast 及原因
- 网络错误：显示重试选项

---

## 8. 环境变量

```env
# .env.local
NEXT_PUBLIC_VAULT_ADDRESS=0x...
NEXT_PUBLIC_USDC_ADDRESS=0x...
NEXT_PUBLIC_CHAIN_ID=137
NEXT_PUBLIC_POLYGON_RPC=https://polygon-mainnet.g.alchemy.com/v2/xxx
NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID=xxx
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
```

---

## 9. 目录结构

```
frontend/
├── src/
│   ├── app/                        # Next.js App Router
│   │   ├── layout.tsx              # Root layout (providers, header, footer)
│   │   ├── page.tsx                # Dashboard page
│   │   ├── vault/
│   │   │   └── page.tsx            # Vault deposit/withdraw
│   │   ├── predictions/
│   │   │   ├── page.tsx            # Prediction history
│   │   │   └── [id]/
│   │   │       └── page.tsx        # Prediction detail
│   │   ├── leaderboard/
│   │   │   └── page.tsx            # Leaderboard
│   │   └── admin/
│   │       └── page.tsx            # Admin panel
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Header.tsx
│   │   │   ├── Footer.tsx
│   │   │   └── MobileNav.tsx
│   │   ├── dashboard/
│   │   │   ├── StatsCards.tsx
│   │   │   ├── TodayPrediction.tsx
│   │   │   ├── PnLChart.tsx
│   │   │   └── RecentTrades.tsx
│   │   ├── vault/
│   │   │   ├── VaultInfo.tsx
│   │   │   ├── DepositForm.tsx
│   │   │   ├── WithdrawForm.tsx
│   │   │   ├── PendingWithdrawals.tsx
│   │   │   └── SharePriceChart.tsx
│   │   ├── predictions/
│   │   │   ├── PredictionList.tsx
│   │   │   ├── PredictionCard.tsx
│   │   │   └── PredictionDetail.tsx
│   │   ├── leaderboard/
│   │   │   └── LeaderboardTable.tsx
│   │   └── ui/                     # shadcn/ui components
│   │       ├── button.tsx
│   │       ├── card.tsx
│   │       └── ...
│   ├── hooks/
│   │   ├── useVault.ts             # Vault contract read hooks
│   │   ├── useVaultWrite.ts        # Vault contract write hooks
│   │   ├── useUSDC.ts              # USDC approval hooks
│   │   ├── usePredictions.ts       # Backend API hooks
│   │   ├── useStats.ts             # Statistics hooks
│   │   └── useBTCPrice.ts          # Binance WebSocket price
│   ├── lib/
│   │   ├── wagmi.ts                # Wagmi config
│   │   ├── api.ts                  # Backend API client (fetch wrapper)
│   │   ├── contracts.ts            # Contract addresses + ABIs
│   │   ├── utils.ts                # Formatting, calculations
│   │   └── constants.ts            # App constants
│   ├── providers/
│   │   ├── Web3Provider.tsx        # Wagmi + RainbowKit provider
│   │   └── QueryProvider.tsx       # TanStack Query provider
│   └── types/
│       ├── market.ts               # Market types
│       ├── prediction.ts           # Prediction types
│       └── vault.ts                # Vault types
├── public/
│   └── favicon.ico
├── next.config.js
├── tailwind.config.ts
├── tsconfig.json
├── package.json
└── .env.local.example
```

---

## 10. 性能优化

| 策略 | 实现方式 |
|------|----------|
| 公开页面使用 SSR | 仪表板、预测页面使用服务端组件 |
| Web3 部分使用客户端组件 | 金库页面、钱包交互 |
| 数据缓存 | TanStack Query，30 秒过期时间 |
| 图片优化 | Next.js Image 组件 |
| 代码分割 | 图表等重量级组件使用动态导入 |
| 骨架屏加载 | 数据加载时显示骨架屏 UI |
