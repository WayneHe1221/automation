export type Product = {
  id: string;
  sourceId: string;
  sourceLabel: string;
  productId: string;
  name: string;
  url: string;
  prices: number[];
  currency: "JPY";
  active: boolean;
  firstSeenAt?: string;
  updatedAt?: string;
};

export type Source = {
  id: string;
  label: string;
  schedule: string;
  activeCount: number;
  status: "ok" | "error";
  lastRunDate?: string | null;
  lastSyncAt?: string;
};

export type EventType = "new" | "price_changed" | "removed" | "restocked";

export type ProductEvent = {
  id: string;
  type: EventType;
  productKey: string;
  productId: string;
  productName: string;
  sourceId: string;
  sourceLabel: string;
  url: string;
  oldPrices: number[];
  newPrices: number[];
  occurredAt: string;
};

export type DashboardData = {
  generatedAt: string;
  products: Product[];
  sources: Source[];
  events: ProductEvent[];
};
