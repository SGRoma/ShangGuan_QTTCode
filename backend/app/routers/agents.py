from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AgentRunLog
from ..schemas import AgentRequest
from ..serializers import model_to_dict
from ..services.agent_service import AGENT_PROFILES, AgentService

router = APIRouter(prefix="/agents", tags=["agents"])
service = AgentService()


@router.get("/logs")
def list_agent_logs(db: Session = Depends(get_db)):
    rows = db.scalars(select(AgentRunLog).order_by(AgentRunLog.created_at.desc()).limit(100)).all()
    return {"rows": [model_to_dict(row) for row in rows]}


def _run(agent_key: str, payload: AgentRequest, db: Session):
    return service.run(db, agent_key, payload.user_input, payload.context, payload.related_entity_type, payload.related_entity_id)


for key in AGENT_PROFILES:

    async def endpoint(payload: AgentRequest, db: Session = Depends(get_db), agent_key: str = key):
        return _run(agent_key, payload, db)

    endpoint.__name__ = f"run_{key.replace('-', '_')}"
    router.post(f"/{key}")(endpoint)
