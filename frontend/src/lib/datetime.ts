const DATE_OPTIONS: Intl.DateTimeFormatOptions = {
  dateStyle: "medium",
};

const DATE_TIME_OPTIONS: Intl.DateTimeFormatOptions = {
  dateStyle: "medium",
  timeStyle: "short",
  hourCycle: "h23",
};

const TIME_OPTIONS: Intl.DateTimeFormatOptions = {
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
};

function parseDateValue(value: string | number | Date | null | undefined): Date | null {
  if (value === null || value === undefined || value === "") return null;
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatDateOnly(
  value: string | number | Date | null | undefined,
  fallback = "—"
): string {
  const date = parseDateValue(value);
  return date ? new Intl.DateTimeFormat(undefined, DATE_OPTIONS).format(date) : fallback;
}

export function formatDateTimeLocal(
  value: string | number | Date | null | undefined,
  fallback = "—"
): string {
  const date = parseDateValue(value);
  return date ? new Intl.DateTimeFormat(undefined, DATE_TIME_OPTIONS).format(date) : fallback;
}

export function formatTimeLocal(
  value: string | number | Date | null | undefined,
  fallback = "—"
): string {
  const date = parseDateValue(value);
  return date ? new Intl.DateTimeFormat(undefined, TIME_OPTIONS).format(date) : fallback;
}
