// ===========================================================================
// InternHunter — Editorial demo UI (T0018.3)
//
// Talks ONLY to the public /api/v1 surface. Consumes the T0017 SSE stream with
// fetch() + a ReadableStream reader (no EventSource: the endpoint is POST+body,
// and EventSource would auto-reconnect and re-run the agent — we don't want that).
//
// Event vocabulary (from the backend):
//   session  { session_id }            -> pin it; send on every later turn
//   token    { text }         (0+)     -> append word-by-word to the answer
//   tool     { name, status, arguments, duration_ms }
//                                       -> a card showing what the agent ran
//   metadata { trace_id, trace_url }   -> show a "view trace" link if trace_url
//   error    { message }               -> friendly error bubble; stop
//   done     {}                        -> terminal; stop reading, no reconnect
//
// Screen-reader contract, because mutating a live region token by token makes it
// unusable: the conversation is a role="log" in the initial markup; aria-busy is
// set before the first token; tokens land in an aria-hidden visual node; and on
// completion the full answer is written ONCE to a visually-hidden node before
// aria-busy is cleared. That yields exactly one announcement per answer, and the
// answer stays navigable afterwards. There is no W3C normative technique for
// streaming into a live region, so this is verified by hand with NVDA and
// VoiceOver rather than assumed correct.
// ===========================================================================

// --- element handles -------------------------------------------------------
const conversation = document.getElementById("conversation");
const lede = document.getElementById("lede");
const chipRow = document.getElementById("chips");
const form = document.getElementById("composer");
const input = document.getElementById("query");
const sendBtn = document.getElementById("send");
const stopBtn = document.getElementById("stop");
const dateline = document.getElementById("dateline");
const toast = document.getElementById("toast");

const markdownRenderer = new window.marked.Renderer();
markdownRenderer.html = () => "";

// The server's own "I have nothing for you" constant, from
// src/agents/service.py. Matching it is a documented contract rather than a
// guess at phrasing; tests/api/test_static_serving.py pins the two together so
// they cannot drift. Telling "no answer" apart from a real answer needs a
// richer signal - a tool event carrying the row count - which is deliberately
// out of scope here.
const NO_ANSWER_TEXT =
  "I couldn't produce an answer for that — please try rephrasing.";

// Re-render at most this often while tokens arrive. Rewriting the whole answer
// node per token is quadratic and thrashes layout; the stream itself is
// untouched, only the paint is coalesced.
const PAINT_INTERVAL_MS = 50;

// --- conversation state ----------------------------------------------------
let sessionId = null;     // pinned from the first `session` event; reused after
let state = "ready";      // ready | submitted | streaming | error
let toastTimer = null;
let inFlight = false;     // derived from state, kept for the chip guard
let controller = null;    // AbortController for the turn in flight
let snapshotDate = "";    // measured corpus date, for the no-answer card

// ===========================================================================
// Frozen-snapshot notice / dateline - read the snapshot date from /api/v1/ready.
// Never crash, never show "undefined": fall back to the dateless sentence.
// ===========================================================================
async function loadDateline() {
  const unknownFreshness =
    "Kho dữ liệu lịch sử · ngày chụp chưa rõ · kết quả không xác nhận vị trí đang tuyển.";
  try {
    const res = await fetch("/api/v1/ready");
    if (!res.ok) return;                       // 503 if DB down - keep fallback
    const data = await res.json();
    const date = data && data.data_snapshot_date;
    const isMeasured = data && data.data_snapshot_date_provenance === "measured";
    if (date && isMeasured) {
      snapshotDate = date;
      dateline.textContent =
        `Kho dữ liệu lịch sử · ảnh chụp ${date} · kết quả không xác nhận vị trí đang tuyển.`;
    } else {
      dateline.textContent = unknownFreshness;
    }
  } catch {
    // network error - the fallback text is already in the markup
  }
}

// ===========================================================================
// DOM builders — one "turn" = the reader's question + the agent's answer.
// ===========================================================================

