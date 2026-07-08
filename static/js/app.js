/**
 * Ajustes CFE — Telcel
 * app.js — misma lógica de negocio, nueva estructura DOM de una sola página.
 */

/* ══════════════════════════════════════════════════════
   ESTADO GLOBAL
   ══════════════════════════════════════════════════════ */
const state = {
  file: null,
  sheets: [],
  selectedSheet: null,
  selectedYear: null,
  totalRows: 0,
};

/* ══════════════════════════════════════════════════════
   DOM REFS
   ══════════════════════════════════════════════════════ */
const $ = id => document.getElementById(id);
const DOM = {
  // Grupos izquierda
  groupFile: $("group-file"),
  groupSheet: $("group-sheet"),
  groupYear: $("group-year"),
  groupAction: $("group-action"),

  // Archivo
  dropzone: $("dropzone"),
  fileInput: $("file-input"),
  fileInfo: $("file-info"),
  fileLabel: $("file-name-label"),
  btnChange: $("btn-change-file"),
  uploadErr: $("upload-error"),
  btnReadSheets: $("btn-leer-pestanas"),

  // Hoja
  sheetList: $("sheet-list"),
  sheetErr: $("sheet-error"),
  btnPreview: $("btn-preview"),

  // Año
  yearPicker: $("year-picker"),

  // Acción
  summaryMini: $("summary-mini"),
  btnCargar: $("btn-cargar"),

  // Panel derecho
  panelEmpty: $("panel-empty"),
  previewSpinner: $("preview-spinner"),
  previewArea: $("preview-area"),
  previewMeta: $("preview-meta"),
  previewThead: $("preview-thead"),
  previewTbody: $("preview-tbody"),
  previewErr: $("preview-error"),
  progressWrap: $("progress-wrap"),
  progressBar: $("progress-bar"),
  progressMsg: $("progress-msg"),
  loadResult: $("load-result"),
  loadErr: $("load-error"),

  // Header
  connBadge: $("conn-badge"),
};


/* ══════════════════════════════════════════════════════
   HELPERS DE VISIBILIDAD
   ══════════════════════════════════════════════════════ */
function show(el) { el.classList.remove("hidden"); }
function hide(el) { el.classList.add("hidden"); }
function toggle(el, visible) { el.classList.toggle("hidden", !visible); }

/** Muestra solo uno de los estados del panel derecho */
function setPanelState(state) {
  hide(DOM.panelEmpty);
  hide(DOM.previewSpinner);
  hide(DOM.previewArea);
  hide(DOM.progressWrap);
  hide(DOM.loadResult);
  hide(DOM.loadErr);
  hide(DOM.previewErr);

  if (state === "empty") show(DOM.panelEmpty);
  if (state === "loading") show(DOM.previewSpinner);
  if (state === "preview") show(DOM.previewArea);
  if (state === "progress") show(DOM.progressWrap);
  if (state === "result") show(DOM.loadResult);
  if (state === "error-load") { show(DOM.loadErr); show(DOM.previewArea); }
  if (state === "error-preview") { show(DOM.previewErr); }
}


/* ══════════════════════════════════════════════════════
   PASO 1 — ARCHIVO
   ══════════════════════════════════════════════════════ */
DOM.dropzone.addEventListener("click", () => DOM.fileInput.click());

DOM.dropzone.addEventListener("dragover", e => {
  e.preventDefault();
  DOM.dropzone.classList.add("drag-over");
});
DOM.dropzone.addEventListener("dragleave", () => {
  DOM.dropzone.classList.remove("drag-over");
});
DOM.dropzone.addEventListener("drop", e => {
  e.preventDefault();
  DOM.dropzone.classList.remove("drag-over");
  const f = e.dataTransfer.files[0];
  if (f) setFile(f);
});
DOM.fileInput.addEventListener("change", () => {
  if (DOM.fileInput.files[0]) setFile(DOM.fileInput.files[0]);
});

DOM.btnChange.addEventListener("click", resetFile);

function setFile(file) {
  const ext = "." + file.name.split(".").pop().toLowerCase();
  if (![".xlsx", ".xlsm", ".xls"].includes(ext)) {
    showInlineError(DOM.uploadErr, `Formato no soportado: ${ext}. Usa .xlsx, .xlsm o .xls`);
    return;
  }
  state.file = file;
  DOM.fileLabel.textContent = file.name;
  show(DOM.fileInfo);
  hide(DOM.dropzone);
  hide(DOM.uploadErr);
  DOM.btnReadSheets.disabled = false;
}

