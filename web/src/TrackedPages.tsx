import { useEffect, useState } from "react";
import {
  ArrowDownRight,
  Boxes,
  Check,
  ExternalLink,
  Link2,
  Pencil,
  RotateCcw,
  X,
} from "lucide-react";
import { DISPLAY_NAME_MAX_LENGTH } from "./data";
import { EVENT_LABELS, formatPrice, formatTime, shortenUrl } from "./format";
import { EventType, ProductEvent, Source } from "./types";

const HISTORY_LIMIT = 12;
const EVENT_ORDER: EventType[] = ["new", "price_changed", "restocked", "removed"];

function HistoryEntry({ event }: { event: ProductEvent }) {
  return (
    <li className={`history-entry history-${event.type}`}>
      <time>{formatTime(event.occurredAt, true)}</time>
      <span className="history-type">{EVENT_LABELS[event.type]}</span>
      <a href={event.url} target="_blank" rel="noreferrer">
        {event.productName || `商品 ${event.productId}`}
      </a>
      {event.type === "price_changed" && (
        <span className="history-price">
          {formatPrice(event.oldPrices)}
          <ArrowDownRight size={12} />
          <b>{formatPrice(event.newPrices)}</b>
        </span>
      )}
    </li>
  );
}

function PageRow({
  source,
  events,
  onRename,
}: {
  source: Source;
  events: ProductEvent[];
  onRename: (sourceId: string, displayName: string) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(source.displayName ?? source.label);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!editing) setDraft(source.displayName ?? source.label);
  }, [editing, source.displayName, source.label]);

  const submit = async (nextName: string) => {
    // 清空或輸入與原始名稱相同時，視為取消自訂。
    const value = nextName.trim() === source.label ? "" : nextName;
    setSaving(true);
    setError("");
    try {
      await onRename(source.id, value);
      setEditing(false);
    } catch {
      setError("名稱儲存失敗，請稍後再試。");
    } finally {
      setSaving(false);
    }
  };

  const counts = EVENT_ORDER.map((type) => ({
    type,
    total: events.filter((event) => event.type === type).length,
  })).filter((entry) => entry.total);

  return (
    <article className="page-row">
      <div className="page-main">
        {editing ? (
          <form
            className="rename-form"
            onSubmit={(submitEvent) => {
              submitEvent.preventDefault();
              void submit(draft);
            }}
          >
            <input
              autoFocus
              value={draft}
              maxLength={DISPLAY_NAME_MAX_LENGTH}
              onChange={(changeEvent) => setDraft(changeEvent.target.value)}
              onKeyDown={(keyEvent) => {
                if (keyEvent.key === "Escape") setEditing(false);
              }}
              aria-label={`${source.label} 的展示名稱`}
              placeholder={source.label}
            />
            <button type="submit" className="rename-save" disabled={saving} aria-label="儲存名稱">
              <Check size={15} />
            </button>
            <button
              type="button"
              className="rename-cancel"
              onClick={() => setEditing(false)}
              aria-label="取消編輯"
            >
              <X size={15} />
            </button>
          </form>
        ) : (
          <div className="page-title">
            <strong>{source.displayName || source.label}</strong>
            {source.displayName && <span className="renamed-badge">自訂名稱</span>}
            <button
              type="button"
              className="icon-button"
              onClick={() => setEditing(true)}
              aria-label={`編輯 ${source.displayName || source.label} 的展示名稱`}
              title="編輯展示名稱"
            >
              <Pencil size={14} />
            </button>
            {source.displayName && (
              <button
                type="button"
                className="icon-button"
                onClick={() => void submit("")}
                disabled={saving}
                aria-label={`還原 ${source.label} 的原始名稱`}
                title={`還原原始名稱：${source.label}`}
              >
                <RotateCcw size={14} />
              </button>
            )}
          </div>
        )}
        {source.pageUrl ? (
          <a className="page-url" href={source.pageUrl} target="_blank" rel="noreferrer">
            <Link2 size={13} />
            {shortenUrl(source.pageUrl)}
            <ExternalLink size={12} />
          </a>
        ) : (
          <span className="page-url muted">尚未提供原始連結</span>
        )}
        {source.displayName && <span className="page-origin">原始名稱：{source.label}</span>}
        {error && <span className="page-error">{error}</span>}
      </div>

      <div className="page-meta">
        <span>{source.category === "deck" ? "Deck 販售" : "一般商品"}</span>
        <span>{source.activeCount} 件</span>
        {source.stockQuantity ? (
          <span>
            <Boxes size={12} />在庫 {source.stockQuantity}
          </span>
        ) : null}
        <span>{source.schedule}</span>
        {source.lastRunDate && <span>執行 {source.lastRunDate}</span>}
        <span>{source.lastSyncAt ? `同步 ${formatTime(source.lastSyncAt, true)}` : "尚未同步"}</span>
      </div>

      <details className="page-history">
        <summary>
          <span className="history-counts">
            {counts.length ? (
              counts.map((entry) => (
                <span key={entry.type} className={`history-count history-${entry.type}`}>
                  {EVENT_LABELS[entry.type]} {entry.total}
                </span>
              ))
            ) : (
              <span className="history-count empty">近期無異動</span>
            )}
          </span>
          <span className="history-toggle">異動歷程</span>
        </summary>
        {events.length ? (
          <ul className="history-list">
            {events.slice(0, HISTORY_LIMIT).map((event) => (
              <HistoryEntry key={event.id} event={event} />
            ))}
            {events.length > HISTORY_LIMIT && (
              <li className="history-more">…等共 {events.length} 筆</li>
            )}
          </ul>
        ) : (
          <p className="history-empty">最近的同步紀錄中，這個網頁沒有商品異動。</p>
        )}
      </details>
    </article>
  );
}

export default function TrackedPages({
  sources,
  events,
  onRename,
}: {
  sources: Source[];
  events: ProductEvent[];
  onRename: (sourceId: string, displayName: string) => Promise<void>;
}) {
  // 與商品分頁一致：一般商品在前、Deck 販售在後，同類別再依顯示名稱排序。
  const ordered = [...sources].sort(
    (left, right) =>
      Number(left.category === "deck") - Number(right.category === "deck") ||
      (left.displayName || left.label).localeCompare(right.displayName || right.label, "zh-Hant"),
  );

  return (
    <section className="panel pages-panel" id="tracked-pages">
      <div className="panel-heading">
        <div>
          <p className="section-kicker">TRACKED PAGES</p>
          <h2>追蹤網頁</h2>
        </div>
        <span className="result-count">{sources.length} 個</span>
      </div>
      <p className="pages-note">
        列出目前監看的列表頁原始連結與各自的異動歷程；展示名稱可自行命名，只影響儀表板顯示。
      </p>
      <div className="page-list">
        {ordered.length ? (
          ordered.map((source) => (
            <PageRow
              key={source.id}
              source={source}
              events={events.filter((event) => event.sourceId === source.id)}
              onRename={onRename}
            />
          ))
        ) : (
          <div className="empty-state">
            <Link2 />
            <b>尚無追蹤網頁</b>
            <span>等待第一次同步完成後就會出現。</span>
          </div>
        )}
      </div>
    </section>
  );
}
