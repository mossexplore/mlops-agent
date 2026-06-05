from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .database import (
    annotate_feedback_review,
    connect,
    get_agent_trace,
    list_ab_experiments,
    list_eval_cases,
    list_eval_runs,
    list_feedback_reviews,
    save_eval_run,
    upsert_ab_experiment,
    upsert_eval_case,
)
from .diagnostics import run_diagnostic_agent
from .knowledge import retrieve_knowledge, should_use_local_knowledge


QUALITY_REASONS = {"knowledge_missing", "retrieval_error", "generic_answer", "unactionable_steps", "scene_misclassification"}


@dataclass
class EvalContext:
    userId: str = "eval-user"
    conversationId: str = "eval-conversation"
    service: str = "Wise"
    scene: str = "模型任务"
    title: str = "质量评测"


def list_feedback_workspace(status: Optional[str] = None, page: int = 1, page_size: int = 20) -> List[Dict[str, Any]]:
    return list_feedback_reviews(status=status, page=page, page_size=page_size)


def annotate_feedback(
    answer_message_id: str,
    user_id: str,
    conversation_id: str,
    quality_reason: str,
    status: str = "open",
    annotation: Optional[str] = None,
    reviewer: Optional[str] = None,
) -> Dict[str, Any]:
    if quality_reason not in QUALITY_REASONS:
        raise ValueError(f"Unsupported quality reason: {quality_reason}")
    return annotate_feedback_review(
        answer_message_id=answer_message_id,
        user_id=user_id,
        conversation_id=conversation_id,
        quality_reason=quality_reason,
        status=status,
        annotation=annotation,
        reviewer=reviewer,
    )


