from __future__ import annotations

from datetime import datetime
from typing import Any

import requests
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import AgentRunLog


AGENT_PROFILES = {
    "stock-research": "StockResearchAgent",
    "technical-analysis": "TechnicalAnalysisAgent",
    "generate-strategy": "StrategyGenerateAgent",
    "explain-backtest": "BacktestExplainAgent",
    "risk-review": "RiskReviewAgent",
    "data-quality-review": "DataQualityAgent",
    "model-iteration-review": "ModelIterationAgent",
}


class AgentService:
    def run(self, db: Session, agent_key: str, user_input: str, context: dict[str, Any] | None = None, related_entity_type: str | None = None, related_entity_id: int | None = None) -> dict[str, Any]:
        context = context or {}
        agent_name = AGENT_PROFILES.get(agent_key, agent_key)
        output = self._call_platform(agent_key, user_input, context) or self._simulate(agent_key, user_input, context)
        db.add(
            AgentRunLog(
                agent_name=agent_name,
                user_input=user_input,
                agent_output=output,
                tools_called_json=output.get("tools_called", []),
                related_entity_type=related_entity_type,
                related_entity_id=related_entity_id,
                status="success",
            )
        )
        db.commit()
        return output

    def _call_platform(self, agent_key: str, user_input: str, context: dict[str, Any]) -> dict[str, Any] | None:
        settings = get_settings()
        if not settings.bltcy_api_key:
            return None
        prompt = {
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": (
                        "你是 AIQuant 的量化研究智能体。只输出 JSON，不允许给出真实下单指令。"
                        f"\nagent_key={agent_key}\nuser_input={user_input}\ncontext={context}"
                    ),
                }
            ],
        }
        try:
            response = requests.post(
                f"{settings.bltcy_base_url.rstrip('/')}/{settings.bltcy_wire_api}",
                headers={"Authorization": f"Bearer {settings.bltcy_api_key}", "Content-Type": "application/json"},
                json={
                    "model": settings.bltcy_model,
                    "input": [prompt],
                    "text": {"format": {"type": "json_object"}},
                },
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
            return {
                "agent": AGENT_PROFILES.get(agent_key, agent_key),
                "generated_at": datetime.utcnow().isoformat(timespec="seconds"),
                "provider": settings.bltcy_name,
                "wire_api": settings.bltcy_wire_api,
                "raw_response": payload,
                "tools_called": ["bltcy_responses_api"],
            }
        except Exception as exc:
            return {
                "agent": AGENT_PROFILES.get(agent_key, agent_key),
                "generated_at": datetime.utcnow().isoformat(timespec="seconds"),
                "provider": settings.bltcy_name,
                "provider_error": str(exc),
                "fallback": self._simulate(agent_key, user_input, context),
                "tools_called": ["bltcy_responses_api", "local_fallback"],
            }

    def _simulate(self, agent_key: str, user_input: str, context: dict[str, Any]) -> dict[str, Any]:
        now = datetime.utcnow().isoformat(timespec="seconds")
        if agent_key == "generate-strategy":
            return {
                "agent": "StrategyGenerateAgent",
                "generated_at": now,
                "strategy_name": context.get("strategy_name") or "低估值趋势放量策略",
                "strategy_type": "factor_rule",
                "conditions": {
                    "pe_max": 25,
                    "pb_max": 3,
                    "roe_min": 0.10,
                    "price_above_ma20": True,
                    "volume_ratio_min": 1.5,
                    "max_drawdown_limit": 0.15,
                },
                "entry_rules": ["score >= 80", "risk_level != high"],
                "exit_rules": ["close < ma20", "stop_loss <= -0.08"],
                "status": "candidate",
                "can_train": False,
                "can_trade": False,
                "risk_level": "medium",
                "risk_notes": ["需要样本外验证", "放量突破策略在震荡市可能频繁失败"],
                "tools_called": ["policy_guardrail", "strategy_schema_builder"],
            }
        if agent_key == "explain-backtest":
            return {
                "agent": "BacktestExplainAgent",
                "generated_at": now,
                "summary": "该回测已绑定策略版本，收益需要与最大回撤、交易次数、超额收益一起判断。",
                "attribution": ["趋势因子贡献主要来自 MA20 上方持仓", "风险来自高波动区间回撤"],
                "risk_level": "medium",
                "tools_called": ["backtest_result_reader"],
            }
        if agent_key == "risk-review":
            return {
                "agent": "RiskReviewAgent",
                "generated_at": now,
                "risk_level": "medium",
                "checks": {"future_leakage": "not_detected", "overfit_risk": "requires_out_of_sample", "drawdown": "review_required"},
                "decision": "pending_review",
                "tools_called": ["risk_policy_check"],
            }
        if agent_key == "data-quality-review":
            return {
                "agent": "DataQualityAgent",
                "generated_at": now,
                "quality_score": 86,
                "issues": ["MVP 未接入完整财报公告日，财务因子仅作占位演示"],
                "dirty_data_action": "mark_if_source_error",
                "tools_called": ["missing_value_scan", "date_alignment_check"],
            }
        if agent_key == "model-iteration-review":
            return {
                "agent": "ModelIterationAgent",
                "generated_at": now,
                "recommendation": "keep_experiment",
                "reason": "当前模型适合作为可解释基线，需等待更多 approved 样本后再提升版本。",
                "tools_called": ["model_registry_reader"],
            }
        if agent_key == "technical-analysis":
            return {
                "agent": "TechnicalAnalysisAgent",
                "generated_at": now,
                "signals": {"ma_trend": "watch", "momentum": "neutral", "volume": "normal"},
                "risk_level": "low",
                "tools_called": ["factor_reader"],
            }
        return {
            "agent": "StockResearchAgent",
            "generated_at": now,
            "summary": "研究结论需要结合行业、估值、趋势和风险，当前输出仅作为候选研究记录。",
            "risk_level": "medium",
            "tools_called": ["stock_profile_reader"],
        }