// Build a turn, append it, and return the pieces the stream writes into.
function startTurn(query) {
  if (lede && lede.parentNode) lede.remove();   // clear the opening note once

  const turn = document.createElement("article");
  turn.className = "turn";

  // the reader's question
  const you = document.createElement("div");
  you.className = "turn__you";
  you.innerHTML = '<span class="turn__label">Bạn hỏi</span>';
  const youText = document.createElement("p");
  youText.className = "turn__you-text";
  youText.textContent = query;
  you.appendChild(youText);

  // the agent's answer, marked by the vermilion editor's rule
  const agent = document.createElement("div");
  agent.className = "turn__agent is-streaming";
  agent.innerHTML = '<span class="turn__label">InternHunter</span>';

  // Tokens are painted here while they arrive. aria-hidden keeps a screen
  // reader out of a node that changes many times per second; the finished
  // answer is published to `spoken` instead, once.
  const answer = document.createElement("div");
  answer.className = "turn__answer turn__answer--pending";
  answer.setAttribute("aria-hidden", "true");
  answer.textContent = "Đang đọc các tin tuyển dụng…";
  agent.appendChild(answer);

  // The single published copy. Visually hidden, but fully navigable, so the
  // answer is readable on demand after it has been announced once.
  const spoken = document.createElement("div");
  spoken.className = "turn__spoken";
  agent.appendChild(spoken);

  // The agent's work is shown here as cards, before the answer. Evidence
  // rather than narration: a card names a tool and its arguments, never "I
  // searched and found".
  const work = document.createElement("div");
  work.className = "turn__work";
  agent.appendChild(work);

  turn.appendChild(you);
  turn.appendChild(agent);
  conversation.appendChild(turn);

  // Mute the log before the first token, so nothing that follows is announced
  // piecemeal.
  conversation.setAttribute("aria-busy", "true");

  scrollToEnd();
  return {
    turn,
    agent,
    answer,
    spoken,
    work,
    gotToken: false,
    rawAnswer: "",
    pendingPaint: null,
    toolCards: new Map(),
    zeroResult: false,
  };
}

// A tool card is evidence, not narration. It appears when the call starts and
// resolves when it finishes, so the reader can see the agent is working and what
// it chose to look at.
function upsertToolCard(ctx, event) {
  const key = event.call_id || event.name;
  let card = ctx.toolCards.get(key);

  if (!card) {
    card = document.createElement("div");
    card.className = "toolcard";
    ctx.work.appendChild(card);
    ctx.toolCards.set(key, card);
  }

  card.dataset.status = event.status;
  card.textContent = "";

  const name = document.createElement("span");
  name.className = "toolcard__name";
  name.textContent = event.name;
  card.appendChild(name);

  for (const [argKey, value] of Object.entries(event.arguments || {})) {
    const arg = document.createElement("span");
    arg.className = "toolcard__arg";
    arg.textContent = `${argKey}: ${value}`;
    card.appendChild(arg);
  }

  const status = document.createElement("span");
  status.className = "toolcard__status";
  if (event.status === "running") {
    status.textContent = "đang chạy…";
  } else if (event.status === "ok") {
    status.textContent = describeResult(event);
  } else {
    status.textContent = event.error ? `lỗi: ${event.error}` : "lỗi";
  }
  card.appendChild(status);

  // A real zero-match is the signal the interface should key its no-answer state
  // to, not the agent falling silent. Absent and zero are different facts.
  if (event.status === "ok" && event.row_count === 0) {
    ctx.zeroResult = true;
  }

  scrollToEnd();
}

// The count, stated honestly. `truncated` matters: a bare number would imply the
// answer shows every match, which is the impression to avoid.
function describeResult(event) {
  const parts = [];
  if (typeof event.row_count === "number") {
    parts.push(
      event.truncated
        ? `hiển thị một phần · ${event.row_count} kết quả`
        : `${event.row_count} kết quả`,
    );
  }
  if (typeof event.duration_ms === "number") {
    parts.push(`${event.duration_ms} ms`);
  }
  return parts.length ? parts.join(" · ") : "xong";
}

// Coalesce token paints onto a timer. The first token paints immediately so the
// placeholder clears at once.
function schedulePaint(ctx) {
  if (ctx.pendingPaint !== null) return;
  ctx.pendingPaint = window.setTimeout(() => {
    ctx.pendingPaint = null;
    paintAnswer(ctx);
  }, PAINT_INTERVAL_MS);
}

