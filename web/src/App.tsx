import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  ArrowDownRight,
  BellRing,
  Boxes,
  Check,
  ChevronDown,
  CircleDollarSign,
  Clock3,
  ExternalLink,
  Eye,
  Layers3,
  LogOut,
  PackageCheck,
  Radar,
  RefreshCw,
  Search,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  Store,
  Wifi,
  X,
} from "lucide-react";
import type { ReactNode } from "react";
import {
  User,
  browserLocalPersistence,
  getRedirectResult,
  onAuthStateChanged,
  setPersistence,
  signInWithPopup,
  signInWithRedirect,
  signOut,
} from "firebase/auth";
import {
  DISPLAY_NAME_MAX_LENGTH,
  hasDashboardAccess,
  loadDemoData,
  loadLocalDisplayNames,
  saveLocalDisplayNames,
  saveSourceDisplayName,
  subscribeDashboard,
} from "./data";
import { EVENT_LABELS, formatPrice, formatTime } from "./format";
import TrackedPages from "./TrackedPages";
import {
  auth,
  database,
  firebaseEnabled,
  googleProvider,
} from "./firebase";
import {
  DashboardData,
  EventType,
  Product,
  ProductCategory,
  ProductEvent,
} from "./types";

const EMPTY_DATA: DashboardData = {
  generatedAt: "",
  products: [],
  sources: [],
  events: [],
};

function isMobileDevice() {
  const userAgent = navigator.userAgent;
  return (
    /Android|iPhone|iPad|iPod/i.test(userAgent) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1)
  );
}

function isEmbeddedBrowser() {
  const userAgent = navigator.userAgent;
  return (
    /FBAN|FBAV|Instagram|Line\/|Telegram/i.test(userAgent) ||
    (/iPhone|iPad|iPod/i.test(userAgent) &&
      /AppleWebKit/i.test(userAgent) &&
      !/Safari/i.test(userAgent))
  );
}

function authErrorMessage(reason: unknown) {
  const code =
    typeof reason === "object" && reason !== null && "code" in reason
      ? String((reason as { code?: unknown }).code ?? "")
      : "";

  if (code === "auth/popup-closed-by-user" || code === "auth/cancelled-popup-request") {
    return "";
  }
  if (code === "auth/popup-blocked") {
    return "瀏覽器阻擋了登入視窗，請允許彈出式視窗後再試一次。";
  }
  if (code === "auth/web-storage-unsupported") {
    return "瀏覽器封鎖了登入所需的網站儲存空間，請關閉無痕模式或內容阻擋器後再試一次。";
  }
  if (code === "auth/network-request-failed") {
    return "無法連線到 Google 登入服務，請確認公司網路未封鎖 Google 或改用其他網路。";
  }
  if (code === "auth/unauthorized-domain") {
    return "目前網站網域尚未獲 Firebase 授權，請聯絡管理員。";
  }
  if (code === "auth/operation-not-allowed") {
    return "Firebase 尚未啟用 Google 登入，請聯絡管理員。";
  }
  if (code === "auth/operation-not-supported-in-this-environment") {
    return "此內建瀏覽器不支援 Google 登入，請改用 Safari 或 Chrome 開啟網站。";
  }

  const suffix = code ? `（${code}）` : "";
  return `Google 登入失敗${suffix}，請再試一次。`;
}

function isToday(value: string) {
  const date = new Date(value);
  const today = new Date();
  return date.toDateString() === today.toDateString();
}

function EventGlyph({ type }: { type: EventType }) {
  if (type === "new") return <Sparkles size={16} />;
  if (type === "price_changed") return <CircleDollarSign size={16} />;
  if (type === "restocked") return <RefreshCw size={16} />;
  return <X size={16} />;
}

function MetricCard({
  icon,
  label,
  value,
  note,
  tone,
}: {
  icon: ReactNode;
  label: string;
  value: string | number;
  note: string;
  tone: "green" | "amber" | "blue" | "violet";
}) {
  return (
    <article className={`metric-card metric-${tone}`}>
      <div className="metric-top">
        <span className="metric-icon">{icon}</span>
        <span className="metric-label">{label}</span>
      </div>
      <strong>{value}</strong>
      <span className="metric-note">{note}</span>
    </article>
  );
}

