export type ProductCategory = "product" | "deck";

export type Product = {
  id: string;
  sourceId: string;
  sourceLabel: string;
  productId: string;
  name: string;
  url: string;
  prices: number[];
  qty: number | null;
  currency: "JPY";
  category: ProductCategory;
  active: boolean;
  firstSeenAt?: string;
  updatedAt?: string;
};

export type Source = {
  id: string;
  label: string;
  schedule: string;
  category: ProductCategory;
  activeCount: number;
  stockQuantity: number;
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
  category: ProductCategory;
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
