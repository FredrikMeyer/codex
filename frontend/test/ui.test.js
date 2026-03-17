import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildWeeklySummaryHtml } from '../ui.js';

test('buildWeeklySummaryHtml shows no-use message when both weeks are zero', () => {
  const html = buildWeeklySummaryHtml({ thisWeek: 0, lastWeek: 0, delta: 0 });
  assert.ok(html.includes('weekly-none'));
  assert.ok(html.includes('No rescue uses in the last 2 weeks'));
});

test('buildWeeklySummaryHtml shows singular "use" when thisWeek is 1', () => {
  const html = buildWeeklySummaryHtml({ thisWeek: 1, lastWeek: 0, delta: 1 });
  assert.ok(html.includes('1 rescue use this week'));
});

test('buildWeeklySummaryHtml shows plural "uses" when thisWeek is not 1', () => {
  const html = buildWeeklySummaryHtml({ thisWeek: 3, lastWeek: 0, delta: 3 });
  assert.ok(html.includes('3 rescue uses this week'));
});

test('buildWeeklySummaryHtml shows better class and down arrow when delta is negative', () => {
  const html = buildWeeklySummaryHtml({ thisWeek: 1, lastWeek: 3, delta: -2 });
  assert.ok(html.includes('class="weekly-delta better"'));
  assert.ok(html.includes('↓2 from last week'));
});

test('buildWeeklySummaryHtml shows worse class and up arrow when delta is positive', () => {
  const html = buildWeeklySummaryHtml({ thisWeek: 4, lastWeek: 2, delta: 2 });
  assert.ok(html.includes('class="weekly-delta worse"'));
  assert.ok(html.includes('↑2 from last week'));
});

test('buildWeeklySummaryHtml shows same class and neutral text when delta is zero and usage exists', () => {
  const html = buildWeeklySummaryHtml({ thisWeek: 2, lastWeek: 2, delta: 0 });
  assert.ok(html.includes('class="weekly-delta same"'));
  assert.ok(html.includes('same as last week'));
});
