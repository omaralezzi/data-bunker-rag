const chatListEl = document.getElementById("chatList");
const messagesEl = document.getElementById("messages");
const newChatBtn = document.getElementById("newChatBtn");
const deleteChatBtn = document.getElementById("deleteChatBtn");
const sendBtn = document.getElementById("sendBtn");
const messageInput = document.getElementById("messageInput");
const domainSelect = document.getElementById("domainSelect");
const limitSelect = document.getElementById("limitSelect");
const modeSelect = document.getElementById("modeSelect");
const answerLanguageSelect = document.getElementById("answerLanguageSelect");

const domainsBtn = document.getElementById("domainsBtn");
const indexStatusBtn = document.getElementById("indexStatusBtn");
const infoModal = document.getElementById("infoModal");
const infoModalTitle = document.getElementById("infoModalTitle");
const infoModalBody = document.getElementById("infoModalBody");
const closeInfoModalBtn = document.getElementById("closeInfoModalBtn");

let currentChatId = null;
let isWaitingForResponse = false;
let thinkingStageInterval = null;
let currentThinkingStageIndex = 0;

async function fetchJSON(url, options = {}) {
  const res = await fetch(url, options);
  return await res.json();
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text || "";
  return div.innerHTML;
}

function getUiLanguage() {
  const selected = answerLanguageSelect?.value || "auto";
  if (selected === "ar") return "ar";
  return "en"; // en + auto => English as default
}

function getUiLabels() {
  const lang = getUiLanguage();

  if (lang === "ar") {
    return {
      emptyTitle: "ابدأ محادثة مع مكتبتك الأوفلاين",
      emptySubtitle: "اسأل من محتوى Kiwix المفهرس عبر Qdrant و Ollama.",
      inputPlaceholder: "اكتب سؤالك عن المعرفة الأوفلاين...",
      thinkingTitle: "جاري تحليل السؤال",
      thinkingSubtitle: "يتم الآن البحث واختيار أفضل المصادر ثم تجهيز الإجابة...",
      thinkingStages: [
        "يفكر...",
        "يبحث في المصادر...",
        "يعيد ترتيب النتائج...",
        "يبني الإجابة..."
      ],
      errorText: "حدث خطأ أثناء تجهيز الإجابة. حاول مرة أخرى.",
      selectedArticlesLabel: "selected articles:",
      followupQuestionsLabel: "follow-up questions:",
      sourcesLabel: "sources:",
      searchQueryLabel: "search query:",
      resolvedLanguageLabel: "resolved language:",
      youLabel: "أنت",
      ragLabel: "RAG",
      domainsTitle: "Domains",
      indexStatusTitle: "Index Status"
    };
  }

  return {
    emptyTitle: "Start a conversation with your offline library",
    emptySubtitle: "Ask from Kiwix content indexed through Qdrant and Ollama.",
    inputPlaceholder: "Ask about your offline knowledge...",
    thinkingTitle: "Processing your question",
    thinkingSubtitle: "Searching sources, ranking results, and preparing the answer...",
    thinkingStages: [
      "Thinking...",
      "Searching sources...",
      "Ranking results...",
      "Building the answer..."
    ],
    errorText: "An error occurred while preparing the answer. Please try again.",
    selectedArticlesLabel: "selected articles:",
    followupQuestionsLabel: "follow-up questions:",
    sourcesLabel: "sources:",
    searchQueryLabel: "search query:",
    resolvedLanguageLabel: "resolved language:",
    youLabel: "You",
    ragLabel: "RAG",
    domainsTitle: "Domains",
    indexStatusTitle: "Index Status"
  };
}

function applyLanguageUi() {
  const labels = getUiLabels();

  if (messageInput) {
    messageInput.placeholder = labels.inputPlaceholder;
  }

  const hasMessages = messagesEl.querySelectorAll(".message").length > 0;
  const hasThinking = !!document.getElementById("thinkingIndicator");

  if (!hasMessages && !hasThinking) {
    renderMessages([]);
  } else if (hasThinking) {
    updateThinkingIndicatorTexts();
  }
}

function openInfoModal(title, html) {
  infoModalTitle.innerHTML = escapeHtml(title);
  infoModalBody.innerHTML = html;
  infoModal.style.display = "block";
}

function closeInfoModal() {
  infoModal.style.display = "none";
}

function stopThinkingStageAnimation() {
  if (thinkingStageInterval) {
    clearInterval(thinkingStageInterval);
    thinkingStageInterval = null;
  }
}

