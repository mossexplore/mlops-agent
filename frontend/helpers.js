/* Shared non-React helpers + static config. Plain JS, loaded before Babel scripts. */
(function () {
  const REASON_LABELS = {
    knowledge_missing: "知识缺失",
    retrieval_error: "检索错误",
    generic_answer: "回答泛泛",
    unactionable_steps: "步骤不可执行",
    scene_misclassification: "误判场景",
  };

  const REASON_TONE = {
    knowledge_missing: "bad",
    retrieval_error: "warn",
    generic_answer: "warn",
    unactionable_steps: "info",
    scene_misclassification: "neutral",
  };

  const QUICK_PROMPTS = [
    { k: "Memory OOM", q: "1401027 insufficient memory 报错" },
    { k: "Pending", q: "训练任务 Pending 很久，帮我按 Runbook 排查" },
    { k: "GPU 低利用", q: "GPU 利用率很低但任务很慢，应该看哪些证据" },
    { k: "Checkpoint", q: "checkpoint 加载阶段失败，如何定位原因" },
    { k: "Dataset", q: "数据集读取很慢导致训练卡住，怎么排查" },
  ];

  const ACTION_LABELS = { check: "检查", tool: "工具", manual: "人工", confirm: "确认", verify: "验证" };

  function reasonLabel(key) {
    return REASON_LABELS[key] || key || "未标注";
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

  function nowTime() {
    const d = new Date();
    return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  }

  function isoDate(date) {
    return date.toISOString().slice(0, 10);
  }

  function rangeDates(days) {
    const end = new Date();
    const start = new Date();
    start.setDate(end.getDate() - (days - 1));
    return { startDate: isoDate(start), endDate: isoDate(end) };
  }

  function pct(value, digits = 0) {
    return `${(Number(value || 0) * 100).toFixed(digits)}`;
  }

  /* ---------- minimal markdown renderer (returns HTML string) ---------- */
  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function renderInline(text) {
    const placeholders = [];
    let escaped = escapeHtml(text);
    escaped = escaped.replace(/`([^`]+)`/g, (_, code) => {
      const token = `@@CODE${placeholders.length}@@`;
      placeholders.push(`<code>${code}</code>`);
      return token;
    });
    escaped = escaped
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\*([^*\n]+)\*/g, "<em>$1</em>")
      .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
    placeholders.forEach((html, i) => {
      escaped = escaped.replace(`@@CODE${i}@@`, html);
    });
    return escaped;
  }

  function renderMarkdown(markdown) {
    const lines = String(markdown ?? "").replace(/\r\n/g, "\n").split("\n");
    const html = [];
    let paragraph = [];
    let listType = null;
    let inCode = false;
    let codeLines = [];

    const closeParagraph = () => {
      if (!paragraph.length) return;
      html.push(`<p>${renderInline(paragraph.join(" "))}</p>`);
      paragraph = [];
    };
    const closeList = () => {
      if (!listType) return;
      html.push(`</${listType}>`);
      listType = null;
    };
    const closeCode = () => {
      html.push(`<pre class="md-code"><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
      codeLines = [];
      inCode = false;
    };

    for (const rawLine of lines) {
      const line = rawLine.replace(/\s+$/, "");
      const trimmed = line.trim();
      if (trimmed.startsWith("```")) {
        closeParagraph();
        closeList();
        if (inCode) closeCode();
        else {
          inCode = true;
          codeLines = [];
        }
        continue;
      }
      if (inCode) {
        codeLines.push(rawLine);
        continue;
      }
      if (!trimmed) {
        closeParagraph();
        closeList();
        continue;
      }
      const heading = /^(#{1,6})\s+(.+)$/.exec(trimmed);
      if (heading) {
        closeParagraph();
        closeList();
        html.push(`<h${heading[1].length}>${renderInline(heading[2])}</h${heading[1].length}>`);
        continue;
      }
      const quote = /^>\s?(.+)$/.exec(trimmed);
      if (quote) {
        closeParagraph();
        closeList();
        html.push(`<blockquote>${renderInline(quote[1])}</blockquote>`);
        continue;
      }
      const bullet = /^[-*+]\s+(.+)$/.exec(trimmed);
      const ordered = /^(\d+)[.)]\s+(.+)$/.exec(trimmed);
      if (bullet || ordered) {
        closeParagraph();
        const nextType = bullet ? "ul" : "ol";
        if (listType !== nextType) {
          closeList();
          html.push(`<${nextType}>`);
          listType = nextType;
        }
        html.push(`<li>${renderInline(bullet ? bullet[1] : ordered[2])}</li>`);
        continue;
      }
      closeList();
      paragraph.push(trimmed);
    }
    if (inCode) closeCode();
    closeParagraph();
    closeList();
    return html.join("");
  }

  window.H = {
    REASON_LABELS,
    REASON_TONE,
    QUICK_PROMPTS,
    ACTION_LABELS,
    reasonLabel,
    splitList,
    joinList,
    nowTime,
    isoDate,
    rangeDates,
    pct,
    escapeHtml,
    renderMarkdown,
  };
})();
