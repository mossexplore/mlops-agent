const els = {
  form: document.querySelector("#knowledgeForm"),
  mode: document.querySelector("#knowledgeMode"),
  title: document.querySelector("#knowledgeTitle"),
  filename: document.querySelector("#knowledgeFilename"),
  category: document.querySelector("#knowledgeCategory"),
  tags: document.querySelector("#knowledgeTags"),
  status: document.querySelector("#knowledgeStatus"),
  visibility: document.querySelector("#knowledgeVisibility"),
  owner: document.querySelector("#knowledgeOwner"),
  reviewNotes: document.querySelector("#knowledgeReviewNotes"),
  content: document.querySelector("#knowledgeContent"),
  list: document.querySelector("#knowledgeList"),
  refresh: document.querySelector("#refreshKnowledge"),
  searchForm: document.querySelector("#knowledgeSearchForm"),
  query: document.querySelector("#knowledgeQuery"),
  results: document.querySelector("#knowledgeResults"),
  revisions: document.querySelector("#knowledgeRevisions"),
  gaps: document.querySelector("#knowledgeGaps"),
  save: document.querySelector("#saveKnowledge"),
  newKnowledge: document.querySelector("#newKnowledge"),
  lifecycleActions: document.querySelector("#lifecycleActions"),
  currentStatusLabel: document.querySelector("#currentStatusLabel"),
  documentHeading: document.querySelector("#documentHeading"),
  documentMetaLine: document.querySelector("#documentMetaLine"),
  governanceSummary: document.querySelector("#governanceSummary"),
  toast: document.querySelector("#knowledgeToast"),
};

let selectedFilename = null;
let toastTimer = null;

