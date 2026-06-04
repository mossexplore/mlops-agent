const els = {
  form: document.querySelector("#knowledgeForm"),
  title: document.querySelector("#knowledgeTitle"),
  filename: document.querySelector("#knowledgeFilename"),
  content: document.querySelector("#knowledgeContent"),
  list: document.querySelector("#knowledgeList"),
  refresh: document.querySelector("#refreshKnowledge"),
  searchForm: document.querySelector("#knowledgeSearchForm"),
  query: document.querySelector("#knowledgeQuery"),
  results: document.querySelector("#knowledgeResults"),
  save: document.querySelector("#saveKnowledge"),
};

let selectedFilename = null;

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
    item.innerHTML = `<strong>${file.title}</strong><span>${file.filename} · ${file.size} bytes · ${file.updatedAt || "未记录时间"}</span>`;
    item.addEventListener("click", () => loadKnowledgeDetail(file.filename));
    els.list.appendChild(item);
  }
}

async function loadFiles() {
  const response = await fetch("/agent/v1/knowledge/list", { method: "POST" });
  const payload = await response.json();
  renderFiles(payload.result.data || []);
}

async function loadKnowledgeDetail(filename) {
  selectedFilename = filename;
  for (const item of els.list.querySelectorAll(".knowledge-file")) {
    item.classList.toggle("active", item.dataset.filename === filename);
  }

  const response = await fetch("/agent/v1/knowledge/detail", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename }),
  });
  const payload = await response.json();
  if (!response.ok || payload.result?.code !== 0) {
    throw new Error(payload.result?.des || "加载知识详情失败");
  }

  const detail = payload.result.data;
  els.title.value = detail.title || "";
  els.filename.value = detail.filename || "";
  els.content.value = detail.content || "";
  els.content.focus();
}

els.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  els.save.disabled = true;
  els.save.textContent = "保存中";
  try {
    const response = await fetch("/agent/v1/knowledge/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: els.title.value.trim(),
        filename: els.filename.value.trim() || null,
        content: els.content.value.trim(),
      }),
    });
    const payload = await response.json();
    if (!response.ok || payload.result?.code !== 0) {
      throw new Error(payload.result?.des || "保存失败");
    }
    selectedFilename = payload.result.data?.filename || els.filename.value.trim() || selectedFilename;
    await loadFiles();
    if (selectedFilename) {
      await loadKnowledgeDetail(selectedFilename);
    }
    els.save.textContent = "已保存";
    window.setTimeout(() => {
      els.save.textContent = "保存知识";
    }, 1200);
  } catch (error) {
    els.save.textContent = "保存失败";
    window.alert(error.message || "保存失败");
    window.setTimeout(() => {
      els.save.textContent = "保存知识";
    }, 1600);
  } finally {
    els.save.disabled = false;
  }
});

els.searchForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const query = els.query.value.trim();
  if (!query) return;
  const response = await fetch("/agent/v1/knowledge/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, topK: 5 }),
  });
  const payload = await response.json();
  const results = payload.result.data || [];
  els.results.innerHTML = "";
  if (!results.length) {
    els.results.innerHTML = `<article class="knowledge-result"><strong>未命中</strong><p>本地 Markdown 知识库中没有找到足够相关的信息。</p></article>`;
    return;
  }
  for (const result of results) {
    const item = document.createElement("article");
    item.className = "knowledge-result";
    item.innerHTML = `
      <strong>${result.source.split("/").pop()} > ${result.heading || "未命名章节"} · score ${result.score}</strong>
      <p>${result.content}</p>
    `;
    els.results.appendChild(item);
  }
});

els.refresh.addEventListener("click", loadFiles);
loadFiles();
