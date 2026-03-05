export function generateId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return Math.random().toString(36).substring(2) + Date.now().toString(36);
}

export function createTimestamp(dateValue) {
  const today = Temporal.Now.plainDateISO().toString();
  return dateValue === today ? Temporal.Now.instant().toString() : dateValue + 'T12:00:00.000Z';
}

export function getEventsForDate(events, date) {
  return events.filter((e) => e.date === date);
}

export function sumForType(events, date, type) {
  return getEventsForDate(events, date)
    .filter((e) => e.type === type)
    .reduce((sum, e) => sum + e.count, 0);
}

function daysAgoISO(daysAgo) {
  return Temporal.Now.plainDateISO().subtract({ days: daysAgo }).toString();
}

export function aggregateByDate(events, days = 30) {
  const result = [];
  for (let i = days - 1; i >= 0; i--) {
    const date = daysAgoISO(i);
    const spray = sumForType(events, date, 'spray');
    const ventoline = sumForType(events, date, 'ventoline');
    if (spray > 0 || ventoline > 0) {
      result.push({ date, spray, ventoline });
    }
  }
  return result;
}

export function aggregateRitalinByDate(events, days = 30) {
  const result = [];
  for (let i = days - 1; i >= 0; i--) {
    const date = daysAgoISO(i);
    const count = events
      .filter((e) => e.date === date)
      .reduce((sum, e) => sum + e.count, 0);
    if (count > 0) result.push({ date, count });
  }
  return result;
}

export function migrateToEventLog(data, generateIdFn = generateId) {
  if (Array.isArray(data)) {
    return data;
  }

  const events = [];
  for (const [date, value] of Object.entries(data)) {
    let spray = 0;
    let ventoline = 0;
    if (typeof value === 'number') {
      ventoline = value;
    } else if (value && typeof value === 'object') {
      spray = value.spray || 0;
      ventoline = value.ventoline || 0;
    }
    if (spray > 0) {
      events.push({ id: generateIdFn(), date, timestamp: date + 'T12:00:00.000Z', type: 'spray', count: spray, preventive: false });
    }
    if (ventoline > 0) {
      events.push({ id: generateIdFn(), date, timestamp: date + 'T12:00:01.000Z', type: 'ventoline', count: ventoline, preventive: false });
    }
  }

  return events;
}

export function updateEntry(entries, updatedEntry) {
  return entries.map((e) => (e.id === updatedEntry.id ? { ...updatedEntry } : e));
}

export function smartMerge(localEntries, cloudEntries) {
  const localIds = new Set(localEntries.map((e) => e.id));
  const unmatched = cloudEntries.filter((e) => !localIds.has(e.id));

  if (unmatched.length === 0) {
    return { entries: localEntries, newCount: 0, idUpdates: 0 };
  }

  const matchedLocalIndices = new Set();
  const trulyNew = [];
  const updatedLocal = [...localEntries];

  for (const cloudEvent of unmatched) {
    const localIdx = updatedLocal.findIndex(
      (e, i) => !matchedLocalIndices.has(i) &&
                 e.date === cloudEvent.date &&
                 e.type === cloudEvent.type &&
                 e.count === cloudEvent.count &&
                 Boolean(e.preventive) === Boolean(cloudEvent.preventive)
    );
    if (localIdx !== -1) {
      matchedLocalIndices.add(localIdx);
      updatedLocal[localIdx] = { ...updatedLocal[localIdx], id: cloudEvent.id };
    } else {
      trulyNew.push(cloudEvent);
    }
  }

  return { entries: [...updatedLocal, ...trulyNew], newCount: trulyNew.length, idUpdates: matchedLocalIndices.size };
}