const statusLabels = {
  draft: "草稿",
  review: "待审核",
  published: "已发布",
  archived: "已归档",
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function parseTags(value) {
  return value
    .split(/[,，]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function formatTags(tags) {
  return (tags || []).join(", ");
}

function normalizeDetail(detail = {}) {
  const tags = Array.isArray(detail.tags) ? detail.tags : [];
  return {
    ...detail,
    category: detail.category || "未分类",
    tags,
    status: detail.status || "published",
    visibility: detail.visibility || "internal",
    owner: detail.owner || "",
    reviewNotes: detail.reviewNotes || "",
    updatedAt: detail.updatedAt || "未记录",
  };
}

function currentFilename() {
  const active = els.list.querySelector(".knowledge-file.active")?.dataset.filename;
  return selectedFilename || active || els.filename.value.trim();
}

async function postJson(url, payload = {}) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const json = await response.json();
  if (!response.ok || json.result?.code !== 0) {
    throw new Error(json.result?.des || "请求失败");
  }
  return json.result.data;
}

function statusBadge(status) {
  return `<span class="status-badge ${escapeHtml(status)}">${statusLabels[status] || status || "未知"}</span>`;
}

function showToast(message, type = "success") {
  window.clearTimeout(toastTimer);
  els.toast.textContent = message;
  els.toast.classList.toggle("error", type === "error");
  els.toast.classList.add("show");
  toastTimer = window.setTimeout(() => {
    els.toast.classList.remove("show");
  }, 2200);
}

function updateDocumentChrome(detail = null) {
  const normalized = detail ? normalizeDetail(detail) : null;
  const status = normalized?.status || els.status.value || "published";
  els.currentStatusLabel.textContent = statusLabels[status] || status;
  els.documentHeading.textContent = normalized?.title || els.title.value.trim() || "知识内容与治理元数据";
  const parts = [
    normalized?.filename || els.filename.value.trim(),
    normalized?.category || els.category.value.trim() || "未分类",
    normalized?.owner || els.owner.value.trim() || "未指定负责人",
  ].filter(Boolean);
  els.documentMetaLine.textContent = parts.length ? parts.join(" · ") : "选择左侧知识或新建一条知识";

  const summary = els.governanceSummary;
  if (summary) {
    summary.querySelector('[data-summary="filename"]').textContent =
      normalized?.filename || els.filename.value.trim() || "未选择";
    summary.querySelector('[data-summary="category"]').textContent =
      normalized?.category || els.category.value.trim() || "未分类";
    summary.querySelector('[data-summary="tags"]').textContent =
      formatTags(normalized?.tags || parseTags(els.tags.value)) || "无标签";
    summary.querySelector('[data-summary="updatedAt"]').textContent =
      normalized?.updatedAt || "未记录";
  }
}

function renderFiles(files) {
  els.list.innerHTML = "";
  if (!files.length) {
    els.list.innerHTML = `<div class="knowledge-file"><strong>暂无知识文件</strong><span>保存 Markdown 后会显示在这里</span></div>`;
    return;
  }
  for (const file of files) {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "knowledge-file";
    item.dataset.filename = file.filename;
    item.classList.toggle("active", file.filename === selectedFilename);
    item.innerHTML = `
      <strong>${escapeHtml(file.title)}</strong>
      <small>${statusBadge(file.status)} ${escapeHtml(file.category || "未分类")}</small>
      <span>${escapeHtml(file.filename)} · ${file.size} bytes · ${file.updatedAt || "未记录时间"}</span>
    `;
    item.addEventListener("click", () => loadKnowledgeDetail(file.filename));
    els.list.appendChild(item);
  }
}

async function loadFiles() {
  const files = await postJson("/agent/v1/knowledge/list");
  renderFiles(files || []);
}

async function loadRevisions(filename) {
  els.revisions.innerHTML = `<article class="knowledge-result"><strong>加载中</strong><p>正在读取版本历史...</p></article>`;
  const revisions = await postJson("/agent/v1/knowledge/revision/list", {
    filename,
    page: 1,
    pageSize: 8,
  });
  if (!revisions.length) {
    els.revisions.innerHTML = `<article class="knowledge-result"><strong>暂无版本</strong><p>保存或切换状态后会记录版本。</p></article>`;
    return;
  }
  els.revisions.innerHTML = revisions
    .map(
      (item) => `
        <article class="knowledge-result">
          <strong>${escapeHtml(item.timestamp)} · ${escapeHtml(item.action || "save")}</strong>
          <div class="meta-line">
            ${statusBadge(item.status)}
            <span>${escapeHtml(item.category || "未分类")}</span>
            ${(item.tags || []).map((tag) => `<span>${escapeHtml(tag)}</span>`).join("")}
          </div>
          <p>${escapeHtml((item.content || "").slice(0, 180))}</p>
        </article>
      `,
    )
    .join("");
}

async function loadKnowledgeGaps() {
  const gaps = await postJson("/agent/v1/knowledge/gap/list", { page: 1, pageSize: 8 });
  if (!gaps.length) {
    els.gaps.innerHTML = `<article class="knowledge-result"><strong>暂无缺口</strong><p>近期点踩问题没有暴露明显知识缺口。</p></article>`;
    return;
  }
  els.gaps.innerHTML = gaps
    .map((item) => {
      const types = item.reason?.feedbackInfoTypes || [];
      const text = item.reason?.feedbackInfo || "";
      return `
        <article class="knowledge-result">
          <strong>${escapeHtml(item.timestamp)} · score ${item.bestScore}</strong>
          <p>${escapeHtml(item.query || "未记录问题")}</p>
          <div class="meta-line">
            ${types.map((type) => `<span>${escapeHtml(type)}</span>`).join("")}
            ${text ? `<span>${escapeHtml(text)}</span>` : ""}
          </div>
        </article>
      `;
    })
    .join("");
}

async function loadKnowledgeDetail(filename) {
  selectedFilename = filename;
  for (const item of els.list.querySelectorAll(".knowledge-file")) {
    item.classList.toggle("active", item.dataset.filename === filename);
  }

  const detail = normalizeDetail(await postJson("/agent/v1/knowledge/detail", { filename }));
  els.mode.textContent = "编辑已有知识";
  els.title.value = detail.title || "";
  els.filename.value = detail.filename || "";
  els.category.value = detail.category || "未分类";
  els.tags.value = formatTags(detail.tags);
  els.status.value = detail.status;
  els.visibility.value = detail.visibility;
  els.owner.value = detail.owner || "";
  els.reviewNotes.value = detail.reviewNotes || "";
  els.content.value = detail.content || "";
  updateDocumentChrome(detail);
  els.content.focus();
  await loadRevisions(filename);
}

function resetForm() {
  selectedFilename = null;
  els.mode.textContent = "新增知识";
  els.form.reset();
  els.status.value = "published";
  els.visibility.value = "internal";
  updateDocumentChrome();
  els.revisions.innerHTML = `<article class="knowledge-result"><strong>尚未选择知识</strong><p>选择左侧知识后查看版本历史。</p></article>`;
  for (const item of els.list.querySelectorAll(".knowledge-file")) {
    item.classList.remove("active");
  }
  els.title.focus();
}

els.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  els.save.disabled = true;
  els.save.textContent = "保存中";
  try {
    const data = await postJson("/agent/v1/knowledge/save", {
      title: els.title.value.trim(),
      filename: els.filename.value.trim() || null,
      category: els.category.value.trim() || "未分类",
      tags: parseTags(els.tags.value),
      status: els.status.value,
      visibility: els.visibility.value,
      owner: els.owner.value.trim() || null,
      reviewNotes: els.reviewNotes.value.trim() || null,
      content: els.content.value.trim(),
    });
    selectedFilename = data?.filename || els.filename.value.trim() || selectedFilename;
    await loadFiles();
    if (selectedFilename) {
      await loadKnowledgeDetail(selectedFilename);
    }
    els.save.textContent = "已保存";
    showToast("知识已保存");
    window.setTimeout(() => {
      els.save.textContent = "保存";
    }, 1200);
  } catch (error) {
    els.save.textContent = "保存失败";
    showToast(error.message || "保存失败", "error");
    window.setTimeout(() => {
      els.save.textContent = "保存";
    }, 1600);
  } finally {
    els.save.disabled = false;
  }
});

