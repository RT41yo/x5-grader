// ===== BASE CONFIG =====
const API_BASE = window.API_BASE || "/api";

// ===== fetch с таймаутом и настраиваемым числом ретраев =====
async function fetchWithTimeout(resource, options = {}, timeoutMs = 3500, retries = 1) {
  const attempt = async () => {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const res = await fetch(resource, { ...options, signal: controller.signal, cache: "no-store", keepalive: false });
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

// Универсальные хелперы: можно передать {timeoutMs, retries}
async function apiGet(path, opts = {}) {
  const url = API_BASE + path;
  const timeoutMs = opts.timeoutMs ?? 5000;
  const retries   = opts.retries   ?? 1;
  const res = await fetchWithTimeout(url, { method: "GET" }, timeoutMs, retries);
  if (!res.ok) throw new Error(`Ошибка GET ${url} (${res.status})`);
  const text = await res.text();
  return text ? JSON.parse(text) : null;
}

// По умолчанию для POST — без ретраев (чтобы не дублировать создание/оценку)
async function apiPost(path, data, opts = {}) {
  const url = API_BASE + path;
  const timeoutMs = opts.timeoutMs ?? 30000; // дефолт подлиннее, чем у GET
  const retries   = opts.retries   ?? 0;     // ВАЖНО: 0, чтобы не было дублей POST
  const res = await fetchWithTimeout(
    url,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data ?? {}),
    },
    timeoutMs,
    retries
  );
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
  // Один обработчик submit — без дублирования
  caseForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = caseForm.querySelector("button[type=submit]");
    if (btn?.disabled) return; // защита от дабл-клика
    if (btn) btn.disabled = true;

    const formData = Object.fromEntries(new FormData(caseForm).entries());
    try {
      formData.skills_json = formData.skills_json?.trim()
        ? JSON.parse(formData.skills_json)
        : [];
    } catch {
      alert("Поле 'Навыки/критерии' должно быть валидным JSON.");
      if (btn) btn.disabled = false;
      return;
    }

    try {
      await apiPost("/admin/cases", formData, { timeoutMs: 15000, retries: 0 });
      caseForm.reset();
      await loadCases();
      alert("Кейс добавлен!");
    } catch (err) {
      alert("Ошибка при добавлении кейса: " + err.message);
    } finally {
      if (btn) btn.disabled = false;
    }
  });

  async function loadCases() {
    try {
      const data = (await apiGet("/admin/cases", { timeoutMs: 8000, retries: 1 })) || [];
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
      console.error(err);
      casesList.innerHTML = '<li class="list-group-item text-danger">Ошибка загрузки</li>';
    }
  }
  loadCases();
}

// ===== SUBMIT PAGE =====
const submitForm = document.getElementById("submitForm");
const caseSelect = document.getElementById("caseSelect");

if (submitForm && caseSelect) {
  // Элементы статуса
  const submitBtn = document.getElementById("submitBtn") || submitForm.querySelector('button[type="submit"]');
  const statusWrap = document.getElementById("submitStatus");      // контейнер со шкалой
  const statusBar  = document.getElementById("submitProgress");    // внутренняя полоса прогресса
  const statusText = document.getElementById("submitStatusText");  // подпись-сообщение

  // Не даём нативному сабмиту увести страницу
  submitForm.addEventListener("submit", (e) => {
    e.preventDefault();
    sendSolution();
  });

  // Если кнопка имеет type="button" — ловим клик тоже (перестраховка)
  if (submitBtn) {
    submitBtn.addEventListener("click", (e) => {
      e.preventDefault();
      sendSolution();
    });
  }

  // Загрузка кейсов
  (async () => {
    try {
      const data = (await apiGet("/admin/cases", { timeoutMs: 8000, retries: 1 })) || [];
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

  // Простая анимация прогресса (имитация ожидания)
  let progressTimer = null;
  function showStatus(startLabel = "Отправка…") {
    if (statusWrap) statusWrap.classList.remove("d-none");
    if (statusText) statusText.classList.remove("text-danger", "text-success");
    if (statusText) statusText.textContent = startLabel;
    if (statusBar) {
      statusBar.style.width = "10%";
      statusBar.textContent = startLabel;
    }
    // Плавно растим прогресс до 90%
    let val = 10;
    clearInterval(progressTimer);
    progressTimer = setInterval(() => {
      val = Math.min(val + 5, 90);
      if (statusBar) statusBar.style.width = val + "%";
    }, 600);
  }
  function finishStatus(ok, label) {
    clearInterval(progressTimer);
    if (statusBar) {
      statusBar.style.width = "100%";
      statusBar.textContent = ok ? "Готово" : "Ошибка";
    }
    if (statusText) {
      statusText.textContent = label || (ok ? "Готово" : "Ошибка");
      statusText.classList.toggle("text-success", ok);
      statusText.classList.toggle("text-danger", !ok);
    }
  }
  function hideStatus() {
    clearInterval(progressTimer);
    if (statusWrap) statusWrap.classList.add("d-none");
    if (statusText) {
      statusText.textContent = "";
      statusText.classList.remove("text-danger", "text-success");
    }
    if (statusBar) {
      statusBar.style.width = "0%";
      statusBar.textContent = "";
    }
  }

  let sendingSubmit = false;
  async function sendSolution() {
    if (sendingSubmit) return;

    const formData = Object.fromEntries(new FormData(submitForm).entries());
    if (!formData.case_id) {
      alert("Пожалуйста, выберите кейс.");
      return;
    }

    try {
      sendingSubmit = true;
      if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = "Отправка…"; }
      showStatus("Отправка…");

      // Длинный таймаут и без ретраев — чтобы не было дублей
      const res = await apiPost("/submit_solution", formData, { timeoutMs: 120000, retries: 0 });
      if (!res?.session_id) throw new Error("Некорректный ответ API: нет session_id");

      finishStatus(true, "Оценка получена, открываю результат…");
      // Небольшая задержка, чтобы пользователь увидел «100%»
      setTimeout(() => {
        window.location.assign(`/result/${res.session_id}`);
      }, 400);
    } catch (err) {
      const msg = String(err?.message || err || "");
      if (msg.toLowerCase().includes("abort")) {
        finishStatus(false, "Браузер прервал запрос. Попробуйте ещё раз.");
      } else {
        finishStatus(false, "Ошибка отправки: " + msg);
      }
      // через пару секунд скрываем статус, чтобы не мешал повторной отправке
      setTimeout(hideStatus, 2500);
    } finally {
      sendingSubmit = false;
      if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = "Отправить"; }
    }
  }
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
      const data = await apiGet(`/result/${window.sessionId}`, { timeoutMs: 15000, retries: 1 });
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
  let sendingChat = false;

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
    if (!text || sendingChat) return;
    sendingChat = true;
    chatInput.value = "";
    appendMessage("Вы", text);

    try {
      // Длинный таймаут и без ретраев — чтобы не дублировать вопросы
      const res = await apiPost("/ask", { session_id: window.sessionId, question: text }, { timeoutMs: 60000, retries: 0 });
      appendMessage("AI", (res && res.answer) || "Нет ответа");
    } catch (err) {
      appendMessage("AI", "Ошибка: " + (err.message || String(err)));
    } finally {
      sendingChat = false;
    }
  }
}
