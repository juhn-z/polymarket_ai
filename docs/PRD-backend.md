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

**职责：** 每天 UTC 00:00 扫描 Polymarket，选择**两天后结算**的 BTC 价格预测事件，并从中找出概率最接近 50% 的子市场作为当日交易目标。

**调度时间：** 每天 00:00 UTC（可配置）

**为什么选择两天后到期的市场？**

- **预留交易窗口：** 给 AI 预测、策略生成、订单成交、止盈止损监控留足时间（约 36 小时）
- **避开高波动末段：** 当日到期的市场流动性枯竭、价格震荡剧烈，不适合算法交易
- **概率收敛节奏适中：** 两天窗口让概率有合理的演化空间，AI 的优势能体现出来

**核心逻辑：**

```
T = current_utc_date()
target_date = T + 2 days   # e.g. 今天 4月5日扫描，找 4月7日结算的市场

Step 1: 通过 Polymarket Gamma API 查询事件
        GET /events?tag=bitcoin&active=true&closed=false
        筛选条件:
          - event.title 匹配模式 "Bitcoin above ___ on {target_date}"
          - event.endDate 落在 target_date 当天 (UTC)
          - event 状态为 active

Step 2: 获取该 event 下所有子市场 (markets)
        每个子市场对应一个价格阈值，例如 58000 / 60000 / 62000 / ... / 78000
        通过 CLOB API 获取每个 market 的实时价格:
          GET /markets/{condition_id}
          → outcome_prices = [yes_price, no_price]

Step 3: 筛选 + 排序候选 markets
        筛选条件 (硬约束):
          - 35% <= yes_price <= 65%        # 概率接近 50%
          - 24h 交易量 >= $10,000          # 保证流动性
          - 订单簿买卖价差 <= 3%           # 防止冷门市场滑点
        排序优先级:
          1. 距离 50% 的偏差 abs(yes_price - 0.5) 升序
          2. 24h 交易量降序

Step 4: 选取 top 1 作为当日目标市场
        若无符合条件的 market → 标记 "no_target_today"，跳过当日交易

Step 5: 持久化到数据库 (markets 表)
        通过 API 暴露给前端
```

**API 接口：**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/markets/today` | 获取今日选定的目标市场 |
| GET | `/api/v1/markets/history` | 历史市场选择记录（分页）|
| GET | `/api/v1/markets/{id}/orderbook` | 获取实时订单簿快照 |
| POST | `/api/v1/markets/scan` | 手动触发市场扫描（管理员）|

**数据模型 - Market：**

```python
class Market(Base):
    id: int                       # primary key
    polymarket_event_id: str      # Polymarket event ID
    polymarket_event_slug: str    # e.g. "bitcoin-above-on-april-7"
    polymarket_condition_id: str  # selected market condition ID
    yes_token_id: str             # CLOB ERC1155 token ID for Yes
    no_token_id: str              # CLOB ERC1155 token ID for No
    
    question: str                 # e.g. "Bitcoin above 66,000 on April 7?"
    price_threshold: int          # e.g. 66000
    
    scan_date: date               # date when scanner ran (UTC)
    target_date: date             # market resolution date (= scan_date + 2)
    target_datetime_utc: datetime # exact resolution timestamp (UTC)
    target_datetime_et: datetime  # exact resolution timestamp (ET, for display)
    
    initial_yes_price: float      # Yes price at scan time
    initial_no_price: float       # No price at scan time
    initial_volume_24h: float     # 24h trading volume at scan time
    initial_spread: float         # bid-ask spread at scan time
    
    candidates_snapshot: dict     # JSON: all candidate markets considered
    selection_reason: str         # short text describing why selected
    
    status: str                   # "selected" | "traded" | "resolved" | "expired" | "skipped"
    resolution: str | None        # "yes" | "no" | None
    final_btc_price: float | None # actual BTC close price at resolution
    
    created_at: datetime
    updated_at: datetime
