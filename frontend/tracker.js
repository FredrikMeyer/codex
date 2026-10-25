/** @returns {string} */
export function generateId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return Math.random().toString(36).substring(2) + Date.now().toString(36);
}

/**
 * @param {string} dateValue
 * @returns {string}
 */
export function createTimestamp(dateValue) {
  const today = Temporal.Now.plainDateISO().toString();
  return dateValue === today ? Temporal.Now.instant().toString() : dateValue + 'T12:00:00.000Z';
}

/**
 * @param {UsageEvent[]} events
 * @param {string} date
 * @returns {UsageEvent[]}
 */
export function getEventsForDate(events, date) {
  return events.filter((e) => e.date === date);
}

/**
 * @param {UsageEvent[]} events
 * @param {string} date
 * @param {MedicineType} type
 * @returns {number}
 */
export function sumForType(events, date, type) {
  return getEventsForDate(events, date)
    .filter((e) => e.type === type)
    .reduce((sum, e) => sum + e.count, 0);
}

/** @param {number} daysAgo @returns {string} */
function daysAgoISO(daysAgo) {
  return Temporal.Now.plainDateISO().subtract({ days: daysAgo }).toString();
}

/**
 * @param {UsageEvent[]} events
 * @param {number} [days]
 * @returns {DailyAsthmaAggregation[]}
 */
export function aggregateByDate(events, days = 30) {
  const result = [];
  for (let i = days - 1; i >= 0; i--) {
    const date = daysAgoISO(i);
    const dayEvents = getEventsForDate(events, date);
    const preventive = dayEvents.filter((e) => e.preventive).reduce((sum, e) => sum + e.count, 0);
    const rescue = dayEvents.filter((e) => !e.preventive).reduce((sum, e) => sum + e.count, 0);
    if (preventive > 0 || rescue > 0) {
      result.push({ date, preventive, rescue });
    }
  }
  return result;
}

/**
 * @param {RitalinEvent[]} events
 * @param {number} [days]
 * @returns {DailyRitalinAggregation[]}
 */
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

/**
 * @param {UsageEvent[] | Record<string, unknown>} data
 * @param {() => string} [generateIdFn]
 * @returns {UsageEvent[]}
 */
