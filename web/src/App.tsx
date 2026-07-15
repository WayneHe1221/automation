import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  ArrowDownRight,
  BellRing,
  Check,
  ChevronDown,
  CircleDollarSign,
  Clock3,
  ExternalLink,
  Eye,
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
  getRedirectResult,
  onAuthStateChanged,
  signInWithPopup,
  signInWithRedirect,
  signOut,
} from "firebase/auth";
import { loadDemoData, subscribeDashboard } from "./data";
import {
  auth,
  database,
  firebaseEnabled,
  googleProvider,
} from "./firebase";
import { DashboardData, EventType, Product, ProductEvent } from "./types";

const EMPTY_DATA: DashboardData = {
  generatedAt: "",
  products: [],
  sources: [],
  events: [],
};

const EVENT_LABELS: Record<EventType, string> = {
  new: "新品上架",
  price_changed: "價格異動",
  removed: "售完／下架",
  restocked: "重新上架",
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

function formatPrice(prices: number[]) {
  if (!prices.length) return "—";
  return prices.map((price) => `¥${price.toLocaleString("ja-JP")}`).join(" / ");
}

function formatTime(value?: string, withDate = false) {
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

function ProductRow({ product }: { product: Product }) {
  return (
    <article className="product-row">
      <div className="product-main">
        <span className="source-dot" aria-hidden="true" />
        <div>
          <a href={product.url} target="_blank" rel="noreferrer">
            {product.name || `商品 ${product.productId}`}
            <ExternalLink size={13} />
          </a>
          <span className="mobile-source">{product.sourceLabel}</span>
        </div>
      </div>
      <span className="source-name">{product.sourceLabel}</span>
      <strong className="price-value">{formatPrice(product.prices)}</strong>
      <span className={`availability ${product.active ? "active" : "inactive"}`}>
        {product.active ? "追蹤中" : "已下架"}
      </span>
    </article>
  );
}

function EventItem({ event }: { event: ProductEvent }) {
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
        <span>{event.sourceLabel}</span>
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
  const [statusFilter, setStatusFilter] = useState("active");
  const [sortOrder, setSortOrder] = useState("source");
  const allowedEmail = import.meta.env.VITE_ALLOWED_EMAIL?.trim().toLowerCase();
  const isAllowedUser = !allowedEmail || user?.email?.toLowerCase() === allowedEmail;

  useEffect(() => {
    if (!auth) return;
    getRedirectResult(auth).catch((reason) => {
      const message = authErrorMessage(reason);
      if (message) setError(message);
    });

    return onAuthStateChanged(auth, (nextUser) => {
      setUser(nextUser);
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

    if (!database || !user || !isAllowedUser) {
      setLoading(false);
      return;
    }

    return subscribeDashboard(
      database,
      (nextData) => {
        setData(nextData);
        setLoading(false);
      },
      (reason) => {
        setError(
          reason.message.includes("permission")
            ? "此帳號尚未加入 Firestore 管理員清單。"
            : "即時資料載入失敗，請稍後再試。",
        );
        setLoading(false);
      },
    );
  }, [user, isAllowedUser]);

  const handleLogin = async () => {
    if (!auth) return;
    setError("");

    if (isEmbeddedBrowser()) {
      setError("Telegram 等內建瀏覽器不支援 Google 登入，請改用 Safari 或 Chrome 開啟網站。");
      return;
    }

    try {
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

  const filteredProducts = useMemo(() => {
    const keyword = search.trim().toLocaleLowerCase();
    const filtered = data.products.filter((product) => {
      const matchesKeyword =
        !keyword ||
        product.name.toLocaleLowerCase().includes(keyword) ||
        product.productId.toLocaleLowerCase().includes(keyword);
      const matchesSource = sourceFilter === "all" || product.sourceId === sourceFilter;
      const matchesStatus =
        statusFilter === "all" ||
        (statusFilter === "active" ? product.active : !product.active);
      return matchesKeyword && matchesSource && matchesStatus;
    });

    return filtered.sort((left, right) => {
      if (sortOrder === "name") return left.name.localeCompare(right.name, "zh-Hant");
      if (sortOrder === "price") {
        const leftPrice = left.prices[0] ?? Number.MAX_SAFE_INTEGER;
        const rightPrice = right.prices[0] ?? Number.MAX_SAFE_INTEGER;
        return leftPrice - rightPrice;
      }
      return (
        left.sourceLabel.localeCompare(right.sourceLabel, "zh-Hant") ||
        left.name.localeCompare(right.name, "zh-Hant")
      );
    });
  }, [data.products, search, sourceFilter, statusFilter, sortOrder]);

  if (!authReady) {
    return <main className="loading-screen"><RefreshCw className="spin" />正在確認登入狀態</main>;
  }

  if (firebaseEnabled && !user) {
    return <LoginScreen error={error} onLogin={handleLogin} />;
  }

  if (firebaseEnabled && !isAllowedUser) {
    return (
      <main className="login-shell">
        <section className="login-card compact">
          <ShieldCheck size={38} />
          <h1>此帳號未獲授權</h1>
          <p>{user?.email}</p>
          <button className="login-button" onClick={() => auth && signOut(auth)} type="button">
            改用其他帳號
          </button>
        </section>
      </main>
    );
  }

  const activeProducts = data.products.filter((product) => product.active).length;
  const namedProducts = data.products.filter((product) => product.active && product.name).length;
  const dataCompleteness = activeProducts ? Math.round((namedProducts / activeProducts) * 100) : 100;
  const todayEvents = data.events.filter((event) => isToday(event.occurredAt));
  const healthySources = data.sources.filter((source) => source.status === "ok").length;

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
          {user && (
            <button className="avatar-button" onClick={() => auth && signOut(auth)} type="button">
              {user.photoURL ? <img src={user.photoURL} alt="" /> : user.email?.slice(0, 1).toUpperCase()}
              <span>{user.displayName || user.email}</span>
              <LogOut size={15} />
            </button>
          )}
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
          <MetricCard icon={<BellRing size={20} />} label="今日異動" value={todayEvents.length} note="新品、價格與庫存事件" tone="amber" />
          <MetricCard icon={<Store size={20} />} label="站台狀態" value={`${healthySources}/${data.sources.length}`} note="目前正常同步來源" tone="blue" />
          <MetricCard icon={<PackageCheck size={20} />} label="資料完整度" value={`${dataCompleteness}%`} note="追蹤商品名稱解析成功率" tone="violet" />
        </section>

        <section className="source-strip" aria-label="來源狀態">
          {data.sources.map((source) => (
            <button
              key={source.id}
              className={sourceFilter === source.id ? "source-chip selected" : "source-chip"}
              onClick={() => setSourceFilter(sourceFilter === source.id ? "all" : source.id)}
              type="button"
            >
              <span className={source.status === "ok" ? "health-dot" : "health-dot error"} />
              <span><b>{source.label}</b><small>{source.activeCount} 件 · {source.schedule}</small></span>
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
            <div className="filters">
              <label className="search-box">
                <Search size={17} />
                <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜尋商品名稱或編號" />
                {search && <button onClick={() => setSearch("")} type="button" aria-label="清除搜尋"><X size={15} /></button>}
              </label>
              <label className="select-box">
                <select value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value)} aria-label="選擇商店">
                  <option value="all">全部商店</option>
                  {data.sources.map((source) => <option key={source.id} value={source.id}>{source.label}</option>)}
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
                  filteredProducts.map((product) => <ProductRow key={product.id} product={product} />)
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
                data.events.slice(0, 20).map((event) => <EventItem key={event.id} event={event} />)
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
      </main>

      <footer>
        <span><Radar size={15} />Card Radar</span>
        <span>由 GitHub Actions 與 Firebase 驅動</span>
      </footer>
    </div>
  );
}