```

**异常处理：**

| 场景 | 处理方式 |
|------|----------|
| Gamma API 无返回符合条件的事件 | 状态置 `skipped`，记录原因，告警 |
| 所有候选市场概率都不在 35%-65% | 状态置 `skipped`，记录候选快照供审查 |
| 同一 scan_date 已存在记录 | 幂等：跳过本次扫描，返回已有记录 |
| Polymarket API 超时 | 指数退避重试 3 次，仍失败则告警 |

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

**职责：** 使用 GPT-5.4 分析聚合数据，输出结构化的概率预测。

**调用方式：** OpenAI Chat Completions API + Structured Outputs（强制 JSON Schema）

**关键参数：**

| 参数 | 值 | 说明 |
|------|---|------|
| model | `gpt-5.4` | 主模型 |
| temperature | `0.2` | 低随机性，提高决定性 |
| top_p | `0.9` | |
| seed | 固定值 | 可复现性 |
| response_format | `json_schema` (strict) | 强制结构化输出 |
| max_tokens | `4096` | |

#### 3.3.1 System Prompt

```text
You are a quantitative crypto market analyst with 10+ years of experience in 
Bitcoin derivatives, on-chain analysis, and prediction markets.

Your task is to estimate the probability that BTC/USDT (Binance spot) closes 
ABOVE a specific price threshold at a specific resolution time. You are NOT 
predicting direction or magnitude — you are estimating a calibrated probability 
between 0 and 1.

Critical rules you MUST follow:

1. Output a calibrated probability, not a confidence-weighted bet. If the data 
   is genuinely ambiguous, output a probability close to the current market 
   price rather than a strong opinion.

2. Use ONLY the data provided in the user message. Do NOT invent prices, 
   indicators, or news that are not given.

3. Distinguish between:
   - "predicted_probability": your honest estimate of the true probability
   - "confidence": how reliable you think your estimate is given data quality
   These are independent — high confidence in 50% probability is valid.

4. Account for time-to-resolution. Markets resolving in 48 hours have less 
   uncertainty than 7-day markets. Adjust accordingly.

5. Be aware of edge cases:
   - If BTC is already well above the threshold and < 24h to resolution → 
     probability should be near 1.0 (but not exactly 1.0).
   - If BTC is well below the threshold and < 24h to resolution → near 0.0.
   - If threshold ≈ current price → probability should be near 0.5, weighted 
     by short-term momentum and volatility.

6. Output ONLY valid JSON matching the provided schema. No markdown, no prose 
   outside JSON.

7. The downstream system will ONLY trade when:
     abs(predicted_probability - market_yes_price) >= 0.25  AND  confidence >= 0.6
   This means: trades only happen when you believe the market is severely 
   mispriced (>=25 percentage points off true probability). Do NOT inflate 
   your edge to force a trade. If the data does not support a >=25% edge, 
   set recommended_action to "skip" and report your honest probability.
```

#### 3.3.2 User Prompt 模板

User message 由 Data Aggregator 输出的 `MarketDataBundle` 序列化为结构化文本：

```text
# MARKET QUESTION
Question: "Will BTC/USDT (Binance) close ABOVE ${target_price} at {target_datetime_et} ET?"
Resolution source: Binance BTC/USDT 1-minute candle close price at the target time.
Time to resolution: {hours_to_resolution} hours ({days_to_resolution} days)

# CURRENT MARKET STATE (Polymarket)
Yes price: {yes_price} (implied probability {yes_pct}%)
No price:  {no_price} (implied probability {no_pct}%)
24h volume: ${volume_24h}
Bid-ask spread: {spread}%

# CURRENT BTC PRICE
Spot price (Binance): ${btc_current_price}
Distance to threshold: {distance_pct}% ({direction_label})
24h change: {change_24h}%
7d change: {change_7d}%

# KLINE SUMMARY
1h candles (last 7d): {kline_1h_summary}   # OHLCV trend description
1d candles (last 30d): {kline_1d_summary}

# TECHNICAL INDICATORS
RSI(14): {rsi_14}                          # >70 overbought, <30 oversold
MACD: macd={macd}, signal={signal}, hist={histogram}
Bollinger Bands: upper={bb_upper}, mid={bb_mid}, lower={bb_lower}
EMA: ema7={ema7}, ema25={ema25}, ema99={ema99}
ATR(14): {atr}                             # current volatility

# MARKET SENTIMENT
Fear & Greed Index: {fgi_value}/100 ({fgi_label})
F&G 7d trend: {fgi_trend}                  # rising/falling/flat
Funding rate (perp): {funding_rate}%        # positive = longs pay shorts
Long/Short ratio: {long_short_ratio}

# NEWS HEADLINES (last 24h, top 10)
{numbered list of news headlines + sentiment}

# MACRO EVENTS (next 48h)
{list of scheduled events: FOMC, CPI, etc.}

# ON-CHAIN SIGNALS
Exchange netflow 24h: ${exchange_netflow_24h}    # positive = inflow (bearish)
Large tx count 24h: {large_tx_count}             # >$1M transfers
Active addresses 24h change: {active_addr_change}%
MVRV ratio: {mvrv}                                # >3.7 historical top zone

