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

// элементы для описания кейса
const caseDetails   = document.getElementById("caseDetails");
const caseTitleEl   = document.getElementById("caseTitle");
const caseDescEl    = document.getElementById("caseDescription");
const caseSkillsBox = document.getElementById("caseSkills");
const caseSkillsUl  = document.getElementById("caseSkillsList");

// локальный кеш кейсов, чтобы быстро показать описание по change
let casesCache = [];

function renderCaseDetailsById(caseId) {
  if (!caseId || !casesCache?.length) return;
  const found = casesCache.find(c => String(c.id) === String(caseId));
  if (!found) {
    caseDetails?.classList.add("d-none");
    return;
  }
  // заголовок + описание
  caseTitleEl.textContent = found.title || "Кейс";
  caseDescEl.textContent  = found.description || "Описание отсутствует.";

  // --- Навыки/критерии (человекочитаемо) ---
  caseSkillsUl.innerHTML = "";
  const skills = Array.isArray(found.skills_json) ? found.skills_json : [];

  if (skills.length) {
    skills.forEach((s, i) => {
      const li = document.createElement("li");

      if (typeof s === "string") {
        li.textContent = s;
      } else if (s && typeof s === "object") {
        const skillName = s.name || s.skill || `Навык ${i + 1}`;
        li.innerHTML = `<strong>${skillName}</strong>`;

        if (Array.isArray(s.criteria) && s.criteria.length) {
          const ul = document.createElement("ul");
          s.criteria.forEach((c, j) => {
            const ci = document.createElement("li");
            if (typeof c === "string") {
              ci.textContent = c;
            } else if (c && typeof c === "object") {
              ci.textContent = c.name || `Критерий ${j + 1}`;
            } else {
              ci.textContent = String(c);
            }
            ul.appendChild(ci);
          });
          li.appendChild(ul);
        }
      } else {
        li.textContent = String(s);
      }

      caseSkillsUl.appendChild(li);
    });

    caseSkillsBox.classList.remove("d-none");
  } else {
    caseSkillsBox.classList.add("d-none");
  }

  caseDetails.classList.remove("d-none");
}

// ===== простая анимация прогресса (до ~85%) =====
let submitProgressTimer = null;
function startSubmitProgress() {
  const bar = document.getElementById("submitProgress");
  const wrap = document.getElementById("submitStatus");
  const txt  = document.getElementById("submitStatusText");
  if (!bar || !wrap) return;

  // показать индикатор
  wrap.classList.remove("d-none");
  if (txt) txt.textContent = "Мы отправили ваше решение на оценку…";

  // сброс ширины
  bar.style.width = "10%";
  bar.setAttribute("aria-valuenow", "10");

  const maxHold = 85;     // держим на ~85% пока ждём сервер
  const stepMs  = 200;    // каждые 200мс плавно увеличиваем
  const stepPx  = 2;      // шаг 2%

  clearInterval(submitProgressTimer);
  submitProgressTimer = setInterval(() => {
    const cur = parseInt(bar.style.width || "0", 10);
    if (cur < maxHold) {
      const next = Math.min(maxHold, cur + stepPx);
      bar.style.width = next + "%";
      bar.setAttribute("aria-valuenow", String(next));
    }
  }, stepMs);
}

function finishSubmitProgress(ok = true) {
  const bar = document.getElementById("submitProgress");
  const wrap = document.getElementById("submitStatus");
  const txt  = document.getElementById("submitStatusText");
  clearInterval(submitProgressTimer);

  if (bar) {
    bar.style.width = "100%";
    bar.setAttribute("aria-valuenow", "100");
  }
  if (txt) {
    txt.textContent = ok ? "Оценка получена. Открываем результат…" : "Произошла ошибка при отправке.";
  }
  // скрывать индикатор не обязательно — при успехе будет переход на /result
}

