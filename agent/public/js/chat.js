// ページ存続中の会話状態
let sessionId = null;
let busy      = false;   // LLM 実行中フラグ（二重送信防止）
let activated = false;   // 初回送信後のレイアウト切り替えフラグ

// DOM 参照
const chatArea     = document.getElementById("chat-area");
const messages     = document.getElementById("messages");
const inner        = document.getElementById("messages-inner");
const composerWrap = document.getElementById("composer-wrap");
const form         = document.getElementById("chat-form");
const input        = document.getElementById("q");
const sendBtn      = document.getElementById("send");

// SVG アバター（エージェント用）
const AGENT_AVATAR =
  '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">' +
  '<path d="M12 2l1.6 6.4L20 10l-6.4 1.6L12 18l-1.6-6.4L4 10l6.4-1.6L12 2z"/>' +
  '</svg>';

// ===== レイアウト管理 =====

// 初回送信時: ランディングを隠してメッセージ欄を表示し、
// 入力欄を chat-area 直下（下部）へ移動する
function activateLayout() {
  if (activated) return;
  activated = true;
  chatArea.appendChild(composerWrap); // DOM 移動（landing → chat-area 直下）
  chatArea.classList.add("active");   // CSS 切り替え
}

// ===== DOM ユーティリティ =====

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// URL をクリック可能なリンクに変換する（出典リンク用）
function linkify(text) {
  const escaped = escapeHtml(text);
  return escaped.replace(/(https?:\/\/[^\s）)]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');
}

// ===== メッセージ表示 =====

// 1 メッセージ行（アバター + バブル）を追加する
function addMessage(text, cls, asHtml) {
  const isAgent = cls.split(" ").includes("agent");

  const row    = document.createElement("div");
  row.className = "row " + cls;

  const avatar    = document.createElement("div");
  avatar.className = "avatar " + (isAgent ? "agent" : "user");
  avatar.innerHTML = isAgent ? AGENT_AVATAR : "ME";

  const msg    = document.createElement("div");
  msg.className = "msg " + cls;
  if (asHtml) msg.innerHTML = linkify(text);
  else        msg.textContent = text;

  row.appendChild(avatar);
  row.appendChild(msg);
  inner.appendChild(row);
  scrollToBottom();
  return { row, msg };
}

// 「考え中」インジケータ（脈動ドット）を表示する
function addThinking() {
  const row = document.createElement("div");
  row.className = "row agent";
  row.innerHTML =
    '<div class="avatar agent">' + AGENT_AVATAR + "</div>" +
    '<div class="thinking">' +
      '<span class="dot"></span><span class="dot"></span><span class="dot"></span>' +
    '</div>';
  inner.appendChild(row);
  scrollToBottom();
  return row;
}

function scrollToBottom() {
  messages.scrollTop = messages.scrollHeight;
}

// ===== 入力欄 =====

// テキストエリアの高さを内容に合わせて自動調整する
function autoGrow() {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 160) + "px";
}

function setBusy(state) {
  busy             = state;
  sendBtn.disabled = state;
  input.disabled   = state;
}

// ===== イベント =====

input.addEventListener("input", autoGrow);

// Enter 送信 / Shift+Enter 改行
// IME（日本語・中国語など）で変換中の Enter は候補確定なので送信しない。
// e.isComposing と keyCode===229 の両方を見る（ブラウザ差異の保険）。
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    if (e.isComposing || e.keyCode === 229) return;
    e.preventDefault();
    form.requestSubmit();
  }
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (busy) return;
  const question = input.value.trim();
  if (!question) return;

  activateLayout(); // 初回のみレイアウト切り替え
  input.value = "";
  autoGrow();
  addMessage(question, "user", false);

  setBusy(true);
  const thinking = addThinking();

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: question, sessionId }),
    });
    const data = await res.json();
    thinking.remove();
    if (!res.ok) {
      addMessage(data.error || "エラーが発生しました。", "agent error", false);
      return;
    }
    sessionId = data.sessionId;
    addMessage(data.answer, "agent", true);
  } catch (_err) {
    thinking.remove();
    addMessage("通信エラーが発生しました。", "agent error", false);
  } finally {
    setBusy(false);
    input.focus();
  }
});

input.focus();
