const state = {
  runbooks: [],
  selectedRunbookId: null,
  steps: [],
};

const els = {
  list: document.querySelector("#runbookList"),
  query: document.querySelector("#runbookQuery"),
  statusFilter: document.querySelector("#runbookStatusFilter"),
  refresh: document.querySelector("#refreshRunbooks"),
  form: document.querySelector("#runbookForm"),
  mode: document.querySelector("#runbookMode"),
  heading: document.querySelector("#runbookHeading"),
  metaLine: document.querySelector("#runbookMetaLine"),
  title: document.querySelector("#runbookTitle"),
  service: document.querySelector("#runbookService"),
  scenario: document.querySelector("#runbookScenario"),
  severity: document.querySelector("#runbookSeverity"),
  status: document.querySelector("#runbookStatus"),
  version: document.querySelector("#runbookVersion"),
  owner: document.querySelector("#runbookOwner"),
  tags: document.querySelector("#runbookTags"),
  trigger: document.querySelector("#runbookTrigger"),
  summary: document.querySelector("#runbookSummary"),
  verification: document.querySelector("#runbookVerification"),
  escalation: document.querySelector("#runbookEscalation"),
  riskControls: document.querySelector("#runbookRiskControls"),
  relatedKnowledge: document.querySelector("#runbookRelatedKnowledge"),
  stepList: document.querySelector("#stepList"),
  addStep: document.querySelector("#addStep"),
  newRunbook: document.querySelector("#newRunbook"),
  preview: document.querySelector("#runbookPreview"),
  toast: document.querySelector("#runbookToast"),
};

const statusLabels = {
  draft: "草稿",
  review: "待审核",
  published: "已发布",
  archived: "已归档",
};

const actionLabels = {
  check: "检查",
  tool: "工具",
  manual: "人工",
  confirm: "确认",
  verify: "验证",
};

