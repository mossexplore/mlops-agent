const form = document.querySelector("#opsFilters");
const rangeLabel = document.querySelector("#opsRange");
const startDateInput = document.querySelector("#startDate");
const endDateInput = document.querySelector("#endDate");
const summaryCards = document.querySelector("#summaryCards");
const dailyTrend = document.querySelector("#dailyTrend");
const feedbackSplit = document.querySelector("#feedbackSplit");
const reasonTop = document.querySelector("#reasonTop");
const topUsers = document.querySelector("#topUsers");
const recentUnlikes = document.querySelector("#recentUnlikes");

function isoDate(date) {
  return date.toISOString().slice(0, 10);
}

function setDefaultDates() {
  const end = new Date();
  const start = new Date();
  start.setDate(end.getDate() - 6);
  startDateInput.value = isoDate(start);
  endDateInput.value = isoDate(end);
}

function formatNumber(value) {
  return new Intl.NumberFormat("zh-CN").format(value || 0);
}

function formatRate(value) {
  return `${Math.round((value || 0) * 100)}%`;
}

function clip(text, max = 84) {
  if (!text) return "暂无内容";
  return text.length > max ? `${text.slice(0, max)}...` : text;
}

function empty(text) {
  return `<p class="empty-copy">${text}</p>`;
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const json = await response.json();
  if (json.result.code !== 0) {
    throw new Error(json.result.des || "请求失败");
  }
  return json.result.data;
}

function collectFilters() {
  const payload = {
    startDate: startDateInput.value || null,
    endDate: endDateInput.value || null,
    userId: document.querySelector("#filterUserId").value.trim() || null,
    service: document.querySelector("#filterService").value || null,
    scene: document.querySelector("#filterScene").value.trim() || null,
  };
  return payload;
}

function renderSummary(summary) {
  const cards = [
    ["活跃用户", summary.activeUsers, "当天范围内提问过的去重用户"],
    ["提问次数", summary.questionCount, "用户发起的问题数量"],
    ["会话数", summary.conversationCount, "产生提问的会话数量"],
    ["点赞数", summary.likeCount, "正向反馈次数"],
    ["点踩数", summary.unlikeCount, "负向反馈次数"],
    ["反馈率", formatRate(summary.feedbackRate), "反馈数 / Agent 回复数"],
  ];

  summaryCards.innerHTML = cards
    .map(
      ([label, value, hint]) => `
        <article class="metric-card">
          <p>${label}</p>
          <strong>${typeof value === "number" ? formatNumber(value) : value}</strong>
          <span>${hint}</span>
        </article>
      `,
    )
    .join("");
}

function renderDaily(rows) {
  if (!rows.length) {
    dailyTrend.innerHTML = empty("当前范围暂无使用数据");
    return;
  }

  const maxValue = Math.max(...rows.map((item) => item.questionCount + item.likeCount + item.unlikeCount), 1);
  dailyTrend.innerHTML = rows
    .map((item) => {
      const questions = Math.max(item.questionCount / maxValue, 0.02);
      const likes = Math.max(item.likeCount / maxValue, 0);
      const unlikes = Math.max(item.unlikeCount / maxValue, 0);
      return `
        <div class="trend-row">
          <span>${item.date.slice(5)}</span>
          <div class="trend-track" style="--questions:${questions}fr;--likes:${likes}fr;--unlikes:${unlikes}fr">
            <span title="提问 ${item.questionCount}"></span>
            <span title="点赞 ${item.likeCount}"></span>
            <span title="点踩 ${item.unlikeCount}"></span>
          </div>
          <span class="trend-values">问 ${item.questionCount} / 赞 ${item.likeCount} / 踩 ${item.unlikeCount}</span>
        </div>
      `;
    })
    .join("");
}

function renderFeedback(summary) {
  const like = summary.likeCount || 0;
  const unlike = summary.unlikeCount || 0;
  const total = Math.max(like + unlike, 1);
  feedbackSplit.innerHTML = `
    <div class="split-track" style="--like-ratio:${like || 0.001}fr;--unlike-ratio:${unlike || 0.001}fr">
      <span title="点赞 ${like}"></span>
      <span title="点踩 ${unlike}"></span>
    </div>
    <div class="split-meta">点赞 ${formatNumber(like)}，点踩 ${formatNumber(unlike)}，点踩占反馈 ${formatRate(unlike / total)}</div>
  `;
}

function renderReasons(items) {
  if (!items.length) {
    reasonTop.innerHTML = empty("暂无点踩原因");
    return;
  }
  reasonTop.innerHTML = items
    .map(
      (item) => `
        <div class="reason-item">
          <strong>${item.reason}</strong>
          <span>${formatNumber(item.count)} 次</span>
        </div>
      `,
    )
    .join("");
}

function renderUsers(items) {
  if (!items.length) {
    topUsers.innerHTML = empty("当前范围暂无用户数据");
    return;
  }
  topUsers.innerHTML = items
    .map(
      (item) => `
        <div class="user-row">
          <div>
            <strong>${item.userId}</strong>
            <div class="user-metrics">
              <span>提问 ${formatNumber(item.questionCount)}</span>
              <span>会话 ${formatNumber(item.conversationCount)}</span>
              <span>赞 ${formatNumber(item.likeCount)}</span>
              <span>踩 ${formatNumber(item.unlikeCount)}</span>
            </div>
          </div>
          <span>${item.lastActiveAt || "无活跃时间"}</span>
        </div>
      `,
    )
    .join("");
}

function renderRecentUnlikes(items) {
  if (!items.length) {
    recentUnlikes.innerHTML = empty("当前范围暂无点踩记录");
    return;
  }
  recentUnlikes.innerHTML = items
    .map((item) => {
      const types = item.reason?.feedbackInfoTypes || [];
      const text = item.reason?.feedbackInfo || "";
      return `
        <div class="unlike-item">
          <strong>${item.userId} · ${item.timestamp}</strong>
          <span>${item.service || "未知来源"} / ${item.scene || "未知场景"}</span>
          <p>${clip(item.query, 120)}</p>
          <div class="unlike-tags">
            ${types.map((type) => `<span>${type}</span>`).join("")}
            ${text ? `<span>${clip(text, 28)}</span>` : ""}
          </div>
        </div>
      `;
    })
    .join("");
}

async function loadDashboard() {
  const payload = collectFilters();
  rangeLabel.textContent = `${payload.startDate || "默认"} 至 ${payload.endDate || "今天"}`;
  summaryCards.innerHTML = empty("正在加载运营数据...");
  const data = await postJson("/agent/v1/ops/dashboard", payload);
  rangeLabel.textContent = `${data.range.startDate} 至 ${data.range.endDate}`;
  renderSummary(data.summary);
  renderDaily(data.daily);
  renderFeedback(data.summary);
  renderReasons(data.reasonTop);
  renderUsers(data.topUsers);
  renderRecentUnlikes(data.recentUnlikes);
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  loadDashboard().catch((error) => {
    summaryCards.innerHTML = empty(error.message);
  });
});

setDefaultDates();
loadDashboard().catch((error) => {
  summaryCards.innerHTML = empty(error.message);
});
