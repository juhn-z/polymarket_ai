# 后端产品需求文档 - Polymarket AI 预测引擎

## 1. 概述

### 1.1 项目目的

构建一个 Python 后端服务，自动扫描 Polymarket 比特币预测市场，聚合多源数据，使用 GPT-5.4 预测市场结果，生成交易策略，通过 Polymarket CLOB API 执行交易，并实时监控持仓进行止盈止损。

### 1.2 技术栈

| 组件 | 选型 |
|------|------|
| 语言 | Python 3.11+ |
| 框架 | FastAPI |
| 任务调度 | APScheduler / Celery + Redis |
| 数据库 | PostgreSQL |
| ORM | SQLAlchemy + Alembic（数据库迁移）|
| LLM | OpenAI GPT-5.4 API |
| WebSocket | websockets / aiohttp |
| Polymarket | py-clob-client（官方 SDK）|
| 容器化 | Docker + Docker Compose |

### 1.3 外部 API

| API | 用途 | 认证方式 |
|-----|------|----------|
| Polymarket CLOB API | 市场数据、下单 | API Key + Secret |
| Polymarket Gamma API | 事件/市场搜索 | 公开 |
| Binance API | BTC/USDT K 线、价格数据 | 公开（有频率限制）|
| Alternative.me API | 加密货币恐慌与贪婪指数 | 公开 |
| NewsAPI / CryptoPanic | 加密新闻聚合 | API Key |
| Glassnode / CryptoQuant | 链上数据（交易所流入流出、巨鲸活动）| API Key |
| OpenAI API | GPT-5.4 预测 | API Key |

---

## 2. 系统架构

```
┌─────────────────────────────────────────────────────┐
│                    FastAPI Server                     │
│                                                       │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │  REST API    │  │  Scheduler   │  │  WebSocket   │ │
│  │  (前端接口)  │  │  (定时任务)  │  │  (监控服务)  │ │
│  └──────┬──────┘  └──────┬───────┘  └──────┬──────┘ │
│         │                │                  │         │
│  ┌──────▼──────────────▼─────────────────▼──────┐   │
│  │              服务层 (Service Layer)             │   │
│  │                                                │   │
│  │  ┌────────────┐  ┌────────────┐  ┌──────────┐ │   │
│  │  │  市场扫描   │  │  数据聚合   │  │  AI 预测 │ │   │
│  │  │  Scanner    │  │  Aggregator │  │  Predict │ │   │
│  │  └────────────┘  └────────────┘  └──────────┘ │   │
│  │                                                │   │
│  │  ┌────────────┐  ┌────────────┐  ┌──────────┐ │   │
│  │  │  策略生成   │  │  交易执行   │  │  持仓监控│ │   │
│  │  │  Generator  │  │  Executor   │  │  Monitor │ │   │
│  │  └────────────┘  └────────────┘  └──────────┘ │   │
│  └───────────────────────┬───────────────────────┘   │
│                          │                            │
│  ┌───────────────────────▼───────────────────────┐   │
│  │              数据层 (PostgreSQL)                │   │
│  └────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

---

## 3. 核心模块

### 3.1 市场扫描器 (Market Scanner)

**职责：** 每日扫描 Polymarket 上的 BTC 价格预测市场，选择最佳目标市场。

**调度时间：** 每天 00:00 UTC（可配置）

**逻辑：**

1. 通过 Polymarket Gamma API 查询标签为 `bitcoin` 或关键词包含 `Bitcoin above` 的活跃事件
2. 筛选符合模式 "Bitcoin above ___ on {date}" 的事件
3. 对每个事件，获取所有子市场（不同的价格阈值）
4. 选择概率最接近 50% 的市场（范围在 35%-65% 之间）
5. 如果有多个候选，优先选择流动性（交易量）最高的
6. 将选定市场保存到数据库，通过 API 通知前端

**API 接口：**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/markets/today` | 获取今日选定的市场 |
| GET | `/api/v1/markets/history` | 获取历史市场选择记录 |
| GET | `/api/v1/markets/scan` | 手动触发市场扫描 |

**数据模型 - Market：**

```python
class Market(Base):
    id: int                      # primary key
    polymarket_condition_id: str  # Polymarket condition ID
    polymarket_token_id: str     # CLOB token ID (Yes/No)
    event_slug: str              # e.g. "bitcoin-above-on-april-6"
    question: str                # e.g. "Bitcoin above 66,000 on April 6?"
    price_threshold: int         # e.g. 66000
    target_date: date            # e.g. 2026-04-06
    current_yes_price: float     # current Yes token price
    current_no_price: float      # current No token price
    selected_at: datetime        # when this market was selected
    status: str                  # "active" | "resolved" | "expired"
    resolution: str | None       # "yes" | "no" | None
    created_at: datetime
    updated_at: datetime
```