def create_eval_case_from_feedback(
    answer_message_id: str,
    user_id: str,
    conversation_id: str,
    title: Optional[str] = None,
    expected_answer: Optional[str] = None,
    required_steps: Optional[List[str]] = None,
    forbidden_content: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    feedback = next(
        (
            item
            for item in list_feedback_reviews(page=1, page_size=500)
            if item["answerMessageId"] == answer_message_id
            and item["userId"] == user_id
            and item["conversationId"] == conversation_id
        ),
        None,
    )
    if not feedback:
        raise ValueError("Feedback record not found")
    reason_tags = feedback.get("feedbackReason", {}) or {}
    inferred_tags = tags or reason_tags.get("feedbackInfoTypes") or []
    case = upsert_eval_case(
        title=title or feedback["query"][:48] or "来自点踩反馈的评测用例",
        query=feedback["query"],
        expected_answer=expected_answer,
        required_steps=required_steps or _infer_required_steps(feedback["query"], feedback["qualityReason"]),
        forbidden_content=forbidden_content or ["无法确认但直接下结论", "编造平台日志", "跳过人工确认"],
        tags=inferred_tags,
        source_feedback_id=answer_message_id,
    )
    annotate_feedback_review(
        answer_message_id=answer_message_id,
        user_id=user_id,
        conversation_id=conversation_id,
        quality_reason=feedback["qualityReason"] if feedback["qualityReason"] != "未标注" else "generic_answer",
        status="converted",
        annotation=feedback.get("annotation"),
        reviewer=feedback.get("reviewer"),
        eval_case_id=case["caseId"],
    )
    return case


def _infer_required_steps(query: str, quality_reason: str) -> List[str]:
    lower = query.lower()
    steps = ["问题识别", "场景判断", "根因候选", "建议动作", "风险提示"]
    if any(token in lower for token in ("内存", "oom", "memory", "1401027")):
        steps.extend(["查看 OOM 事件", "检查 request/limit", "降低 batch size"])
    if quality_reason == "knowledge_missing":
        steps.append("说明知识库缺口")
    if quality_reason == "retrieval_error":
        steps.append("给出来源或说明未命中")
    return steps


def score_answer(answer: str, case: Dict[str, Any], knowledge_hit: bool) -> Dict[str, Any]:
    normalized = answer.lower()
    required = case.get("requiredSteps") or []
    forbidden = case.get("forbiddenContent") or []
    required_hits = [step for step in required if step.lower() in normalized or step in answer]
    forbidden_hits = [item for item in forbidden if item.lower() in normalized or item in answer]
    has_actions = bool(re.search(r"建议动作|查看|检查|确认|降低|补充|执行前", answer))
    has_risk = "风险提示" in answer or "人工确认" in answer or "不确定" in answer
    no_answer = any(token in answer for token in ("未命中", "无法基于现有", "证据不足"))
    required_score = len(required_hits) / len(required) if required else 1
    score = 0.5 * required_score + 0.2 * float(has_actions) + 0.15 * float(has_risk) + 0.15 * float(knowledge_hit)
    if forbidden_hits:
        score -= 0.25
    score = max(0, min(score, 1))
    return {
        "score": round(score, 4),
        "passed": score >= 0.72 and not forbidden_hits,
        "checks": {
            "requiredHitCount": len(required_hits),
            "requiredTotal": len(required),
            "requiredHits": required_hits,
            "forbiddenHits": forbidden_hits,
            "hasExecutableActions": has_actions,
            "hasRiskWarning": has_risk,
            "knowledgeHit": knowledge_hit,
            "noAnswer": no_answer,
        },
    }


def run_eval_suite(
    name: str,
    variant: str = "baseline",
    prompt_version: Optional[str] = None,
    retrieval_threshold: Optional[float] = None,
    model: Optional[str] = None,
    case_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    cases = list_eval_cases(status="active", page=1, page_size=500)
    if case_ids:
        wanted = set(case_ids)
        cases = [case for case in cases if case["caseId"] in wanted]
    run_id = str(uuid.uuid4())
    results: List[Dict[str, Any]] = []
    context = EvalContext(conversationId=f"eval-{run_id}")
    for case in cases:
        start = time.perf_counter()
        try:
            knowledge_results = retrieve_knowledge(case["query"], top_k=5)
            grounded = should_use_local_knowledge(case["query"], knowledge_results)
            diagnostic = run_diagnostic_agent(
                query=case["query"],
                context=context,
                query_message_id=str(uuid.uuid4()),
                answer_message_id=str(uuid.uuid4()),
                knowledge_results=knowledge_results if grounded else [],
                previous_state=None,
                need_deep_thinking=0,
            )
            answer = diagnostic["answer"]
            scored = score_answer(answer, case, knowledge_hit=bool(grounded and knowledge_results))
            results.append(
                {
                    "caseId": case["caseId"],
                    "answer": answer,
                    "score": scored["score"],
                    "passed": scored["passed"],
                    "checks": scored["checks"],
                    "knowledgeHit": bool(grounded and knowledge_results),
                    "totalMs": int((time.perf_counter() - start) * 1000),
                }
            )
        except Exception as exc:  # noqa: BLE001 - persisted as eval result
            results.append(
                {
                    "caseId": case["caseId"],
                    "answer": "",
                    "score": 0,
                    "passed": False,
                    "checks": {"error": str(exc)},
                    "knowledgeHit": False,
                    "error": str(exc),
                    "totalMs": int((time.perf_counter() - start) * 1000),
                }
            )
    case_count = len(results)
    pass_count = sum(1 for item in results if item["passed"])
    avg_score = round(sum(item["score"] for item in results) / case_count, 4) if case_count else 0
    knowledge_hit_rate = round(sum(1 for item in results if item["knowledgeHit"]) / case_count, 4) if case_count else 0
    run = {
        "runId": run_id,
        "name": name,
        "variant": variant,
        "promptVersion": prompt_version,
        "retrievalThreshold": retrieval_threshold,
        "model": model,
        "caseCount": case_count,
        "passCount": pass_count,
        "avgScore": avg_score,
        "knowledgeHitRate": knowledge_hit_rate,
    }
    return save_eval_run(run, results)


def get_quality_metrics() -> Dict[str, Any]:
    with connect() as conn:
        summary = conn.execute(
            """
            SELECT
              COUNT(DISTINCT CASE WHEN m.type IN ('user', 'query') THEN m.memory_id END) AS question_count,
              COUNT(DISTINCT CASE WHEN m.type IN ('assistant', 'answer') THEN m.memory_id END) AS answer_count,
              COUNT(DISTINCT CASE WHEN f.feedback = 'like' THEN f.answer_message_id END) AS like_count,
              COUNT(DISTINCT CASE WHEN f.feedback = 'unlike' THEN f.answer_message_id END) AS unlike_count,
              AVG(t.total_ms) AS avg_latency_ms
            FROM t_chat_memory AS m
            LEFT JOIN t_chat_feedback AS f
              ON f.answer_message_id = m.memory_id
             AND f.user_id = m.user_id
             AND f.conversation_id = m.conversation_id
            LEFT JOIN t_agent_trace AS t
              ON t.answer_message_id = m.memory_id
            """
        ).fetchone()
        knowledge_questions = conn.execute(
            "SELECT COUNT(DISTINCT query) AS count FROM t_knowledge_hit WHERE channel = 'chat'"
        ).fetchone()
        no_answer = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM t_agent_trace
            WHERE answer LIKE '%未命中%' OR answer LIKE '%证据不足%' OR answer LIKE '%无法基于现有%'
            """
        ).fetchone()
        duplicate = conn.execute(
            """
            SELECT COUNT(*) AS duplicate_count
            FROM (
              SELECT lower(trim(content)) AS normalized, COUNT(*) AS c
              FROM t_chat_memory
              WHERE type IN ('user', 'query')
              GROUP BY lower(trim(content))
              HAVING c > 1
            )
            """
        ).fetchone()
    question_count = (summary["question_count"] if summary else 0) or 0
    answer_count = (summary["answer_count"] if summary else 0) or 0
    like_count = (summary["like_count"] if summary else 0) or 0
    unlike_count = (summary["unlike_count"] if summary else 0) or 0
    feedback_count = like_count + unlike_count
    return {
        "questionCount": question_count,
        "answerCount": answer_count,
        "knowledgeHitRate": round(((knowledge_questions["count"] if knowledge_questions else 0) or 0) / question_count, 4) if question_count else 0,
        "satisfactionRate": round(like_count / feedback_count, 4) if feedback_count else 0,
        "unlikeRate": round(unlike_count / feedback_count, 4) if feedback_count else 0,
        "noAnswerRate": round(((no_answer["count"] if no_answer else 0) or 0) / answer_count, 4) if answer_count else 0,
        "repeatQuestionRate": round(((duplicate["duplicate_count"] if duplicate else 0) or 0) / question_count, 4) if question_count else 0,
        "avgLatencyMs": round((summary["avg_latency_ms"] if summary else 0) or 0, 2),
    }


def create_or_update_experiment(
    name: str,
    variants: List[str],
    traffic_split: Dict[str, float],
    primary_metric: str = "satisfactionRate",
    status: str = "draft",
    notes: Optional[str] = None,
    experiment_id: Optional[str] = None,
) -> Dict[str, Any]:
    return upsert_ab_experiment(
        name=name,
        variants=variants,
        traffic_split=traffic_split,
        primary_metric=primary_metric,
        status=status,
        notes=notes,
        experiment_id=experiment_id,
    )


def get_quality_dashboard() -> Dict[str, Any]:
    return {
        "metrics": get_quality_metrics(),
        "feedback": list_feedback_workspace(page=1, page_size=10),
        "evalCases": list_eval_cases(status="active", page=1, page_size=10),
        "evalRuns": list_eval_runs(page=1, page_size=10),
        "experiments": list_ab_experiments()[:10],
        "qualityReasons": sorted(QUALITY_REASONS),
    }
