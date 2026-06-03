const state = {
  conversationId: crypto.randomUUID(),
  lastAssistantMessageId: null,
  lastQueryMessageId: null,
  pendingFeedbackMessageId: null,
};

const els = {
  userId: document.querySelector("#userId"),
  service: document.querySelector("#service"),
  scene: document.querySelector("#scene"),
  title: document.querySelector("#title"),
  conversationLabel: document.querySelector("#conversationLabel"),
  deepThinking: document.querySelector("#deepThinking"),
  messages: document.querySelector("#messages"),
  query: document.querySelector("#query"),
  composer: document.querySelector("#composer"),
  send: document.querySelector("#send"),
  history: document.querySelector("#history"),
  newConversation: document.querySelector("#newConversation"),
  loadHistory: document.querySelector("#loadHistory"),
  historySearch: document.querySelector("#historySearch"),
  dialog: document.querySelector("#feedbackDialog"),
  feedbackText: document.querySelector("#feedbackText"),
  submitUnlike: document.querySelector("#submitUnlike"),
  emptyState: document.querySelector("#emptyState"),
};

const sendIcon = `
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M5 12h13" />
    <path d="m13 6 6 6-6 6" />
  </svg>
`;

let conversations = [];

function setConversationLabel() {
  els.conversationLabel.textContent = `会话 ${state.conversationId.slice(0, 8)}`;
}

function currentUserId() {
  return els.userId.value.trim() || "anonymous";
}

function currentContext() {
  return {
    userId: currentUserId(),
    conversationId: state.conversationId,
    service: els.service.value,
    scene: els.scene.value.trim() || "模型任务",
    title: els.title.textContent,
  };
}

function setSendLoading(isLoading) {
  els.send.disabled = isLoading;
  els.send.title = isLoading ? "生成中" : "发送";
  els.send.setAttribute("aria-label", isLoading ? "生成中" : "发送");
  els.send.innerHTML = isLoading ? `<span class="send-loader"></span>` : sendIcon;
}

function feedbackLabel(feedback) {
  if (feedback === "like") return "已赞";
  if (feedback === "unlike") return "已踩";
  return "";
}

function avatarSvg(type) {
  if (type === "assistant") {
    return `
      <svg viewBox="0 0 48 48" aria-hidden="true">
        <defs>
          <linearGradient id="agentAvatar" x1="7" y1="8" x2="41" y2="42" gradientUnits="userSpaceOnUse">
            <stop stop-color="#64E2D0" />
            <stop offset="1" stop-color="#1B7891" />
          </linearGradient>
        </defs>
        <rect x="7" y="9" width="34" height="32" rx="12" fill="url(#agentAvatar)" />
        <path d="M18 8h12" stroke="#D9FFFB" stroke-width="3" stroke-linecap="round" />
        <circle cx="18" cy="25" r="3" fill="#081827" />
        <circle cx="30" cy="25" r="3" fill="#081827" />
        <path d="M18 33c4 3 12 3 16 0" stroke="#081827" stroke-width="2.5" stroke-linecap="round" />
        <circle cx="38" cy="16" r="4" fill="#A8FFF4" />
      </svg>
    `;
  }
  return `
    <svg viewBox="0 0 48 48" aria-hidden="true">
      <defs>
        <linearGradient id="userAvatar" x1="8" y1="5" x2="39" y2="43" gradientUnits="userSpaceOnUse">
          <stop stop-color="#25354F" />
          <stop offset="1" stop-color="#0F1728" />
        </linearGradient>
      </defs>
      <rect x="6" y="6" width="36" height="36" rx="14" fill="url(#userAvatar)" />
      <circle cx="24" cy="19" r="7" fill="#F4F8FB" />
      <path d="M13 38c2.7-8 8.4-11 11-11s8.3 3 11 11" fill="#F4F8FB" />
      <path d="M13 38c2.7-8 8.4-11 11-11s8.3 3 11 11" fill="#49C0B6" opacity=".34" />
    </svg>
  `;
}

