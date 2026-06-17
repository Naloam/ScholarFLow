import i18n from "../i18n";

export function formatDate(value?: string | null): string {
  if (!value) {
    return "N/A";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(
    i18n.language.startsWith("zh") ? "zh-CN" : "en-US",
    {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    },
  ).format(date);
}

export function formatPercent(value?: number | null): string {
  if (value === undefined || value === null) {
    return "0%";
  }
  return `${Math.round(value * 100)}%`;
}
