import { test } from 'node:test';
import assert from 'node:assert/strict';
import { aggregateByDate, aggregateRitalinByDate, smartMerge, migrateToEventLog, getEventsForDate, sumForType, createTimestamp, generateId, updateEntry } from '../tracker.js';

test('generateId returns a non-empty string', () => {
  const id = generateId();
  assert.equal(typeof id, 'string');
  assert.ok(id.length > 0);
});

test('generateId returns unique values', () => {
  const ids = new Set(Array.from({ length: 100 }, generateId));
  assert.equal(ids.size, 100);
});

test('createTimestamp returns ISO string for today', () => {
  const today = new Date().toISOString().slice(0, 10);
  const ts = createTimestamp(today);
  assert.ok(ts.startsWith(today));
  assert.ok(ts.includes('T'));
});

test('createTimestamp returns noon UTC for non-today dates', () => {
  const ts = createTimestamp('2024-01-15');
  assert.equal(ts, '2024-01-15T12:00:00.000Z');
});

test('getEventsForDate filters events by date', () => {
  const events = [
    { date: '2024-01-01', type: 'ventoline', count: 2 },
    { date: '2024-01-02', type: 'spray', count: 1 },
    { date: '2024-01-01', type: 'spray', count: 3 }
  ];
  const result = getEventsForDate(events, '2024-01-01');
  assert.equal(result.length, 2);
  assert.ok(result.every((e) => e.date === '2024-01-01'));
});

test('sumForType sums counts for a given date and type', () => {
  const events = [
    { date: '2024-01-01', type: 'ventoline', count: 2 },
    { date: '2024-01-01', type: 'ventoline', count: 3 },
    { date: '2024-01-01', type: 'spray', count: 5 }
  ];
  assert.equal(sumForType(events, '2024-01-01', 'ventoline'), 5);
  assert.equal(sumForType(events, '2024-01-01', 'spray'), 5);
  assert.equal(sumForType(events, '2024-01-02', 'ventoline'), 0);
});

test('aggregateByDate returns only days with data', () => {
  const today = new Date().toISOString().slice(0, 10);
  const events = [
    { date: today, type: 'ventoline', count: 2 },
    { date: today, type: 'spray', count: 1 }
  ];
  const result = aggregateByDate(events);
  assert.equal(result.length, 1);
  assert.equal(result[0].date, today);
  assert.equal(result[0].ventoline, 2);
  assert.equal(result[0].spray, 1);
});

test('aggregateByDate returns empty array when no events in window', () => {
  const result = aggregateByDate([], 30);
  assert.equal(result.length, 0);
});

test('aggregateByDate ignores events older than the window', () => {
  const oldDate = '2000-01-01';
  const events = [{ date: oldDate, type: 'ventoline', count: 5 }];
  const result = aggregateByDate(events, 30);
  assert.equal(result.length, 0);
});

test('aggregateRitalinByDate returns count per day', () => {
  const today = new Date().toISOString().slice(0, 10);
  const events = [
    { date: today, count: 3 },
    { date: today, count: 2 }
  ];
  const result = aggregateRitalinByDate(events);
  assert.equal(result.length, 1);
  assert.equal(result[0].count, 5);
});

test('aggregateRitalinByDate ignores old events', () => {
  const events = [{ date: '2000-01-01', count: 5 }];
  const result = aggregateRitalinByDate(events, 30);
  assert.equal(result.length, 0);
});

test('smartMerge returns original entries when cloud is already in sync', () => {
  const localEntries = [
    { id: 'a', date: '2024-01-01', type: 'ventoline', count: 2, preventive: false }
  ];
  const cloudEntries = [
    { id: 'a', date: '2024-01-01', type: 'ventoline', count: 2, preventive: false }
  ];
  const { entries, newCount, idUpdates } = smartMerge(localEntries, cloudEntries);
  assert.equal(newCount, 0);
  assert.equal(idUpdates, 0);
  assert.deepEqual(entries, localEntries);
});

