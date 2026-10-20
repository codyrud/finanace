const GREEK_META = {
  delta: { label: "Delta", symbol: "Δ" },
  gamma: { label: "Gamma", symbol: "Γ" },
  vega: { label: "Vega", symbol: "ν" },
  theta: { label: "Theta", symbol: "θ" },
  rho: { label: "Rho", symbol: "ρ" },
};

const SVG_NS = "http://www.w3.org/2000/svg";
const CHART_MARGIN = { top: 20, right: 56, bottom: 44, left: 56 };

function niceTicks(dataMin, dataMax, targetCount) {
  if (dataMin === dataMax) {
    dataMin -= 1;
    dataMax += 1;
  }
  const range = dataMax - dataMin;
  const roughStep = range / targetCount;
  const magnitude = Math.pow(10, Math.floor(Math.log10(roughStep)));
  const residual = roughStep / magnitude;
  let step;
  if (residual > 5) step = 10 * magnitude;
  else if (residual > 2) step = 5 * magnitude;
  else if (residual > 1) step = 2 * magnitude;
  else step = magnitude;

  const niceMin = Math.floor(dataMin / step) * step;
  const niceMax = Math.ceil(dataMax / step) * step;
  const ticks = [];
  for (let v = niceMin; v <= niceMax + step / 2; v += step) {
    ticks.push(Math.round(v / step) * step);
  }
  return { min: niceMin, max: niceMax, ticks, step };
}

function makeLinearScale(domainMin, domainMax, rangeMin, rangeMax) {
  const span = domainMax - domainMin || 1;
  return (value) => rangeMin + ((value - domainMin) / span) * (rangeMax - rangeMin);
}

function svgEl(tag, attrs) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs)) {
    el.setAttribute(key, value);
  }
  return el;
}

function pointsToPath(points, xScale, yScale, key) {
  return points.map((p, i) => `${i === 0 ? "M" : "L"}${xScale(p.spot).toFixed(2)},${yScale(p[key]).toFixed(2)}`).join(" ");
}

function renderChart(svg, points, optionType, greekKey) {
  while (svg.firstChild) svg.removeChild(svg.firstChild);

  const rect = svg.getBoundingClientRect();
  const width = Math.round(rect.width) || 760;
  const height = Math.round(rect.height) || 440;
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  const plot = {
    left: CHART_MARGIN.left,
    right: width - CHART_MARGIN.right,
    top: CHART_MARGIN.top,
    bottom: height - CHART_MARGIN.bottom,
  };

  const spots = points.map((p) => p.spot);
  const prices = points.map((p) => p.price);
  const greeks = points.map((p) => p[greekKey]);

  const priceTicks = niceTicks(Math.min(0, ...prices), Math.max(...prices), 6);
  const greekTicks = niceTicks(Math.min(...greeks), Math.max(...greeks), 6);

  const xScale = makeLinearScale(spots[0], spots[spots.length - 1], plot.left, plot.right);
  const yPriceScale = makeLinearScale(priceTicks.min, priceTicks.max, plot.bottom, plot.top);
  const yGreekScale = makeLinearScale(greekTicks.min, greekTicks.max, plot.bottom, plot.top);

  for (const tick of priceTicks.ticks) {
    const y = yPriceScale(tick);
    svg.appendChild(svgEl("line", { x1: plot.left, x2: plot.right, y1: y, y2: y, stroke: "var(--chart-grid)", "stroke-width": 1 }));
    const label = svgEl("text", { x: plot.left - 8, y: y + 4, "text-anchor": "end", "font-size": 11, fill: "var(--muted)" });
    label.textContent = formatTick(tick, priceTicks.step);
    svg.appendChild(label);
  }

  for (const tick of greekTicks.ticks) {
    const y = yGreekScale(tick);
    const t = svgEl("text", { x: plot.right + 8, y: y + 4, "text-anchor": "start", "font-size": 11, fill: "var(--muted)" });
    t.textContent = formatTick(tick, greekTicks.step);
    svg.appendChild(t);
  }

  const xTickCount = Math.min(9, points.length);
  const xTickStep = Math.max(1, Math.floor((points.length - 1) / (xTickCount - 1)));
  for (let i = 0; i < points.length; i += xTickStep) {
    const x = xScale(points[i].spot);
    const t = svgEl("text", { x, y: plot.bottom + 20, "text-anchor": "middle", "font-size": 11, fill: "var(--muted)" });
    t.textContent = points[i].spot.toFixed(2);
    svg.appendChild(t);
  }

  svg.appendChild(svgEl("line", { x1: plot.left, x2: plot.left, y1: plot.top, y2: plot.bottom, stroke: "var(--border)", "stroke-width": 1 }));
  svg.appendChild(svgEl("line", { x1: plot.right, x2: plot.right, y1: plot.top, y2: plot.bottom, stroke: "var(--border)", "stroke-width": 1 }));
  svg.appendChild(svgEl("line", { x1: plot.left, x2: plot.right, y1: plot.bottom, y2: plot.bottom, stroke: "var(--border)", "stroke-width": 1 }));

  const priceTitle = svgEl("text", { x: 14, y: (plot.top + plot.bottom) / 2, "text-anchor": "middle", "font-size": 12, fill: "var(--fg)", transform: `rotate(-90 14 ${(plot.top + plot.bottom) / 2})` });
  priceTitle.textContent = "Theoretical Price";
  svg.appendChild(priceTitle);

  const greekMeta = GREEK_META[greekKey];
  const greekTitle = svgEl("text", { x: width - 14, y: (plot.top + plot.bottom) / 2, "text-anchor": "middle", "font-size": 12, fill: "var(--fg)", transform: `rotate(90 ${width - 14} ${(plot.top + plot.bottom) / 2})` });
  greekTitle.textContent = `${greekMeta.label} (${greekMeta.symbol})`;
  svg.appendChild(greekTitle);

  svg.appendChild(svgEl("path", { d: pointsToPath(points, xScale, yPriceScale, "price"), fill: "none", stroke: "var(--chart-price)", "stroke-width": 2 }));
  svg.appendChild(svgEl("path", { d: pointsToPath(points, xScale, yGreekScale, greekKey), fill: "none", stroke: "var(--chart-greek)", "stroke-width": 2, "stroke-dasharray": "6 4" }));
}