function feedbackIcon(type) {
  const rotate = type === "unlike" ? ' class="thumb-down"' : "";
  return `
    <svg${rotate} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M7.8 10.8V20" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" />
      <path d="M8 11.2l3.8-6.9c.5-.9 1.9-.6 1.9.5v5.1h4.1c1.4 0 2.4 1.3 2.1 2.7l-1 4.6c-.3 1.2-1.3 2-2.5 2H8" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round" />
      <path d="M4 11.1h3.8v8.1H4c-.8 0-1.4-.6-1.4-1.4v-5.4c0-.8.6-1.3 1.4-1.3Z" fill="currentColor" opacity=".18" stroke="currentColor" stroke-width="1.5" />
    </svg>
  `;
}

function setFeedbackState(messageNode, feedback) {
  const buttons = messageNode.querySelectorAll("[data-feedback]");
  for (const button of buttons) {
    const isActive = button.dataset.feedback === feedback;
    const action = button.dataset.feedback === "like" ? "点赞" : "点踩";
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-pressed", String(isActive));
    button.title = isActive ? feedbackLabel(feedback) : action;
    button.setAttribute("aria-label", isActive ? feedbackLabel(feedback) : action);
  }
}

function appendMessage(type, content, options = {}) {
  els.emptyState?.remove();
  const node = document.createElement("article");
  node.className = `message ${type}`;
  node.dataset.messageId = options.messageId || "";
  node.dataset.queryMessageId = options.queryMessageId || "";

  const meta = document.createElement("div");
  meta.className = "message-meta";
  meta.innerHTML = `
    <span class="avatar ${type}" title="${type === "assistant" ? "Agent" : "User"}">${avatarSvg(type)}</span>
    <span>${options.timestamp || "刚刚"}</span>
  `;
  node.appendChild(meta);

  const contentNode = document.createElement("div");
  contentNode.className = "message-content";
  contentNode.textContent = content;
  node.appendChild(contentNode);

  if (type === "assistant" && options.messageId) {
    const feedback = document.createElement("div");
    feedback.className = "feedback";
    feedback.innerHTML = `
      <button type="button" title="点赞" aria-label="点赞" aria-pressed="false" data-feedback="like">${feedbackIcon("like")}</button>
      <button type="button" title="点踩" aria-label="点踩" aria-pressed="false" data-feedback="unlike">${feedbackIcon("unlike")}</button>
    `;
    node.appendChild(feedback);
    setFeedbackState(node, options.feedbackInfo?.feedback);
  }

  els.messages.appendChild(node);
  els.messages.scrollTop = els.messages.scrollHeight;
  return { node, contentNode };
}

function resetConversation() {
  state.conversationId = crypto.randomUUID();
  state.lastAssistantMessageId = null;
  state.lastQueryMessageId = null;
  state.pendingFeedbackMessageId = null;
  els.messages.innerHTML = "";
  els.messages.appendChild(createEmptyState());
  setConversationLabel();
  highlightHistory();
}

function createEmptyState() {
  const node = document.createElement("div");
  node.className = "empty-state";
  node.id = "emptyState";
  node.innerHTML = `
    <div class="terminal-mark" aria-hidden="true">
      <svg viewBox="0 0 24 24">
        <path d="m7 8 4 4-4 4" />
        <path d="M13 17h6" />
      </svg>
    </div>
    <div class="empty-title">Wise MLOps Agent</div>
    <p class="empty-subtitle">专业智能诊断伙伴，为模型任务、资源异常和平台日志提供排查建议。</p>
    <div class="empty-tags">
      <span>Memory</span>
      <span>OOM</span>
      <span>GPU</span>
      <span>Checkpoint</span>
      <span>Dataset</span>
    </div>
  `;
  els.emptyState = node;
  return node;
}

function highlightHistory() {
  for (const item of els.history.querySelectorAll(".history-item")) {
    item.classList.toggle("active", item.dataset.conversationId === state.conversationId);
  }
}

async function sendFeedback(messageNode, feedback, reason = null) {
  const messageId = messageNode.dataset.messageId;
  const queryMessageId = messageNode.dataset.queryMessageId || state.lastQueryMessageId;
  const response = await fetch("/agent/v1/assistant/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      feedback,
      reason,
      context: {
        userId: currentUserId(),
        conversationId: state.conversationId,
        messageId,
        queryMessageId,
      },
    }),
  });
  const payload = await response.json();
  if (!response.ok || payload.result?.code !== 0) {
    throw new Error(payload.result?.des || "反馈提交失败");
  }
  setFeedbackState(messageNode, feedback);
}