let toastTimer = null;

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function splitList(value) {
  return String(value ?? "")
    .split(/[,，]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function joinList(value) {
  return (value || []).join(", ");
}

function showToast(message, isError = false) {
  clearTimeout(toastTimer);
  els.toast.textContent = message;
  els.toast.classList.toggle("error", isError);
  els.toast.classList.add("show");
  toastTimer = setTimeout(() => els.toast.classList.remove("show"), 2400);
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

function blankStep(order = state.steps.length + 1) {
  return {
    order,
    title: "新的诊断步骤",
    actionType: "check",
    instruction: "",
    evidenceRequired: "",
    toolName: "",
    expectedResult: "",
    riskLevel: "low",
  };
}

function renderList() {
  if (!state.runbooks.length) {
    els.list.innerHTML = `<p class="empty-copy">暂无 Runbook</p>`;
    return;
  }
  els.list.innerHTML = state.runbooks
    .map(
      (item) => `
        <button class="runbook-item ${item.runbookId === state.selectedRunbookId ? "active" : ""}" type="button" data-runbook-id="${escapeHtml(item.runbookId)}">
          <strong>${escapeHtml(item.title)}</strong>
          <span>${escapeHtml(item.service)} / ${escapeHtml(item.scenario)} · ${escapeHtml(item.severity)}</span>
          <small>${escapeHtml(item.summary || item.trigger || "")}</small>
          <div class="item-meta">
            <span class="status-badge ${escapeHtml(item.status)}">${escapeHtml(statusLabels[item.status] || item.status)}</span>
            <span>${item.stepCount || 0} steps</span>
          </div>
        </button>
      `,
    )
    .join("");
}

function renderSteps() {
  els.stepList.innerHTML = state.steps
    .map(
      (step, index) => `
        <article class="step-card" data-step-index="${index}">
          <div class="step-card-head">
            <strong>步骤 ${index + 1}</strong>
            <button type="button" data-step-action="remove">删除</button>
          </div>
          <div class="step-fields">
            <label>
              标题
              <input data-step-field="title" value="${escapeHtml(step.title)}" />
            </label>
            <label>
              类型
              <select data-step-field="actionType">
                ${Object.entries(actionLabels)
                  .map(([value, label]) => `<option value="${value}" ${step.actionType === value ? "selected" : ""}>${label}</option>`)
                  .join("")}
              </select>
            </label>
            <label>
              风险
              <select data-step-field="riskLevel">
                ${["low", "medium", "high"]
                  .map((value) => `<option value="${value}" ${step.riskLevel === value ? "selected" : ""}>${value}</option>`)
                  .join("")}
              </select>
            </label>
            <label>
              工具
              <input data-step-field="toolName" value="${escapeHtml(step.toolName || "")}" placeholder="例如：resource_metrics" />
            </label>
            <label class="span-2">
              操作说明
              <textarea data-step-field="instruction" rows="2">${escapeHtml(step.instruction || "")}</textarea>
            </label>
            <label>
              所需证据
              <input data-step-field="evidenceRequired" value="${escapeHtml(step.evidenceRequired || "")}" />
            </label>
            <label>
              预期结果
              <input data-step-field="expectedResult" value="${escapeHtml(step.expectedResult || "")}" />
            </label>
          </div>
        </article>
      `,
    )
    .join("");
  renderPreview();
}

function renderPreview() {
  const highRisk = state.steps.filter((step) => step.riskLevel === "high");
  els.preview.innerHTML = `
    <div class="preview-summary">
      <strong>${escapeHtml(els.title.value || "未命名 Runbook")}</strong>
      <span>${escapeHtml(els.service.value)} / ${escapeHtml(els.scenario.value || "未设置场景")} · ${escapeHtml(els.severity.value)}</span>
      <p>${escapeHtml(els.summary.value || "暂无摘要")}</p>
    </div>
    <ol class="flow-list">
      ${state.steps
        .map(
          (step) => `
            <li>
              <span class="flow-type ${escapeHtml(step.actionType)}">${escapeHtml(actionLabels[step.actionType] || step.actionType)}</span>
              <strong>${escapeHtml(step.title)}</strong>
              <p>${escapeHtml(step.instruction || "尚未填写操作说明")}</p>
              <small>${escapeHtml(step.evidenceRequired || "未填写证据")} · ${escapeHtml(step.expectedResult || "未填写预期结果")}</small>
            </li>
          `,
        )
        .join("")}
    </ol>
    ${
      highRisk.length
        ? `<div class="risk-box"><strong>高风险确认</strong><p>${highRisk.map((step) => escapeHtml(step.title)).join("、")} 执行前必须确认影响范围和回退方案。</p></div>`
        : `<div class="risk-box low"><strong>风险状态</strong><p>当前步骤未标记高风险动作。</p></div>`
    }
  `;
}

function bindRunbook(item) {
  state.selectedRunbookId = item?.runbookId || null;
  els.mode.textContent = item ? "编辑 Runbook" : "新增 Runbook";
  els.heading.textContent = item?.title || "诊断流程元数据";
  els.metaLine.textContent = item ? `${item.runbookId} · ${item.updatedAt || "未记录更新时间"}` : "尚未保存";
  els.title.value = item?.title || "";
  els.service.value = item?.service || "Wise";
  els.scenario.value = item?.scenario || "模型任务";
  els.severity.value = item?.severity || "P2";
  els.status.value = item?.status || "draft";
  els.version.value = item?.version || "v1";
  els.owner.value = item?.owner || "";
  els.tags.value = joinList(item?.tags);
  els.trigger.value = item?.trigger || "";
  els.summary.value = item?.summary || "";
  els.verification.value = item?.verification || "";
  els.escalation.value = item?.escalation || "";
  els.riskControls.value = joinList(item?.riskControls);
  els.relatedKnowledge.value = joinList(item?.relatedKnowledge);
  state.steps = item?.steps?.length ? item.steps.map((step, index) => ({ ...step, order: index + 1 })) : [blankStep(1)];
  renderSteps();
  renderList();
}

function collectPayload() {
  return {
    runbookId: state.selectedRunbookId,
    title: els.title.value.trim(),
    service: els.service.value,
    scenario: els.scenario.value.trim() || "模型任务",
    severity: els.severity.value,
    status: els.status.value,
    owner: els.owner.value.trim() || null,
    version: els.version.value.trim() || "v1",
    trigger: els.trigger.value.trim() || null,
    summary: els.summary.value.trim() || null,
    verification: els.verification.value.trim() || null,
    escalation: els.escalation.value.trim() || null,
    riskControls: splitList(els.riskControls.value),
    tags: splitList(els.tags.value),
    relatedKnowledge: splitList(els.relatedKnowledge.value),
    steps: state.steps.map((step, index) => ({ ...step, order: index + 1 })),
  };
}

async function loadRunbooks(selectFirst = false) {
  const payload = {
    query: els.query.value.trim() || null,
    status: els.statusFilter.value || null,
  };
  state.runbooks = await postJson("/agent/v1/runbook/list", payload);
  renderList();
  if (selectFirst && state.runbooks.length) {
    await selectRunbook(state.runbooks[0].runbookId);
  }
}

async function selectRunbook(runbookId) {
  const detail = await postJson("/agent/v1/runbook/detail", { runbookId });
  bindRunbook(detail);
}

els.list.addEventListener("click", (event) => {
  const item = event.target.closest("[data-runbook-id]");
  if (!item) return;
  selectRunbook(item.dataset.runbookId).catch((error) => showToast(error.message, true));
});

els.stepList.addEventListener("input", (event) => {
  const field = event.target.dataset.stepField;
  if (!field) return;
  const card = event.target.closest("[data-step-index]");
  state.steps[Number(card.dataset.stepIndex)][field] = event.target.value;
  renderPreview();
});

els.stepList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-step-action='remove']");
  if (!button) return;
  const card = button.closest("[data-step-index]");
  state.steps.splice(Number(card.dataset.stepIndex), 1);
  if (!state.steps.length) state.steps.push(blankStep(1));
  renderSteps();
});

els.addStep.addEventListener("click", () => {
  state.steps.push(blankStep());
  renderSteps();
});

els.form.addEventListener("input", renderPreview);

els.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const saved = await postJson("/agent/v1/runbook/save", collectPayload());
    showToast("Runbook 已保存");
    await loadRunbooks(false);
    bindRunbook(saved);
  } catch (error) {
    showToast(error.message, true);
  }
});

els.newRunbook.addEventListener("click", () => bindRunbook(null));

els.refresh.addEventListener("click", () => loadRunbooks(false).catch((error) => showToast(error.message, true)));
els.query.addEventListener("change", () => loadRunbooks(false).catch((error) => showToast(error.message, true)));
els.statusFilter.addEventListener("change", () => loadRunbooks(true).catch((error) => showToast(error.message, true)));

document.querySelector(".lifecycle-actions").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-runbook-status]");
  if (!button || !state.selectedRunbookId) return;
  try {
    const updated = await postJson("/agent/v1/runbook/status", {
      runbookId: state.selectedRunbookId,
      status: button.dataset.runbookStatus,
    });
    showToast("状态已更新");
    await loadRunbooks(false);
    bindRunbook(updated);
  } catch (error) {
    showToast(error.message, true);
  }
});

loadRunbooks(true).catch((error) => showToast(error.message, true));