function resetFile() {
  state.file = null;
  state.sheets = [];
  state.selectedSheet = null;
  state.selectedYear = null;
  state.totalRows = 0;
  DOM.fileInput.value = "";
  hide(DOM.fileInfo);
  show(DOM.dropzone);
  DOM.btnReadSheets.disabled = true;
  hide(DOM.groupSheet);
  hide(DOM.groupYear);
  hide(DOM.groupAction);
  setPanelState("empty");
}

DOM.btnReadSheets.addEventListener("click", async () => {
  if (!state.file) return;
  hide(DOM.uploadErr);
  setLoading(DOM.btnReadSheets, "Leyendo…");

  const fd = new FormData();
  fd.append("file", state.file);

  try {
    const res = await fetch("/api/pestanas", { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok || data.error) throw new Error(data.error || "Error leyendo pestañas");

    state.sheets = data.pestanas;
    renderSheetList(data.pestanas);
    show(DOM.groupSheet);
    hide(DOM.groupYear);
    hide(DOM.groupAction);
  } catch (err) {
    showInlineError(DOM.uploadErr, err.message);
  } finally {
    clearLoading(DOM.btnReadSheets, "Leer pestañas");
  }
});


/* ══════════════════════════════════════════════════════
   PASO 2 — PESTAÑA
   ══════════════════════════════════════════════════════ */
function renderSheetList(sheets) {
  DOM.sheetList.innerHTML = "";
  state.selectedSheet = null;
  DOM.btnPreview.disabled = true;

  sheets.forEach(name => {
    const btn = document.createElement("button");
    btn.className = "sheet-btn";
    const yearMatch = name.match(/\d{4}/);
    const year = yearMatch ? yearMatch[0] : "";
    const label = year ? name.replace(year, "").trim() : name;
    btn.innerHTML = `
      <span class="sheet-year">${escHtml(year || name)}</span>
      <span class="sheet-name-full">${escHtml(year ? label : "")}</span>
    `;
    btn.dataset.sheet = name;
    btn.addEventListener("click", () => selectSheet(name, btn));
    DOM.sheetList.appendChild(btn);
  });
}

function selectSheet(name, btn) {
  document.querySelectorAll(".sheet-btn").forEach(b => b.classList.remove("selected"));
  btn.classList.add("selected");
  state.selectedSheet = name;
  DOM.btnPreview.disabled = false;
  hide(DOM.sheetErr);
}

DOM.btnPreview.addEventListener("click", async () => {
  if (!state.selectedSheet) return;
  await loadPreview();
});


/* ══════════════════════════════════════════════════════
   PASO 3 — VISTA PREVIA
   ══════════════════════════════════════════════════════ */
async function loadPreview() {
  setPanelState("loading");
  hide(DOM.groupYear);
  hide(DOM.groupAction);

  const fd = new FormData();
  fd.append("file", state.file);
  fd.append("sheet", state.selectedSheet);

  try {
    const res = await fetch("/api/preview", { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok || data.error) throw new Error(data.error || "Error leyendo datos");

    state.totalRows = data.total;
    renderPreviewTable(data.columns, data.rows, data.total);
    setPanelState("preview");

    // Mostrar selector de año tras preview exitoso
    renderYearPicker();
    show(DOM.groupYear);
    hide(DOM.groupAction);
  } catch (err) {
    setPanelState("error-preview");
    DOM.previewErr.textContent = err.message;
  }
}

function renderPreviewTable(columns, rows, total) {
  DOM.previewMeta.innerHTML = `
    <span>Pestaña: <strong>${escHtml(state.selectedSheet)}</strong></span>
    <span>Total: <strong>${total.toLocaleString()} registros</strong></span>
    <span>Columnas: <strong>${columns.length}</strong></span>
    <span class="badge-muted">Vista previa: primeras ${rows.length} filas</span>
  `;

  DOM.previewThead.innerHTML = `
    <tr>${columns.map(c => `<th title="${escHtml(c)}">${escHtml(c)}</th>`).join("")}</tr>
  `;

  DOM.previewTbody.innerHTML = rows.map(row => `
    <tr>${row.map(cell => {
    if (cell === null || cell === undefined || cell === "")
      return `<td><span class="cell-null">—</span></td>`;
    const v = String(cell);
    const d = v.length > 60 ? v.slice(0, 60) + "…" : v;
    return `<td title="${escHtml(v)}">${escHtml(d)}</td>`;
  }).join("")}</tr>
  `).join("");
}


/* ══════════════════════════════════════════════════════
   SELECTOR DE AÑO
   ══════════════════════════════════════════════════════ */
function renderYearPicker() {
  const currentYear = new Date().getFullYear();
  DOM.yearPicker.innerHTML = "";
  state.selectedYear = null;

  for (let y = currentYear; y >= 2018; y--) {
    const btn = document.createElement("button");
    btn.className = "year-btn";
    btn.textContent = y;
    btn.dataset.year = y;
    btn.addEventListener("click", () => selectYear(String(y)));
    DOM.yearPicker.appendChild(btn);
  }
}

function selectYear(year) {
  state.selectedYear = year;
  document.querySelectorAll(".year-btn").forEach(b => {
    b.classList.toggle("selected", b.dataset.year === year);
  });
  updateSummary();
  show(DOM.groupAction);
  DOM.btnCargar.disabled = false;
  hide(DOM.loadResult);
  hide(DOM.loadErr);
}

function updateSummary() {
  DOM.summaryMini.innerHTML = `
    <div class="row">
      <span class="lbl">Archivo</span>
      <span class="val" title="${escHtml(state.file?.name)}">${escHtml(state.file?.name || "—")}</span>
    </div>
    <div class="row">
      <span class="lbl">Pestaña</span>
      <span class="val">${escHtml(state.selectedSheet || "—")}</span>
    </div>
    <div class="row">
      <span class="lbl">Registros</span>
      <span class="val">${state.totalRows.toLocaleString()}</span>
    </div>
    <div class="row">
      <span class="lbl">Año</span>
      <span class="val">${escHtml(state.selectedYear || "—")}</span>
    </div>
  `;
}


/* ══════════════════════════════════════════════════════
   CARGA A HANA
   ══════════════════════════════════════════════════════ */
DOM.btnCargar.addEventListener("click", async () => {
  if (!state.selectedYear) return;

  hide(DOM.loadErr);
  setPanelState("progress");
  DOM.btnCargar.disabled = true;

  animateProgress();

  const fd = new FormData();
  fd.append("file", state.file);
  fd.append("sheet", state.selectedSheet);
  fd.append("year", state.selectedYear);

  try {
    const res = await fetch("/api/cargar", { method: "POST", body: fd });
    const data = await res.json();

    stopProgress(100);

    if (!res.ok || data.error) throw new Error(data.error || "Error en la carga");

    // Guardamos lo necesario para la notificación al hub
    state.executionId = data.executionId;
    state.rowsRead = data.rowsRead;
    state.rowsInserted = data.insertados;

    DOM.loadResult.innerHTML = buildResultHtml(data);
    setPanelState("result");
    updateConnBadge("ok");

    // El resumen ya está en pantalla → ahora sí, avisamos al hub
    finalizarConHub();

  } catch (err) {
    stopProgress(0);
    DOM.loadErr.textContent = err.message;
    setPanelState("error-load");
    updateConnBadge("error");
  } finally {
    DOM.btnCargar.disabled = false;
  }
});


/* ══════════════════════════════════════════════════════
   NOTIFICACIÓN FINAL AL HUB TLCL
   ══════════════════════════════════════════════════════ */

const HUB_RELOAD_DELAY_MS = 13000; // segundos antes de reiniciar la pantalla

async function finalizarConHub() {
  const hubEl = document.getElementById("hub-status");
  if (!hubEl) return;

  // Bloquear el panel izquierdo apenas empieza la notificación final
  bloquearPanelIzquierdo();

  let variant, message;

  try {
    const res = await fetch("/api/notificar-hub", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        executionId: state.executionId,
        rowsRead: state.rowsRead,
        rowsInserted: state.rowsInserted,
      }),
    });
    const data = await res.json();

    const esAdvertencia = data.ok && /advertencia/i.test(data.message || "");
    variant = !data.ok ? "danger" : (esAdvertencia ? "warn" : "ok");
    message = data.message;
  } catch (err) {
    variant = "danger";
    message = "No se pudo confirmar el proceso final con el hub TLCL. Los datos ya fueron cargados en HANA.";
  }

  hubEl.innerHTML = buildHubAlertHtml(variant, message);
  iniciarCuentaRegresivaYRecargar();
}

