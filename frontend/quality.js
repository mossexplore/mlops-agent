const metricsEl = document.querySelector("#qualityMetrics");
const feedbackEl = document.querySelector("#feedbackQueue");
const casesEl = document.querySelector("#evalCases");
const runsEl = document.querySelector("#evalRuns");
const experimentsEl = document.querySelector("#experiments");
const toast = document.querySelector("#qualityToast");

const reasonLabels = {
  knowledge_missing: "知识缺失",
  retrieval_error: "检索错误",
  generic_answer: "回答泛泛",
  unactionable_steps: "步骤不可执行",
  scene_misclassification: "误判场景",
};

let toastTimer = null;

function showToast(message) {
  clearTimeout(toastTimer);
  toast.textContent = message;
  toast.classList.add("show");
  toastTimer = setTimeout(() => toast.classList.remove("show"), 2200);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function splitList(value) {
  return value
    .split(/[,，]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseSplit(value) {
  const result = {};
  for (const item of splitList(value)) {
    const [name, ratio] = item.split(":").map((part) => part.trim());
    if (name) result[name] = Number(ratio || 0);
  }
  return result;
}

function formatRate(value) {
  return `${Math.round((value || 0) * 100)}%`;
}

function empty(text) {
  return `<p class="empty-copy">${escapeHtml(text)}</p>`;
}

async function postJson(url, payload = {}) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const json = await response.json();
  if (!response.ok || json.result.code !== 0) {
    throw new Error(json.result.des || "请求失败");
  }
  return json.result.data;
}

function renderMetrics(metrics) {
  const cards = [
    ["知识命中率", formatRate(metrics.knowledgeHitRate)],
    ["回答满意率", formatRate(metrics.satisfactionRate)],
    ["点踩率", formatRate(metrics.unlikeRate)],
    ["无答案率", formatRate(metrics.noAnswerRate)],
    ["重复提问率", formatRate(metrics.repeatQuestionRate)],
    ["平均耗时", `${metrics.avgLatencyMs || 0}ms`],
  ];
  metricsEl.innerHTML = cards
    .map(([label, value]) => `<article class="metric-tile"><p>${label}</p><strong>${value}</strong></article>`)
    .join("");
}

function renderFeedback(items) {
  if (!items.length) {
    feedbackEl.innerHTML = empty("暂无点踩记录");
    return;
  }
  feedbackEl.innerHTML = items
    .map(
      (item) => `
        <article class="feedback-item" data-answer="${escapeHtml(item.answerMessageId)}" data-user="${escapeHtml(item.userId)}" data-conversation="${escapeHtml(item.conversationId)}">
          <strong>${escapeHtml(item.userId)} · ${escapeHtml(item.timestamp)}</strong>
          <p>${escapeHtml(item.query || "未记录问题")}</p>
          <p>当前标注：${escapeHtml(reasonLabels[item.qualityReason] || item.qualityReason)} / ${escapeHtml(item.status)}</p>
          <div class="feedback-actions">
            <select data-field="reason">
              ${Object.entries(reasonLabels).map(([value, label]) => `<option value="${value}" ${item.qualityReason === value ? "selected" : ""}>${label}</option>`).join("")}
            </select>
            <input data-field="annotation" value="${escapeHtml(item.annotation || "")}" placeholder="标注说明" />
            <button type="button" data-action="annotate">标注</button>
            <button type="button" data-action="case">转用例</button>
          </div>
        </article>
      `,
    )
    .join("");
}

function renderCases(items) {
  casesEl.innerHTML = items.length
    ? items
        .map(
          (item) => `
            <article class="eval-item">
              <strong>${escapeHtml(item.title)}</strong>
              <p>${escapeHtml(item.query)}</p>
              <p>${item.requiredSteps.map((step) => `<span class="pill">${escapeHtml(step)}</span>`).join(" ")}</p>
            </article>
          `,
        )
        .join("")
    : empty("暂无评测用例，可从点踩反馈沉淀或手动创建");
}

function renderRuns(items) {
  runsEl.innerHTML = items.length
    ? items
        .map(
          (item) => `
            <article class="run-item">
              <strong>${escapeHtml(item.name)} · ${escapeHtml(item.variant)}</strong>
              <p>通过率 ${formatRate(item.passRate)} · 平均分 ${item.avgScore} · 知识命中 ${formatRate(item.knowledgeHitRate)}</p>
              <p>${escapeHtml(item.createdAt || "")}</p>
            </article>
          `,
        )
        .join("")
    : empty("暂无评测运行记录");
}

function renderExperiments(items) {
  experimentsEl.innerHTML = items.length
    ? items
        .map(
          (item) => `
            <article class="experiment-item">
              <strong>${escapeHtml(item.name)} · ${escapeHtml(item.status)}</strong>
              <p>指标：${escapeHtml(item.primaryMetric)} · variants：${item.variants.map(escapeHtml).join(", ")}</p>
              <p>${escapeHtml(JSON.stringify(item.trafficSplit))}</p>
            </article>
          `,
        )
        .join("")
    : empty("暂无 A/B 实验配置");
}

async function loadQuality() {
  const data = await postJson("/agent/v1/quality/dashboard");
  renderMetrics(data.metrics);
  renderFeedback(data.feedback);
  renderCases(data.evalCases);
  renderRuns(data.evalRuns);
  renderExperiments(data.experiments);
}

document.querySelector("#refreshQuality").addEventListener("click", () => loadQuality().catch((error) => showToast(error.message)));

document.querySelector("#saveEvalCase").addEventListener("click", async () => {
  await postJson("/agent/v1/quality/eval-case/save", {
    title: document.querySelector("#caseTitle").value.trim(),
    query: document.querySelector("#caseQuery").value.trim(),
    expectedAnswer: document.querySelector("#caseExpected").value.trim() || null,
    requiredSteps: splitList(document.querySelector("#caseRequired").value),
    forbiddenContent: splitList(document.querySelector("#caseForbidden").value),
    tags: splitList(document.querySelector("#caseTags").value),
  });
  showToast("评测用例已保存");
  await loadQuality();
});

document.querySelector("#runEval").addEventListener("click", async () => {
  const run = await postJson("/agent/v1/quality/eval/run", {
    name: document.querySelector("#evalRunName").value.trim(),
    variant: document.querySelector("#evalVariant").value.trim() || "baseline",
    promptVersion: document.querySelector("#evalPromptVersion").value.trim() || null,
  });
  showToast(`评测完成：通过率 ${formatRate(run.passRate)}`);
  await loadQuality();
});

document.querySelector("#saveExperiment").addEventListener("click", async () => {
  const variants = splitList(document.querySelector("#experimentVariants").value);
  await postJson("/agent/v1/quality/experiment/save", {
    name: document.querySelector("#experimentName").value.trim(),
    variants,
    trafficSplit: parseSplit(document.querySelector("#experimentSplit").value),
    primaryMetric: document.querySelector("#experimentMetric").value,
    status: "draft",
  });
  showToast("实验配置已保存");
  await loadQuality();
});

feedbackEl.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const item = button.closest(".feedback-item");
  const payload = {
    answerMessageId: item.dataset.answer,
    userId: item.dataset.user,
    conversationId: item.dataset.conversation,
  };
  if (button.dataset.action === "annotate") {
    await postJson("/agent/v1/quality/feedback/annotate", {
      ...payload,
      qualityReason: item.querySelector('[data-field="reason"]').value,
      annotation: item.querySelector('[data-field="annotation"]').value,
      reviewer: "admin",
    });
    showToast("反馈已标注");
  } else {
    await postJson("/agent/v1/quality/eval-case/from-feedback", payload);
    showToast("已转为评测用例");
  }
  await loadQuality();
});

loadQuality().catch((error) => showToast(error.message));
