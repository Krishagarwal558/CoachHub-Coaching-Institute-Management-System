const chartDefaults = () => {
  if (!window.Chart) return;
  Chart.defaults.font.family = "Inter, system-ui, sans-serif";
  Chart.defaults.color = "#64748b";
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
};

const parseData = (node, name) => JSON.parse(node.dataset[name] || "[]");

const makeScoreChart = () => {
  const canvas = document.querySelector("#scoreChart");
  if (!canvas || !window.Chart) return;
  new Chart(canvas, {
    type: "line",
    data: {
      labels: parseData(canvas, "labels"),
      datasets: [{
        label: "Score %",
        data: parseData(canvas, "values"),
        borderColor: "#2563eb",
        backgroundColor: "rgba(37, 99, 235, .12)",
        fill: true,
        tension: .42,
        pointRadius: 4
      }]
    },
    options: { responsive: true, maintainAspectRatio: false, scales: { y: { suggestedMin: 0, suggestedMax: 100 } } }
  });
};

const makeClassChart = () => {
  const canvas = document.querySelector("#classChart");
  if (!canvas || !window.Chart) return;
  new Chart(canvas, {
    type: "bar",
    data: {
      labels: parseData(canvas, "labels"),
      datasets: [
        { label: "Average score", data: parseData(canvas, "scores"), backgroundColor: "#2563eb", borderRadius: 6 },
        { label: "Attendance", data: parseData(canvas, "attendance"), backgroundColor: "#14b8a6", borderRadius: 6 }
      ]
    },
    options: { responsive: true, maintainAspectRatio: false, scales: { y: { suggestedMin: 0, suggestedMax: 100 } } }
  });
};

const bindTableSearch = () => {
  document.querySelectorAll("[data-filter-table]").forEach((input) => {
    const table = document.getElementById(input.dataset.filterTable);
    if (!table) return;
    input.addEventListener("input", () => {
      const query = input.value.trim().toLowerCase();
      table.querySelectorAll("tbody tr").forEach((row) => {
        row.style.display = row.innerText.toLowerCase().includes(query) ? "" : "none";
      });
    });
  });
};

const closeToasts = () => {
  setTimeout(() => {
    document.querySelectorAll(".toast").forEach((toast) => {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(-6px)";
      setTimeout(() => toast.remove(), 250);
    });
  }, 3800);
};

window.addEventListener("DOMContentLoaded", () => {
  chartDefaults();
  makeScoreChart();
  makeClassChart();
  bindTableSearch();
  closeToasts();
});
