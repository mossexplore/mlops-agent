from typing import Iterator, List


def build_answer(query: str, need_deep_thinking: int = 0) -> str:
    normalized = query.strip()
    if not normalized:
        return "请先输入需要诊断的问题，我会结合 MLOps 场景给出排查建议。"

    lower = normalized.lower()
    if "1401027" in lower or "insufficient memory" in lower or "内存" in normalized:
        answer = (
            "### [内存不足错误] MLOps 任务内存资源不足\n\n"
            "1. **错误分析**\n"
            "- `1401027 insufficient memory` 通常表示训练、推理或调度进程申请的内存超过当前可用资源。\n"
            "- 常见原因包括 batch size 过大、数据加载并发过高、容器 memory limit 偏小、特征缓存膨胀、模型参数或 checkpoint 占用过高。\n\n"
            "2. **快速处理**\n"
            "- 先查看任务实例的内存峰值、OOM 事件、容器 limit/request 和节点剩余资源。\n"
            "- 降低 batch size、num_workers、prefetch factor，关闭不必要的缓存或中间结果保留。\n"
            "- 如果是 GPU 任务，同时检查显存和主机内存，数据预处理阶段也可能耗尽主机内存。\n\n"
            "3. **长期优化**\n"
            "- 为训练任务补充资源画像，按模型规模、数据量和并发度给出推荐规格。\n"
            "- 对数据集读取链路做流式化或分片加载，避免一次性展开大文件。\n"
            "- 加入内存水位告警、失败自动归因和重试前参数建议，减少重复失败。"
        )
    else:
        answer = (
            f"### MLOps Agent 诊断建议\n\n"
            f"你咨询的问题是：**{normalized}**。\n\n"
            "1. **先确认现象**：记录报错码、任务 ID、运行环境、资源规格、最近一次变更和失败时间点。\n"
            "2. **定位范围**：分别检查调度、镜像、数据、模型配置、资源配额和运行日志，优先看最近失败前后的关键日志。\n"
            "3. **给出动作**：如果是资源类问题，先降低并发或扩大规格；如果是配置类问题，回滚最近参数并用小样本复现；如果是平台类问题，保留任务 ID 便于追溯。\n"
            "4. **沉淀结论**：把最终原因、处理动作和预防建议写入会话历史，方便后续同类问题复用。"
        )

    if need_deep_thinking:
        answer += (
            "\n\n### 深度排查补充\n"
            "- 建议补充任务运行日志、资源监控曲线、镜像版本、数据规模和最近配置变更，我可以继续帮你缩小根因。"
        )
    return answer


def stream_chunks(text: str) -> Iterator[str]:
    buffer = ""
    separators = {"，", "。", "\n", "；", ".", ",", " "}
    for char in text:
        buffer += char
        if len(buffer) >= 8 or char in separators:
            yield buffer
            buffer = ""
    if buffer:
        yield buffer
