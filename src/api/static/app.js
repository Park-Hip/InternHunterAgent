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
//   metadata { trace_id, trace_url }   -> show a "view trace" link if trace_url
//   error    { message }               -> friendly error bubble; stop
//   done     {}                        -> terminal; stop reading, no reconnect
// ===========================================================================

// --- element handles -------------------------------------------------------
const conversation = document.getElementById("conversation");
const lede = document.getElementById("lede");
const chipRow = document.getElementById("chips");
const form = document.getElementById("composer");
const input = document.getElementById("query");
const sendBtn = document.getElementById("send");
const dateline = document.getElementById("dateline");
const toast = document.getElementById("toast");

// --- conversation state ----------------------------------------------------
let sessionId = null;   // pinned from the first `session` event; reused after
let inFlight = false;   // one stream at a time; lock the inputs while it runs
let toastTimer = null;

// ===========================================================================
// Disclaimer / dateline — read the truthful snapshot date from /api/v1/ready.
// Never crash, never show "undefined": fall back to the dateless sentence.
// ===========================================================================
async function loadDateline() {
  const unknownFreshness =
    "Demo data · refresh date unavailable · public listings, may be inaccurate.";
  try {
    const res = await fetch("/api/v1/ready");
    if (!res.ok) return;                       // 503 if DB down — keep fallback
    const data = await res.json();
    const date = data && data.data_snapshot_date;
    const isMeasured = data && data.data_snapshot_date_provenance === "measured";
    if (date && isMeasured) {
      dateline.textContent =
        `Demo data · snapshot ${date} · public listings, may be inaccurate.`;
    } else {
      dateline.textContent = unknownFreshness;
    }
  } catch {
    // network error — the fallback text is already in the markup
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
  you.innerHTML = '<span class="turn__label">You asked</span>';
  const youText = document.createElement("p");
  youText.className = "turn__you-text";
  youText.textContent = query;
  you.appendChild(youText);

  // the agent's answer, marked by the vermilion editor's rule
  const agent = document.createElement("div");
  agent.className = "turn__agent is-streaming";
  agent.innerHTML = '<span class="turn__label">InternHunter</span>';
  const answer = document.createElement("p");
  answer.className = "turn__answer turn__answer--pending";
  answer.textContent = "Reading the listings…";
  agent.appendChild(answer);

  turn.appendChild(you);
  turn.appendChild(agent);
  conversation.appendChild(turn);

  scrollToEnd();
  return { turn, agent, answer, gotToken: false };
}

// Append one token, clearing the pending placeholder on the first one.
function appendToken(ctx, text) {
  if (!ctx.gotToken) {
    ctx.gotToken = true;
    ctx.answer.classList.remove("turn__answer--pending");
    ctx.answer.textContent = "";
  }
  ctx.answer.textContent += text;
  scrollToEnd();
}

// Show the trailing "view trace" link only when trace_url is a real URL.
function showTraceLink(ctx, traceUrl) {
  const p = document.createElement("p");
  p.className = "turn__trace";
  const a = document.createElement("a");
  a.href = traceUrl;
  a.target = "_blank";
  a.rel = "noopener noreferrer";
  a.textContent = "View the trace →";
  p.appendChild(a);
  ctx.agent.appendChild(p);
}

// Replace the answer with a friendly error bubble (mid-stream `error` event).
function showErrorBubble(ctx, message) {
  ctx.agent.classList.remove("is-streaming");
  ctx.agent.classList.add("is-error");
  ctx.answer.classList.remove("turn__answer--pending");
  ctx.answer.textContent =
    message || "I couldn't complete that request right now. Please try again later.";
}

// Finish a turn: drop the streaming cursor.
function endTurn(ctx) {
  ctx.agent.classList.remove("is-streaming");
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
// Input locking — one stream at a time.
// ===========================================================================
function setBusy(busy) {
  inFlight = busy;
  input.disabled = busy;
  sendBtn.disabled = busy;
  sendBtn.textContent = busy ? "Asking…" : "Ask";
  for (const chip of chipRow.querySelectorAll(".chip")) chip.disabled = busy;
}

// ===========================================================================
// The stream — the core of the demo.
// ===========================================================================
async function ask(query) {
  if (inFlight) return;
  const text = query.trim();
  if (!text) return;

  setBusy(true);
  const ctx = startTurn(text);

  try {
    const body = { query: text };
    if (sessionId) body.session_id = sessionId;   // omit on the first turn

    const res = await fetch("/api/v1/agent/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    // Pre-stream failure: a real HTTP status before the stream body opens.
    if (!res.ok) {
      const payload = await res.json().catch(() => ({}));
      showErrorBubble(ctx, "That question didn’t go through.");
      endTurn(ctx);
      showToast(payload.detail || "Something went wrong. Please try again.");
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
          appendToken(ctx, data.text);
        } else if (ev === "metadata") {
          if (data.trace_url) showTraceLink(ctx, data.trace_url);
        } else if (ev === "error") {
          showErrorBubble(ctx, data.message);
          endTurn(ctx);
          return;                                 // stop; no reconnect
        } else if (ev === "done") {
          endTurn(ctx);
          return;                                 // terminal
        }
      }
    }
    // Stream closed without an explicit `done` (unexpected) — tidy up.
    endTurn(ctx);
  } catch (err) {
    // Network drop mid-stream: degrade to a friendly bubble, never a crash.
    showErrorBubble(ctx, "The connection dropped — please try again.");
    endTurn(ctx);
  } finally {
    setBusy(false);
  }
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

// Canned honesty chips: clicking submits the chip's exact text immediately.
chipRow.addEventListener("click", (e) => {
  const chip = e.target.closest(".chip");
  if (!chip || inFlight) return;
  ask(chip.dataset.query);
});

loadDateline();