# YOUR TASK
Estimate the probability that the answer to the question is YES.
Output JSON matching the response schema exactly.
```

#### 3.3.3 输出 JSON Schema (Structured Output)

强制使用 OpenAI Structured Output 功能，schema 如下：

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": [
    "predicted_probability",
    "confidence",
    "direction",
    "key_factors",
    "risk_factors",
    "technical_analysis",
    "sentiment_analysis",
    "news_impact",
    "onchain_analysis",
    "reasoning",
    "recommended_action"
  ],
  "properties": {
    "predicted_probability": {
      "type": "number",
      "minimum": 0.01,
      "maximum": 0.99,
      "description": "Calibrated probability that BTC closes ABOVE threshold at resolution time"
    },
    "confidence": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 1.0,
      "description": "How reliable this estimate is given data quality and uncertainty"
    },
    "direction": {
      "type": "string",
      "enum": ["bullish", "bearish", "neutral"],
      "description": "Overall short-term BTC bias"
    },
    "key_factors": {
      "type": "array",
      "items": { "type": "string" },
      "minItems": 2,
      "maxItems": 5,
      "description": "Top 2-5 factors supporting the prediction"
    },
    "risk_factors": {
      "type": "array",
      "items": { "type": "string" },
      "minItems": 2,
      "maxItems": 5,
      "description": "Top 2-5 risks that could invalidate the prediction"
    },
    "technical_analysis": {
      "type": "string",
      "description": "1-2 sentences on TA signals (RSI/MACD/BB/EMA)"
    },
    "sentiment_analysis": {
      "type": "string",
      "description": "1-2 sentences on F&G, funding, positioning"
    },
    "news_impact": {
      "type": "string",
      "description": "1-2 sentences on news/macro event impact"
    },
    "onchain_analysis": {
      "type": "string",
      "description": "1-2 sentences on on-chain signals"
    },
    "reasoning": {
      "type": "string",
      "description": "Synthesis of all signals and final justification (<= 300 words)"
    },
    "recommended_action": {
      "type": "string",
      "enum": ["buy_yes", "buy_no", "skip"],
      "description": "buy_yes if predicted_probability - market_yes_price >= 0.25 AND confidence >= 0.6; buy_no if market_yes_price - predicted_probability >= 0.25 AND confidence >= 0.6; otherwise skip"
    }
  }
}
```

#### 3.3.4 输出示例

**示例 A — 有套利空间（边际 30%，触发交易）：**

```json
{
  "predicted_probability": 0.25,
  "confidence": 0.78,
  "direction": "bearish",
  "key_factors": [
    "BTC trading 3.8% BELOW threshold with only 36h to resolution",
    "ATR-implied move suggests <15% chance of crossing threshold by resolution",
    "Exchange netflow +$240M (inflow, bearish) for 3 consecutive days",
    "RSI 38 with bearish MACD divergence on 4h chart"
  ],
  "risk_factors": [
    "Potential short squeeze if funding flips negative",
    "FOMC dovish surprise possible (though base case is hawkish)",
    "Thin liquidity in Asia hours could cause flash spikes"
  ],
  "technical_analysis": "RSI 38 oversold-but-not-extreme, MACD bearish crossover 8h ago, price below EMA7/EMA25.",
  "sentiment_analysis": "F&G at 38 (Fear) trending down, funding 0.01% near neutral, L/S ratio 0.85 (shorts dominant).",
  "news_impact": "Two consecutive days of ETF outflows ($150M total); regulatory uncertainty around stablecoin bill.",
  "onchain_analysis": "Strong exchange inflows of $240M over 3 days indicate distribution; whale wallets reducing positions.",
  "reasoning": "BTC is currently $63,500, threshold is $66,000 (3.8% above current). With 36 hours to resolution and ATR(14)=$850, the implied 1-sigma move is roughly $1,470, meaning a >2.5σ move is required to cross the threshold. Technical, on-chain, and sentiment signals all point bearish. Polymarket prices Yes at 55% which appears to overweight recency bias from last week's rally. My estimate is 25%, giving an edge of 30% in favor of No with high confidence. This is a high-conviction trade.",
  "recommended_action": "buy_no"
}
```

**示例 B — 无套利空间（边际 14%，建议 skip）：**