function LoginScreen({ error, onLogin }: { error: string; onLogin: () => void }) {
  return (
    <main className="login-shell">
      <section className="login-card">
        <div className="login-radar" aria-hidden="true">
          <span />
          <span />
          <span />
          <Radar size={42} />
        </div>
        <p className="eyebrow">PRIVATE MONITORING CONSOLE</p>
        <h1>Card Radar</h1>
        <p className="login-copy">
          集中查看各卡牌商店的新品、價格變化與監控狀態。
        </p>
        <button className="login-button" onClick={onLogin} type="button">
          <ShieldCheck size={19} />
          使用 Google 帳號登入
        </button>
        {error && <p className="form-error">{error}</p>}
        <p className="login-footnote">只有授權帳號能讀取監控資料</p>
      </section>
    </main>
  );
}

function AccountMenu({ user, onLogout }: { user: User; onLogout: () => void }) {
  return (
    <details className="account-menu">
      <summary className="avatar-button" aria-label="開啟我的帳戶選單">
        {user.photoURL ? (
          <img src={user.photoURL} alt="" />
        ) : (
          <span className="avatar-fallback">{user.email?.slice(0, 1).toUpperCase()}</span>
        )}
        <span>{user.displayName || user.email}</span>
        <ChevronDown size={15} />
      </summary>
      <div className="account-popover">
        <div className="account-identity">
          {user.photoURL ? (
            <img src={user.photoURL} alt="" />
          ) : (
            <span className="avatar-fallback">{user.email?.slice(0, 1).toUpperCase()}</span>
          )}
          <span>
            <strong>{user.displayName || "Google 帳戶"}</strong>
            <small>{user.email}</small>
          </span>
        </div>
        <button className="logout-button" onClick={onLogout} type="button">
          <LogOut size={16} />
          登出
        </button>
      </div>
    </details>
  );
}

function ProductRow({ product, sourceName }: { product: Product; sourceName: string }) {
  return (
    <article className="product-row">
      <div className="product-main">
        <span className="source-dot" aria-hidden="true" />
        <div>
          <a href={product.url} target="_blank" rel="noreferrer">
            {product.name || `商品 ${product.productId}`}
            <ExternalLink size={13} />
          </a>
          <span className="product-sub">
            <span className="mobile-source">{sourceName}</span>
            {product.qty != null && (
              <span className="stock-badge"><Boxes size={12} />在庫 {product.qty}</span>
            )}
          </span>
        </div>
      </div>
      <span className="source-name">{sourceName}</span>
      <strong className="price-value">{formatPrice(product.prices)}</strong>
      <span className={`availability ${product.active ? "active" : "inactive"}`}>
        {product.active ? "追蹤中" : "已下架"}
      </span>
    </article>
  );
}