function updateThinkingIndicatorTexts() {
  const labels = getUiLabels();
  const titleEl = document.querySelector("#thinkingIndicator .thinking-title");
  const subtitleEl = document.querySelector("#thinkingIndicator .thinking-subtitle");
  const stageEl = document.querySelector("#thinkingIndicator .thinking-stage");

  if (titleEl) titleEl.textContent = labels.thinkingTitle;
  if (subtitleEl) subtitleEl.textContent = labels.thinkingSubtitle;

  if (stageEl) {
    const stages = labels.thinkingStages || [];
    if (stages.length) {
      stageEl.textContent = stages[currentThinkingStageIndex % stages.length];
    }
  }
}

function startThinkingStageAnimation() {
  stopThinkingStageAnimation();

  const labels = getUiLabels();
  const stages = labels.thinkingStages || [];
  currentThinkingStageIndex = 0;
  updateThinkingIndicatorTexts();

  if (!stages.length) return;

  thinkingStageInterval = setInterval(() => {
    currentThinkingStageIndex = (currentThinkingStageIndex + 1) % stages.length;
    const stageEl = document.querySelector("#thinkingIndicator .thinking-stage");
    if (stageEl) {
      stageEl.textContent = stages[currentThinkingStageIndex];
    }
  }, 1400);
}

function removeThinkingIndicator() {
  stopThinkingStageAnimation();
  const existing = document.getElementById("thinkingIndicator");
  if (existing) existing.remove();
}

function renderThinkingIndicator() {
  removeThinkingIndicator();

  const labels = getUiLabels();
  const currentStage = (labels.thinkingStages || [])[0] || "";

  const wrapper = document.createElement("div");
  wrapper.className = "message assistant thinking-message";
  wrapper.id = "thinkingIndicator";

  wrapper.innerHTML = `
    <div class="message-role">${escapeHtml(labels.ragLabel)}</div>
    <div class="thinking-box">
      <div class="thinking-header">
        <div class="thinking-spinner">
          <span></span>
          <span></span>
          <span></span>
        </div>
        <div class="thinking-texts">
          <div class="thinking-title">${escapeHtml(labels.thinkingTitle)}</div>
          <div class="thinking-subtitle">${escapeHtml(labels.thinkingSubtitle)}</div>
          <div class="thinking-stage">${escapeHtml(currentStage)}</div>
        </div>
      </div>
      <div class="thinking-progress">
        <div class="thinking-progress-bar"></div>
      </div>
    </div>
  `;

  messagesEl.appendChild(wrapper);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  startThinkingStageAnimation();
}

