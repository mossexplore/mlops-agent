const form = document.querySelector("#opsFilters");
const rangeLabel = document.querySelector("#opsRange");
const startDateInput = document.querySelector("#startDate");
const endDateInput = document.querySelector("#endDate");
const summaryCards = document.querySelector("#summaryCards");
const dailyTrend = document.querySelector("#dailyTrend");
const feedbackSplit = document.querySelector("#feedbackSplit");
const feedbackMeta = document.querySelector("#feedbackMeta");
const reasonTop = document.querySelector("#reasonTop");
const reasonList = document.querySelector("#reasonList");
const topUsers = document.querySelector("#topUsers");
const topUsersChartWrap = document.querySelector("#topUsersChartWrap");
const recentUnlikes = document.querySelector("#recentUnlikes");
const charts = {};

const chartColors = {
  question: "#38bdf8",
  like: "#22c55e",
  unlike: "#fb7185",
  amber: "#f59e0b",
  muted: "#64748b",
  grid: "rgba(148, 163, 184, 0.14)",
  text: "#94a3b8",
  main: "#e5e7eb",
};

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

function chartReady() {
  return typeof window.Chart !== "undefined";
}

function destroyChart(key) {
  charts[key]?.destroy();
  charts[key] = null;
}

function setChartEmpty(container, text) {
  container.classList.add("is-empty");
  container.innerHTML = empty(text);
}

function resetCanvas(container, canvasId, label) {
  container.classList.remove("is-empty");
  container.innerHTML = `<canvas id="${canvasId}" aria-label="${label}" role="img"></canvas>`;
  return container.querySelector("canvas");
}

function baseChartOptions(extra = {}) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      intersect: false,
      mode: "index",
    },
    plugins: {
      legend: {
        display: false,
        labels: {
          color: chartColors.text,
          boxWidth: 10,
          boxHeight: 10,
        },
      },
      tooltip: {
        displayColors: true,
        backgroundColor: "rgba(15, 23, 42, 0.96)",
        borderColor: "rgba(148, 163, 184, 0.24)",
        borderWidth: 1,
        titleColor: chartColors.main,
        bodyColor: chartColors.main,
        padding: 10,
      },
    },
    scales: {
      x: {
        grid: {
          color: "transparent",
        },
        ticks: {
          color: chartColors.text,
          maxRotation: 0,
        },
        border: {
          color: chartColors.grid,
        },
      },
      y: {
        beginAtZero: true,
        grid: {
          color: chartColors.grid,
        },
        ticks: {
          color: chartColors.text,
          precision: 0,
        },
        border: {
          color: chartColors.grid,
        },
      },
    },
    ...extra,
  };
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
  destroyChart("daily");
  if (!rows.length) {
    setChartEmpty(dailyTrend, "当前范围暂无使用数据");
    return;
  }
  if (!chartReady()) {
    setChartEmpty(dailyTrend, "Chart.js 未加载，无法渲染趋势图");
    return;
  }

  const canvas = resetCanvas(dailyTrend, "dailyTrendChart", "每日使用趋势图");
  charts.daily = new Chart(canvas, {
    type: "line",
    data: {
      labels: rows.map((item) => item.date.slice(5)),
      datasets: [
        {
          label: "提问",
          data: rows.map((item) => item.questionCount || 0),
          borderColor: chartColors.question,
          backgroundColor: "rgba(56, 189, 248, 0.16)",
          fill: true,
          tension: 0.36,
          pointRadius: 3,
          pointHoverRadius: 5,
        },
        {
          label: "点赞",
          data: rows.map((item) => item.likeCount || 0),
          borderColor: chartColors.like,
          backgroundColor: "rgba(34, 197, 94, 0.12)",
          borderDash: [4, 4],
          tension: 0.36,
          pointRadius: 2,
          pointHoverRadius: 4,
        },
        {
          label: "点踩",
          data: rows.map((item) => item.unlikeCount || 0),
          borderColor: chartColors.unlike,
          backgroundColor: "rgba(251, 113, 133, 0.12)",
          borderDash: [2, 4],
          tension: 0.36,
          pointRadius: 2,
          pointHoverRadius: 4,
        },
      ],
    },
    options: baseChartOptions(),
  });
}

