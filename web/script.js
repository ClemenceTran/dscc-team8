const element = (id) => document.getElementById(id);
const percent = new Intl.NumberFormat(undefined, { style: "percent", maximumFractionDigits: 1 });
const numbers = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 });
const riskColors = {"low": "#079579", "medium": "#a75e08", "high": "#d64e70"};
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)");
let latestResults = [];
const numberFormat = new Intl.NumberFormat();
let chart;
let busy = false;
let lastSuccess = null;

function renderChart(results) {
  const labels = Object.keys(riskColors);
  const colors = labels.map((label) => riskColors[label]);
  const values = labels.map((label) => results.reduce((sum, batch) => sum + batch.riskCounts[label], 0));
  const customerCount = values.reduce((sum, value) => sum + value, 0);
  const fallback = element("chart-fallback");
  const area = element("chart-area");
  element("chart-empty").hidden = Boolean(results.length);
  area.hidden = !results.length || !window.Chart;
  fallback.hidden = !results.length || Boolean(window.Chart);
  if (!results.length) return;
  if (!window.Chart) {
    fallback.replaceChildren(...labels.map((label, index) => {
      const row = document.createElement("div");
      const caption = document.createElement("span");
      caption.textContent = label + " (" + values[index] + ")";
      const bar = document.createElement("progress");
      bar.max = customerCount;
      bar.value = values[index];
      bar.setAttribute("aria-label", caption.textContent);
      row.append(caption, bar);
      return row;
    }));
    return;
  }
  element("chart").setAttribute("aria-label", labels.map((label, i) => label + ": " + values[i]).join(", "));
  element("chart-total").textContent = customerCount;
  element("legend").replaceChildren(...labels.map((label, index) => {
    const row = document.createElement("li");
    const swatch = document.createElement("span");
    swatch.className = "swatch";
    swatch.style.backgroundColor = colors[index];
    swatch.setAttribute("aria-hidden", "true");
    const name = document.createElement("span");
    name.className = "label";
    name.textContent = label;
    const count = document.createElement("strong");
    count.textContent = values[index];
    const share = document.createElement("span");
    share.className = "share";
    share.textContent = percent.format(values[index] / customerCount);
    row.append(swatch, name, count, share);
    return row;
  }));
  const dataset = { data: values, backgroundColor: colors, borderColor: "#fff", borderWidth: 3 };
  if (chart) {
    chart.data.labels = labels;
    chart.data.datasets[0] = dataset;
    chart.update("none");
  } else {
    chart = new window.Chart(element("chart"), {
      type: "doughnut",
      data: { labels, datasets: [dataset] },
      options: { responsive: true, maintainAspectRatio: false, cutout: "73%",
        animation: reduceMotion.matches ? false : { duration: 500 }, plugins: { legend: { display: false } } }
    });
  }
}

function render(results) {
  const count = results.length;
  const customers = results.reduce((sum, batch) => sum + batch.customerCount, 0);
  const churned = results.reduce((sum, batch) => sum + batch.churnCount, 0);
  const totalDuration = results.reduce((sum, result) => sum + result.durationMs, 0);
  element("total").textContent = numberFormat.format(customers);
  element("negative").textContent = customers ? percent.format(churned / customers) : "—";
  element("duration").textContent = count ? numbers.format(totalDuration / count) + " ms" : "—";
  latestResults = results;
  renderReview();
  renderChart(results);
}

function renderReview() {
  const threshold = Number(element("threshold").value) / 100;
  const flagged = latestResults.filter((result) => result.maxChurnProbability >= threshold);
  const reviewOnly = element("review-only").checked;
  const visible = reviewOnly ? flagged : latestResults;
  element("threshold-value").textContent = percent.format(threshold);
  element("review-count").textContent = latestResults.length ? flagged.length + " / " + latestResults.length : "—";
  element("mock-note").hidden = !latestResults.some((result) => result.modelVersion.startsWith("mock-"));
  const empty = element("empty");
  empty.hidden = Boolean(visible.length);
  empty.textContent = latestResults.length ? "No batches meet this threshold." : "Waiting for the first CSV batch.";
  element("rows").replaceChildren(...visible.map((result) => {
    const row = document.createElement("tr");
    const values = [
      result.fileName, result.customerCount, result.riskCounts.high,
      percent.format(result.maxChurnProbability), result.modelVersion,
      numbers.format(result.durationMs) + " ms", new Date(result.timestamp).toLocaleString()
    ];
    for (const value of values) row.insertCell().textContent = value;
    return row;
  }));
}

async function refresh() {
  if (busy) return;
  busy = true;
  element("refresh").disabled = true;
  const status = element("status");
  try {
    const response = await fetch(window.RECENT_API_URL, { cache: "no-store", signal: AbortSignal.timeout(10000) });
    if (!response.ok) throw new Error("Results API returned HTTP " + response.status);
    const results = await response.json();
    render(results);
    lastSuccess = new Date().toLocaleTimeString();
    status.classList.remove("error");
    status.classList.add("ready");
    status.textContent = "Updated at " + lastSuccess + " · Refreshes every 30 seconds";
  } catch (error) {
    status.classList.remove("ready");
    status.classList.add("error");
    status.textContent = "Could not refresh results. " +
      (lastSuccess ? "Showing results from " + lastSuccess + ". " : "") + "Retrying in 30 seconds.";
    console.warn(error);
  } finally {
    busy = false;
    element("refresh").disabled = false;
  }
}

element("threshold").addEventListener("input", renderReview);
element("review-only").addEventListener("change", renderReview);
element("refresh").addEventListener("click", refresh);
refresh();
setInterval(refresh, 30000);
