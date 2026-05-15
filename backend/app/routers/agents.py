from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AgentRunLog, DatasetVersion, QuantModelVersion, TrainingSample
from ..schemas import AgentRequest
from ..serializers import model_to_dict
from ..services.agent_service import AGENT_PROFILES, AgentService

router = APIRouter(prefix="/agents", tags=["agents"])
service = AgentService()

AGENT_CATALOG: dict[str, dict[str, Any]] = {
    "generate-strategy": {
        "label": "策略生成智能体",
        "role": "把研究想法转为候选策略规则和风险边界。",
        "auto_task": "由策略实验室或研究闭环触发，也可手动运行。",
    },
    "explain-backtest": {
        "label": "回测解释智能体",
        "role": "解释收益、回撤、交易次数和信号行为。",
        "auto_task": "回测完成后自动触发解释。",
    },
    "risk-review": {
        "label": "风险复核智能体",
        "role": "检查未来函数、过拟合、回撤和真实交易边界。",
        "auto_task": "策略版本和回测结果生成后自动触发。",
    },
    "data-quality-review": {
        "label": "数据质量智能体",
        "role": "检查缺失、异常、污染和样本可训练性。",
        "auto_task": "数据模型运行或样本审核前后触发。",
    },
    "model-iteration-review": {
        "label": "模型迭代智能体",
        "role": "评估模型是否值得保留、调参、废弃或晋升。",
        "auto_task": "训练样本增加或回测结果更新后触发。",
    },
    "stock-research": {
        "label": "股票研究智能体",
        "role": "生成股票基本研究摘要和观察重点。",
        "auto_task": "总控选择股票后可手动触发，后续适合定时运行。",
    },
    "technical-analysis": {
        "label": "技术分析智能体",
        "role": "读取行情和因子，输出趋势、动量、成交量和风险观察。",
        "auto_task": "股票监测刷新后可触发，当前以手动和闭环调用为主。",
    },
}


@router.get("/logs")
def list_agent_logs(db: Session = Depends(get_db)):
    rows = db.scalars(select(AgentRunLog).order_by(AgentRunLog.created_at.desc()).limit(100)).all()
    return {"rows": [model_to_dict(row) for row in rows]}


@router.get("/monitor")
def monitor_agents(db: Session = Depends(get_db)):
    rows = db.scalars(select(AgentRunLog).order_by(AgentRunLog.created_at.desc()).limit(300)).all()
    approved_samples = db.scalar(select(func.count()).select_from(TrainingSample).where(TrainingSample.status == "approved", TrainingSample.can_train.is_(True))) or 0
    datasets = db.scalars(select(DatasetVersion).order_by(DatasetVersion.created_at.desc()).limit(20)).all()
    models = db.scalars(select(QuantModelVersion).order_by(QuantModelVersion.created_at.desc()).limit(20)).all()
    now = datetime.utcnow()

    agents = []
    for key, profile in AGENT_PROFILES.items():
        agent_logs = [row for row in rows if row.agent_name == profile]
        success = sum(1 for row in agent_logs if row.status == "success")
        failed = sum(1 for row in agent_logs if row.status and row.status != "success")
        latest = agent_logs[0] if agent_logs else None
        recent_24h = sum(1 for row in agent_logs if row.created_at and row.created_at >= now - timedelta(days=1))
        provider_calls = sum(1 for row in agent_logs if "bltcy_responses_api" in (row.tools_called_json or []))
        fallback_calls = sum(1 for row in agent_logs if "local_fallback" in (row.tools_called_json or []))
        agents.append(
            {
                "key": key,
                "agent_name": profile,
                "label": AGENT_CATALOG.get(key, {}).get("label", profile),
                "role": AGENT_CATALOG.get(key, {}).get("role", ""),
                "auto_task": AGENT_CATALOG.get(key, {}).get("auto_task", ""),
                "status": "active" if latest else "idle",
                "run_count": len(agent_logs),
                "recent_24h": recent_24h,
                "success_count": success,
                "failed_count": failed,
                "success_rate": round(success / max(1, len(agent_logs)), 4),
                "provider_calls": provider_calls,
                "fallback_calls": fallback_calls,
                "last_run_at": latest.created_at if latest else None,
                "last_output": latest.agent_output if latest else None,
                "related_entity_type": latest.related_entity_type if latest else None,
                "related_entity_id": latest.related_entity_id if latest else None,
            }
        )

    return {
        "agents": agents,
        "logs": [model_to_dict(row) for row in rows[:80]],
        "learning": {
            "approved_samples": approved_samples,
            "dataset_count": len(datasets),
            "model_count": len(models),
            "latest_dataset": model_to_dict(datasets[0]) if datasets else None,
            "latest_model": model_to_dict(models[0]) if models else None,
            "progress_text": "当前学习闭环以 approved + can_train 样本作为训练输入；智能体负责生成、解释、复核和迭代建议，不直接晋升模型。",
        },
        "automation": {
            "mode": "event_driven_mvp",
            "description": "当前自动运行发生在研究闭环、总控执行、回测解释和风控复核等事件中；尚未启用独立后台定时调度器。",
            "recommended_next": "后续应增加任务调度表和后台 worker，让数据质量、技术分析、模型迭代智能体按日线收盘后自动运行。",
        },
    }


def _run(agent_key: str, payload: AgentRequest, db: Session):
    return service.run(db, agent_key, payload.user_input, payload.context, payload.related_entity_type, payload.related_entity_id)


for key in AGENT_PROFILES:

    async def endpoint(payload: AgentRequest, db: Session = Depends(get_db), agent_key: str = key):
        return _run(agent_key, payload, db)

    endpoint.__name__ = f"run_{key.replace('-', '_')}"
    router.post(f"/{key}")(endpoint)