async function submitChat(event) {
  event.preventDefault();
  const query = els.query.value.trim();
  if (!query || els.send.disabled) return;

  appendMessage("user", query);
  els.query.value = "";
  setSendLoading(true);

  try {
    const response = await fetch("/agent/v1/assistant/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        needDeepThinking: els.deepThinking.checked ? 1 : 0,
        prompt: "mlops-agent",
        context: currentContext(),
      }),
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let pending = "";
    let assistant = null;
    let fullText = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      pending += decoder.decode(value, { stream: true });
      const events = pending.split("\n\n");
      pending = events.pop() || "";

      for (const eventText of events) {
        const line = eventText.split("\n").find((item) => item.startsWith("data: "));
        if (!line) continue;
        const payload = JSON.parse(line.slice(6));
        state.lastAssistantMessageId = payload.messageId;
        state.lastQueryMessageId = payload.queryMessageId;
        fullText += payload.content;
        if (!assistant) {
          assistant = appendMessage("assistant", "", {
            messageId: payload.messageId,
            queryMessageId: payload.queryMessageId,
          });
        }
        assistant.node.dataset.queryMessageId = payload.queryMessageId;
        assistant.contentNode.textContent = fullText;
        els.messages.scrollTop = els.messages.scrollHeight;
      }
    }
    await loadHistory();
  } finally {
    setSendLoading(false);
  }
}

function renderHistory() {
  const keyword = els.historySearch.value.trim().toLowerCase();
  const filtered = keyword
    ? conversations.filter((item) => `${item.title} ${item.conversationId}`.toLowerCase().includes(keyword))
    : conversations;
  els.history.innerHTML = "";
  for (const item of filtered) {
    const button = document.createElement("button");
    button.className = "history-item";
    button.dataset.conversationId = item.conversationId;
    button.innerHTML = `<strong>${item.title}</strong><span>${item.timestamp || ""}</span>`;
    button.addEventListener("click", () => loadConversation(item.conversationId));
    els.history.appendChild(button);
  }
  highlightHistory();
}

async function loadHistory() {
  const response = await fetch("/agent/v1/assistant/conversation/list", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ userId: currentUserId() }),
  });
  const payload = await response.json();
  conversations = payload.result.data || [];
  renderHistory();
}

async function loadConversation(conversationId) {
  state.conversationId = conversationId;
  setConversationLabel();
  highlightHistory();
  const response = await fetch("/agent/v1/assistant/chat/list", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      userId: currentUserId(),
      conversationId,
      page: 1,
      pageSize: 100,
    }),
  });
  const payload = await response.json();
  els.messages.innerHTML = "";
  els.emptyState = null;
  for (const item of payload.result.data || []) {
    appendMessage(item.type, item.content, {
      messageId: item.messageId,
      queryMessageId: item.queryMessageId,
      timestamp: item.timestamp,
      feedbackInfo: item.feedbackInfo,
    });
    if (item.type === "assistant") {
      state.lastAssistantMessageId = item.messageId;
      state.lastQueryMessageId = item.queryMessageId || state.lastQueryMessageId;
    }
  }
  if (!(payload.result.data || []).length) {
    els.messages.appendChild(createEmptyState());
  }
}

els.composer.addEventListener("submit", submitChat);
els.newConversation.addEventListener("click", resetConversation);
els.loadHistory.addEventListener("click", loadHistory);
els.historySearch.addEventListener("input", renderHistory);
els.messages.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-feedback]");
  if (!button) return;
  const messageNode = button.closest(".message");
  if (button.dataset.feedback === "like") {
    await sendFeedback(messageNode, "like");
    return;
  }
  state.pendingFeedbackMessageId = messageNode.dataset.messageId;
  els.feedbackText.value = "";
  for (const checkbox of document.querySelectorAll(".chips input")) {
    checkbox.checked = false;
  }
  els.dialog.showModal();
});

els.submitUnlike.addEventListener("click", async () => {
  const messageNode = els.messages.querySelector(`[data-message-id="${state.pendingFeedbackMessageId}"]`);
  if (!messageNode) return;
  const selected = [...document.querySelectorAll(".chips input:checked")].map((item) => item.value);
  await sendFeedback(messageNode, "unlike", {
    feedbackInfo: els.feedbackText.value.trim(),
    feedbackInfoTypes: selected,
  });
});

setConversationLabel();
loadHistory();
