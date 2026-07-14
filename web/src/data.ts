import {
  Firestore,
  collection,
  limit,
  onSnapshot,
  orderBy,
  query,
} from "firebase/firestore";
import { DashboardData, Product, ProductEvent, Source } from "./types";

type FirestoreTimestamp = { toDate: () => Date };

function toIso(value: unknown): string | undefined {
  if (!value) return undefined;
  if (typeof value === "string") return value;
  if (value instanceof Date) return value.toISOString();
  if (typeof value === "object" && "toDate" in value) {
    return (value as FirestoreTimestamp).toDate().toISOString();
  }
  return undefined;
}

export async function loadDemoData(): Promise<DashboardData> {
  const response = await fetch("/demo-data.json", { cache: "no-store" });
  if (!response.ok) throw new Error("無法載入本機預覽資料");
  return response.json() as Promise<DashboardData>;
}

export function subscribeDashboard(
  database: Firestore,
  onData: (data: DashboardData) => void,
  onError: (error: Error) => void,
) {
  let products: Product[] = [];
  let sources: Source[] = [];
  let events: ProductEvent[] = [];
  const ready = { products: false, sources: false, events: false };

  const emit = () => {
    if (!ready.products || !ready.sources || !ready.events) return;
    const timestamps = sources
      .map((source) => source.lastSyncAt)
      .filter((value): value is string => Boolean(value));
    onData({
      generatedAt: timestamps.sort().at(-1) ?? new Date().toISOString(),
      products,
      sources,
      events,
    });
  };

  const unsubscribeProducts = onSnapshot(
    collection(database, "products"),
    (snapshot) => {
      products = snapshot.docs.map((document) => {
        const data = document.data();
        return {
          id: document.id,
          sourceId: data.sourceId,
          sourceLabel: data.sourceLabel,
          productId: data.productId,
          name: data.name,
          url: data.url,
          prices: data.prices ?? [],
          currency: "JPY",
          active: data.active !== false,
          firstSeenAt: toIso(data.firstSeenAt),
          updatedAt: toIso(data.updatedAt),
        };
      });
      ready.products = true;
      emit();
    },
    onError,
  );

  const unsubscribeSources = onSnapshot(
    collection(database, "sources"),
    (snapshot) => {
      sources = snapshot.docs.map((document) => {
        const data = document.data();
        return {
          id: document.id,
          label: data.label,
          schedule: data.schedule,
          activeCount: data.activeCount ?? 0,
          status: data.status === "error" ? "error" : "ok",
          lastRunDate: data.lastRunDate ?? null,
          lastSyncAt: toIso(data.lastSyncAt),
        };
      });
      ready.sources = true;
      emit();
    },
    onError,
  );

  const eventsQuery = query(
    collection(database, "events"),
    orderBy("occurredAt", "desc"),
    limit(80),
  );
  const unsubscribeEvents = onSnapshot(
    eventsQuery,
    (snapshot) => {
      events = snapshot.docs.map((document) => {
        const data = document.data();
        return {
          id: document.id,
          type: data.type,
          productKey: data.productKey,
          productId: data.productId,
          productName: data.productName,
          sourceId: data.sourceId,
          sourceLabel: data.sourceLabel,
          url: data.url,
          oldPrices: data.oldPrices ?? [],
          newPrices: data.newPrices ?? [],
          occurredAt: toIso(data.occurredAt) ?? new Date().toISOString(),
        };
      });
      ready.events = true;
      emit();
    },
    onError,
  );

  return () => {
    unsubscribeProducts();
    unsubscribeSources();
    unsubscribeEvents();
  };
}