function flushPaint(ctx) {
  if (ctx.pendingPaint !== null) {
    window.clearTimeout(ctx.pendingPaint);
    ctx.pendingPaint = null;
  }
  paintAnswer(ctx);
}

// Write the accumulated answer to the visual node.
function paintAnswer(ctx) {
  if (!ctx.gotToken) return;
  ctx.answer.textContent = ctx.rawAnswer;
  scrollToEnd();
}

// Append one token, clearing the pending placeholder on the first one.
function appendToken(ctx, text) {
  if (!ctx.gotToken) {
    ctx.gotToken = true;
    ctx.answer.classList.remove("turn__answer--pending");
    ctx.rawAnswer = "";
    paintAnswer(ctx);
  }
  ctx.rawAnswer += text;
  schedulePaint(ctx);
}

// Render only the complete response so unfinished Markdown never causes the
// stream to jump between malformed intermediate layouts. Raw HTML is removed
// by the Marked renderer and DOMPurify sanitizes the generated HTML before it
// is assigned to the page.
function renderMarkdown(ctx) {
  if (!ctx.gotToken || typeof window.marked?.parse !== "function" || !window.DOMPurify) {
    return;
  }

  try {
    const html = window.marked.parse(ctx.rawAnswer, {
      breaks: true,
      gfm: true,
      renderer: markdownRenderer,
    });
    ctx.answer.innerHTML = DOMPurify.sanitize(html, {
      ALLOW_DATA_ATTR: false,
      FORBID_ATTR: ["style"],
      FORBID_TAGS: ["math", "style", "svg"],
      USE_PROFILES: { html: true },
    });
    ctx.answer.classList.add("turn__answer--markdown");
  } catch {
    // Plain text is a safe and readable fallback if a future parser upgrade
    // cannot render a particular response.
  }
}

// Show the trailing "view trace" link only when trace_url is a real URL.
function showTraceLink(ctx, traceUrl) {
  const p = document.createElement("p");
  p.className = "turn__trace";
  const a = document.createElement("a");
  a.href = traceUrl;
  a.target = "_blank";
  a.rel = "noopener noreferrer";
  a.textContent = "Xem dấu vết →";
  p.appendChild(a);
  ctx.agent.appendChild(p);
}

// True when the agent answered, but the search genuinely matched nothing. The
// FALLBACK_ANSWER case is different: that is the agent producing no output at
// all, and it is handled separately as a fallback.
function isNoAnswer(ctx) {
  return ctx.zeroResult === true || ctx.rawAnswer.trim() === NO_ANSWER_TEXT;
}

// A "no answer" outcome is a designed state, not an apology paragraph. It says
// what was searched and when the corpus was captured, and offers reformulations.
// It deliberately does not claim a row count or a date range: the stream does
// not carry either, and a dataset-bounded agent must not invent one.
function showNoAnswerCard(ctx, query) {
  ctx.agent.classList.add("is-nodata");
  ctx.answer.classList.remove("turn__answer--pending");
  ctx.answer.textContent = "";

  const card = document.createElement("div");
  card.className = "turn__nodata";

  const title = document.createElement("p");
  title.className = "turn__nodata-title";
  title.textContent = "Không có câu trả lời cho câu hỏi này";
  card.appendChild(title);

  const detail = document.createElement("p");
  detail.className = "turn__nodata-detail";
  detail.textContent = ctx.zeroResult
    ? `Truy vấn đã chạy và không tìm thấy tin nào phù hợp${snapshotDate ? ` trong kho chụp ngày ${snapshotDate}` : " trong kho dữ liệu đã thu thập"}. Kho chỉ chứa tin tuyển dụng đã thu thập, không phải vị trí đang tuyển.`
    : snapshotDate
      ? `Đã tìm trong kho dữ liệu lịch sử chụp ngày ${snapshotDate}. Kho chỉ chứa tin tuyển dụng đã thu thập, không phải vị trí đang tuyển.`
      : "Đã tìm trong kho dữ liệu lịch sử đã thu thập. Kho chỉ chứa tin tuyển dụng đã thu thập, không phải vị trí đang tuyển.";
  card.appendChild(detail);

  const asked = document.createElement("p");
  asked.className = "turn__nodata-asked";
  asked.textContent = `Câu hỏi: ${query}`;
  card.appendChild(asked);

  const hints = document.createElement("div");
  hints.className = "turn__nodata-chips";
  for (const label of ["Bỏ điều kiện lương", "Thử địa điểm khác", "Hỏi về kỹ năng thay vì chức danh"]) {
    const chip = document.createElement("button");
    chip.className = "chip";
    chip.type = "button";
    chip.textContent = label;
    chip.dataset.query = label;
    hints.appendChild(chip);
  }
  card.appendChild(hints);

  ctx.agent.appendChild(card);
  scrollToEnd();
}