function bloquearPanelIzquierdo() {
  const panel = document.querySelector(".panel-left");
  if (panel) panel.classList.add("panel-blocked");
}

let _hubCountdownInterval = null;
let _hubReloadTimeout = null;

function iniciarCuentaRegresivaYRecargar() {
  let restante = Math.ceil(HUB_RELOAD_DELAY_MS / 1000);
  const countdownEl = document.getElementById("hub-countdown");
  const btnPausar = document.getElementById("hub-btn-pausar");
  const btnTerminar = document.getElementById("hub-btn-terminar");

  const tick = () => {
    if (countdownEl) {
      countdownEl.textContent = `Esta pantalla se reiniciará en ${restante}s…`;
    }
    restante -= 1;
  };

  const detenerReinicio = () => {
    clearInterval(_hubCountdownInterval);
    clearTimeout(_hubReloadTimeout);
    if (countdownEl) {
      countdownEl.textContent = "Reinicio automático detenido. Puede revisar el resumen con calma.";
    }
    if (btnPausar) {
      btnPausar.disabled = true;
      btnPausar.textContent = "Reinicio detenido";
    }
  };

  // Arranca el conteo
  tick();
  _hubCountdownInterval = setInterval(() => {
    if (restante < 0) {
      clearInterval(_hubCountdownInterval);
      return;
    }
    tick();
  }, 1000);

  _hubReloadTimeout = setTimeout(() => {
    window.location.reload();
  }, HUB_RELOAD_DELAY_MS);

  // Botón: detener el contador
  if (btnPausar) {
    btnPausar.addEventListener("click", detenerReinicio);
  }

  // Botón: terminar ahora (reinicia de inmediato)
  if (btnTerminar) {
    btnTerminar.addEventListener("click", () => {
      clearInterval(_hubCountdownInterval);
      clearTimeout(_hubReloadTimeout);
      window.location.reload();
    });
  }
}