### 3.2 数据聚合器 (Data Aggregator)

**职责：** 收集并格式化多源数据，供 LLM 预测使用。

**数据来源：**

#### 3.2.1 Binance K 线数据
- BTC/USDT 1 小时 K 线，最近 7 天
- BTC/USDT 1 日 K 线，最近 30 天
- 当前价格、24 小时最高/最低价、24 小时成交量
- 提取：趋势方向、波动率、支撑/阻力位

#### 3.2.2 技术指标
通过 `ta` 库基于 K 线数据计算：
- RSI（14 周期）
- MACD（12, 26, 9）
- 布林带（20 周期，2 倍标准差）
- EMA（7, 25, 99）
- ATR（平均真实波幅）
- 成交量加权均价

#### 3.2.3 市场情绪
- 恐慌与贪婪指数（Alternative.me）：当前值 + 7 日趋势
- Binance 合约资金费率
- 多空比

#### 3.2.4 新闻与事件
- 最新 10 条 BTC 相关新闻标题和摘要
- 重大宏观事件（FOMC 会议、CPI 发布）来自经济日历
- 社交媒体情绪分值（可选，来自 LunarCrush 或类似平台）

#### 3.2.5 链上数据
- 交易所净流入/流出（24 小时、7 天）
- 大额交易笔数（> 100 万美元）
- 活跃地址数趋势
- 矿工流出量
- MVRV 比率

**输出格式：**

```python
@dataclass
class MarketDataBundle:
    timestamp: datetime
    btc_current_price: float
    target_price: int              # market threshold (e.g. 66000)
    target_datetime: datetime      # when the market resolves
    
    # K-line summary
    kline_1h_7d: list[dict]        # OHLCV
    kline_1d_30d: list[dict]       # OHLCV
    price_change_24h: float        # percentage
    price_change_7d: float         # percentage
    
    # Technical indicators
    rsi_14: float
    macd: dict                     # {"macd", "signal", "histogram"}
    bollinger: dict                # {"upper", "middle", "lower"}
    ema: dict                      # {"ema7", "ema25", "ema99"}
    atr: float
    
    # Sentiment
    fear_greed_index: int          # 0-100
    fear_greed_label: str          # "Extreme Fear" to "Extreme Greed"
    funding_rate: float
    long_short_ratio: float
    
    # News
    news_headlines: list[dict]     # [{"title", "summary", "sentiment", "source"}]
    macro_events: list[dict]       # [{"event", "date", "expected", "impact"}]
    
    # On-chain
    exchange_netflow_24h: float    # positive = inflow (bearish)
    large_tx_count_24h: int
    active_addresses_change: float # percentage change
    mvrv_ratio: float
```

### 3.3 AI 预测器 (AI Predictor)

**职责：** 使用 GPT-5.4 分析聚合数据，预测市场结果概率。

**Prompt 工程：**

```
System: You are an expert crypto market analyst. You will be given comprehensive 
Bitcoin market data and asked to predict whether BTC/USDT will be above a specific 
price at a specific time. Analyze all provided data systematically and output a 
structured prediction.

User: [MarketDataBundle formatted as structured text]

Question: Will Bitcoin (BTC/USDT on Binance) close above {target_price} at 
{target_datetime} ET?

Please analyze:
1. Technical analysis (trend, indicators, support/resistance)
2. Market sentiment (fear/greed, funding, positioning)
3. News impact assessment
4. On-chain signal interpretation
5. Historical pattern matching

Output JSON:
{
  "predicted_probability": 0.0-1.0,    // your estimated probability of Yes
  "confidence": 0.0-1.0,              // how confident you are in this prediction
  "direction": "bullish" | "bearish" | "neutral",
  "key_factors": ["factor1", "factor2", ...],
  "risk_factors": ["risk1", "risk2", ...],
  "reasoning": "detailed reasoning text",
  "recommended_action": "buy_yes" | "buy_no" | "skip"
}
```