const DEFAULT_TURN_ERROR =
  "Hiện chưa thể hoàn tất yêu cầu này. Vui lòng thử lại sau.";

// Fail a turn: tell the reader it failed, and say why. Whatever streamed before
// the failure is a fragment rather than an answer, so it is neither rendered as
// Markdown nor published to the accessible copy. The failure text takes the same
// single-announcement path an answer does, so a failed turn is announced once and
// stays navigable like a successful one.
function failTurn(ctx, message) {
  flushPaint(ctx);
  ctx.agent.classList.remove("is-streaming");
  ctx.agent.classList.add("is-error");

  ctx.answer.classList.remove("turn__answer--pending");
  ctx.answer.textContent = message || DEFAULT_TURN_ERROR;
  publishAnswer(ctx, ctx.answer.textContent);
}

// Publish the finished answer to the accessible copy exactly once, then unmute
// the log. Order matters: the text is written while aria-busy is still true, so
// the announcement fires as a single utterance when aria-busy clears, rather
// than once per token.
function publishAnswer(ctx, finalText) {
  ctx.spoken.textContent = finalText;
  conversation.setAttribute("aria-busy", "false");
}

// Finish a turn: drop the streaming cursor, publish, and hand the composer back.
function endTurn(ctx, { stopped = false } = {}) {
  flushPaint(ctx);
  ctx.agent.classList.remove("is-streaming");

  if (isNoAnswer(ctx)) {
    showNoAnswerCard(ctx, ctx.query || "");
    publishAnswer(
      ctx,
      "Không có câu trả lời cho câu hỏi này trong kho dữ liệu đã thu thập.",
    );
    return;
  }

  renderMarkdown(ctx);
  const published = stopped ? `Đã dừng. ${ctx.rawAnswer.trim()}` : ctx.rawAnswer.trim();
  publishAnswer(ctx, published || "Câu trả lời rỗng.");
}

function scrollToEnd() {
  // keep the newest content in view without yanking the whole page around
  window.requestAnimationFrame(() => {
    conversation.lastElementChild?.scrollIntoView({
      block: "nearest",
      behavior: "smooth",
    });
  });
}

// ===========================================================================
// Toast — pre-stream HTTP failures (400 empty query / 429 rate-limited) that
// arrive as a normal response BEFORE the stream opens.
// ===========================================================================
function showToast(message) {
  toast.textContent = message;
  toast.hidden = false;
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.hidden = true;
  }, 5000);
}

// ===========================================================================
// State — four explicit states, and the control says which one is active.
//   ready      -> send enabled, Stop hidden
//   submitted  -> Stop shown, no token yet
//   streaming  -> Stop shown
//   error      -> the turn is styled as failed; the composer is usable again
// ===========================================================================
function setState(next) {
  state = next;
  inFlight = next === "submitted" || next === "streaming";

  input.disabled = inFlight;
  // Swap the control rather than relabel it, so the accessible name of the
  // control the reader can activate always matches what it will do.
  sendBtn.hidden = inFlight;
  stopBtn.hidden = !inFlight;
  document.body.dataset.streamState = next;

  for (const chip of chipRow.querySelectorAll(".chip")) chip.disabled = inFlight;
}

