/**
 * Безопасный поднабор Markdown для ответов бота. См. docs/WIDGET_ANSWER_FORMAT.md
 */

/**
 * @param {string} s
 */
function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/**
 * @param {string} s
 */
function formatInline(s) {
  let out = escapeHtml(s);
  out = out.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
  out = out.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");
  return out;
}

/**
 * @param {string} line
 */
function lineKind(line) {
  const t = line.trim();
  if (!t) return "blank";
  if (/^#{1,3}\s+/.test(t)) return "h";
  if (/^[-*]\s+/.test(t)) return "ul";
  if (/^\d+\.\s+/.test(t)) return "ol";
  return "p";
}

/**
 * @param {string} line
 */
function stripListPrefix(line) {
  const t = line.trim();
  if (/^[-*]\s+/.test(t)) return t.replace(/^[-*]\s+/, "");
  if (/^\d+\.\s+/.test(t)) return t.replace(/^\d+\.\s+/, "");
  if (/^#{1,3}\s+/.test(t)) return t.replace(/^#{1,3}\s+/, "");
  return t;
}

/**
 * @param {string[]} lines
 * @returns {{ type: string, lines: string[] }[]}
 */
function groupLines(lines) {
  /** @type {{ type: string, lines: string[] }[]} */
  const groups = [];
  /** @type {{ type: string, lines: string[] } | null} */
  let current = null;

  for (const raw of lines) {
    const kind = lineKind(raw);
    if (kind === "blank") {
      if (current) {
        groups.push(current);
        current = null;
      }
      continue;
    }
    if (!current || current.type !== kind) {
      if (current) groups.push(current);
      current = { type: kind, lines: [raw] };
    } else {
      current.lines.push(raw);
    }
  }
  if (current) groups.push(current);
  return groups;
}

/**
 * @param {{ type: string, lines: string[] }} group
 */
function renderGroup(group) {
  const { type, lines } = group;
  if (type === "ul") {
    const items = lines
      .map((ln) => `<li>${formatInline(stripListPrefix(ln))}</li>`)
      .join("");
    return `<ul>${items}</ul>`;
  }
  if (type === "ol") {
    const items = lines
      .map((ln) => `<li>${formatInline(stripListPrefix(ln))}</li>`)
      .join("");
    return `<ol>${items}</ol>`;
  }
  if (type === "h") {
    return lines
      .map((ln) => `<p class="clinic-msg__lead"><strong>${formatInline(stripListPrefix(ln))}</strong></p>`)
      .join("");
  }
  return lines.map((ln) => `<p>${formatInline(ln.trim())}</p>`).join("");
}

/**
 * @param {string} text
 * @returns {string}
 */
export function renderBotAnswerHtml(text) {
  const normalized = String(text || "").replace(/\r\n/g, "\n").trim();
  if (!normalized) return "";
  const groups = groupLines(normalized.split("\n"));
  return groups.map(renderGroup).join("");
}

/**
 * @param {HTMLElement | null} el
 * @param {string} text
 */
export function setBotAnswerBody(el, text) {
  if (!el) return;
  const html = renderBotAnswerHtml(text);
  if (!html) {
    el.classList.remove("clinic-msg__body--rich");
    el.textContent = "";
    return;
  }
  el.classList.add("clinic-msg__body--rich");
  el.innerHTML = html;
}
