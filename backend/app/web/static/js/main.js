// ===== BASE CONFIG =====
const API_BASE = window.API_BASE || "/api";

// ===== fetch с таймаутом и 1 ретраем =====
async function fetchWithTimeout(resource, options = {}, timeoutMs = 3500, retries = 1) {
  const attempt = async () => {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const res = await fetch(resource, { ...options, signal: controller.signal });
      clearTimeout(id);
      return res;
    } catch (e) {
      clearTimeout(id);
      throw e;
    }
  };
  try {
    return await attempt();
  } catch (e) {
    if (retries > 0) return fetchWithTimeout(resource, options, timeoutMs, retries - 1);
    throw e;
  }
}

async function apiGet(path) {
  const url = API_BASE + path;
  const res = await fetchWithTimeout(url, { method: "GET" });
  if (!res.ok) throw new Error(`Ошибка GET ${url} (${res.status})`);
  const text = await res.text();
  return text ? JSON.parse(text) : null;
}

async function apiPost(path, data) {
  const url = API_BASE + path;
  const res = await fetchWithTimeout(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data ?? {}),
  });
  if (!res.ok) throw new Error(`Ошибка POST ${url} (${res.status})`);
  const text = await res.text();
  return text ? JSON.parse(text) : null;
}

// ===== safe render helpers =====
function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text != null) node.textContent = text;
  return node;
}

// ===== ADMIN PAGE =====
const caseForm = document.getElementById("caseForm");
const casesList = document.getElementById("casesList");

if (caseForm) {
  caseForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = caseForm.querySelector("button[type=submit]");
    btn.disabled = true;

    const formData = Object.fromEntries(new FormData(caseForm).entries());
    try {
      formData.skills_json = formData.skills_json?.trim()
        ? JSON.parse(formData.skills_json)
        : [];
    } catch {
      alert("Поле 'Навыки/критерии' должно быть валидным JSON.");
      btn.disabled = false;
      return;
    }

    try {
      await apiPost("/admin/cases", formData);
      caseForm.reset();
      await loadCases();
      alert("Кейс добавлен!");
    } catch (err) {
      alert("Ошибка при добавлении кейса: " + err.message);
    } finally {
      btn.disabled = false;
    }
  });

  async function loadCases() {
    try {
      const data = (await apiGet("/admin/cases")) || [];
      casesList.innerHTML = "";
      data.forEach((c) => {
        const li = el("li", "list-group-item d-flex justify-content-between align-items-center");
        const left = el("span");
        const strong = el("strong", null, c.title ?? "");
        left.appendChild(strong);
        if (c.description) {
          left.append(" — " + c.description);
        }
        const badge = el("span", "badge bg-secondary", (c.skills_json?.length ?? 0) + " навыков");
        li.append(left, badge);
        casesList.appendChild(li);
      });
    } catch (err) {
      casesList.innerHTML = '<li class="list-group-item text-danger">Ошибка загрузки</li>';
    }
  }
  loadCases();
}

// ===== SUBMIT PAGE =====
const submitForm = document.getElementById("submitForm");
const caseSelect = document.getElementById("caseSelect");

if (submitForm && caseSelect) {
  (async () => {
    try {
      const data = (await apiGet("/admin/cases")) || [];
      caseSelect.innerHTML = "";
      const placeholder = el("option", null, "Выберите кейс");
      placeholder.disabled = true; placeholder.selected = true;
      caseSelect.appendChild(placeholder);
      data.forEach((c) => {
        const opt = el("option", null, c.title ?? "");
        opt.value = c.id;
        caseSelect.appendChild(opt);
      });
    } catch (err) {
      alert("Ошибка загрузки кейсов: " + err.message);
    }
  })();

  const answerEl = submitForm.querySelector('textarea[name="answer_text"]');
  const MAX_LEN = 6000;
  if (answerEl) {
    answerEl.addEventListener("input", () => {
      if (answerEl.value.length > MAX_LEN) {
        answerEl.value = answerEl.value.slice(0, MAX_LEN);
      }
    });
  }

  submitForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = submitForm.querySelector("button[type=submit]");
    btn.disabled = true; btn.textContent = "Отправка…";

    const formData = Object.fromEntries(new FormData(submitForm).entries());
    if (!formData.case_id) {
      alert("Пожалуйста, выберите кейс.");
      btn.disabled = false; btn.textContent = "Отправить";
      return;
    }
    try {
      const res = await apiPost("/submit_solution", formData);
      if (!res?.session_id) throw new Error("Некорректный ответ API");
      window.location.assign(`/result/${res.session_id}`);
    } catch (err) {
      alert("Ошибка отправки решения: " + err.message);
    } finally {
      btn.disabled = false; btn.textContent = "Отправить";
    }
  });
}

