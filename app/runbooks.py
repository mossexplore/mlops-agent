from __future__ import annotations

from typing import Any, Dict, List, Optional

from .database import get_runbook, list_runbooks, update_runbook_status, upsert_runbook


RUNBOOK_STATUSES = {"draft", "review", "published", "archived"}
RUNBOOK_SEVERITIES = {"P0", "P1", "P2", "P3", "P4"}
STEP_ACTION_TYPES = {"check", "tool", "manual", "confirm", "verify"}
RISK_LEVELS = {"low", "medium", "high"}


def _validate_runbook_payload(status: str, severity: str, steps: List[Dict[str, Any]]) -> None:
    if status not in RUNBOOK_STATUSES:
        raise ValueError(f"Unsupported runbook status: {status}")
    if severity not in RUNBOOK_SEVERITIES:
        raise ValueError(f"Unsupported runbook severity: {severity}")
    for step in steps:
        action_type = step.get("actionType") or "check"
        risk_level = step.get("riskLevel") or "low"
        if action_type not in STEP_ACTION_TYPES:
            raise ValueError(f"Unsupported runbook step action type: {action_type}")
        if risk_level not in RISK_LEVELS:
            raise ValueError(f"Unsupported runbook step risk level: {risk_level}")


def list_runbook_workspace(
    status: Optional[str] = None,
    service: Optional[str] = None,
    scenario: Optional[str] = None,
    query: Optional[str] = None,
) -> List[Dict[str, Any]]:
    return list_runbooks(status=status, service=service, scenario=scenario, query=query)


def get_runbook_detail(runbook_id: str) -> Optional[Dict[str, Any]]:
    return get_runbook(runbook_id)


def save_runbook_workspace(
    title: str,
    service: str,
    scenario: str,
    severity: str,
    status: str,
    owner: Optional[str],
    version: str,
    trigger: Optional[str],
    summary: Optional[str],
    verification: Optional[str],
    escalation: Optional[str],
    risk_controls: List[str],
    tags: List[str],
    related_knowledge: List[str],
    steps: List[Dict[str, Any]],
    runbook_id: Optional[str] = None,
) -> Dict[str, Any]:
    _validate_runbook_payload(status, severity, steps)
    return upsert_runbook(
        runbook_id=runbook_id,
        title=title,
        service=service,
        scenario=scenario,
        severity=severity,
        status=status,
        owner=owner,
        version=version,
        trigger=trigger,
        summary=summary,
        verification=verification,
        escalation=escalation,
        risk_controls=risk_controls,
        tags=tags,
        related_knowledge=related_knowledge,
        steps=steps,
    )


def change_runbook_status(runbook_id: str, status: str) -> Optional[Dict[str, Any]]:
    if status not in RUNBOOK_STATUSES:
        raise ValueError(f"Unsupported runbook status: {status}")
    return update_runbook_status(runbook_id, status)
