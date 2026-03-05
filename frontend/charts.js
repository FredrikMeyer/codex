import { aggregateByDate, aggregateRitalinByDate } from './tracker.js';

export function buildAsthmaChartSvg(events) {
  const data = aggregateByDate(events);

  if (data.length === 0) {
    return null;
  }

  const WIDTH = 600;
  const HEIGHT = 180;
  const PAD_LEFT = 20;
  const PAD_RIGHT = 10;
  const PAD_TOP = 10;
  const PAD_BOTTOM = 30;
  const chartWidth = WIDTH - PAD_LEFT - PAD_RIGHT;
  const chartHeight = HEIGHT - PAD_TOP - PAD_BOTTOM;

  const maxDoses = Math.max(...data.map((d) => d.spray + d.ventoline));
  const barGroupWidth = chartWidth / data.length;
  const barWidth = Math.min(barGroupWidth * 0.35, 18);
  const gap = barWidth * 0.3;
  const barH = (value) => (value / maxDoses) * chartHeight;
  const barY = (value) => PAD_TOP + chartHeight - barH(value);
  const labelStep = Math.max(1, Math.ceil(data.length / 8));

  const elements = data.flatMap((d, i) => {
    const cx = PAD_LEFT + i * barGroupWidth + barGroupWidth / 2;
    const sprayX = cx - barWidth - gap / 2;
    const ventX = cx + gap / 2;
    const parts = [];
    if (d.spray > 0) {
      parts.push(`<rect class="bar-spray" x="${sprayX.toFixed(1)}" y="${barY(d.spray).toFixed(1)}" width="${barWidth.toFixed(1)}" height="${barH(d.spray).toFixed(1)}"><title>Spray: ${d.spray}</title></rect>`);
    }
    if (d.ventoline > 0) {
      parts.push(`<rect class="bar-ventoline" x="${ventX.toFixed(1)}" y="${barY(d.ventoline).toFixed(1)}" width="${barWidth.toFixed(1)}" height="${barH(d.ventoline).toFixed(1)}"><title>Ventoline: ${d.ventoline}</title></rect>`);
    }
    if (i % labelStep === 0) {
      const date = new Date(d.date + 'T12:00:00Z');
      const label = date.toLocaleDateString('en-GB', { month: 'short', day: 'numeric' });
      parts.push(`<text class="axis-label" x="${cx.toFixed(1)}" y="${(HEIGHT - 8).toFixed(1)}" text-anchor="middle">${label}</text>`);
    }
    return parts;
  });

  const gridLine = `<line class="grid-line" x1="${PAD_LEFT}" y1="${PAD_TOP}" x2="${WIDTH - PAD_RIGHT}" y2="${PAD_TOP}"/>`;
  return `<svg viewBox="0 0 ${WIDTH} ${HEIGHT}" xmlns="http://www.w3.org/2000/svg">${gridLine}${elements.join('')}</svg>`;
}

export function buildRitalinChartSvg(events) {
  const data = aggregateRitalinByDate(events);

  if (data.length === 0) {
    return null;
  }

  const WIDTH = 600;
  const HEIGHT = 180;
  const PAD_LEFT = 20;
  const PAD_RIGHT = 10;
  const PAD_TOP = 10;
  const PAD_BOTTOM = 30;
  const chartWidth = WIDTH - PAD_LEFT - PAD_RIGHT;
  const chartHeight = HEIGHT - PAD_TOP - PAD_BOTTOM;

  const maxDoses = Math.max(...data.map((d) => d.count));
  const barGroupWidth = chartWidth / data.length;
  const barWidth = Math.min(barGroupWidth * 0.6, 24);
  const barH = (value) => (value / maxDoses) * chartHeight;
  const barY = (value) => PAD_TOP + chartHeight - barH(value);
  const labelStep = Math.max(1, Math.ceil(data.length / 8));

  const elements = data.flatMap((d, i) => {
    const cx = PAD_LEFT + i * barGroupWidth + barGroupWidth / 2;
    const parts = [];
    parts.push(`<rect class="bar-ritalin" x="${(cx - barWidth / 2).toFixed(1)}" y="${barY(d.count).toFixed(1)}" width="${barWidth.toFixed(1)}" height="${barH(d.count).toFixed(1)}"><title>Doses: ${d.count}</title></rect>`);
    if (i % labelStep === 0) {
      const date = new Date(d.date + 'T12:00:00Z');
      const label = date.toLocaleDateString('en-GB', { month: 'short', day: 'numeric' });
      parts.push(`<text class="axis-label" x="${cx.toFixed(1)}" y="${(HEIGHT - 8).toFixed(1)}" text-anchor="middle">${label}</text>`);
    }
    return parts;
  });

  const gridLine = `<line class="grid-line" x1="${PAD_LEFT}" y1="${PAD_TOP}" x2="${WIDTH - PAD_RIGHT}" y2="${PAD_TOP}"/>`;
  return `<svg viewBox="0 0 ${WIDTH} ${HEIGHT}" xmlns="http://www.w3.org/2000/svg">${gridLine}${elements.join('')}</svg>`;
}
