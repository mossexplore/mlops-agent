from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .agent import build_answer


RISK_KEYWORDS = ("删除", "重启", "扩容", "缩容", "停机", "回滚", "清空", "kill", "delete", "restart", "scale")
RESOURCE_KEYWORDS = ("oom", "内存", "memory", "显存", "gpu", "cpu", "资源", "1401027")
LOG_KEYWORDS = ("日志", "log", "报错", "error", "exception", "traceback")
SCHEDULING_KEYWORDS = ("调度", "队列", "pending", "节点", "quota", "配额")
IMAGE_KEYWORDS = ("镜像", "image", "版本", "依赖", "cuda", "环境")


def now_iso() -> str:
    return datetime.now().isoformat(timespec="milliseconds")


@dataclass
class SpanRecorder:
    trace_id: str
    spans: List[Dict[str, Any]] = field(default_factory=list)

    def record(
        self,
        name: str,
        kind: str,
        input_data: Any,
        output_data: Any,
        status: str = "ok",
        error: Optional[str] = None,
        parent_span_id: Optional[str] = None,
        started_at: Optional[str] = None,
        start_perf: Optional[float] = None,
    ) -> Dict[str, Any]:
        end_perf = time.perf_counter()
        ended_at = now_iso()
        span = {
            "spanId": str(uuid.uuid4()),
            "traceId": self.trace_id,
            "parentSpanId": parent_span_id,
            "name": name,
            "kind": kind,
            "input": input_data,
            "output": output_data,
            "status": status,
            "durationMs": int((end_perf - (start_perf or end_perf)) * 1000),
            "error": error,
            "startedAt": started_at or ended_at,
            "endedAt": ended_at,
        }
        self.spans.append(span)
        return span


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(keyword in lower or keyword in text for keyword in keywords)


def identify_problem(query: str) -> Dict[str, Any]:
    normalized = query.strip()
    signals: List[str] = []
    if "1401027" in normalized or "insufficient memory" in normalized.lower():
        signals.append("1401027 insufficient memory")
    if _contains_any(normalized, RESOURCE_KEYWORDS):
        signals.append("资源不足/OOM")
    if _contains_any(normalized, LOG_KEYWORDS):
        signals.append("日志报错")
    if _contains_any(normalized, SCHEDULING_KEYWORDS):
        signals.append("调度/配额")
    if _contains_any(normalized, IMAGE_KEYWORDS):
        signals.append("镜像/环境")
    return {
        "problem": normalized or "未提供问题",
        "signals": signals or ["需要补充错误码、任务 ID 或日志片段"],
        "confidence": "high" if signals else "low",
    }