test('smartMerge adds truly new cloud events', () => {
  const localEntries = [
    { id: 'a', date: '2024-01-01', type: 'ventoline', count: 2, preventive: false }
  ];
  const cloudEntries = [
    { id: 'a', date: '2024-01-01', type: 'ventoline', count: 2, preventive: false },
    { id: 'b', date: '2024-01-02', type: 'spray', count: 1, preventive: true }
  ];
  const { entries, newCount } = smartMerge(localEntries, cloudEntries);
  assert.equal(newCount, 1);
  assert.equal(entries.length, 2);
  assert.ok(entries.some((e) => e.id === 'b'));
});

test('smartMerge updates local ID when functionally equivalent cloud event has different ID', () => {
  const localEntries = [
    { id: 'local-id', date: '2024-01-01', type: 'ventoline', count: 2, preventive: false }
  ];
  const cloudEntries = [
    { id: 'cloud-id', date: '2024-01-01', type: 'ventoline', count: 2, preventive: false }
  ];
  const { entries, newCount, idUpdates } = smartMerge(localEntries, cloudEntries);
  assert.equal(newCount, 0);
  assert.equal(idUpdates, 1);
  assert.equal(entries[0].id, 'cloud-id');
});

test('smartMerge deduplicates by (date, type, count, preventive)', () => {
  const localEntries = [
    { id: 'a', date: '2024-01-01', type: 'ventoline', count: 2, preventive: false },
    { id: 'b', date: '2024-01-01', type: 'spray', count: 1, preventive: false }
  ];
  const cloudEntries = [
    { id: 'c', date: '2024-01-01', type: 'ventoline', count: 2, preventive: false },
    { id: 'd', date: '2024-01-01', type: 'spray', count: 1, preventive: false }
  ];
  const { entries, newCount, idUpdates } = smartMerge(localEntries, cloudEntries);
  assert.equal(newCount, 0);
  assert.equal(idUpdates, 2);
  assert.equal(entries.length, 2);
});

test('migrateToEventLog returns array unchanged', () => {
  const input = [{ id: 'a', date: '2024-01-01', type: 'ventoline', count: 2 }];
  const result = migrateToEventLog(input);
  assert.deepEqual(result, input);
});

test('migrateToEventLog converts number format (legacy v1)', () => {
  const input = { '2024-01-01': 3 };
  const result = migrateToEventLog(input, () => 'test-id');
  assert.equal(result.length, 1);
  assert.equal(result[0].type, 'ventoline');
  assert.equal(result[0].count, 3);
  assert.equal(result[0].date, '2024-01-01');
  assert.equal(result[0].preventive, false);
});

test('migrateToEventLog converts object format with spray and ventoline', () => {
  const input = { '2024-01-01': { spray: 2, ventoline: 3 } };
  const result = migrateToEventLog(input, () => 'test-id');
  assert.equal(result.length, 2);
  const spray = result.find((e) => e.type === 'spray');
  const ventoline = result.find((e) => e.type === 'ventoline');
  assert.ok(spray);
  assert.ok(ventoline);
  assert.equal(spray.count, 2);
  assert.equal(ventoline.count, 3);
});

test('migrateToEventLog skips zero counts', () => {
  const input = { '2024-01-01': { spray: 0, ventoline: 5 } };
  const result = migrateToEventLog(input, () => 'test-id');
  assert.equal(result.length, 1);
  assert.equal(result[0].type, 'ventoline');
});

test('updateEntry replaces the entry with the matching id', () => {
  const entries = [
    { id: 'a', date: '2024-01-01', type: 'ventoline', count: 2, preventive: false },
    { id: 'b', date: '2024-01-02', type: 'spray', count: 1, preventive: false }
  ];
  const result = updateEntry(entries, { id: 'a', date: '2024-01-01', type: 'spray', count: 3, preventive: true });
  assert.equal(result[0].type, 'spray');
  assert.equal(result[0].count, 3);
  assert.equal(result[0].preventive, true);
  assert.equal(result[1].id, 'b');
  assert.equal(result.length, 2);
});

test('updateEntry returns unchanged array when id not found', () => {
  const entries = [
    { id: 'a', date: '2024-01-01', type: 'ventoline', count: 2, preventive: false }
  ];
  const result = updateEntry(entries, { id: 'z', date: '2024-01-01', type: 'spray', count: 1, preventive: false });
  assert.deepEqual(result, entries);
});