// ===========================================================================
// The stream — the core of the demo.
// ===========================================================================
async function ask(query) {
  if (inFlight) return;
  const text = query.trim();
  if (!text) return;

  setState("submitted");
  const ctx = startTurn(text);
  ctx.query = text;
  // One controller per turn, so Stop abandons exactly this request. The server
  // already detects client disconnect and closes the agent stream, so no
  // cancel endpoint is needed.
  controller = new AbortController();
  const signal = controller.signal;
  let stopped = false;

  try {
    const body = { query: text };
    if (sessionId) body.session_id = sessionId;   // omit on the first turn

    const res = await fetch("/api/v1/agent/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });

    // Pre-stream failure: a real HTTP status before the stream body opens.
    if (!res.ok) {
      const payload = await res.json().catch(() => ({}));
      failTurn(ctx, "Câu hỏi chưa được gửi đi.");
      showToast(payload.detail || "Đã xảy ra lỗi. Vui lòng thử lại.");
      return;
    }

    // Read the stream, splitting on the blank line that ends each SSE block.
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = "";

    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });

      let i;
      while ((i = buf.indexOf("\n\n")) !== -1) {
        const block = buf.slice(0, i);
        buf = buf.slice(i + 2);

        const ev = /event: (.*)/.exec(block)?.[1];
        const data = JSON.parse(/data: (.*)/s.exec(block)?.[1] ?? "{}");

        if (ev === "session") {
          sessionId = data.session_id;
        } else if (ev === "token") {
          if (state === "submitted") setState("streaming");
          appendToken(ctx, data.text);
        } else if (ev === "tool") {
          upsertToolCard(ctx, data);
        } else if (ev === "metadata") {
          if (data.trace_url) showTraceLink(ctx, data.trace_url);
        } else if (ev === "error") {
          setState("error");
          failTurn(ctx, data.message);
          return;                                 // stop; no reconnect
        } else if (ev === "done") {
          endTurn(ctx);
          return;                                 // terminal
        }
      }
    }
    // Stream closed without an explicit `done` (unexpected) — tidy up.
    endTurn(ctx, { stopped });
  } catch (err) {
    // A deliberate Stop is not a failure: keep whatever arrived on screen and
    // hand the composer back.
    if (err && err.name === "AbortError") {
      stopped = true;
      ctx.agent.classList.remove("is-streaming");
      if (ctx.gotToken) {
        // Keep the partial answer exactly as painted, in plain text: a
        // half-streamed answer is not valid Markdown yet.
        flushPaint(ctx);
        publishAnswer(ctx, `Đã dừng. ${ctx.rawAnswer.trim()}`);
      } else {
        endTurn(ctx, { stopped });
      }
      return;
    }
    // Network drop mid-stream: degrade to a friendly bubble, never a crash.
    setState("error");
    failTurn(ctx, "Kết nối bị gián đoạn - vui lòng thử lại.");
  } finally {
    if (controller && controller.signal === signal) controller = null;
    // Ready on every path, including Stop and error: the composer is never left
    // locked. A failed turn still carries its own styling on the turn itself,
    // which is where the reader is looking.
    setState("ready");
  }
}

// Stop abandons the turn in flight. The partial answer stays on screen.
function stopCurrentTurn() {
  if (!controller) return;
  controller.abort();
}

// ===========================================================================
// Wiring
// ===========================================================================
form.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = input.value;
  input.value = "";
  ask(text);
});

// Never submit while a Vietnamese or Japanese IME composition session is
// active: Enter is choosing a candidate at that moment, and submitting here
// would drop the composed text and fire the agent mid-word.
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && e.isComposing) e.preventDefault();
});

stopBtn.addEventListener("click", () => stopCurrentTurn());

// Canned honesty chips: clicking submits the chip's exact text immediately.
chipRow.addEventListener("click", (e) => {
  const chip = e.target.closest(".chip");
  if (!chip || inFlight) return;
  ask(chip.dataset.query);
});

// Reformulation chips inside a no-answer card live in the conversation, not in
// the canned row, so they are wired through the same delegation.
conversation.addEventListener("click", (e) => {
  const chip = e.target.closest(".turn__nodata .chip");
  if (!chip || inFlight) return;
  ask(chip.dataset.query);
});

loadDateline();
