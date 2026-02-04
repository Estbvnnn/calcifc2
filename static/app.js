const form = document.getElementById("ifc-form");
const resetButton = document.getElementById("reset");
const results = document.getElementById("results");
const emptyMessage = results.querySelector(".empty");
const historyContainer = document.querySelector(".history-list");
const refreshHistoryButton = document.getElementById("refresh-history");

const renderResults = (data) => {
  results.innerHTML = `
    <h2>Résultats</h2>
    <div class="result-meta">
      <p><strong>Projet :</strong> ${data.project}</p>
      <p><strong>Fichier :</strong> ${data.filename}</p>
      <p><strong>Zone :</strong> ${data.zone || "Non définie"}</p>
      <p><strong>Usage :</strong> ${data.building_use}</p>
    </div>
    <div class="result-summary">
      <div class="summary-card">
        <strong>Lignes totales</strong>
        <span>${data.summary.total_lines}</span>
      </div>
      <div class="summary-card">
        <strong>Entités IFC</strong>
        <span>${data.summary.entity_count}</span>
      </div>
      <div class="summary-card">
        <strong>Headers IFC</strong>
        <span>${data.summary.header_count}</span>
      </div>
    </div>
    <div class="result-summary">
      <div class="summary-card">
        <strong>Neige (kN/m²)</strong>
        <span>${data.loads.snow_kN_m2}</span>
      </div>
      <div class="summary-card">
        <strong>Vent (kN/m²)</strong>
        <span>${data.loads.wind_kN_m2}</span>
      </div>
      <div class="summary-card">
        <strong>Sismique (ag)</strong>
        <span>${data.loads.seismic_ag}</span>
      </div>
    </div>
    <h3>Contrôles rapides</h3>
    <ul class="checklist">
      ${data.checks
        .map(
          (check) => `
          <li class="check-item">
            <strong>${check.name}</strong>
            <span>${check.status}</span>
            <p>${check.details}</p>
          </li>
        `
        )
        .join("")}
    </ul>
    <h3>Étapes suivantes</h3>
    <ul class="list">
      ${data.next_steps.map((step) => `<li>${step}</li>`).join("")}
    </ul>
    <div class="actions">
      <a class="button-link" href="/report/${data.analysis_id}">Télécharger le pré-rapport JSON</a>
    </div>
  `;
};

const renderHistory = (items) => {
  if (!items.length) {
    historyContainer.classList.add("empty");
    historyContainer.textContent = "Aucune analyse enregistrée.";
    return;
  }

  historyContainer.classList.remove("empty");
  historyContainer.innerHTML = items
    .map(
      (item) => `
        <div class="history-item">
          <div>
            <strong>${item.project}</strong>
            <p>${item.filename}</p>
            <span>${item.zone} · ${item.building_use}</span>
          </div>
          <div class="history-actions">
            <span>${new Date(item.created_at).toLocaleString("fr-FR")}</span>
            <a class="button-link" href="/report/${item.id}">Rapport</a>
          </div>
        </div>
      `
    )
    .join("");
};

const loadHistory = async () => {
  try {
    const response = await fetch("/history");
    const data = await response.json();
    renderHistory(data.items || []);
  } catch (error) {
    historyContainer.classList.add("empty");
    historyContainer.textContent = "Impossible de charger l'historique.";
  }
};

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(form);
  results.innerHTML = "<h2>Résultats</h2><p>Analyse en cours...</p>";

  try {
    const response = await fetch("/analyze", {
      method: "POST",
      body: formData,
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Erreur lors de l'analyse.");
    }

    renderResults(data);
    loadHistory();
  } catch (error) {
    results.innerHTML = `
      <h2>Résultats</h2>
      <p class="empty">${error.message}</p>
    `;
  }
});

resetButton.addEventListener("click", () => {
  form.reset();
  results.innerHTML = "<h2>Résultats</h2>";
  results.appendChild(emptyMessage);
});

refreshHistoryButton.addEventListener("click", () => {
  loadHistory();
});

loadHistory();