function renderMessages(messages) {
  const labels = getUiLabels();

  messagesEl.innerHTML = "";

  if ((!messages || messages.length === 0) && !isWaitingForResponse) {
    messagesEl.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">✦</div>
        <h2>${escapeHtml(labels.emptyTitle)}</h2>
        <p>${escapeHtml(labels.emptySubtitle)}</p>
      </div>
    `;
    return;
  }

  if (messages && messages.length) {
    for (const msg of messages) {
      const wrapper = document.createElement("div");
      wrapper.className = `message ${msg.role}`;

      let metaHtml = "";
      if (msg.role === "assistant") {
        const searchQuery = msg.search_query
          ? `<div><strong>${escapeHtml(labels.searchQueryLabel)}</strong> ${escapeHtml(msg.search_query)}</div>`
          : "";

        const resolvedLanguage = msg.resolved_language
          ? `<div><strong>${escapeHtml(labels.resolvedLanguageLabel)}</strong> ${escapeHtml(msg.resolved_language)}</div>`
          : "";

        const selectedArticles = Array.isArray(msg.selected_articles) && msg.selected_articles.length
          ? `
            <div class="selected-articles">
              <div><strong>${escapeHtml(labels.selectedArticlesLabel)}</strong></div>
              ${msg.selected_articles.map(a => `
                <div class="source-item">
                  <a href="http://localhost:8090/content/wikipedia_en_all_maxi_2026-02/A/${encodeURIComponent(a.title)}"
                     target="_blank"
                     class="article-link">
                     ${escapeHtml(a.title)}
                  </a>
                  <div>domain: ${escapeHtml(a.domain)} | rerank: ${escapeHtml(String(a.rerank_score))}</div>
                </div>
              `).join("")}
            </div>
          `
          : "";

        const followups = Array.isArray(msg.followup_questions) && msg.followup_questions.length
          ? `
            <div class="followup-questions">
              <div><strong>${escapeHtml(labels.followupQuestionsLabel)}</strong></div>
              ${msg.followup_questions.map(q => `
                <button class="followup-btn" data-question="${escapeHtml(q)}">${escapeHtml(q)}</button>
              `).join("")}
            </div>
          `
          : "";

        const sources = Array.isArray(msg.sources) && msg.sources.length
          ? `
            <div class="sources">
              <div><strong>${escapeHtml(labels.sourcesLabel)}</strong></div>
              ${msg.sources.map(s => `
                <div class="source-item">
                  <strong>${escapeHtml(s.title)}</strong>
                  <div>domain: ${escapeHtml(s.domain)} | chunk: ${escapeHtml(String(s.chunk))}</div>
                </div>
              `).join("")}
            </div>
          `
          : "";

        metaHtml = `
          <div class="message-meta">
            ${searchQuery}
            ${resolvedLanguage}
            ${selectedArticles}
            ${followups}
            ${sources}
          </div>
        `;
      }

      wrapper.innerHTML = `
        <div class="message-role">${msg.role === "user" ? escapeHtml(labels.youLabel) : escapeHtml(labels.ragLabel)}</div>
        <div class="message-content">${escapeHtml(msg.content)}</div>
        ${metaHtml}
      `;

      messagesEl.appendChild(wrapper);
    }
  }

  if (isWaitingForResponse) {
    renderThinkingIndicator();
  }

  messagesEl.querySelectorAll(".followup-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      messageInput.value = btn.dataset.question || "";
      messageInput.focus();
    });
  });

  messagesEl.scrollTop = messagesEl.scrollHeight;
}

async function loadChats() {
  const data = await fetchJSON("/api/chats");
  chatListEl.innerHTML = "";

  for (const item of data.items) {
    const div = document.createElement("div");
    div.className = `chat-item ${item.id === currentChatId ? "active" : ""}`;
    div.innerHTML = `<div class="chat-item-title">${escapeHtml(item.title)}</div>`;
    div.onclick = () => openChat(item.id);
    chatListEl.appendChild(div);
  }
}

async function createChat() {
  const data = await fetchJSON("/api/chats", {
    method: "POST",
    headers: { "Content-Type": "application/json" }
  });
  currentChatId = data.id;
  isWaitingForResponse = false;
  renderMessages([]);
  await loadChats();
}

async function openChat(chatId) {
  const data = await fetchJSON(`/api/chats/${chatId}`);
  currentChatId = data.id;
  isWaitingForResponse = false;
  renderMessages(data.messages || []);
  await loadChats();
}

async function deleteCurrentChat() {
  if (!currentChatId) return;
  await fetchJSON(`/api/chats/${currentChatId}`, { method: "DELETE" });
  currentChatId = null;
  isWaitingForResponse = false;
  renderMessages([]);
  await loadChats();
}

async function sendMessage() {
  const text = messageInput.value.trim();
  if (!text || isWaitingForResponse) return;

  sendBtn.disabled = true;
  sendBtn.classList.add("loading");
  messageInput.disabled = true;
  isWaitingForResponse = true;

  const userMessage = {
    role: "user",
    content: text
  };

  const chatData = currentChatId ? await fetchJSON(`/api/chats/${currentChatId}`) : { messages: [] };
  const mergedMessages = [...(chatData.messages || []), userMessage];

  renderMessages(mergedMessages);

  const payload = {
    chat_id: currentChatId,
    message: text,
    domain: domainSelect.value,
    limit: parseInt(limitSelect.value, 10),
    mode: modeSelect.value,
    answer_language: answerLanguageSelect.value
  };

  messageInput.value = "";

  try {
    const data = await fetchJSON("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    currentChatId = data.chat_id;
    isWaitingForResponse = false;
    removeThinkingIndicator();
    await openChat(currentChatId);
  } catch (error) {
    isWaitingForResponse = false;
    removeThinkingIndicator();

    const labels = getUiLabels();

    const errorBox = document.createElement("div");
    errorBox.className = "message assistant";
    errorBox.innerHTML = `
      <div class="message-role">${escapeHtml(labels.ragLabel)}</div>
      <div class="message-content">${escapeHtml(labels.errorText)}</div>
    `;
    messagesEl.appendChild(errorBox);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  } finally {
    sendBtn.disabled = false;
    sendBtn.classList.remove("loading");
    messageInput.disabled = false;
    messageInput.focus();
  }
}

async function showDomainsInfo() {
  const data = await fetchJSON("/api/domains");
  const labels = getUiLabels();

  const rows = (data.items || []).map(item => `
    <tr>
      <td style="padding:10px; border-bottom:1px solid rgba(201,180,88,0.15);">${escapeHtml(item.domain)}</td>
      <td style="padding:10px; border-bottom:1px solid rgba(201,180,88,0.15);">${escapeHtml(String(item.article_count))}</td>
      <td style="padding:10px; border-bottom:1px solid rgba(201,180,88,0.15);">${escapeHtml(String(item.indexed_count))}</td>
      <td style="padding:10px; border-bottom:1px solid rgba(201,180,88,0.15);">${escapeHtml(item.file)}</td>
    </tr>
  `).join("");

  openInfoModal(
    labels.domainsTitle,
    `
      <div style="margin-bottom:12px; opacity:.85;">Collection: <strong>${escapeHtml(data.collection_name || "")}</strong></div>
      <table style="width:100%; border-collapse:collapse; font-size:15px;">
        <thead>
          <tr>
            <th style="text-align:left; padding:10px; border-bottom:1px solid rgba(201,180,88,0.25);">Domain</th>
            <th style="text-align:left; padding:10px; border-bottom:1px solid rgba(201,180,88,0.25);">Articles in file</th>
            <th style="text-align:left; padding:10px; border-bottom:1px solid rgba(201,180,88,0.25);">Indexed in Qdrant</th>
            <th style="text-align:left; padding:10px; border-bottom:1px solid rgba(201,180,88,0.25);">Source file</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    `
  );
}

function renderStatusBadge(ok) {
  return ok
    ? `<span style="display:inline-block; padding:4px 10px; border-radius:999px; background:rgba(80,160,90,.18); border:1px solid rgba(80,160,90,.35);">OK</span>`
    : `<span style="display:inline-block; padding:4px 10px; border-radius:999px; background:rgba(180,70,70,.18); border:1px solid rgba(180,70,70,.35);">DOWN</span>`;
}

async function showIndexStatus() {
  const data = await fetchJSON("/api/index-status");
  const labels = getUiLabels();

  const modelsHtml = (data.ollama_models || []).length
    ? (data.ollama_models || []).map(m => `<li>${escapeHtml(m)}</li>`).join("")
    : "<li>No models found</li>";

  openInfoModal(
    labels.indexStatusTitle,
    `
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:18px;">
        <div style="padding:14px; border:1px solid rgba(201,180,88,0.2); border-radius:14px; background:rgba(201,180,88,0.04);">
          <div style="margin-bottom:6px;"><strong>Qdrant</strong> ${renderStatusBadge(data.qdrant_ok)}</div>
          <div style="opacity:.85;">${escapeHtml(data.qdrant_url || "")}</div>
        </div>

        <div style="padding:14px; border:1px solid rgba(201,180,88,0.2); border-radius:14px; background:rgba(201,180,88,0.04);">
          <div style="margin-bottom:6px;"><strong>Kiwix</strong> ${renderStatusBadge(data.kiwix_ok)}</div>
          <div style="opacity:.85;">${escapeHtml(data.kiwix_base || "")}</div>
        </div>

        <div style="padding:14px; border:1px solid rgba(201,180,88,0.2); border-radius:14px; background:rgba(201,180,88,0.04);">
          <div style="margin-bottom:6px;"><strong>Ollama</strong> ${renderStatusBadge(data.ollama_ok)}</div>
          <div style="opacity:.85;">${escapeHtml(data.ollama_base || "")}</div>
        </div>

        <div style="padding:14px; border:1px solid rgba(201,180,88,0.2); border-radius:14px; background:rgba(201,180,88,0.04);">
          <div style="margin-bottom:6px;"><strong>Collection</strong></div>
          <div>${escapeHtml(data.collection_name || "")}</div>
          <div style="opacity:.85;">Total points: ${escapeHtml(String(data.total_points || 0))}</div>
        </div>
      </div>

      <div style="padding:14px; border:1px solid rgba(201,180,88,0.2); border-radius:14px; background:rgba(201,180,88,0.04);">
        <div style="margin-bottom:8px;"><strong>Ollama Models</strong></div>
        <ul style="margin:0; padding-left:18px;">
          ${modelsHtml}
        </ul>
      </div>
    `
  );
}

newChatBtn.addEventListener("click", createChat);
deleteChatBtn.addEventListener("click", deleteCurrentChat);
sendBtn.addEventListener("click", sendMessage);

domainsBtn.addEventListener("click", showDomainsInfo);
indexStatusBtn.addEventListener("click", showIndexStatus);
closeInfoModalBtn.addEventListener("click", closeInfoModal);
infoModal.addEventListener("click", (e) => {
  if (e.target === infoModal) closeInfoModal();
});

answerLanguageSelect.addEventListener("change", () => {
  applyLanguageUi();
});

messageInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

(async function init() {
  applyLanguageUi();
  await loadChats();
})();