**API 接口：**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/predictions/today` | 获取今日 AI 预测 |
| GET | `/api/v1/predictions/history` | 获取历史预测记录 |
| POST | `/api/v1/predictions/trigger` | 手动触发预测（管理员）|

**数据模型 - Prediction：**

```python
class Prediction(Base):
    id: int
    market_id: int                 # FK to Market
    predicted_probability: float   # AI predicted probability (0-1)
    confidence: float              # AI confidence level (0-1)
    direction: str                 # "bullish" | "bearish" | "neutral"
    key_factors: list[str]         # JSON array
    risk_factors: list[str]        # JSON array
    reasoning: str                 # full reasoning text
    recommended_action: str        # "buy_yes" | "buy_no" | "skip"
    market_probability: float      # Polymarket probability at prediction time
    edge: float                    # |predicted - market| probability difference
    model_version: str             # "gpt-5.4"
    data_snapshot: dict            # full MarketDataBundle as JSON
    created_at: datetime
```

### 3.4 策略生成器 (Strategy Generator)

**职责：** 将 AI 预测转化为可执行的交易策略。

**策略逻辑：**

```python
def generate_strategy(prediction, market, vault_balance):
    edge = prediction.predicted_probability - market.current_yes_price
    abs_edge = abs(edge)
    
    # Skip if edge is too small or confidence too low
    if abs_edge < 0.05 or prediction.confidence < 0.6:
        return Strategy(action="skip", reason="Insufficient edge or confidence")
    
    # Determine side
    if edge > 0:
        side = "buy_yes"   # AI thinks higher probability than market
    else:
        side = "buy_no"    # AI thinks lower probability than market
    
    # Position sizing (Kelly Criterion simplified)
    # f = (bp - q) / b where b=odds, p=predicted prob, q=1-p
    kelly_fraction = calculate_kelly(prediction, market)
    max_position = vault_balance * 0.1  # never risk more than 10% per trade
    position_size = min(kelly_fraction * vault_balance, max_position)
    
    # Take profit / Stop loss
    take_profit = market_price + (abs_edge * 0.7)  # take 70% of edge
    stop_loss = market_price - (abs_edge * 0.5)    # stop at 50% of edge
    
    return Strategy(
        action=side,
        position_size=position_size,
        entry_price=market_price,
        take_profit=take_profit,
        stop_loss=stop_loss,
        kelly_fraction=kelly_fraction
    )
```

**数据模型 - Strategy：**

```python
class Strategy(Base):
    id: int
    prediction_id: int             # FK to Prediction
    market_id: int                 # FK to Market
    action: str                    # "buy_yes" | "buy_no" | "skip"
    side: str                      # "yes" | "no"
    position_size: float           # USDC amount
    entry_price: float             # expected entry price
    take_profit: float             # target price to sell
    stop_loss: float               # stop loss price
    kelly_fraction: float          # Kelly criterion fraction
    status: str                    # "pending" | "executing" | "active" | "closed" | "failed"
    created_at: datetime
    executed_at: datetime | None
```

### 3.5 交易执行器 (Trade Executor)

**职责：** 通过 Polymarket CLOB API 执行交易策略。

**工作流程：**

1. 从策略生成器接收策略
2. 通过管理员钱包从 Vault 合约提取 USDC
3. 将 USDC 存入 Polymarket 代理钱包
4. 通过 CLOB API 下限价单
5. 监控订单成交状态
6. 更新数据库中的策略状态

**关键操作：**

| 操作 | API | 说明 |
|------|-----|------|
| 下单 | `POST /order` | 提交限价单（Yes/No 代币）|
| 撤单 | `DELETE /order/{id}` | 取消未成交订单 |
| 查询订单 | `GET /order/{id}` | 检查订单成交状态 |
| 查询持仓 | `GET /positions` | 获取当前代币持仓 |
| 查询余额 | `GET /balance` | 获取可用 USDC 余额 |

**API 接口：**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/trades/active` | 获取活跃交易 |
| GET | `/api/v1/trades/history` | 获取交易历史 |
| GET | `/api/v1/trades/{id}` | 获取特定交易详情 |

**数据模型 - Trade：**

```python
class Trade(Base):
    id: int
    strategy_id: int               # FK to Strategy
    market_id: int                 # FK to Market
    polymarket_order_id: str       # CLOB order ID
    side: str                      # "yes" | "no"
    action: str                    # "buy" | "sell"
    amount: float                  # USDC amount
    price: float                   # execution price
    shares: float                  # token shares received
    status: str                    # "pending" | "filled" | "partial" | "cancelled" | "failed"
    fee: float                     # trading fee
    pnl: float | None              # realized PnL (after closing)
    created_at: datetime
    filled_at: datetime | None
    closed_at: datetime | None
```