```json
{
  "predicted_probability": 0.62,
  "confidence": 0.74,
  "direction": "bullish",
  "key_factors": [
    "Price 1.5% above threshold with 36h to resolution",
    "RSI 58 with rising MACD histogram suggests continued momentum",
    "Exchange netflow -$120M (outflow, bullish)"
  ],
  "risk_factors": [
    "FOMC minutes release in 18h could trigger volatility",
    "Funding rate 0.04% indicates some long crowding",
    "Resistance at $67,200 historically rejected 3 times"
  ],
  "technical_analysis": "RSI 58 neutral-bullish, MACD positive crossover 4h ago, price above EMA25.",
  "sentiment_analysis": "F&G at 62 (Greed) trending sideways, funding moderate, L/S ratio 1.12 balanced.",
  "news_impact": "ETF inflows of $85M yesterday support positive bias; no negative regulatory news.",
  "onchain_analysis": "Exchange outflow $120M suggests accumulation; active addresses +3.2%.",
  "reasoning": "Polymarket prices Yes at 76%, my honest estimate is 62%. Edge of 14% is below the 25% threshold required to trade. While I lean toward No, the data does not justify high-conviction action — FOMC risk is real but priced ambiguously. Recommend skip.",
  "recommended_action": "skip"
}
```

#### 3.3.5 错误与降级处理

| 场景 | 处理方式 |
|------|---------|
| LLM 返回非法 JSON | Structured Output 模式下不应发生；若发生则重试 1 次 |
| `abs(predicted_probability - market_yes_price) < 0.25` | Strategy Generator 强制 skip（边际不足，无套利空间）|
| `confidence < 0.6` | Strategy Generator 强制 skip（置信度不足）|
| LLM 返回 `buy_yes/buy_no` 但实际边际 < 25% | Strategy Generator 覆盖为 skip 并记录冲突日志 |
| LLM API 调用失败 | 指数退避重试 3 次，全失败则当日 skip 交易并告警 |
| 单次调用 token 超限 | 截断 K 线历史（保留摘要而非全量），重试 |
| 输出与 schema 不匹配 | 记录原始响应供审查，重试 1 次 |

**API 接口：**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/predictions/today` | 获取今日 AI 预测 |
| GET | `/api/v1/predictions/history` | 获取历史预测记录 |
| GET | `/api/v1/predictions/{id}` | 预测详情（含 prompt 和原始响应）|
| POST | `/api/v1/predictions/trigger` | 手动触发预测（管理员）|

**数据模型 - Prediction：**

```python
class Prediction(Base):
    id: int
    market_id: int                 # FK to Market
    
    predicted_probability: float   # AI predicted probability (0.01-0.99)
    confidence: float              # AI confidence level (0-1)
    direction: str                 # "bullish" | "bearish" | "neutral"
    
    key_factors: list[str]         # JSON array
    risk_factors: list[str]        # JSON array
    technical_analysis: str
    sentiment_analysis: str
    news_impact: str
    onchain_analysis: str
    reasoning: str                 # full reasoning text
    recommended_action: str        # "buy_yes" | "buy_no" | "skip"
    
    market_probability: float      # Polymarket Yes price at prediction time
    edge: float                    # predicted_probability - market_probability
    
    model_version: str             # "gpt-5.4"
    prompt_version: str            # "v1.0"  (track prompt iterations)
    seed: int                      # for reproducibility
    
    raw_request: dict              # full prompt sent to LLM
    raw_response: dict             # full LLM response
    data_snapshot: dict            # full MarketDataBundle as JSON
    
    tokens_used: int               # for cost tracking
    latency_ms: int                # API latency
    
    created_at: datetime
```

### 3.4 策略生成器 (Strategy Generator)

**职责：** 将 AI 预测转化为可执行的交易策略。

**核心套利约束：**

> **AI 预测概率与当前市场概率的偏差（绝对值）必须 ≥ 25%，才认为存在足够的套利空间执行交易。**
>
> 这是项目的核心交易准则：
> - Polymarket 是高效市场，小 edge 的预测大概率是噪声而非 alpha
> - 25% 的硬阈值过滤掉绝大多数"模糊判断"，只在 AI 确信市场严重错定价时下注
> - 同时要求 AI `confidence ≥ 0.6`，避免高 edge 但低置信的极端预测

**策略逻辑：**

```python
MIN_EDGE = 0.25         # absolute probability gap required to trade
MIN_CONFIDENCE = 0.6    # minimum AI confidence required