export function migrateToEventLog(data, generateIdFn = generateId) {
  if (Array.isArray(data)) {
    return data;
  }

  const events = /** @type {UsageEvent[]} */ ([]);
  for (const [date, value] of Object.entries(data)) {
    let spray = 0;
    let ventoline = 0;
    if (typeof value === 'number') {
      ventoline = value;
    } else if (value && typeof value === 'object') {
      const v = /** @type {Record<string, number>} */ (value);
      spray = v['spray'] || 0;
      ventoline = v['ventoline'] || 0;
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

/**
 * @param {UsageEvent[]} events
 * @returns {WeeklySummary}
 */
export function weeklyRescueSummary(events) {
  const today = Temporal.Now.plainDateISO();
  const thisWeekStart = today.subtract({ days: 6 });
  const lastWeekStart = today.subtract({ days: 13 });

  /** @param {UsageEvent} e @returns {boolean} */
  const inThisWeek = (e) => {
    const d = Temporal.PlainDate.from(e.date);
    return !e.preventive &&
      Temporal.PlainDate.compare(d, thisWeekStart) >= 0 &&
      Temporal.PlainDate.compare(d, today) <= 0;
  };

  /** @param {UsageEvent} e @returns {boolean} */
  const inLastWeek = (e) => {
    const d = Temporal.PlainDate.from(e.date);
    return !e.preventive &&
      Temporal.PlainDate.compare(d, lastWeekStart) >= 0 &&
      Temporal.PlainDate.compare(d, thisWeekStart) < 0;
  };

  const thisWeek = events.filter(inThisWeek).reduce((sum, e) => sum + e.count, 0);
  const lastWeek = events.filter(inLastWeek).reduce((sum, e) => sum + e.count, 0);

  return { thisWeek, lastWeek, delta: thisWeek - lastWeek };
}

/**
 * @param {UsageEvent[]} events
 * @param {number} [months]
 * @returns {MonthlyAggregation[]}
 */
export function aggregateByMonth(events, months = 6) {
  const today = Temporal.Now.plainDateISO();
  const startDate = today.subtract({ months: months - 1 }).with({ day: 1 });

  const result = [];
  for (let m = 0; m < months; m++) {
    const monthStart = startDate.add({ months: m });
    const monthStr = monthStart.toString().slice(0, 7);
    const monthEvents = events.filter((e) => e.date.startsWith(monthStr));

    const preventive = monthEvents
      .filter((e) => e.preventive)
      .reduce((sum, e) => sum + e.count, 0);
    const rescue = monthEvents
      .filter((e) => !e.preventive)
      .reduce((sum, e) => sum + e.count, 0);

    const label = monthStart.toLocaleString('en-GB', { month: 'long', year: 'numeric' });
    result.push({ month: monthStr, label, preventive, rescue, total: preventive + rescue });
  }

  return result;
}

/**
 * @param {UsageEvent[]} events
 * @param {number} [n]
 * @returns {WeekEntry[]}
 */
export function worstWeeks(events, n = 3) {
  const today = Temporal.Now.plainDateISO();
  const cutoff = today.subtract({ weeks: 26 });

  /** @type {Map<string, number>} */
  const weekMap = new Map();
  for (const event of events) {
    if (event.preventive) continue;
    const date = Temporal.PlainDate.from(event.date);
    if (Temporal.PlainDate.compare(date, cutoff) < 0) continue;

    const weekStart = date.subtract({ days: date.dayOfWeek - 1 }).toString();
    weekMap.set(weekStart, (weekMap.get(weekStart) || 0) + event.count);
  }

  return Array.from(weekMap.entries())
    .map(([weekStart, rescueDoses]) => ({
      weekStart,
      rescueDoses,
      aboveGinaThreshold: rescueDoses > 2,
    }))
    .sort((a, b) => b.rescueDoses - a.rescueDoses)
    .slice(0, n);
}

/**
 * @template {UsageEvent | RitalinEvent} T
 * @param {T[]} entries
 * @param {T} updatedEntry
 * @returns {T[]}
 */
export function updateEntry(entries, updatedEntry) {
  return entries.map((e) => (e.id === updatedEntry.id ? { ...updatedEntry } : e));
}

/**
 * @template {UsageEvent | RitalinEvent} T
 * @param {T[]} entries
 * @param {string} date
 * @returns {{ kept: T[], removedIds: string[] }}
 */
export function removeEntriesOnDate(entries, date) {
  return {
    kept: entries.filter((e) => e.date !== date),
    removedIds: entries.filter((e) => e.date === date).map((e) => e.id)
  };
}

/**
 * @template {UsageEvent | RitalinEvent} T
 * @param {T[]} entries
 * @param {Set<string>} syncedIds
 * @returns {T[]}
 */
export function unsyncedEntries(entries, syncedIds) {
  return entries.filter((e) => !syncedIds.has(e.id));
}

/**
 * Merges cloud events into local ones. The cloud is authoritative for events
 * already synced, so a synced local event missing from the cloud was deleted
 * on another device. Local events never uploaded are always kept.
 *
 * @template {UsageEvent | RitalinEvent} T
 * @param {T[]} localEntries
 * @param {T[]} cloudEntries
 * @param {Set<string>} syncedIds
 * @returns {ReconcileResult<T>}
 */
export function reconcile(localEntries, cloudEntries, syncedIds) {
  const cloudIds = new Set(cloudEntries.map((e) => e.id));
  const localIds = new Set(localEntries.map((e) => e.id));
  const kept = localEntries.filter((e) => cloudIds.has(e.id) || !syncedIds.has(e.id));
  const added = cloudEntries.filter((e) => !localIds.has(e.id));
  return {
    entries: [...kept, ...added],
    added: added.length,
    removed: localEntries.length - kept.length
  };
}

/**
 * @param {string} search
 * @returns {'asthma' | 'ritalin' | null}
 */
export function parseTabFromSearch(search) {
  const tab = new URLSearchParams(search).get('tab');
  return tab === 'asthma' || tab === 'ritalin' ? tab : null;
}