### 3.6 持仓监控器 (Position Monitor)

**职责：** 实时监控未平仓持仓，自动执行止盈和止损。

**实现方式：**

- 通过 WebSocket 连接 Polymarket 获取实时价格更新
- 备选方案：每 30 秒 REST 轮询
- 对比持仓与止盈/止损阈值
- 满足条件时自动平仓
- 市场到期时特殊处理（自动赎回）

**监控循环：**

```python
async def monitor_loop():
    while True:
        active_strategies = get_active_strategies()
        for strategy in active_strategies:
            current_price = get_current_price(strategy.market_id, strategy.side)
            
            # Take profit
            if current_price >= strategy.take_profit:
                await close_position(strategy, reason="take_profit")
            
            # Stop loss
            elif current_price <= strategy.stop_loss:
                await close_position(strategy, reason="stop_loss")
            
            # Market about to resolve (30 min before)
            elif is_near_resolution(strategy.market):
                await close_position(strategy, reason="pre_resolution")
            
            # Update current price in DB
            await update_position_price(strategy, current_price)
        
        await asyncio.sleep(10)  # check every 10 seconds
```

**告警条件：**

| 条件 | 操作 |
|------|------|
| 价格触及止盈线 | 自动卖出，记录利润 |
| 价格触及止损线 | 自动卖出，记录亏损 |
| 距离市场结算 30 分钟 | 自动卖出剩余持仓 |
| API 错误 / 连接断开 | 重试 3 次，然后通知管理员 |
| 价格在 5 分钟内波动 >10% | 通知管理员进行人工审核 |

---

## 4. REST API 接口规范

### 4.1 市场接口

```
GET    /api/v1/markets/today           # 今日选定市场
GET    /api/v1/markets/history         # 历史市场记录（分页）
GET    /api/v1/markets/{id}            # 市场详情
POST   /api/v1/markets/scan            # 手动触发扫描（管理员）
```

### 4.2 预测接口

```
GET    /api/v1/predictions/today       # 今日预测
GET    /api/v1/predictions/history     # 历史预测记录（分页）
GET    /api/v1/predictions/{id}        # 预测详情（含推理过程）
POST   /api/v1/predictions/trigger     # 手动触发预测（管理员）
```

### 4.3 策略与交易接口

```
GET    /api/v1/strategies/active       # 活跃策略
GET    /api/v1/strategies/history      # 历史策略
GET    /api/v1/trades/active           # 活跃交易
GET    /api/v1/trades/history          # 交易历史
GET    /api/v1/trades/{id}             # 交易详情
```

### 4.4 统计接口

```
GET    /api/v1/stats/overview          # 总览（胜率、总盈亏等）
GET    /api/v1/stats/leaderboard       # 存款人排行榜
GET    /api/v1/stats/daily             # 每日盈亏图表数据
GET    /api/v1/stats/vault             # 金库 TVL、份额价格历史
```

### 4.5 系统接口

```
GET    /api/v1/health                  # 健康检查
GET    /api/v1/system/status           # 系统状态（调度器、监控等）
POST   /api/v1/system/pause            # 暂停交易（管理员）
POST   /api/v1/system/resume           # 恢复交易（管理员）
```

---

## 5. 数据库设计

### 5.1 数据表

| 表名 | 说明 |
|------|------|
| `markets` | 选定的 Polymarket 市场 |
| `predictions` | 每个市场的 AI 预测 |
| `strategies` | 基于预测生成的交易策略 |
| `trades` | 具体的交易执行记录 |
| `vault_snapshots` | 定期的金库状态快照（TVL、份额价格）|
| `users` | 金库存款人（钱包地址）|
| `system_logs` | 系统事件日志 |

### 5.2 金库快照（用于前端图表）

```python
class VaultSnapshot(Base):
    id: int
    total_assets: float        # total USDC in vault + deployed
    share_price: float         # current share price
    tvl: float                 # total value locked
    depositor_count: int       # number of unique depositors
    deployed_amount: float     # amount currently in Polymarket
    snapshot_at: datetime      # snapshot timestamp
```

---

## 6. 定时任务

| 任务 | 调度时间 | 说明 |
|------|----------|------|
| 市场扫描 | 每天 00:00 UTC | 扫描并选择今日市场 |
| 数据聚合 | 每天 01:00 UTC | 收集所有数据源 |
| AI 预测 | 每天 02:00 UTC | 运行 GPT-5.4 预测 |
| 策略生成 | 每天 02:30 UTC | 生成交易策略 |
| 交易执行 | 每天 03:00 UTC | 执行策略（如已批准）|
| 金库快照 | 每 1 小时 | 记录金库状态 |
| 持仓监控 | 持续运行 | 实时价格监控 |
| 健康检查 | 每 5 分钟 | 系统健康验证 |