// ===== RESULT PAGE =====
const resultBlock = document.getElementById("resultBlock");
const chatInput = document.getElementById("chatInput");
const chatSend = document.getElementById("chatSend");
const chatBox = document.getElementById("chatBox");

if (typeof window.sessionId === "undefined" && typeof sessionId !== "undefined") {
  window.sessionId = sessionId;
}

function renderEvaluation(container, data) {
  container.innerHTML = "";

  // Общая оценка
  const header = el("div", "mb-3");
  const score = Number(data.overall_score ?? 0);
  header.appendChild(el("p", null, `Общая оценка: ${score}`));

  // Прогрессбар
  const prog = el("div", "progress mb-3");
  const progInner = el("div", "progress-bar");
  progInner.style.width = Math.min(100, Math.max(0, score)) + "%";
  progInner.textContent = score + "%";
  prog.appendChild(progInner);
  container.append(header, prog);

  // Навыки и критерии
  if (Array.isArray(data.skills)) {
    data.skills.forEach((s) => {
      const card = el("div", "card mb-2");
      const body = el("div", "card-body");
      const title = el("h6", "card-title", `${s.name ?? "Навык"} — ${s.skill_score ?? "-"}`);
      body.appendChild(title);

      if (Array.isArray(s.criteria) && s.criteria.length) {
        const table = el("table", "table table-sm");
        const thead = el("thead");
        const trh = el("tr");
        ["Критерий", "Балл", "Доказательство", "Рекомендация"].forEach((h) => trh.appendChild(el("th", null, h)));
        thead.appendChild(trh);
        const tbody = el("tbody");
        s.criteria.forEach((c) => {
          const tr = el("tr");
          tr.appendChild(el("td", null, c.name ?? ""));
          tr.appendChild(el("td", null, String(c.score ?? "")));
          tr.appendChild(el("td", null, c.evidence ?? ""));
          tr.appendChild(el("td", null, c.suggestion ?? ""));
          tbody.appendChild(tr);
        });
        table.append(thead, tbody);
        body.appendChild(table);
      }

      if (Array.isArray(s.improvement_plan) && s.improvement_plan.length) {
        const ul = el("ul");
        s.improvement_plan.forEach((step) => ul.appendChild(el("li", null, step)));
        body.appendChild(ul);
      }

      card.appendChild(body);
      container.appendChild(card);
    });
  }
}

if (resultBlock && typeof window.sessionId !== "undefined") {
  (async () => {
    try {
      const data = await apiGet(`/result/${window.sessionId}`);
      if (!data) {
        resultBlock.textContent = "Пока нет данных.";
        return;
      }
      renderEvaluation(resultBlock, data);
    } catch (err) {
      resultBlock.innerHTML = `<p class="text-danger">Ошибка загрузки результата: ${err.message}</p>`;
    }
  })();
}

// ===== CHAT =====
if (chatSend && chatInput && chatBox && typeof window.sessionId !== "undefined") {
  let sending = false;
  chatSend.addEventListener("click", sendChat);
  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendChat();
    }
  });

  function appendMessage(author, text) {
    const div = el("div", "mb-2");
    div.innerHTML = `<strong>${author}:</strong> ${text}`;
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
  }

  async function sendChat() {
    const text = chatInput.value.trim();
    if (!text || sending) return;
    sending = true;
    chatInput.value = "";
    appendMessage("Вы", text);

    try {
      const res = await apiPost("/ask", { session_id: window.sessionId, question: text });
      appendMessage("AI", (res && res.answer) || "Нет ответа");
    } catch (err) {
      appendMessage("AI", "Ошибка: " + err.message);
    } finally {
      sending = false;
    }
  }
}