// основной блок Submit
if (submitForm && caseSelect) {
  // запрет нативного сабмита
  submitForm.addEventListener("submit", (e) => {
    e.preventDefault();
    sendSolution();
  });

  const submitBtn =
    document.getElementById("submitBtn") ||
    submitForm.querySelector('button[type="submit"]') ||
    submitForm.querySelector("button");

  if (submitBtn) {
    submitBtn.addEventListener("click", (e) => {
      e.preventDefault();
      sendSolution();
    });
  }

  // Загрузка кейсов и заполнение селекта
  (async () => {
    try {
      const data = (await apiGet("/admin/cases", { timeoutMs: 8000, retries: 1 })) || [];
      casesCache = data;
      caseSelect.innerHTML = "";
      const placeholder = document.createElement("option");
      placeholder.textContent = "Выберите кейс";
      placeholder.disabled = true;
      placeholder.selected = true;
      caseSelect.appendChild(placeholder);

      data.forEach((c) => {
        const opt = document.createElement("option");
        opt.value = c.id;
        opt.textContent = c.title ?? "";
        caseSelect.appendChild(opt);
      });

      // показываем описание, когда пользователь выбрал кейс
      caseSelect.addEventListener("change", () => {
        renderCaseDetailsById(caseSelect.value);
      });
    } catch (err) {
      alert("Ошибка загрузки кейсов: " + err.message);
    }
  })();

  // ограничение длины ответа
  const answerEl = submitForm.querySelector('textarea[name="answer_text"]');
  const MAX_LEN = 6000;
  if (answerEl) {
    answerEl.addEventListener("input", () => {
      if (answerEl.value.length > MAX_LEN) {
        answerEl.value = answerEl.value.slice(0, MAX_LEN);
      }
    });
  }

  let sendingSubmit = false;
  async function sendSolution() {
    if (sendingSubmit) return;
    const btn =
      document.getElementById("submitBtn") ||
      submitForm.querySelector('button[type="submit"]') ||
      submitForm.querySelector("button");

    const formData = Object.fromEntries(new FormData(submitForm).entries());
    if (!formData.case_id) {
      alert("Пожалуйста, выберите кейс.");
      return;
    }

    try {
      sendingSubmit = true;
      if (btn) { btn.disabled = true; btn.textContent = "Отправка…"; }

      startSubmitProgress(); // <<< запускаем индикатор

      // Длинный таймаут и без ретраев — чтобы не было дублей
      const res = await apiPost("/submit_solution", formData, { timeoutMs: 90000, retries: 0 });
      if (!res?.session_id) throw new Error("Некорректный ответ API: нет session_id");

      finishSubmitProgress(true); // <<< доводим до 100%
      window.location.assign(`/result/${res.session_id}`);
    } catch (err) {
      const msg = String(err?.message || err || "");
      alert("Ошибка отправки решения: " + msg);
      finishSubmitProgress(false); // <<< доводим до 100% и оставляем сообщение
      // можно спрятать полоску через пару секунд, если хочешь:
      setTimeout(() => document.getElementById("submitStatus")?.classList.add("d-none"), 2500);
    } finally {
      sendingSubmit = false;
      if (btn) { btn.disabled = false; btn.textContent = "Отправить"; }
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

  const prog = el("div", "progress mb-3");
  const progInner = el("div", "progress-bar bg-success");
  progInner.style.width = Math.min(100, Math.max(0, score)) + "%";
  progInner.textContent = score + "%";
  prog.appendChild(progInner);
  container.append(header, prog);

  // Навыки и критерии
  if (Array.isArray(data.skills)) {
    data.skills.forEach((s) => {
      const card = el("div", "card mb-3");
      const body = el("div", "card-body");
      const title = el("h6", "card-title mb-3", `${s.name ?? s.skill ?? "Навык"} — ${s.skill_score ?? "-"}`);
      body.appendChild(title);

      // Таблица критериев (3 колонки)
      if (Array.isArray(s.criteria) && s.criteria.length) {
        const table = el("table", "table table-sm mb-3");
        const thead = el("thead");
        const trh = el("tr");
        ["Критерий", "Балл", "Доказательство"].forEach((h) => trh.appendChild(el("th", null, h)));
        thead.appendChild(trh);
        const tbody = el("tbody");
        s.criteria.forEach((c) => {
          const tr = el("tr");
          tr.appendChild(el("td", null, c.name ?? ""));
          tr.appendChild(el("td", null, String(c.score ?? "")));
          tr.appendChild(el("td", null, c.evidence ?? ""));
          tbody.appendChild(tr);
        });
        table.append(thead, tbody);
        body.appendChild(table);
      }

      // Рекомендации по навыку
      if (Array.isArray(s.improvement_plan) && s.improvement_plan.length) {
        body.appendChild(el("div", "fw-semibold mb-1", "Рекомендации"));
        const ul = el("ul", "mb-0");
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