function EventItem({ event, sourceName }: { event: ProductEvent; sourceName: string }) {
  return (
    <a className={`event-item event-${event.type}`} href={event.url} target="_blank" rel="noreferrer">
      <span className="event-icon">
        <EventGlyph type={event.type} />
      </span>
      <span className="event-copy">
        <span className="event-meta">
          <b>{EVENT_LABELS[event.type]}</b>
          <time>{formatTime(event.occurredAt, true)}</time>
        </span>
        <strong>{event.productName || `商品 ${event.productId}`}</strong>
        <span>{sourceName}</span>
        {event.type === "price_changed" && (
          <span className="price-change">
            {formatPrice(event.oldPrices)}
            <ArrowDownRight size={14} />
            <b>{formatPrice(event.newPrices)}</b>
          </span>
        )}
      </span>
    </a>
  );
}

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [authReady, setAuthReady] = useState(!firebaseEnabled);
  const [data, setData] = useState<DashboardData>(EMPTY_DATA);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [categoryFilter, setCategoryFilter] = useState<ProductCategory | "all">("all");
  const [statusFilter, setStatusFilter] = useState("active");
  const [sortOrder, setSortOrder] = useState("source");
  const [accessState, setAccessState] = useState<
    "idle" | "checking" | "authorized" | "denied"
  >(firebaseEnabled ? "idle" : "authorized");
  // 預覽模式沒有 Firestore 可寫，展示名稱改存在瀏覽器本機。
  const [localNames, setLocalNames] = useState<Record<string, string>>(() =>
    firebaseEnabled ? {} : loadLocalDisplayNames(),
  );

  useEffect(() => {
    if (!auth) return;
    getRedirectResult(auth).catch((reason) => {
      const message = authErrorMessage(reason);
      if (message) setError(message);
    });

    return onAuthStateChanged(auth, (nextUser) => {
      setUser(nextUser);
      setAccessState(nextUser ? "checking" : "idle");
      setAuthReady(true);
    });
  }, []);

  useEffect(() => {
    setLoading(true);
    setError("");

    if (!firebaseEnabled) {
      loadDemoData()
        .then(setData)
        .catch((reason: Error) => setError(reason.message))
        .finally(() => setLoading(false));
      return;
    }

    const firestore = database;
    if (!firestore || !user) {
      setLoading(false);
      return;
    }

    let cancelled = false;
    let unsubscribe: (() => void) | undefined;
    setAccessState("checking");

    hasDashboardAccess(firestore, user.uid)
      .then((hasAccess) => {
        if (cancelled) return;
        if (!hasAccess) {
          setAccessState("denied");
          setLoading(false);
          return;
        }

        setAccessState("authorized");
        unsubscribe = subscribeDashboard(
          firestore,
          (nextData) => {
            setData(nextData);
            setLoading(false);
          },
          () => {
            setError("即時資料載入失敗，請稍後再試。");
            setLoading(false);
          },
        );
      })
      .catch(() => {
        if (cancelled) return;
        setAccessState("denied");
        setError("無法確認此帳號的儀表板權限，請稍後再試。");
        setLoading(false);
      });

    return () => {
      cancelled = true;
      unsubscribe?.();
    };
  }, [user]);

  const handleLogin = async () => {
    if (!auth) return;
    setError("");

    if (isEmbeddedBrowser()) {
      setError("Telegram 等內建瀏覽器不支援 Google 登入，請改用 Safari 或 Chrome 開啟網站。");
      return;
    }

    try {
      await setPersistence(auth, browserLocalPersistence);
      if (isMobileDevice()) {
        await signInWithRedirect(auth, googleProvider);
        return;
      }
      await signInWithPopup(auth, googleProvider);
    } catch (reason) {
      const message = authErrorMessage(reason);
      if (message) setError(message);
    }
  };

  const handleLogout = async () => {
    if (!auth) return;
    setError("");
    try {
      await signOut(auth);
    } catch {
      setError("登出失敗，請稍後再試。");
    }
  };

  const sources = useMemo(
    () =>
      data.sources.map((source) => ({
        ...source,
        displayName: localNames[source.id] ?? source.displayName,
      })),
    [data.sources, localNames],
  );

  const sourceNames = useMemo(() => {
    const names = new Map<string, string>();
    sources.forEach((source) => names.set(source.id, source.displayName || source.label));
    return names;
  }, [sources]);

  /** 找不到來源文件時（例如已停售站台的舊事件）退回同步時記下的名稱。 */
  const sourceName = (sourceId: string, fallback: string) =>
    sourceNames.get(sourceId) ?? fallback;

  const handleRename = async (sourceId: string, displayName: string) => {
    const value = displayName.trim().slice(0, DISPLAY_NAME_MAX_LENGTH);
    if (firebaseEnabled && database) {
      await saveSourceDisplayName(database, sourceId, value);
      return;
    }
    const next = { ...localNames };
    if (value) {
      next[sourceId] = value;
    } else {
      delete next[sourceId];
    }
    saveLocalDisplayNames(next);
    setLocalNames(next);
  };

  const filteredProducts = useMemo(() => {
    const keyword = search.trim().toLocaleLowerCase();
    const filtered = data.products.filter((product) => {
      const matchesKeyword =
        !keyword ||
        product.name.toLocaleLowerCase().includes(keyword) ||
        product.productId.toLocaleLowerCase().includes(keyword);
      const matchesSource = sourceFilter === "all" || product.sourceId === sourceFilter;
      const matchesCategory =
        categoryFilter === "all" || product.category === categoryFilter;
      const matchesStatus =
        statusFilter === "all" ||
        (statusFilter === "active" ? product.active : !product.active);
      return matchesKeyword && matchesSource && matchesCategory && matchesStatus;
    });

    return filtered.sort((left, right) => {
      if (sortOrder === "name") return left.name.localeCompare(right.name, "zh-Hant");
      if (sortOrder === "price") {
        const leftPrice = left.prices[0] ?? Number.MAX_SAFE_INTEGER;
        const rightPrice = right.prices[0] ?? Number.MAX_SAFE_INTEGER;
        return leftPrice - rightPrice;
      }
      const leftSource = sourceNames.get(left.sourceId) ?? left.sourceLabel;
      const rightSource = sourceNames.get(right.sourceId) ?? right.sourceLabel;
      return (
        leftSource.localeCompare(rightSource, "zh-Hant") ||
        left.name.localeCompare(right.name, "zh-Hant")
      );
    });
  }, [
    data.products,
    search,
    sourceFilter,
    categoryFilter,
    statusFilter,
    sortOrder,
    sourceNames,
  ]);

  const visibleSources = useMemo(
    () =>
      categoryFilter === "all"
        ? sources
        : sources.filter((source) => source.category === categoryFilter),
    [sources, categoryFilter],
  );

  const categoryCounts = useMemo(
    () => ({
      all: data.products.length,
      product: data.products.filter((product) => product.category === "product").length,
      deck: data.products.filter((product) => product.category === "deck").length,
    }),
    [data.products],
  );

  const selectCategory = (category: ProductCategory | "all") => {
    setCategoryFilter(category);
    setSourceFilter("all");
  };

  if (!authReady) {
    return <main className="loading-screen"><RefreshCw className="spin" />正在確認登入狀態</main>;
  }

  if (firebaseEnabled && !user) {
    return <LoginScreen error={error} onLogin={handleLogin} />;
  }

  if (firebaseEnabled && user && accessState === "checking") {
    return <main className="loading-screen"><RefreshCw className="spin" />正在確認帳號權限</main>;
  }

  if (firebaseEnabled && user && accessState === "denied") {
    return (
      <main className="login-shell">
        <section className="login-card compact">
          <ShieldCheck size={38} />
          <h1>此帳號未獲授權</h1>
          <p>{user?.email}</p>
          {error && <p className="form-error">{error}</p>}
          <button className="login-button" onClick={handleLogout} type="button">
            改用其他帳號
          </button>
        </section>
      </main>
    );
  }

  const activeProducts = data.products.filter((product) => product.active).length;
  const trackedStock = data.products.reduce(
    (sum, product) => (product.active && product.qty != null ? sum + product.qty : sum),
    0,
  );
  const namedProducts = data.products.filter((product) => product.active && product.name).length;
  const dataCompleteness = activeProducts ? Math.round((namedProducts / activeProducts) * 100) : 100;
  const todayEvents = data.events.filter((event) => isToday(event.occurredAt));
  const healthySources = sources.filter((source) => source.status === "ok").length;

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="回到頁面頂端">
          <span className="brand-mark"><Radar size={23} /></span>
          <span><b>Card Radar</b><small>Monitoring console</small></span>
        </a>
        <div className="topbar-status">
          {!firebaseEnabled && <span className="demo-pill"><Eye size={14} />預覽模式</span>}
          <span className="live-pill"><Wifi size={14} />即時連線</span>
          {user && <AccountMenu user={user} onLogout={handleLogout} />}
        </div>
      </header>

      <main id="top" className="dashboard">
        <section className="hero">
          <div>
            <p className="eyebrow">LIVE INVENTORY INTELLIGENCE</p>
            <h1>商品監控總覽</h1>
            <p>跨站追蹤新品、價格與庫存變化，一眼掌握最新動態。</p>
          </div>
          <div className="sync-card">
            <span className="pulse-dot" />
            <div><small>最後資料同步</small><strong>{formatTime(data.generatedAt, true)}</strong></div>
            <Clock3 size={18} />
          </div>
        </section>

        {error && <div className="error-banner"><ShieldCheck size={18} />{error}</div>}

        <section className="metrics-grid" aria-label="監控摘要">
          <MetricCard icon={<ShoppingBag size={20} />} label="追蹤中商品" value={activeProducts} note={`共 ${data.products.length} 筆商品紀錄`} tone="green" />
          <MetricCard icon={<Boxes size={20} />} label="追蹤庫存總數" value={trackedStock.toLocaleString("ja-JP")} note="已回報庫存數的商品加總" tone="violet" />
          <MetricCard icon={<BellRing size={20} />} label="今日異動" value={todayEvents.length} note="新品、價格與庫存事件" tone="amber" />
          <MetricCard icon={<Store size={20} />} label="站台狀態" value={`${healthySources}/${sources.length}`} note="目前正常同步來源" tone="blue" />
          <MetricCard icon={<PackageCheck size={20} />} label="資料完整度" value={`${dataCompleteness}%`} note="追蹤商品名稱解析成功率" tone="green" />
        </section>

        <section className="source-strip" aria-label="來源狀態">
          {visibleSources.map((source) => (
            <button
              key={source.id}
              className={sourceFilter === source.id ? "source-chip selected" : "source-chip"}
              onClick={() => setSourceFilter(sourceFilter === source.id ? "all" : source.id)}
              type="button"
            >
              <span className={source.status === "ok" ? "health-dot" : "health-dot error"} />
              <span><b>{source.displayName || source.label}</b><small>{source.activeCount} 件{source.stockQuantity ? ` · 在庫 ${source.stockQuantity}` : ""} · {source.schedule}</small></span>
              <Check size={14} />
            </button>
          ))}
        </section>

        <div className="content-grid">
          <section className="panel products-panel">
            <div className="panel-heading">
              <div><p className="section-kicker">CATALOG</p><h2>追蹤商品</h2></div>
              <span className="result-count">{filteredProducts.length} 件</span>
            </div>
            <div className="catalog-tabs" role="group" aria-label="商品分類">
              <button
                className={categoryFilter === "all" ? "selected" : ""}
                onClick={() => selectCategory("all")}
                type="button"
              >
                <ShoppingBag size={15} />全部商品<span>{categoryCounts.all}</span>
              </button>
              <button
                className={categoryFilter === "product" ? "selected" : ""}
                onClick={() => selectCategory("product")}
                type="button"
              >
                <PackageCheck size={15} />一般商品<span>{categoryCounts.product}</span>
              </button>
              <button
                className={categoryFilter === "deck" ? "selected" : ""}
                onClick={() => selectCategory("deck")}
                type="button"
              >
                <Layers3 size={15} />Deck 販售<span>{categoryCounts.deck}</span>
              </button>
            </div>
            <div className="filters">
              <label className="search-box">
                <Search size={17} />
                <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜尋商品名稱或編號" />
                {search && <button onClick={() => setSearch("")} type="button" aria-label="清除搜尋"><X size={15} /></button>}
              </label>
              <label className="select-box">
                <select value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value)} aria-label="選擇商店">
                  <option value="all">全部商店</option>
                  {visibleSources.map((source) => (
                    <option key={source.id} value={source.id}>
                      {source.displayName || source.label}
                    </option>
                  ))}
                </select>
                <ChevronDown size={15} />
              </label>
              <label className="select-box compact-select">
                <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} aria-label="選擇狀態">
                  <option value="active">追蹤中</option>
                  <option value="inactive">已下架</option>
                  <option value="all">全部狀態</option>
                </select>
                <ChevronDown size={15} />
              </label>
              <label className="select-box compact-select">
                <select value={sortOrder} onChange={(event) => setSortOrder(event.target.value)} aria-label="排序方式">
                  <option value="source">依商店</option>
                  <option value="name">依名稱</option>
                  <option value="price">依價格</option>
                </select>
                <ChevronDown size={15} />
              </label>
            </div>
            <div className="product-table">
              <div className="table-head"><span>商品</span><span>來源</span><span>目前價格</span><span>狀態</span></div>
              <div className="table-body">
                {loading ? (
                  <div className="empty-state"><RefreshCw className="spin" /><b>正在載入監控資料</b></div>
                ) : filteredProducts.length ? (
                  filteredProducts.map((product) => (
                    <ProductRow
                      key={product.id}
                      product={product}
                      sourceName={sourceName(product.sourceId, product.sourceLabel)}
                    />
                  ))
                ) : (
                  <div className="empty-state"><Search /><b>沒有符合條件的商品</b><span>試著調整搜尋或篩選條件</span></div>
                )}
              </div>
            </div>
          </section>

          <aside className="panel activity-panel">
            <div className="panel-heading">
              <div><p className="section-kicker">ACTIVITY</p><h2>最近異動</h2></div>
              <Activity size={19} />
            </div>
            <div className="event-list">
              {data.events.length ? (
                data.events.slice(0, 20).map((event) => (
                  <EventItem
                    key={event.id}
                    event={event}
                    sourceName={sourceName(event.sourceId, event.sourceLabel)}
                  />
                ))
              ) : (
                <div className="activity-empty">
                  <span><PackageCheck size={24} /></span>
                  <b>基準資料已就緒</b>
                  <p>Firebase 同步後，新品、價格和庫存異動會出現在這裡。</p>
                </div>
              )}
            </div>
            <div className="activity-footer"><span className="pulse-dot" />持續監聽 Firestore 更新</div>
          </aside>
        </div>

        <TrackedPages sources={sources} events={data.events} onRename={handleRename} />
      </main>

      <footer>
        <span><Radar size={15} />Card Radar</span>
        <span>由 GitHub Actions 與 Firebase 驅動</span>
      </footer>
    </div>
  );
}