function buildHubAlertHtml(variant, message) {
  const icons = {
    ok: `<circle cx="9" cy="9" r="8" stroke="currentColor" stroke-width="1.5"/><path d="M5.5 9l2.5 2.5 4.5-4.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>`,
    warn: `<path d="M9 2L16.5 15.5H1.5L9 2z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><path d="M9 6.5v3.5M9 12.5h.01" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>`,
    danger: `<circle cx="9" cy="9" r="8" stroke="currentColor" stroke-width="1.5"/><path d="M6.5 6.5l5 5M11.5 6.5l-5 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>`,
  };
  const labels = {
    ok: "Proceso finalizado",
    warn: "Finalizado con advertencia",
    danger: "No se pudo confirmar el proceso",
  };

  return `
    <div class="hub-alert hub-alert--${variant}">
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none">${icons[variant]}</svg>
      <div>
        <strong>${labels[variant]}</strong>
        <p>${escHtml(message)}</p>
        <p class="hub-countdown" id="hub-countdown"></p>
        <div class="hub-actions">
          <button class="btn btn-secondary btn-sm" id="hub-btn-pausar" type="button">
            Detener reinicio
          </button>
          <button class="btn btn-primary btn-sm" id="hub-btn-terminar" type="button">
            Terminar
          </button>
        </div>
      </div>
    </div>
  `;
}


/* ══════════════════════════════════════════════════════
   HTML DE RESULTADO
   ══════════════════════════════════════════════════════ */
