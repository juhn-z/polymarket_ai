"""AI Predictor — wraps GPT-5.4 to produce calibrated BTC probability forecasts.

Per PRD §3.3: uses OpenAI Structured Outputs. The prediction must include a
25% edge hard rule in the system prompt so the model is aware of the
downstream gating logic (actual gate enforcement lives in StrategyGenerator).
"""
from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.adapters.protocols import OpenAIClient
from app.domain.markets import Market
from app.domain.predictions import Prediction, PredictionDirection, PredictionRecommendation
from app.repositories.prediction_repository import PredictionRepository
from app.services.data_aggregator import MarketDataBundle

MODEL_VERSION = "gpt-5.4"
PROMPT_VERSION = "v1.0"
SEED = 42
MIN_EDGE_PCT = 25  # decimal 0.25 — keep the prompt wording in raw percent

SYSTEM_PROMPT = f"""\
You are a quantitative crypto market analyst with 10+ years of experience in
Bitcoin derivatives, on-chain analysis, and prediction markets.

Your task is to estimate the probability that BTC/USDT (Binance spot) closes
ABOVE a specific price threshold at a specific resolution time. You are NOT
predicting direction or magnitude — you are estimating a calibrated
probability between 0 and 1.

Critical rules you MUST follow:

1. Output a calibrated probability, not a confidence-weighted bet. If the
   data is genuinely ambiguous, output a probability close to the current
   market price rather than a strong opinion.

2. Use ONLY the data provided in the user message. Do NOT invent prices,
   indicators, or news that are not given.

3. Distinguish between:
   - "predicted_probability": your honest estimate of the true probability
   - "confidence": how reliable you think your estimate is given data quality
   These are independent — high confidence in 50% probability is valid.

4. Account for time-to-resolution. Markets resolving in 48 hours have less
   uncertainty than 7-day markets. Adjust accordingly.

5. Output ONLY valid JSON matching the provided schema. No markdown,
   no prose outside JSON.

6. The downstream system will ONLY trade when:
     abs(predicted_probability - market_yes_price) >= 0.{MIN_EDGE_PCT:02d}  AND  confidence >= 0.6
   If the data does not support a >={MIN_EDGE_PCT}% edge, set
   recommended_action to "skip" and report your honest probability.
"""

PREDICTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
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
        "recommended_action",
    ],
    "properties": {
        "predicted_probability": {"type": "number", "minimum": 0.01, "maximum": 0.99},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "direction": {"type": "string", "enum": ["bullish", "bearish", "neutral"]},
        "key_factors": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 5},
        "risk_factors": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 5},
        "technical_analysis": {"type": "string"},
        "sentiment_analysis": {"type": "string"},
        "news_impact": {"type": "string"},
        "onchain_analysis": {"type": "string"},
        "reasoning": {"type": "string"},
        "recommended_action": {"type": "string", "enum": ["buy_yes", "buy_no", "skip"]},
    },
}


class AIPredictor:
    def __init__(
        self,
        openai: OpenAIClient,
        repo: PredictionRepository,
        *,
        model: str = MODEL_VERSION,
        seed: int = SEED,
    ) -> None:
        self._openai = openai
        self._repo = repo
        self._model = model
        self._seed = seed

    async def predict(self, market: Market, bundle: MarketDataBundle) -> Prediction:
        user_prompt = _render_user_prompt(market, bundle)
        raw_request = {
            "model": self._model,
            "seed": self._seed,
            "system": SYSTEM_PROMPT,
            "user": user_prompt,
            "response_schema": PREDICTION_SCHEMA,
        }

        result = await self._openai.predict(
            system=SYSTEM_PROMPT,
            user=user_prompt,
            response_schema=PREDICTION_SCHEMA,
            seed=self._seed,
            model=self._model,
        )
        content = result.get("content", {})
        tokens_used = int(result.get("tokens_used", 0))
        latency_ms = int(result.get("latency_ms", 0))

        prediction = _build_prediction(
            market=market,
            bundle=bundle,
            content=content,
            raw_request=raw_request,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
            model=self._model,
            seed=self._seed,
        )
        return await self._repo.save(prediction)


