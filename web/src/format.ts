import { EventType } from "./types";

export const EVENT_LABELS: Record<EventType, string> = {
  new: "新品上架",
  price_changed: "價格異動",
  removed: "售完／下架",
  restocked: "重新上架",
};

export function formatPrice(prices: number[]) {
  if (!prices.length) return "—";
  return prices.map((price) => `¥${price.toLocaleString("ja-JP")}`).join(" / ");
}

export function formatTime(value?: string, withDate = false) {
  if (!value) return "尚未同步";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-TW", {
    month: withDate ? "2-digit" : undefined,
    day: withDate ? "2-digit" : undefined,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

/** 以 host + 路徑呈現追蹤網頁的原始連結，過長時截斷。 */
export function shortenUrl(url: string, maxLength = 58) {
  let text = url;
  try {
    const parsed = new URL(url);
    text = `${parsed.host}${parsed.pathname}${parsed.search}`.replace(/\/$/, "");
  } catch {
    text = url;
  }
  return text.length > maxLength ? `${text.slice(0, maxLength - 1)}…` : text;
}