function renderFeedback(summary) {
  destroyChart("feedback");
  const like = summary.likeCount || 0;
  const unlike = summary.unlikeCount || 0;
  const total = Math.max(like + unlike, 1);
  feedbackMeta.innerHTML = `
    <div class="feedback-kpi">
      <span>反馈率</span>
      <strong>${formatRate(summary.feedbackRate)}</strong>
    </div>
    <div class="feedback-kpi danger">
      <span>点踩占比</span>
      <strong>${formatRate(unlike / total)}</strong>
    </div>
    <p>点赞 ${formatNumber(like)}，点踩 ${formatNumber(unlike)}，Agent 回复反馈覆盖率 ${formatRate(summary.feedbackRate)}。</p>
  `;

  if (!like && !unlike) {
    setChartEmpty(feedbackSplit, "暂无反馈数据");
    return;
  }
  if (!chartReady()) {
    setChartEmpty(feedbackSplit, "Chart.js 未加载，无法渲染反馈图");
    return;
  }

  const canvas = resetCanvas(feedbackSplit, "feedbackChart", "点赞点踩占比图");
  charts.feedback = new Chart(canvas, {
    type: "doughnut",
    data: {
      labels: ["点赞", "点踩"],
      datasets: [
        {
          data: [like, unlike],
          backgroundColor: [chartColors.like, chartColors.unlike],
          borderColor: "rgba(15, 23, 42, 0.96)",
          borderWidth: 3,
          hoverOffset: 5,
        },
      ],
    },
    options: baseChartOptions({
      cutout: "70%",
      scales: {},
      plugins: {
        ...baseChartOptions().plugins,
        legend: {
          display: true,
          position: "bottom",
          labels: {
            color: chartColors.text,
            usePointStyle: true,
            pointStyle: "circle",
            padding: 14,
          },
        },
      },
    }),
  });
}

function renderReasons(items) {
  destroyChart("reasons");
  if (!items.length) {
    setChartEmpty(reasonTop, "暂无点踩原因");
    reasonList.innerHTML = "";
    return;
  }

  reasonList.innerHTML = items
    .map(
      (item) => `
        <div class="reason-item">
          <strong>${item.reason}</strong>
          <span>${formatNumber(item.count)} 次</span>
        </div>
      `,
    )
    .join("");

  if (!chartReady()) {
    setChartEmpty(reasonTop, "Chart.js 未加载，无法渲染原因排行图");
    return;
  }

  const canvas = resetCanvas(reasonTop, "reasonChart", "点踩原因排行图");
  const topItems = items.slice(0, 6).reverse();
  charts.reasons = new Chart(canvas, {
    type: "bar",
    data: {
      labels: topItems.map((item) => item.reason),
      datasets: [
        {
          label: "点踩次数",
          data: topItems.map((item) => item.count || 0),
          backgroundColor: "rgba(251, 113, 133, 0.72)",
          borderColor: chartColors.unlike,
          borderWidth: 1,
          borderRadius: 8,
          barThickness: 14,
        },
      ],
    },
    options: baseChartOptions({
      indexAxis: "y",
      plugins: {
        ...baseChartOptions().plugins,
        tooltip: {
          ...baseChartOptions().plugins.tooltip,
          callbacks: {
            label: (context) => ` ${formatNumber(context.parsed.x)} 次`,
          },
        },
      },
      scales: {
        x: {
          beginAtZero: true,
          grid: {
            color: chartColors.grid,
          },
          ticks: {
            color: chartColors.text,
            precision: 0,
          },
        },
        y: {
          grid: {
            color: "transparent",
          },
          ticks: {
            color: chartColors.text,
            callback(value) {
              const label = this.getLabelForValue(value);
              return label.length > 12 ? `${label.slice(0, 12)}...` : label;
            },
          },
        },
      },
    }),
  });
}

function renderUsers(items) {
  destroyChart("users");
  if (!items.length) {
    topUsers.innerHTML = empty("当前范围暂无用户数据");
    setChartEmpty(topUsersChartWrap, "暂无用户排行数据");
    return;
  }

  if (chartReady()) {
    const canvas = resetCanvas(topUsersChartWrap, "topUsersChart", "高频使用用户排行图");
    const topItems = items.slice(0, 8).reverse();
    charts.users = new Chart(canvas, {
      type: "bar",
      data: {
        labels: topItems.map((item) => item.userId),
        datasets: [
          {
            label: "提问",
            data: topItems.map((item) => item.questionCount || 0),
            backgroundColor: "rgba(56, 189, 248, 0.74)",
            borderColor: chartColors.question,
            borderWidth: 1,
            borderRadius: 8,
            barThickness: 14,
          },
          {
            label: "会话",
            data: topItems.map((item) => item.conversationCount || 0),
            backgroundColor: "rgba(245, 158, 11, 0.7)",
            borderColor: chartColors.amber,
            borderWidth: 1,
            borderRadius: 8,
            barThickness: 14,
          },
        ],
      },
      options: baseChartOptions({
        indexAxis: "y",
        plugins: {
          ...baseChartOptions().plugins,
          legend: {
            display: true,
            position: "bottom",
            labels: {
              color: chartColors.text,
              usePointStyle: true,
              pointStyle: "rectRounded",
            },
          },
        },
        scales: {
          x: {
            beginAtZero: true,
            stacked: false,
            grid: {
              color: chartColors.grid,
            },
            ticks: {
              color: chartColors.text,
              precision: 0,
            },
          },
          y: {
            grid: {
              color: "transparent",
            },
            ticks: {
              color: chartColors.text,
            },
          },
        },
      }),
    });
  } else {
    setChartEmpty(topUsersChartWrap, "Chart.js 未加载，无法渲染用户排行图");
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
