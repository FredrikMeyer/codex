import { aggregateByMonth, worstWeeks } from './tracker.js';
import { buildAsthmaChartSvg } from './charts.js';

export function buildReportHtml(entries) {
  const monthly = aggregateByMonth(entries, 6);
  const worst = worstWeeks(entries, 5);
  const chartSvg = buildAsthmaChartSvg(entries);

  const today = Temporal.Now.plainDateISO();
  const todayLabel = today.toLocaleString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });
  const periodLabel = `${monthly[0].label} – ${monthly[monthly.length - 1].label}`;

  const monthlyRows = monthly.map((m) => {
    const ratio = m.total > 0 ? Math.round((m.rescue / m.total) * 100) : null;
    const highRescue = ratio !== null && ratio > 30;
    return `<tr${highRescue ? ' class="warn"' : ''}>
      <td>${m.label}</td>
      <td class="num">${m.preventive || '—'}</td>
      <td class="num">${m.rescue || '—'}</td>
      <td class="num">${m.total || '—'}</td>
      <td class="num">${ratio !== null ? ratio + '%' : '—'}</td>
    </tr>`;
  }).join('');

  const worstRows = worst.length > 0
    ? worst.map((w) => {
        const date = Temporal.PlainDate.from(w.weekStart);
        const label = date.toLocaleString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });
        const flag = w.aboveGinaThreshold ? '<span class="gina-flag">Above threshold</span>' : '—';
        return `<tr${w.aboveGinaThreshold ? ' class="warn"' : ''}>
          <td>${label}</td>
          <td class="num">${w.rescueDoses}</td>
          <td>${flag}</td>
        </tr>`;
      }).join('')
    : '<tr><td colspan="3" class="empty">No rescue medication recorded in this period</td></tr>';

  const chartSection = chartSvg
    ? `<section>
        <h2>30-Day Trend</h2>
        <div class="chart">${chartSvg}</div>
        <div class="legend">
          <span class="legend-spray">Preventive</span>
          <span class="legend-ventoline">Rescue</span>
        </div>
      </section>`
    : '';

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Asthma Report — ${todayLabel}</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    background: #fff;
    color: #111;
    font-size: 13px;
    line-height: 1.6;
  }

  .page {
    max-width: 720px;
    margin: 0 auto;
    padding: 48px 40px 64px;
  }

  /* ── Header ── */
  header {
    border-top: 3px solid #1d4ed8;
    padding-top: 20px;
    margin-bottom: 40px;
  }

  header h1 {
    font-family: Georgia, 'Times New Roman', serif;
    font-size: 20px;
    font-weight: normal;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: #111;
    margin-bottom: 4px;
  }

  header .sub {
    font-size: 11px;
    color: #9ca3af;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  .meta {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-top: 20px;
  }

  .meta-item .label {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #9ca3af;
    margin-bottom: 2px;
  }

  .meta-item .value {
    font-size: 13px;
    font-weight: 600;
    color: #111;
  }

  /* ── Sections ── */
  section {
    margin-bottom: 36px;
  }

  h2 {
    font-family: Georgia, 'Times New Roman', serif;
    font-size: 11px;
    font-weight: normal;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: #9ca3af;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid #e5e7eb;
  }

  /* ── Tables ── */
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
  }

  thead th {
    text-align: left;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: #9ca3af;
    font-weight: 600;
    padding: 0 12px 8px 0;
    border-bottom: 1px solid #e5e7eb;
  }

  thead th.num { text-align: right; }

  tbody td {
    padding: 8px 12px 8px 0;
    border-bottom: 1px solid #f3f4f6;
    color: #374151;
  }

  tbody td.num {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }

  tbody td.empty {
    color: #9ca3af;
    font-style: italic;
    padding: 12px 0;
  }

  tr.warn td { color: #92400e; }

  .gina-flag {
    display: inline-block;
    background: #fef3c7;
    color: #92400e;
    font-size: 10px;
    padding: 2px 7px;
    border-radius: 3px;
    letter-spacing: 0.02em;
  }

  .gina-note {
    margin-top: 10px;
    font-size: 11px;
    color: #9ca3af;
    font-style: italic;
  }

  /* ── Chart ── */
  .chart {
    width: 100%;
    overflow: hidden;
    margin-bottom: 10px;
  }

  .chart svg {
    width: 100%;
    height: auto;
    display: block;
  }

  .bar-spray    { fill: #1d4ed8; }
  .bar-ventoline { fill: #b45309; }
  .axis-label   { fill: #9ca3af; font-size: 10px; font-family: -apple-system, sans-serif; }
  .grid-line    { stroke: #e5e7eb; }

  .legend {
    display: flex;
    gap: 20px;
    font-size: 11px;
    color: #6b7280;
  }

  .legend-spray::before   { content: '■'; color: #1d4ed8; margin-right: 5px; }
  .legend-ventoline::before { content: '■'; color: #b45309; margin-right: 5px; }

  /* ── Footer ── */
  footer {
    margin-top: 48px;
    padding-top: 14px;
    border-top: 1px solid #e5e7eb;
    font-size: 11px;
    color: #9ca3af;
    display: flex;
    justify-content: space-between;
  }

  @media print {
    body { background: white; }
    .page { padding: 0; }
    @page { margin: 2cm; }
  }
</style>
</head>
<body>
<div class="page">
  <header>
    <h1>Asthma Medication Report</h1>
    <div class="sub">For GP appointment</div>
    <div class="meta">
      <div class="meta-item">
        <div class="label">Period</div>
        <div class="value">${periodLabel}</div>
      </div>
      <div class="meta-item">
        <div class="label">Prepared</div>
        <div class="value">${todayLabel}</div>
      </div>
    </div>
  </header>

  <section>
    <h2>Monthly Overview</h2>
    <table>
      <thead>
        <tr>
          <th>Month</th>
          <th class="num">Preventive</th>
          <th class="num">Rescue</th>
          <th class="num">Total</th>
          <th class="num">Rescue %</th>
        </tr>
      </thead>
      <tbody>${monthlyRows}</tbody>
    </table>
  </section>

  <section>
    <h2>Highest Rescue Weeks</h2>
    <table>
      <thead>
        <tr>
          <th>Week starting</th>
          <th class="num">Rescue doses</th>
          <th>GINA status</th>
        </tr>
      </thead>
      <tbody>${worstRows}</tbody>
    </table>
    <p class="gina-note">GINA guideline: &gt;2 rescue doses/week indicates poorly controlled asthma.</p>
  </section>

  ${chartSection}

  <footer>
    <span>Personal asthma medication data</span>
    <span>Generated ${todayLabel}</span>
  </footer>
</div>
</body>
</html>`;
}