---

## 7. 配置文件

```yaml
# config.yaml
app:
  name: "PolyPredict AI"
  env: "development"  # development | staging | production
  debug: true
  port: 8000

database:
  url: "postgresql://user:pass@localhost:5432/polypredict"

polymarket:
  clob_api_url: "https://clob.polymarket.com"
  gamma_api_url: "https://gamma-api.polymarket.com"
  api_key: "${POLYMARKET_API_KEY}"
  api_secret: "${POLYMARKET_API_SECRET}"
  passphrase: "${POLYMARKET_PASSPHRASE}"

binance:
  api_url: "https://api.binance.com"
  
openai:
  api_key: "${OPENAI_API_KEY}"
  model: "gpt-5.4"
  temperature: 0.3
  max_tokens: 4096

onchain:
  glassnode_api_key: "${GLASSNODE_API_KEY}"
  
news:
  cryptopanic_api_key: "${CRYPTOPANIC_API_KEY}"

strategy:
  min_edge: 0.05              # minimum probability edge to trade
  min_confidence: 0.6         # minimum AI confidence to trade
  max_position_pct: 0.10      # max 10% of vault per trade
  take_profit_factor: 0.7     # take profit at 70% of edge
  stop_loss_factor: 0.5       # stop loss at 50% of edge
  pre_resolution_minutes: 30  # close position 30min before resolution

vault:
  contract_address: "${VAULT_CONTRACT_ADDRESS}"
  admin_private_key: "${ADMIN_PRIVATE_KEY}"
  rpc_url: "${POLYGON_RPC_URL}"

monitoring:
  price_check_interval: 10    # seconds
  alert_price_change_pct: 10  # alert if >10% move in 5min
  max_retry: 3
```

---

## 8. 目录结构

```
backend/
├── app/
│   ├── main.py                    # FastAPI app entry point
│   ├── config.py                  # Configuration loader
│   ├── database.py                # Database connection
│   ├── models/                    # SQLAlchemy models
│   │   ├── market.py
│   │   ├── prediction.py
│   │   ├── strategy.py
│   │   ├── trade.py
│   │   ├── vault_snapshot.py
│   │   └── user.py
│   ├── schemas/                   # Pydantic schemas
│   │   ├── market.py
│   │   ├── prediction.py
│   │   ├── strategy.py
│   │   ├── trade.py
│   │   └── stats.py
│   ├── api/                       # API routes
│   │   ├── v1/
│   │   │   ├── markets.py
│   │   │   ├── predictions.py
│   │   │   ├── strategies.py
│   │   │   ├── trades.py
│   │   │   ├── stats.py
│   │   │   └── system.py
│   │   └── deps.py                # Dependencies (auth, db session)
│   ├── services/                  # Business logic
│   │   ├── market_scanner.py
│   │   ├── data_aggregator.py
│   │   ├── ai_predictor.py
│   │   ├── strategy_generator.py
│   │   ├── trade_executor.py
│   │   ├── position_monitor.py
│   │   └── vault_service.py
│   ├── tasks/                     # Scheduled tasks
│   │   ├── scheduler.py
│   │   └── jobs.py
│   └── utils/
│       ├── logger.py
│       ├── indicators.py          # Technical indicator calculations
│       └── polymarket_client.py   # Polymarket API wrapper
├── alembic/                       # Database migrations
│   └── versions/
├── tests/
│   ├── test_market_scanner.py
│   ├── test_ai_predictor.py
│   ├── test_strategy_generator.py
│   └── test_trade_executor.py
├── alembic.ini
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## 9. 错误处理与容错

| 场景 | 处理方式 |
|------|----------|
| Polymarket API 宕机 | 指数退避重试 3 次，回退到缓存数据 |
| OpenAI API 错误 | 重试 3 次，全部失败则跳过预测 |
| Binance API 频率限制 | 使用缓存 K 线数据，冷却后重试 |
| 数据库连接断开 | 自动重连（带退避）|
| 交易执行失败 | 记录错误，通知管理员，标记策略为失败 |
| WebSocket 断连 | 自动重连，回退到 REST 轮询 |
| Vault 合约调用失败 | 提高 Gas 重试，通知管理员 |
