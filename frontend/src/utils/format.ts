export function formatDate(value?: string | null): string {
  if (!value) {
    return "N/A";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function formatPercent(value?: number | null): string {
  if (value === undefined || value === null) {
    return "0%";
  }
  return `${Math.round(value * 100)}%`;
}