function buildResultHtml(data) {
  const {
    insertados, nErrores = 0,
    nErroresBD = 0, nDupsExcel = 0,
    errores = [], mensaje, tabla, anio
  } = data;

  const statsHtml = `
    <div class="result-stats">
      <div class="stat-card ok">
        <span class="stat-num">${insertados.toLocaleString()}</span>
        <span class="stat-lbl">Insertados</span>
      </div>
      ${nDupsExcel > 0 ? `
      <div class="stat-card warn">
        <span class="stat-num">${nDupsExcel.toLocaleString()}</span>
        <span class="stat-lbl">Duplicados en archivo</span>
      </div>` : ""}
      ${nErroresBD > 0 ? `
      <div class="stat-card danger">
        <span class="stat-num">${nErroresBD.toLocaleString()}</span>
        <span class="stat-lbl">Errores en BD</span>
      </div>` : ""}
      <div class="stat-card neutral">
        <span class="stat-num">${escHtml(anio)}</span>
        <span class="stat-lbl">Año del ajuste</span>
      </div>
    </div>
  `;

  let erroresHtml = "";
  if (nErrores > 0) {
    const filasMostradas = errores.length;
    const filasOcultas = nErrores - filasMostradas;

    let hintText = "Revísalos en el archivo fuente.";
    if (nDupsExcel > 0 && nErroresBD === 0) {
      hintText = "Filas con la misma clave RPU+Desde+Hasta. Se conservó la primera ocurrencia de cada una.";
    } else if (nDupsExcel === 0 && nErroresBD > 0) {
      hintText = "Algunos registros no pudieron insertarse. Revisa el motivo en la tabla.";
    }

    erroresHtml = `
      <div class="error-block">
        <div class="error-block-header">
          <div>
            <strong>${nErrores.toLocaleString()} registro(s) no se cargaron</strong>
            <span class="error-block-hint">${hintText}</span>
          </div>
        </div>
        <div class="table-scroll" style="max-height:320px">
          <table class="data-table error-table">
            <thead><tr>
              <th>RPU</th><th>Desde</th><th>Hasta</th>
              <th>División</th><th>Nombre sitio</th><th>Motivo</th>
            </tr></thead>
            <tbody>
              ${errores.map(e => `
                <tr>
                  <td>${escHtml(e.RPU)}</td>
                  <td>${escHtml(e.FROMDATE)}</td>
                  <td>${escHtml(e.TODATE)}</td>
                  <td>${escHtml(e.DIVISION)}</td>
                  <td>${escHtml(e.NAME)}</td>
                  <td><span class="error-badge error-badge--${motivoClass(e.motivo)}">${escHtml(e.motivo)}</span></td>
                </tr>`).join("")}
            </tbody>
          </table>
        </div>
        ${filasOcultas > 0 ? `
          <p class="error-overflow-note">
            Se muestran ${filasMostradas.toLocaleString()} de ${nErrores.toLocaleString()} registros con problema.
            Revisa los logs del servidor para el detalle completo.
          </p>` : ""}
      </div>
    `;
  }

  return `
    <div class="result-header">
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
        <circle cx="9" cy="9" r="8" stroke="#16A34A" stroke-width="1.5"/>
        <path d="M5.5 9l2.5 2.5 4.5-4.5" stroke="#16A34A" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      <h3>Carga completada</h3>
    </div>
    <p class="result-msg">${escHtml(data.mensaje)}</p>
    ${statsHtml}
    ${erroresHtml}
    <div class="hub-status" id="hub-status">
      <div class="hub-status-loading">
        <div class="spinner spinner-sm"></div>
        <span>Finalizando proceso, esperando confirmación del hub…</span>
      </div>
    </div>
  `;
}

function motivoClass(motivo) {
  if (!motivo) return "default";
  const m = motivo.toLowerCase();
  if (m.includes("duplicado")) return "dup";
  if (m.includes("nulo")) return "null";
  if (m.includes("tipo")) return "type";
  if (m.includes("largo")) return "len";
  return "default";
}


/* ══════════════════════════════════════════════════════
   PROGRESS BAR
   ══════════════════════════════════════════════════════ */
let _progressTimer = null;

function animateProgress() {
  let pct = 0;
  DOM.progressBar.style.width = "0%";
  DOM.progressMsg.textContent = "Conectando a HANA…";
  _progressTimer = setInterval(() => {
    if (pct < 40) { pct += 3; DOM.progressMsg.textContent = "Conectando a HANA…"; }
    else if (pct < 75) { pct += 1.2; DOM.progressMsg.textContent = "Insertando registros…"; }
    else if (pct < 90) { pct += 0.3; DOM.progressMsg.textContent = "Finalizando transacción…"; }
    DOM.progressBar.style.width = Math.min(pct, 90) + "%";
  }, 200);
}

function stopProgress(finalPct) {
  clearInterval(_progressTimer);
  DOM.progressBar.style.width = finalPct + "%";
  DOM.progressMsg.textContent = finalPct === 100 ? "¡Carga exitosa!" : "Carga finalizada.";
}


/* ══════════════════════════════════════════════════════
   HELPERS
   ══════════════════════════════════════════════════════ */
function showInlineError(el, msg) {
  el.textContent = msg;
  show(el);
}

function updateConnBadge(status) {
  DOM.connBadge.className = "conn-badge";
  if (status === "ok") {
    DOM.connBadge.classList.add("ok");
    DOM.connBadge.textContent = "Conectado";
  } else {
    DOM.connBadge.classList.add("error");
    DOM.connBadge.textContent = "Error de conexión";
  }
}

function setLoading(btn, label) {
  btn.dataset.origText = btn.textContent;
  btn.textContent = label;
  btn.disabled = true;
}

function clearLoading(btn, label) {
  btn.textContent = label;
  btn.disabled = false;
}

function escHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}