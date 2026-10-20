const spotInput = document.getElementById("spot");
const strikeInput = document.getElementById("strike");
const daysInput = document.getElementById("days_to_maturity");
const rateSlider = document.getElementById("rate");
const volSlider = document.getElementById("volatility");
const rateBubble = document.getElementById("rate-bubble");
const volBubble = document.getElementById("volatility-bubble");

const errorEl = document.getElementById("error");
const resultsEl = document.getElementById("results");
const chartSection = document.getElementById("chart-section");
const chartSvg = document.getElementById("chart-svg");
const chartLegend = document.getElementById("chart-legend");

const CURVE_POINT_COUNT = 25;
const CURVE_RANGE_FACTOR = 0.3;

let latestCurve = null;
let latestOptionType = "call";
let updateTimer = null;

function formatPercent(value) {
  const rounded = Math.round(value * 10) / 10;
  return `${rounded % 1 === 0 ? rounded.toFixed(0) : rounded.toFixed(1)}%`;
}

function updateSliderVisual(slider, bubble) {
  const min = parseFloat(slider.min);
  const max = parseFloat(slider.max);
  const value = parseFloat(slider.value);
  const pct = (value - min) / (max - min);
  bubble.textContent = formatPercent(value);
  bubble.style.left = `${Math.min(97, Math.max(3, pct * 100))}%`;
  slider.style.background = `linear-gradient(to right, var(--accent) ${pct * 100}%, var(--track-bg) ${pct * 100}%)`;
}

function selectedRadioValue(name) {
  return document.querySelector(`input[name="${name}"]:checked`).value;
}

function readBaseInputs() {
  const spot = parseFloat(spotInput.value);
  const strike = parseFloat(strikeInput.value);
  const days = parseFloat(daysInput.value);
  const rate = parseFloat(rateSlider.value) / 100;
  const volatility = parseFloat(volSlider.value) / 100;
  const option_type = selectedRadioValue("option_type");

  if (!(spot > 0) || !(strike > 0) || !(days > 0)) {
    return null;
  }
  return { option_type, spot, strike, time_to_expiry: days / 365, rate, volatility };
}

function buildSpotRange(centerSpot) {
  const min = centerSpot * (1 - CURVE_RANGE_FACTOR);
  const max = centerSpot * (1 + CURVE_RANGE_FACTOR);
  const step = (max - min) / (CURVE_POINT_COUNT - 1);
  return Array.from({ length: CURVE_POINT_COUNT }, (_, i) => min + i * step);
}

async function fetchPrice(inputs) {
  const response = await fetch("/api/price", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(inputs),
  });
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.error || `Request failed (${response.status})`);
  }
  return body;
}

async function computeCurve(baseInputs) {
  const spots = buildSpotRange(baseInputs.spot);
  const responses = await Promise.all(spots.map((spot) => fetchPrice({ ...baseInputs, spot })));
  return responses.map((body, i) => ({
    spot: spots[i],
    price: body.price,
    delta: body.greeks.delta,
    gamma: body.greeks.gamma,
    theta: body.greeks.theta,
    vega: body.greeks.vega,
    rho: body.greeks.rho,
  }));
}

function showResults(body) {
  document.getElementById("result-price").textContent = body.price.toFixed(4);
  document.getElementById("greek-delta").textContent = body.greeks.delta.toFixed(4);
  document.getElementById("greek-gamma").textContent = body.greeks.gamma.toFixed(4);
  document.getElementById("greek-theta").textContent = body.greeks.theta.toFixed(4);
  document.getElementById("greek-vega").textContent = body.greeks.vega.toFixed(4);
  document.getElementById("greek-rho").textContent = body.greeks.rho.toFixed(4);
  resultsEl.hidden = false;
}

function showError(message) {
  errorEl.textContent = message;
  errorEl.hidden = false;
  resultsEl.hidden = true;
  chartSection.hidden = true;
}

function renderFromCache() {
  if (!latestCurve) return;
  const greekKey = selectedRadioValue("greek_type");
  renderChart(chartSvg, latestCurve, latestOptionType, greekKey);
  renderLegend(chartLegend, latestOptionType, greekKey);
}

async function updateAll() {
  const baseInputs = readBaseInputs();
  if (!baseInputs) {
    showError("Spot, strike, and days to maturity must all be positive numbers.");
    return;
  }

  try {
    const [pointResult, curve] = await Promise.all([fetchPrice(baseInputs), computeCurve(baseInputs)]);
    errorEl.hidden = true;
    showResults(pointResult);
    latestCurve = curve;
    latestOptionType = baseInputs.option_type;
    chartSection.hidden = false;
    renderFromCache();
  } catch (err) {
    showError(err.message || "Could not price this option.");
  }
}

function scheduleUpdate() {
  clearTimeout(updateTimer);
  updateTimer = setTimeout(updateAll, 200);
}

[spotInput, strikeInput, daysInput].forEach((el) => el.addEventListener("input", scheduleUpdate));
document.querySelectorAll('input[name="option_type"]').forEach((el) => el.addEventListener("change", scheduleUpdate));

[[rateSlider, rateBubble], [volSlider, volBubble]].forEach(([slider, bubble]) => {
  slider.addEventListener("input", () => {
    updateSliderVisual(slider, bubble);
    scheduleUpdate();
  });
});

document.querySelectorAll('input[name="greek_type"]').forEach((el) => el.addEventListener("change", renderFromCache));

let resizeTimer = null;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(renderFromCache, 150);
});

document.getElementById("save-image-btn").addEventListener("click", () => {
  if (latestCurve) exportSvgAsPng(chartSvg, "option-pricer-chart.png");
});

document.getElementById("download-csv-btn").addEventListener("click", () => {
  if (latestCurve) downloadCsv(latestCurve, "option-pricer-curve.csv");
});

updateSliderVisual(rateSlider, rateBubble);
updateSliderVisual(volSlider, volBubble);
updateAll();
