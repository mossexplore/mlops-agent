/* API client for the Wise MLOps Console.
   Wraps the FastAPI `/agent/v1/...` endpoints. Plain JS (no JSX) so it can load
   before the Babel-compiled view scripts and expose `window.API`. */
(function () {
  async function post(url, body) {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    if (response.status === 401) {
      window.location.href = "/login";
      throw new Error("未登录");
    }
    let json;
    try {
      json = await response.json();
    } catch (_e) {
      throw new Error("响应解析失败");
    }
    if (!response.ok || json.result?.code !== 0) {
      throw new Error(json.result?.des || `请求失败 (${response.status})`);
    }
    return json.result.data;
  }

  /* Streaming chat. Calls onChunk(payload) for every SSE event; resolves with the
     final accumulated text + metadata. Returns the AbortController so callers can stop. */
  function chatStream(body, onChunk, signal) {
    return fetch("/agent/v1/assistant/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    }).then(async (response) => {
      if (response.status === 401) {
        window.location.href = "/login";
        throw new Error("未登录");
      }
      if (!response.ok || !response.body) {
        throw new Error(`请求失败 (${response.status})`);
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let pending = "";
      let fullText = "";
      let last = null;
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        pending += decoder.decode(value, { stream: true });
        const events = pending.split("\n\n");
        pending = events.pop() || "";
        for (const eventText of events) {
          const line = eventText.split("\n").find((l) => l.startsWith("data: "));
          if (!line) continue;
          const payload = JSON.parse(line.slice(6));
          fullText += payload.content || "";
          last = payload;
          onChunk(payload, fullText);
        }
      }
      return { fullText, last };
    });
  }

  const API = {
    post,
    chatStream,

    // auth
    me: () => fetch("/agent/v1/auth/me").then((r) => (r.ok ? r.json() : null)),
    logout: () => fetch("/agent/v1/auth/logout", { method: "POST" }),

    // chat / conversations
    conversationList: (userId, conversationId) =>
      post("/agent/v1/assistant/conversation/list", { userId, conversationId }),
    chatList: (userId, conversationId, page = 1, pageSize = 100) =>
      post("/agent/v1/assistant/chat/list", { userId, conversationId, page, pageSize }),
    traceDetail: (traceId) => post("/agent/v1/assistant/trace/detail", { traceId }),
    diagnosticState: (userId, conversationId) =>
      post("/agent/v1/assistant/diagnostic/state", { userId, conversationId }),
    feedback: (context, feedback, reason = null) =>
      post("/agent/v1/assistant/feedback", { feedback, reason, context }),

    // knowledge
    knowledgeList: () => post("/agent/v1/knowledge/list", {}),
    knowledgeDetail: (filename) => post("/agent/v1/knowledge/detail", { filename }),
    knowledgeSave: (payload) => post("/agent/v1/knowledge/save", payload),
    knowledgeSearch: (query, topK = 5) => post("/agent/v1/knowledge/search", { query, topK }),
    knowledgeStatus: (filename, status, reviewNotes = null) =>
      post("/agent/v1/knowledge/status", { filename, status, reviewNotes }),
    knowledgeRevisions: (filename, page = 1, pageSize = 8) =>
      post("/agent/v1/knowledge/revision/list", { filename, page, pageSize }),
    knowledgeGaps: (page = 1, pageSize = 8) =>
      post("/agent/v1/knowledge/gap/list", { page, pageSize }),

    // runbooks
    runbookList: (filters = {}) => post("/agent/v1/runbook/list", filters),
    runbookDetail: (runbookId) => post("/agent/v1/runbook/detail", { runbookId }),
    runbookSave: (payload) => post("/agent/v1/runbook/save", payload),
    runbookStatus: (runbookId, status) => post("/agent/v1/runbook/status", { runbookId, status }),

    // ops
    opsDashboard: (filters = {}) => post("/agent/v1/ops/dashboard", filters),

    // quality
    qualityDashboard: () => post("/agent/v1/quality/dashboard", {}),
    qualityFeedbackAnnotate: (payload) => post("/agent/v1/quality/feedback/annotate", payload),
    qualityEvalCaseSave: (payload) => post("/agent/v1/quality/eval-case/save", payload),
    qualityEvalCaseFromFeedback: (payload) => post("/agent/v1/quality/eval-case/from-feedback", payload),
    qualityEvalRun: (payload) => post("/agent/v1/quality/eval/run", payload),
    qualityExperimentSave: (payload) => post("/agent/v1/quality/experiment/save", payload),
  };

  window.API = API;
})();