function formatTick(value, step) {
  const decimals = Math.max(0, -Math.floor(Math.log10(step)));
  const fixed = value.toFixed(decimals);
  return /^-0(\.0+)?$/.test(fixed) ? fixed.slice(1) : fixed;
}

function renderLegend(container, optionType, greekKey) {
  const greekMeta = GREEK_META[greekKey];
  container.innerHTML = "";
  const priceItem = document.createElement("span");
  priceItem.className = "legend-item";
  priceItem.innerHTML = `<span class="legend-swatch" style="border-color: var(--chart-price)"></span>Theoretical Price (${optionType.toUpperCase()})`;
  const greekItem = document.createElement("span");
  greekItem.className = "legend-item";
  greekItem.innerHTML = `<span class="legend-swatch" style="border-color: var(--chart-greek); border-top-style: dashed"></span>${greekMeta.label} (${greekMeta.symbol})`;
  container.append(priceItem, greekItem);
}

function curveToCsv(points) {
  const header = "spot,price,delta,gamma,theta,vega,rho";
  const rows = points.map((p) => [p.spot, p.price, p.delta, p.gamma, p.theta, p.vega, p.rho].map((v) => v.toFixed(6)).join(","));
  return [header, ...rows].join("\n");
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function downloadCsv(points, filename) {
  downloadBlob(new Blob([curveToCsv(points)], { type: "text/csv" }), filename);
}

function exportSvgAsPng(svg, filename) {
  const resolvedSvg = svg.cloneNode(true);
  const computedStyle = getComputedStyle(document.body);
  for (const token of ["--chart-grid", "--muted", "--fg", "--chart-price", "--chart-greek", "--border"]) {
    resolvedSvg.innerHTML = resolvedSvg.innerHTML.split(`var(${token})`).join(computedStyle.getPropertyValue(token).trim());
  }
  resolvedSvg.setAttribute("xmlns", SVG_NS);
  resolvedSvg.style.background = computedStyle.getPropertyValue("--card").trim() || "#fff";

  const svgString = new XMLSerializer().serializeToString(resolvedSvg);
  const svgBlob = new Blob([svgString], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(svgBlob);

  const image = new Image();
  image.onload = () => {
    const scale = 2;
    const canvas = document.createElement("canvas");
    canvas.width = svg.viewBox.baseVal.width * scale;
    canvas.height = svg.viewBox.baseVal.height * scale;
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = computedStyle.getPropertyValue("--card").trim() || "#fff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
    URL.revokeObjectURL(url);
    canvas.toBlob((blob) => downloadBlob(blob, filename), "image/png");
  };
  image.src = url;
}