els.lifecycleActions.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-status-action]");
  if (!button) return;

  const filename = currentFilename();
  if (!filename) {
    showToast("请先选择或保存一条知识。", "error");
    return;
  }
  selectedFilename = filename;

  const status = button.dataset.statusAction;
  const previousText = button.textContent;
  button.disabled = true;
  button.textContent = "处理中";
  try {
    const detail = await postJson("/agent/v1/knowledge/status", {
      filename,
      status,
      reviewNotes: els.reviewNotes.value.trim() || null,
    });
    els.status.value = detail.status;
    updateDocumentChrome(detail);
    await loadFiles();
    await loadKnowledgeDetail(filename);
    showToast(`状态已更新为：${statusLabels[detail.status] || detail.status}`);
  } catch (error) {
    showToast(error.message || "状态更新失败", "error");
  } finally {
    button.disabled = false;
    button.textContent = previousText;
  }
});

els.searchForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const query = els.query.value.trim();
  if (!query) return;
  const results = await postJson("/agent/v1/knowledge/search", { query, topK: 5 });
  els.results.innerHTML = "";
  if (!results.length) {
    els.results.innerHTML = `<article class="knowledge-result"><strong>未命中</strong><p>已发布知识中没有找到足够相关的信息。</p></article>`;
    return;
  }
  els.results.innerHTML = results
    .map(
      (result) => `
        <article class="knowledge-result">
          <strong>${escapeHtml(result.source.split("/").pop())} > ${escapeHtml(result.heading || "未命名章节")} · score ${result.score}</strong>
          <div class="meta-line">
            ${statusBadge(result.status)}
            <span>${escapeHtml(result.category || "未分类")}</span>
            ${(result.tags || []).map((tag) => `<span>${escapeHtml(tag)}</span>`).join("")}
          </div>
          <p>${escapeHtml(result.content)}</p>
        </article>
      `,
    )
    .join("");
});

els.refresh.addEventListener("click", () => {
  loadFiles().catch((error) => window.alert(error.message));
  loadKnowledgeGaps().catch(() => {});
});
els.newKnowledge.addEventListener("click", () => {
  resetForm();
  showToast("已切换到新建知识");
});
document.querySelector(".knowledge-tabs")?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-tab]");
  if (!button) return;
  const tab = button.dataset.tab;
  document.querySelectorAll("[data-tab]").forEach((item) => {
    item.classList.toggle("active", item.dataset.tab === tab);
  });
  document.querySelectorAll("[data-pane]").forEach((pane) => {
    pane.classList.toggle("active", pane.dataset.pane === tab);
  });
  const labels = { search: "检索测试", revisions: "版本历史", gaps: "知识缺口" };
  showToast(`已切换到：${labels[tab] || "知识洞察"}`);
});
["input", "change"].forEach((eventName) => {
  [els.title, els.filename, els.category, els.owner, els.status].forEach((node) => {
    node.addEventListener(eventName, () => updateDocumentChrome());
  });
});

els.revisions.innerHTML = `<article class="knowledge-result"><strong>尚未选择知识</strong><p>选择左侧知识后查看版本历史。</p></article>`;
updateDocumentChrome();
loadFiles().catch((error) => window.alert(error.message));
loadKnowledgeGaps().catch(() => {});
