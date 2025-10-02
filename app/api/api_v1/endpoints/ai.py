from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Any

from ....models.user import User
from ....models.project import Project
from ....models.ai import AIRisk, AIInsight, AIMeetingSummary, AIScenario, AIForecast
from ....schemas.ai import (
    RiskRequest, RiskResponse,
    ResourceOptimizationRequest, ResourceOptimizationResult,
    WorkflowAutomationRequest, WorkflowAutomationResult,
    NLCommand, NLResult,
    MeetingSummaryRequest, MeetingSummaryResult,
    ScenarioRequest, ScenarioResult,
    ForecastRequest, ForecastResult,
)
from ...deps_tenant import get_current_active_user_master, get_tenant_db
from ...deps_tenant import get_current_organization_master
from ....services.grok_client import GrokClient

router = APIRouter()

@router.post("/risk/predict", response_model=RiskResponse)
async def predict_risk(
    payload: RiskRequest,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    # Ensure project exists
    proj = await db.execute(select(Project).where(Project.id == payload.project_id))
    if not proj.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    # Call Grok to get explainable risk
    client = GrokClient()
    prompt = f"Predict project risk with score (0-100), severity, explanation and factors. Context: {payload.context}"
    result = await client.extract("keys: score (0-100), severity, explanation, factors(object)", prompt)
    score = float(result.get("score", 0))
    severity = result.get("severity", "low")
    explanation = result.get("explanation", "")
    factors = result.get("factors", {})

    risk = AIRisk(project_id=payload.project_id, task_id=payload.task_id, risk_type="composite", score=score,
                  severity=severity, explanation=explanation, factors=factors)
    db.add(risk)
    await db.commit()
    await db.refresh(risk)

    return RiskResponse(
        risk_id=risk.id,
        score=risk.score,
        severity=risk.severity,
        explanation=risk.explanation or "",
        factors=risk.factors or {},
    )

@router.post("/resources/optimize", response_model=ResourceOptimizationResult)
async def optimize_resources(
    payload: ResourceOptimizationRequest,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    client = GrokClient()
    import json
    prompt = f"""
You are a resource optimizer. Given candidates and tasks, match tasks to users minimizing overload and maximizing skill fit.
Respond as JSON with assignments:[{{task_id,user_id,rationale}}] and conflicts:[{{task_id,reason}}].
Candidates: {json.dumps(payload.candidates)}
Tasks: {json.dumps(payload.tasks)}
"""
    resp = await client.chat(prompt, system="Resource optimizer")
    try:
        data = json.loads(resp)
    except Exception:
        data = {"assignments": [], "conflicts": [], "raw": resp}
    return ResourceOptimizationResult(assignments=data.get("assignments", []), conflicts=data.get("conflicts", []))

@router.post("/workflow/automate", response_model=WorkflowAutomationResult)
async def automate_workflow(
    payload: WorkflowAutomationRequest,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
):
    # Compose context (lightweight):
    context = {"project_id": payload.project_id, "user_id": current_user.id}
    client = GrokClient()
    plan = await client.plan(payload.instruction, context)
    return WorkflowAutomationResult(actions=plan.get("actions", []))

@router.post("/nl/command", response_model=NLResult)
async def natural_language_command(
    payload: NLCommand,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
):
    client = GrokClient()
    context = {"project_id": payload.project_id, "user_id": current_user.id}
    plan = await client.plan(payload.prompt, context)
    return NLResult(actions=plan.get("actions", []), summary=None)

@router.post("/meeting/summarize", response_model=MeetingSummaryResult)
async def summarize_meeting(
    payload: MeetingSummaryRequest,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
):
    client = GrokClient()
    extraction = await client.extract(
        "keys: summary(string), action_items(array of {title,assignee_id?,due_date?}), decisions(array of string), sentiments(object)",
        payload.transcript,
    )
    ms = AIMeetingSummary(
        project_id=payload.project_id,
        summary=extraction.get("summary", ""),
        action_items=extraction.get("action_items", []),
        decisions=extraction.get("decisions", []),
        sentiments=extraction.get("sentiments", {}),
    )
    db.add(ms)
    await db.commit()
    return MeetingSummaryResult(
        summary=ms.summary or "",
        action_items=ms.action_items or [],
        decisions=ms.decisions or [],
        sentiments=ms.sentiments or {},
    )

@router.post("/scenario/what-if", response_model=ScenarioResult)
async def scenario_what_if(
    payload: ScenarioRequest,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
):
    client = GrokClient()
    import json
    prompt = f"Provide JSON impact and recommendation for assumptions: {json.dumps(payload.assumptions)}"
    extraction = await client.extract(
        "keys: impact(object), recommendation(string)", prompt
    )
    sc = AIScenario(
        project_id=payload.project_id,
        title="What-if",
        assumptions=payload.assumptions,
        impact=extraction.get("impact", {}),
        recommendation=extraction.get("recommendation", ""),
    )
    db.add(sc)
    await db.commit()
    return ScenarioResult(impact=sc.impact or {}, recommendation=sc.recommendation or "")

@router.post("/forecast/predict", response_model=ForecastResult)
async def forecast_predict(
    payload: ForecastRequest,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
):
    client = GrokClient()
    import json
    prompt = f"Forecast {payload.forecast_type} with confidence based on inputs: {json.dumps(payload.inputs)}. Return JSON with outputs(object), confidence(number 0-1)."
    extraction = await client.extract("keys: outputs(object), confidence(number)", prompt)
    fc = AIForecast(
        project_id=payload.project_id,
        forecast_type=payload.forecast_type,
        inputs=payload.inputs,
        outputs=extraction.get("outputs", {}),
    )
    db.add(fc)
    await db.commit()
    return ForecastResult(outputs=fc.outputs or {}, confidence=float(extraction.get("confidence", 0.5)))

