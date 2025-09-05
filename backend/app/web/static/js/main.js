// static/js/main.js

// ===== БАЗОВЫЕ НАСТРОЙКИ =====
const API_BASE = "/api"; // все запросы идут через nginx на Flask

// ===== Хелперы fetch =====
async function apiGet(path) {
  const url = API_BASE + path;
  const res = await fetch(url, { method: "GET" });
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    console.error("GET failed:", url, res.status, txt);
    throw new Error(`Ошибка GET ${url} (${res.status})`);
  }
  // может вернуться пусто (204)
  const text = await res.text();
  return text ? JSON.parse(text) : null;
}

async function apiPost(path, data) {
  const url = API_BASE + path;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data ?? {}),
  });
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    console.error("POST failed:", url, res.status, txt);
    throw new Error(`Ошибка POST ${url} (${res.status})`);
  }
  const text = await res.text();
  return text ? JSON.parse(text) : null;
}

// ====== ADMIN PAGE ======
const caseForm = document.getElementById("caseForm");
const casesList = document.getElementById("casesList");

if (caseForm) {
  caseForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const formData = Object.fromEntries(new FormData(caseForm).entries());

    // Безопасный разбор skills_json
    try {
      if (formData.skills_json && formData.skills_json.trim() !== "") {
        formData.skills_json = JSON.parse(formData.skills_json);
      } else {
        formData.skills_json = [];
      }
    } catch (e) {
      alert("Поле 'Навыки/критерии' должно быть валидным JSON.");
      return;
    }

    try {
      await apiPost("/admin/cases", formData);
      alert("Кейс добавлен!");
      caseForm.reset();
      await loadCases();
    } catch (err) {
      alert("Ошибка при добавлении кейса: " + err.message);
    }
  });

  async function loadCases() {
    try {
      const data = (await apiGet("/admin/cases")) || [];
      casesList.innerHTML = "";
      data.forEach((c) => {
        const li = document.createElement("li");
        li.className = "list-group-item d-flex justify-content-between align-items-center";
        li.innerHTML = `
          <span><strong>${c.title}</strong> — ${c.description ?? ""}</span>
          <span class="badge bg-secondary">${(c.skills_json?.length ?? 0)} навыков</span>
        `;
        casesList.appendChild(li);
      });
    } catch (err) {
      console.error(err);
      casesList.innerHTML =
        '<li class="list-group-item text-danger">Ошибка загрузки</li>';
    }
  }

  // первичная загрузка
  loadCases();
}

// ====== SUBMIT PAGE ======
const submitForm = document.getElementById("submitForm");
const caseSelect = document.getElementById("caseSelect");

if (submitForm && caseSelect) {
  // Загрузка кейсов в select
  (async () => {
    try {
      const data = (await apiGet("/admin/cases")) || [];
      caseSelect.innerHTML = '<option value="" disabled selected>Выберите кейс</option>';
      data.forEach((c) => {
        const opt = document.createElement("option");
        opt.value = c.id;
        opt.textContent = c.title;
        caseSelect.appendChild(opt);
      });
    } catch (err) {
      console.error(err);
      alert("Ошибка загрузки кейсов: " + err.message);
    }
  })();

  submitForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const formData = Object.fromEntries(new FormData(submitForm).entries());
    if (!formData.case_id) {
      alert("Пожалуйста, выберите кейс.");
      return;
    }
    try {
      const res = await apiPost("/submit_solution", formData);
      if (!res || !res.session_id) {
        throw new Error("Некорректный ответ API");
      }
      window.location.href = `/result/${res.session_id}`;
    } catch (err) {
      console.error(err);
      alert("Ошибка отправки решения: " + err.message);
    }
  });
}

// ====== RESULT PAGE ======
const resultBlock = document.getElementById("resultBlock");
const chatInput = document.getElementById("chatInput");
const chatSend = document.getElementById("chatSend");
const chatBox = document.getElementById("chatBox");

// в result.html сервер кладёт window.sessionId
if (resultBlock && typeof window.sessionId !== "undefined") {
  (async () => {
    try {
      const data = await apiGet(`/result/${window.sessionId}`);
      if (!data) {
        resultBlock.innerHTML = `<p class="text-warning">Пока нет данных.</p>`;
        return;
      }
      resultBlock.innerHTML = `
        <p><strong>Общая оценка:</strong> ${data.overall_score ?? "-"}</p>
        ${
          data.skills && Array.isArray(data.skills)
            ? `<ul class="list-group mb-3">
              ${data.skills
                .map(
                  (s) => `
                <li class="list-group-item">
                  <strong>${s.name}</strong>: ${s.skill_score ?? "-"}
                  ${
                    s.improvement_plan && s.improvement_plan.length
                      ? `<div class="text-muted small mt-1">${s.improvement_plan.join("; ")}</div>`
                      : ""
                  }
                </li>`
                )
                .join("")}
            </ul>`
            : ""
        }
      `;
    } catch (err) {
      console.error(err);
      resultBlock.innerHTML = `<p class="text-danger">Ошибка загрузки результата</p>`;
    }
  })();
}

// ====== CHAT (на result.html) ======
if (chatSend && chatInput && chatBox && typeof window.sessionId !== "undefined") {
  chatSend.addEventListener("click", sendChat);
  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      sendChat();
    }
  });

  async function sendChat() {
    const text = chatInput.value.trim();
    if (!text) return;
    chatInput.value = "";
    appendMessage("Вы", text);

    try {
      const res = await apiPost("/ask", {
        session_id: window.sessionId,
        question: text,
      });
      appendMessage("AI", (res && res.answer) || "Нет ответа");
    } catch (err) {
      console.error(err);
      appendMessage("AI", "Ошибка: " + err.message);
    }
  }

  function appendMessage(author, text) {
    const div = document.createElement("div");
    div.className = "mb-2";
    div.innerHTML = `<strong>${author}:</strong> ${text}`;
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
  }
}