def generate_strategy(prediction, market, vault_balance):
    market_yes_price = market.current_yes_price
    edge = prediction.predicted_probability - market_yes_price
    abs_edge = abs(edge)
    
    # === HARD GATE 1: edge must be >= 25% ===
    if abs_edge < MIN_EDGE:
        return Strategy(
            action="skip",
            reason=f"Edge {abs_edge:.1%} < required {MIN_EDGE:.0%}"
        )
    
    # === HARD GATE 2: confidence must be >= 60% ===
    if prediction.confidence < MIN_CONFIDENCE:
        return Strategy(
            action="skip",
            reason=f"Confidence {prediction.confidence:.1%} < required {MIN_CONFIDENCE:.0%}"
        )
    
    # === HARD GATE 3: AI's recommended_action must align with edge sign ===
    expected_action = "buy_yes" if edge > 0 else "buy_no"
    if prediction.recommended_action != expected_action:
        return Strategy(
            action="skip",
            reason="AI recommendation conflicts with edge direction"
        )
    
    # Determine side
    side = "yes" if edge > 0 else "no"
    entry_price = market_yes_price if side == "yes" else (1 - market_yes_price)
    
    # Position sizing (fractional Kelly to limit drawdown)
    # f = (bp - q) / b where b=odds, p=predicted prob, q=1-p
    kelly_fraction = calculate_kelly(prediction, market) * 0.5  # half Kelly
    max_position = vault_balance * MAX_POSITION_PCT  # e.g. 10%
    position_size = min(kelly_fraction * vault_balance, max_position)
    
    # Take profit / Stop loss based on edge magnitude
    take_profit = entry_price + (abs_edge * TAKE_PROFIT_FACTOR)  # e.g. 70% of edge
    stop_loss = entry_price - (abs_edge * STOP_LOSS_FACTOR)      # e.g. 50% of edge
    
    return Strategy(
        action="buy_" + side,
        side=side,
        position_size=position_size,
        entry_price=entry_price,
        take_profit=take_profit,
        stop_loss=stop_loss,
        kelly_fraction=kelly_fraction,
        edge=edge,
    )
```

**决策矩阵：**

| AI 预测概率 | 市场概率 | 偏差 (abs) | Confidence | 决策 |
|------------|---------|------------|-----------|------|
| 0.62 | 0.76 | 14% | 0.74 | **skip** — 偏差不足 25% |
| 0.20 | 0.50 | 30% | 0.80 | **buy_no** — 偏差 30%，置信 80% |
| 0.85 | 0.55 | 30% | 0.55 | **skip** — 置信 < 60% |
| 0.90 | 0.60 | 30% | 0.75 | **buy_yes** — 满足所有条件 |
| 0.50 | 0.50 | 0% | 0.90 | **skip** — 无套利空间 |

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

**每日交易流水线（按顺序串行）：**

| 任务 | 调度时间 (UTC) | 目标 | 说明 |
|------|----------------|------|------|
| 市场扫描 | 00:00 | 选择 T+2 日的目标市场 | 扫描两天后结算的事件，找概率最接近 50% 的子市场 |
| 数据聚合 | 00:10 | 收集 LLM 输入数据 | K 线 + 技术指标 + 情绪 + 新闻 + 链上数据 |
| AI 预测 | 00:20 | GPT-5.4 输出预测 | Structured Output，含概率/置信度/推理 |
| 策略生成 | 00:25 | 决定交易方向和仓位 | 基于 edge + Kelly 公式 |
| 交易执行 | 00:30 | 通过 CLOB API 下单 | 限价单挂单，自动监控成交 |

**持续运行任务：**

| 任务 | 频率 | 说明 |
|------|------|------|
| 持仓监控 | 持续（10 秒间隔）| 实时价格监控，触发止盈止损 |
| 金库快照 | 每 1 小时 | 记录 TVL、份额价格用于前端图表 |
| 健康检查 | 每 5 分钟 | 调度器、监控器、外部 API 健康检查 |
| 市场结算同步 | 每 30 分钟 | 检查已到期市场的最终结算结果 |

**交易窗口示意：**

```
T 日 00:00 UTC  → 扫描，选定 T+2 日结算的市场
T 日 00:30 UTC  → 下单建仓
T 日 ~ T+2 日   → 持仓监控，触发止盈/止损
T+2 日 -30min   → 强制平仓（避开结算期波动）
T+2 日 16:00 ET → 市场结算，未平仓部分自动赎回
```

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
  min_edge: 0.25              # CORE RULE: predicted prob must differ from market by >= 25%
  min_confidence: 0.6         # minimum AI confidence to trade
  max_position_pct: 0.10      # max 10% of vault per trade
  kelly_multiplier: 0.5       # use half Kelly for safety
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