def _render_user_prompt(market: Market, bundle: MarketDataBundle) -> str:
    """Serialize the MarketDataBundle into the structured text block defined in PRD §3.3.2."""
    hours_to_resolution = int((bundle.target_datetime - bundle.timestamp).total_seconds() // 3600)
    distance_pct = (
        (Decimal(str(market.price_threshold)) - bundle.btc_current_price)
        / bundle.btc_current_price
        * Decimal("100")
    )
    indicators_block = _format_indicators(bundle)
    sentiment_block = _format_sentiment(bundle)
    news_block = _format_news(bundle)

    return (
        "# MARKET QUESTION\n"
        f"Question: \"Will BTC/USDT (Binance) close ABOVE ${market.price_threshold} "
        f"at {bundle.target_datetime.isoformat()}?\"\n"
        f"Time to resolution: {hours_to_resolution} hours\n\n"
        "# CURRENT MARKET STATE (Polymarket)\n"
        f"Yes price: {market.current_yes_price} "
        f"(implied probability {_pct(market.current_yes_price)}%)\n"
        f"No price: {market.current_no_price}\n\n"
        "# CURRENT BTC PRICE\n"
        f"Spot price (Binance): ${bundle.btc_current_price}\n"
        f"Distance to threshold: {distance_pct:.2f}%\n"
        f"24h change: {bundle.price_change_24h}%\n"
        f"24h high/low: {bundle.high_24h} / {bundle.low_24h}\n\n"
        "# TECHNICAL INDICATORS\n"
        f"{indicators_block}\n\n"
        "# MARKET SENTIMENT\n"
        f"{sentiment_block}\n\n"
        "# NEWS HEADLINES\n"
        f"{news_block}\n\n"
        "# YOUR TASK\n"
        "Estimate the probability that the answer is YES. Output JSON matching the schema exactly."
    )


def _format_indicators(b: MarketDataBundle) -> str:
    parts = [f"RSI(14): {b.rsi_14 if b.rsi_14 is not None else 'n/a'}"]
    if b.macd is not None:
        parts.append(f"MACD: macd={b.macd.macd}, signal={b.macd.signal}, hist={b.macd.histogram}")
    else:
        parts.append("MACD: n/a")
    if b.bollinger is not None:
        parts.append(
            f"Bollinger: upper={b.bollinger.upper}, mid={b.bollinger.middle}, lower={b.bollinger.lower}"
        )
    else:
        parts.append("Bollinger: n/a")
    if b.ema is not None:
        parts.append(f"EMA: 7={b.ema.ema7}, 25={b.ema.ema25}, 99={b.ema.ema99}")
    else:
        parts.append("EMA: n/a")
    parts.append(f"ATR(14): {b.atr if b.atr is not None else 'n/a'}")
    return "\n".join(parts)


def _format_sentiment(b: MarketDataBundle) -> str:
    idx = b.fear_greed_index if b.fear_greed_index is not None else "n/a"
    label = b.fear_greed_label or "n/a"
    trend = ",".join(str(v) for v in b.fear_greed_trend_7d) if b.fear_greed_trend_7d else "n/a"
    return f"Fear & Greed: {idx}/100 ({label})\nF&G 7d trend: {trend}"


def _format_news(b: MarketDataBundle) -> str:
    if not b.news_headlines:
        return "(no recent news)"
    return "\n".join(
        f"{i+1}. {item.get('title', '?')} — {item.get('source', '?')}"
        for i, item in enumerate(b.news_headlines)
    )


def _pct(value: Decimal) -> str:
    return f"{(value * Decimal('100')).quantize(Decimal('0.01'))}"


def _build_prediction(
    *,
    market: Market,
    bundle: MarketDataBundle,
    content: dict[str, Any],
    raw_request: dict[str, Any],
    tokens_used: int,
    latency_ms: int,
    model: str,
    seed: int,
) -> Prediction:
    if market.id is None:
        raise ValueError("Cannot build Prediction for unsaved Market")

    try:
        predicted_probability = _require_decimal(content, "predicted_probability", Decimal("0.01"), Decimal("0.99"))
        confidence = _require_decimal(content, "confidence", Decimal("0"), Decimal("1"))
        direction = _require_enum(content, "direction", ("bullish", "bearish", "neutral"))
        key_factors = _require_string_list(content, "key_factors", min_len=2, max_len=5)
        risk_factors = _require_string_list(content, "risk_factors", min_len=2, max_len=5)
        technical_analysis = _require_str(content, "technical_analysis")
        sentiment_analysis = _require_str(content, "sentiment_analysis")
        news_impact = _require_str(content, "news_impact")
        onchain_analysis = _require_str(content, "onchain_analysis")
        reasoning = _require_str(content, "reasoning")
        recommended_action = _require_enum(content, "recommended_action", ("buy_yes", "buy_no", "skip"))
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError(f"OpenAI response does not match prediction schema: {exc}") from exc

    market_probability = market.current_yes_price
    edge = predicted_probability - market_probability

    return Prediction(
        market_id=market.id,
        predicted_probability=predicted_probability,
        confidence=confidence,
        direction=direction,  # type: ignore[arg-type]
        key_factors=key_factors,
        risk_factors=risk_factors,
        technical_analysis=technical_analysis,
        sentiment_analysis=sentiment_analysis,
        news_impact=news_impact,
        onchain_analysis=onchain_analysis,
        reasoning=reasoning,
        recommended_action=recommended_action,  # type: ignore[arg-type]
        market_probability=market_probability,
        edge=edge,
        model_version=model,
        prompt_version=PROMPT_VERSION,
        seed=seed,
        raw_request=raw_request,
        raw_response=content,
        data_snapshot=_bundle_to_snapshot(bundle),
        tokens_used=tokens_used,
        latency_ms=latency_ms,
        created_at=datetime.now(timezone.utc),
    )


def _require_decimal(payload: dict[str, Any], key: str, lo: Decimal, hi: Decimal) -> Decimal:
    raw = payload[key]
    value = Decimal(str(raw))
    if value < lo or value > hi:
        raise ValueError(f"{key}={value} outside [{lo}, {hi}]")
    return value


def _require_enum(payload: dict[str, Any], key: str, allowed: tuple[str, ...]) -> str:
    value = payload[key]
    if value not in allowed:
        raise ValueError(f"{key}={value!r} not in {allowed}")
    return value


def _require_str(payload: dict[str, Any], key: str) -> str:
    value = payload[key]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _require_string_list(payload: dict[str, Any], key: str, *, min_len: int, max_len: int) -> list[str]:
    raw = payload[key]
    if not isinstance(raw, list):
        raise ValueError(f"{key} must be a list")
    if len(raw) < min_len or len(raw) > max_len:
        raise ValueError(f"{key} must have {min_len}..{max_len} items, got {len(raw)}")
    items = []
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{key} items must be non-empty strings")
        items.append(item)
    return items


def _bundle_to_snapshot(bundle: MarketDataBundle) -> dict[str, Any]:
    """Convert bundle to JSON-serializable dict (Decimals → strings, dataclasses → dicts)."""
    def _convert(value: Any) -> Any:
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if is_dataclass(value) and not isinstance(value, type):
            return {k: _convert(v) for k, v in asdict(value).items()}
        if isinstance(value, dict):
            return {k: _convert(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_convert(v) for v in value]
        return value

    return {k: _convert(v) for k, v in asdict(bundle).items()}
