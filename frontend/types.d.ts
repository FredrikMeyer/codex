/** Medicine type for asthma events. */
type MedicineType = 'spray' | 'ventoline';

/** A single asthma medicine usage event. */
interface UsageEvent {
  id: string;
  date: string;
  timestamp: string;
  type: MedicineType;
  count: number;
  preventive: boolean;
  received_at?: string;
}

/** A single Ritalin usage event. */
interface RitalinEvent {
  id: string;
  date: string;
  timestamp: string;
  count: number;
  received_at?: string;
}

/** Aggregated asthma doses for one calendar day. */
interface DailyAsthmaAggregation {
  date: string;
  preventive: number;
  rescue: number;
}

/** Aggregated Ritalin doses for one calendar day. */
interface DailyRitalinAggregation {
  date: string;
  count: number;
}

/** Aggregated asthma doses for one calendar month. */
interface MonthlyAggregation {
  month: string;
  label: string;
  preventive: number;
  rescue: number;
  total: number;
}

/** Rescue-dose summary comparing this week to last week. */
interface WeeklySummary {
  thisWeek: number;
  lastWeek: number;
  delta: number;
}

/** Rescue-dose total for a single calendar week. */
interface WeekEntry {
  weekStart: string;
  rescueDoses: number;
  aboveGinaThreshold: boolean;
}

/** Result returned by smartMerge. */
interface MergeResult<T> {
  entries: T[];
  newCount: number;
  idUpdates: number;
}

/** Result returned by upload API calls. */
interface UploadResult {
  successCount: number;
  errorCount: number;
}