def judge_scene(query: str, context: Any, previous_state: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    scene = getattr(context, "scene", "") or "模型任务"
    service = getattr(context, "service", "") or "Wise"
    if _contains_any(query, RESOURCE_KEYWORDS):
        category = "resource"
    elif _contains_any(query, SCHEDULING_KEYWORDS):
        category = "scheduling"
    elif _contains_any(query, IMAGE_KEYWORDS):
        category = "runtime"
    elif _contains_any(query, LOG_KEYWORDS):
        category = "log"
    else:
        category = "unknown"
    return {
        "service": service,
        "scene": scene,
        "category": category,
        "previousStep": previous_state.get("currentStep") if previous_state else None,
        "previousSummary": previous_state.get("summary") if previous_state else None,
    }


def run_guardrails(query: str, knowledge_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    guardrails: List[Dict[str, Any]] = []
    risky = _contains_any(query, RISK_KEYWORDS)
    guardrails.append(
        {
            "name": "dangerous_operation_confirmation",
            "passed": not risky,
            "severity": "high" if risky else "low",
            "message": "涉及删除、重启、扩缩容、回滚等操作时必须由人工确认后执行。" if risky else "未发现高风险操作请求。",
        }
    )
    has_platform_data = any(token in query.lower() for token in ("任务id", "job", "run id", "实例", "pod", "container"))
    guardrails.append(
        {
            "name": "no_platform_data_fabrication",
            "passed": True,
            "severity": "medium",
            "message": "当前未接入真实 MLOps 平台工具，不能编造任务日志、指标或调度事件；只能基于用户输入和知识库片段推理。",
            "needsMoreEvidence": not has_platform_data,
        }
    )
    guardrails.append(
        {
            "name": "retrieval_grounding",
            "passed": bool(knowledge_results),
            "severity": "medium" if not knowledge_results else "low",
            "message": "已命中已发布知识片段。" if knowledge_results else "未命中可靠知识片段，答案会明确提示不确定性。",
        }
    )
    return guardrails


def plan_tool_calls(query: str, context: Any) -> List[Dict[str, Any]]:
    conversation_id = getattr(context, "conversationId", "")
    candidates = [
        ("task_status", "查询任务状态", _contains_any(query, ("任务", "job", "状态", "失败", "pending"))),
        ("task_logs", "查询任务日志", _contains_any(query, LOG_KEYWORDS)),
        ("resource_metrics", "查询资源指标", _contains_any(query, RESOURCE_KEYWORDS)),
        ("image_version", "查询镜像版本", _contains_any(query, IMAGE_KEYWORDS)),
        ("scheduling_events", "查询调度事件", _contains_any(query, SCHEDULING_KEYWORDS)),
    ]
    calls = []
    for tool_name, description, relevant in candidates:
        if not relevant:
            continue
        calls.append(
            {
                "tool": tool_name,
                "description": description,
                "status": "planned_not_executed",
                "reason": "当前版本尚未接入真实 MLOps 平台，只记录待接入工具意图。",
                "conversationId": conversation_id,
            }
        )
    return calls


def root_cause_candidates(problem: Dict[str, Any], scene: Dict[str, Any], knowledge_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    category = scene["category"]
    if category == "resource":
        candidates.extend(
            [
                {"cause": "容器 memory limit/request 偏低或节点剩余资源不足", "confidence": "high"},
                {"cause": "batch size、num_workers、prefetch 或缓存策略导致峰值内存过高", "confidence": "medium"},
                {"cause": "数据预处理或 checkpoint 加载阶段瞬时占用过高", "confidence": "medium"},
            ]
        )
    elif category == "scheduling":
        candidates.extend(
            [
                {"cause": "队列资源配额不足或节点标签/污点不满足调度条件", "confidence": "medium"},
                {"cause": "任务 request 超过可用资源，长时间 Pending", "confidence": "medium"},
            ]
        )
    elif category == "runtime":
        candidates.extend(
            [
                {"cause": "镜像依赖、CUDA/驱动或启动命令与任务配置不匹配", "confidence": "medium"},
                {"cause": "最近镜像版本变更引入兼容性问题", "confidence": "medium"},
            ]
        )
    elif category == "log":
        candidates.append({"cause": "日志中存在未解析的异常堆栈，需要补充关键错误上下文", "confidence": "low"})
    else:
        candidates.append({"cause": "当前证据不足，需补充错误码、任务 ID、日志或资源监控截图", "confidence": "low"})

    if knowledge_results:
        top = knowledge_results[0]
        candidates.append(
            {
                "cause": f"知识库命中 `{Path(top.get('source', '')).name}` 的 `{top.get('heading') or '未命名章节'}`，建议优先按该 runbook 排查。",
                "confidence": "medium",
            }
        )
    return candidates


def recommended_actions(scene: Dict[str, Any], tools: List[Dict[str, Any]]) -> List[str]:
    actions = []
    if scene["category"] == "resource":
        actions.extend(
            [
                "先查看任务实例 OOM 事件、内存峰值、容器 limit/request 和节点剩余资源。",
                "临时降低 batch size、num_workers、prefetch factor，关闭不必要缓存后小样本复现。",
                "若确认资源不足，再由负责人评估扩容或调整资源规格。",
            ]
        )
    elif scene["category"] == "scheduling":
        actions.extend(
            [
                "查看任务 Pending/Failed 事件、队列配额、节点标签和调度器拒绝原因。",
                "确认 request/limit 是否超过队列或节点可用资源。",
            ]
        )
    elif scene["category"] == "runtime":
        actions.extend(
            [
                "比对成功任务和失败任务的镜像版本、启动命令、依赖包和 CUDA/驱动版本。",
                "优先用上一个稳定镜像做小样本回归验证。",
            ]
        )
    else:
        actions.extend(
            [
                "补充任务 ID、完整错误码、失败时间点、最近配置变更和关键日志片段。",
                "按调度、镜像、数据、模型配置、资源配额五个方向逐项排除。",
            ]
        )
    if tools:
        actions.append("后续接入平台工具后，可自动拉取任务状态、日志、指标、镜像版本和调度事件来验证根因。")
    return actions


def risk_warnings(guardrails: List[Dict[str, Any]]) -> List[str]:
    warnings = [
        "当前诊断不会编造平台实时数据；未接入工具前，所有日志、指标、事件都需要用户提供或人工查询。",
    ]
    if any(not item["passed"] and item["severity"] == "high" for item in guardrails):
        warnings.append("涉及高风险操作，执行删除、重启、扩缩容或回滚前必须人工确认影响范围和回退方案。")
    if any(item.get("needsMoreEvidence") for item in guardrails):
        warnings.append("缺少任务 ID、日志或监控证据，根因只能作为候选，不能作为最终定论。")
    return warnings


def update_state(problem: Dict[str, Any], scene: Dict[str, Any], candidates: List[Dict[str, Any]], warnings: List[str]) -> Dict[str, Any]:
    current_step = "等待补充日志或监控证据" if scene["category"] == "unknown" else "已形成根因候选，等待证据验证"
    facts = [f"识别信号：{', '.join(problem['signals'])}", f"场景：{scene['scene']} / {scene['category']}"]
    if candidates:
        facts.append(f"首要候选：{candidates[0]['cause']}")
    open_questions = [
        "任务 ID 或实例 ID 是什么？",
        "失败前后的关键日志片段是什么？",
        "资源监控峰值和容器 request/limit 是多少？",
    ]
    if scene["category"] == "runtime":
        open_questions.append("失败任务和成功任务的镜像版本是否一致？")
    risk_level = "high" if any("高风险" in item for item in warnings) else ("medium" if scene["category"] == "unknown" else "low")
    return {
        "currentStep": current_step,
        "summary": candidates[0]["cause"] if candidates else "证据不足，需继续收集信息。",
        "facts": facts,
        "openQuestions": open_questions,
        "riskLevel": risk_level,
    }


def render_answer(
    query: str,
    problem: Dict[str, Any],
    scene: Dict[str, Any],
    knowledge_results: List[Dict[str, Any]],
    tools: List[Dict[str, Any]],
    candidates: List[Dict[str, Any]],
    actions: List[str],
    warnings: List[str],
    diagnostic_state: Dict[str, Any],
    need_deep_thinking: int = 0,
) -> str:
    sources = []
    for item in knowledge_results[:3]:
        sources.append(f"- `{Path(item.get('source', '')).name}` > `{item.get('heading') or '未命名章节'}` · score {item.get('score')}")
    tool_lines = [
        f"- {item['description']}：{item['status']}，{item['reason']}"
        for item in tools
    ] or ["- 本轮没有触发平台工具意图。"]
    candidate_lines = [f"{index}. {item['cause']}（置信度：{item['confidence']}）" for index, item in enumerate(candidates, start=1)]
    action_lines = [f"{index}. {item}" for index, item in enumerate(actions, start=1)]
    warning_lines = [f"- {item}" for item in warnings]
    answer = [
        "### 可解释诊断链路",
        "",
        "#### 1. 问题识别",
        f"- 原始问题：{query}",
        f"- 识别信号：{', '.join(problem['signals'])}",
        f"- 置信度：{problem['confidence']}",
        "",
        "#### 2. 场景判断",
        f"- 服务：{scene['service']}",
        f"- 场景：{scene['scene']}",
        f"- 类型：{scene['category']}",
        f"- 上一轮状态：{scene.get('previousStep') or '无'}",
        "",
        "#### 3. 知识检索",
        "根据本地知识库检索结果：" if sources else "本轮未形成可靠知识库 grounding：",
        *(sources or ["- 未命中已发布知识片段，本轮不把知识库结果作为确定依据。"]),
        "",
        "#### 4. 工具调用计划",
        *tool_lines,
        "",
        "#### 5. 根因候选",
        *candidate_lines,
        "",
        "#### 6. 建议动作",
        *action_lines,
        "",
        "#### 7. 风险提示",
        *warning_lines,
        "",
        "#### 8. 多轮诊断状态",
        f"- 当前步骤：{diagnostic_state['currentStep']}",
        f"- 下一步需要：{'; '.join(diagnostic_state['openQuestions'][:3])}",
    ]
    if need_deep_thinking:
        answer.extend(["", "#### 深度补充", build_answer(query, need_deep_thinking=1)])
    return "\n".join(answer).strip()


def run_diagnostic_agent(
    query: str,
    context: Any,
    query_message_id: str,
    answer_message_id: str,
    knowledge_results: List[Dict[str, Any]],
    previous_state: Optional[Dict[str, Any]] = None,
    need_deep_thinking: int = 0,
) -> Dict[str, Any]:
    trace_id = str(uuid.uuid4())
    trace_start_perf = time.perf_counter()
    trace_started_at = now_iso()
    recorder = SpanRecorder(trace_id=trace_id)

    started = now_iso()
    start_perf = time.perf_counter()
    problem = identify_problem(query)
    recorder.record("problem_identification", "agent", {"query": query}, problem, started_at=started, start_perf=start_perf)

    started = now_iso()
    start_perf = time.perf_counter()
    scene = judge_scene(query, context, previous_state)
    recorder.record("scene_judgement", "chain", {"query": query, "context": getattr(context, "model_dump", lambda: {})()}, scene, started_at=started, start_perf=start_perf)

    started = now_iso()
    start_perf = time.perf_counter()
    retrieval_output = [
        {
            "source": Path(item.get("source", "")).name,
            "heading": item.get("heading"),
            "score": item.get("score"),
            "status": item.get("status"),
        }
        for item in knowledge_results
    ]
    recorder.record("knowledge_retrieval", "retriever", {"query": query, "topK": 5}, retrieval_output, started_at=started, start_perf=start_perf)

    started = now_iso()
    start_perf = time.perf_counter()
    guardrails = run_guardrails(query, knowledge_results)
    recorder.record("guardrails", "guardrail", {"query": query}, guardrails, started_at=started, start_perf=start_perf)

    started = now_iso()
    start_perf = time.perf_counter()
    tools = plan_tool_calls(query, context)
    recorder.record("tool_planning", "tool", {"query": query}, tools, started_at=started, start_perf=start_perf)

    started = now_iso()
    start_perf = time.perf_counter()
    candidates = root_cause_candidates(problem, scene, knowledge_results)
    recorder.record("root_cause_candidates", "chain", {"problem": problem, "scene": scene}, candidates, started_at=started, start_perf=start_perf)

    started = now_iso()
    start_perf = time.perf_counter()
    actions = recommended_actions(scene, tools)
    warnings = risk_warnings(guardrails)
    diagnostic_state = update_state(problem, scene, candidates, warnings)
    answer = render_answer(
        query=query,
        problem=problem,
        scene=scene,
        knowledge_results=knowledge_results,
        tools=tools,
        candidates=candidates,
        actions=actions,
        warnings=warnings,
        diagnostic_state=diagnostic_state,
        need_deep_thinking=need_deep_thinking,
    )
    recorder.record(
        "response_generation",
        "llm",
        {"sections": ["problem", "scene", "retrieval", "candidates", "actions", "warnings", "state"]},
        {"answerLength": len(answer), "state": diagnostic_state},
        started_at=started,
        start_perf=start_perf,
    )

    return {
        "trace": {
            "traceId": trace_id,
            "userId": context.userId,
            "conversationId": context.conversationId,
            "queryMessageId": query_message_id,
            "answerMessageId": answer_message_id,
            "query": query,
            "answer": answer,
            "status": "ok",
            "guardrails": guardrails,
            "diagnosticState": diagnostic_state,
            "totalMs": int((time.perf_counter() - trace_start_perf) * 1000),
            "createdAt": trace_started_at,
        },
        "spans": recorder.spans,
        "answer": answer,
        "diagnosticState": diagnostic_state,
        "guardrails": guardrails,
    }
