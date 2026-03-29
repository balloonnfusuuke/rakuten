"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

const API_BASE =
  typeof window !== "undefined"
    ? process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"
    : "";

type Position = {
  id: number | null;
  symbol: string;
  status: string;
  entry_price: number | null;
  target_price: number | null;
  stop_price: number | null;
  peak_price: number | null;
  shares: number | null;
  screened_date: string | null;
  entry_date: string | null;
  exit_reason: string | null;
  pnl: number | null;
};

type Summary = {
  watching: number;
  holding: number;
  closed: number;
  exposure_usd: number;
};

type MonitorStatus = {
  running: boolean;
  pid: number | null;
  demo?: boolean | null;
};

type QuoteInfo = {
  price: number | null;
  change_pct: number | null;
  market_state: string | null;
  currency: string | null;
  name: string | null;
  error?: string;
};

type QuotesPayload = {
  quotes: Record<string, QuoteInfo>;
  source: string;
  as_of: string | null;
  error: string | null;
  warning?: string | null;
  excel_path?: string | null;
  file_age_sec?: number | null;
};

type MarketSource = {
  source: string;
  excel_path_configured: boolean;
  excel_resolved_path: string | null;
  excel_exists: boolean;
  excel_mtime_iso: string | null;
  file_age_sec: number | null;
  last_read_error: string | null;
};

function formatPrice(
  price: number | null | undefined,
  currency: string | null | undefined,
): string {
  if (price == null || Number.isNaN(price)) return "—";
  const cur = (currency || "USD").toUpperCase();
  if (cur === "JPY")
    return `¥${price.toLocaleString("ja-JP", { maximumFractionDigits: 0 })}`;
  return `$${price.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function formatSignedPnl(
  amount: number | null,
  currency: string | null | undefined,
): string {
  if (amount == null || Number.isNaN(amount)) return "—";
  const cur = (currency || "USD").toUpperCase();
  const sign = amount >= 0 ? "+" : "";
  if (cur === "JPY")
    return `${sign}¥${Math.round(amount).toLocaleString("ja-JP")}`;
  return `${sign}$${amount.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function Section({
  step,
  title,
  description,
  children,
}: {
  step: string;
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mb-8 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <header className="mb-5 flex flex-col gap-3 border-b border-slate-100 pb-4 sm:flex-row sm:items-start sm:gap-4">
        <span
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-base font-bold text-white shadow"
          aria-hidden
        >
          {step}
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-lg font-bold tracking-tight text-slate-900 sm:text-xl">
            {title}
          </h2>
          <p className="mt-1.5 text-sm leading-relaxed text-slate-600">
            {description}
          </p>
        </div>
      </header>
      {children}
    </section>
  );
}

function Th({
  children,
  hint,
}: {
  children: React.ReactNode;
  hint: string;
}) {
  return (
    <th
      scope="col"
      className="whitespace-nowrap px-3 py-3 text-left text-xs font-bold uppercase tracking-wide text-slate-500"
      title={hint}
    >
      <span className="border-b border-dotted border-slate-300">{children}</span>
    </th>
  );
}

function statusLabel(s: string) {
  if (s === "WATCHING") return "ウォッチ（監視リストのみ）";
  if (s === "HOLDING") return "保有中（売買ルール対象）";
  if (s === "CLOSED") return "決済済み";
  return s;
}

export function DashboardClient() {
  const [prodApiMisconfigured, setProdApiMisconfigured] = useState(false);
  const [apiOk, setApiOk] = useState<boolean | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [mon, setMon] = useState<MonitorStatus | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [quotes, setQuotes] = useState<QuotesPayload | null>(null);
  const [marketSource, setMarketSource] = useState<MarketSource | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [symbolsInput, setSymbolsInput] = useState("AAPL, MSFT");
  const [promote, setPromote] = useState({
    symbol: "",
    entry: "",
    shares: "10",
  });

  const showToast = (msg: string) => {
    setToast(msg);
    window.setTimeout(() => setToast(null), 4500);
  };

  const api = useCallback(async (path: string, init?: RequestInit) => {
    const res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers || {}),
      },
    });
    return res;
  }, []);

  const refreshData = useCallback(async () => {
    try {
      const h = await api("/health");
      setApiOk(h.ok);
      if (!h.ok) return;
      const [posRes, sumRes, stRes, logRes, srcRes] = await Promise.all([
        api("/positions"),
        api("/api/summary"),
        api("/api/monitor/status"),
        api("/api/logs?limit=150"),
        api("/api/market/source"),
      ]);
      if (srcRes.ok) setMarketSource(await srcRes.json());
      let posList: Position[] = [];
      if (posRes.ok) {
        posList = await posRes.json();
        setPositions(posList);
      }
      if (sumRes.ok) setSummary(await sumRes.json());
      if (stRes.ok) setMon(await stRes.json());
      if (logRes.ok) {
        const j = await logRes.json();
        setLogs(j.lines || []);
      }
      const openSyms = Array.from(
        new Set(
          posList
            .filter((r) => r.status !== "CLOSED")
            .map((r) => r.symbol.trim().toUpperCase()),
        ),
      );
      if (openSyms.length) {
        const q = await api(
          `/api/quotes?symbols=${encodeURIComponent(openSyms.join(","))}`,
        );
        if (q.ok) setQuotes(await q.json());
        else setQuotes(null);
      } else {
        setQuotes(null);
      }
    } catch {
      setApiOk(false);
    }
  }, [api]);

  useEffect(() => {
    const url = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
    const host = window.location.hostname;
    const isLocal = host === "localhost" || host === "127.0.0.1";
    const pointsToLocal =
      url.includes("127.0.0.1") || url.includes("localhost");
    setProdApiMisconfigured(!isLocal && pointsToLocal);
  }, []);

  useEffect(() => {
    refreshData();
    const t = window.setInterval(refreshData, 5000);
    return () => window.clearInterval(t);
  }, [refreshData]);

  const runAction = async (
    label: string,
    fn: () => Promise<Response>,
    successMsg?: string,
  ) => {
    setBusy(label);
    try {
      const res = await fn();
      const j = (await res.json().catch(() => ({}))) as Record<string, unknown>;
      const detailErr = () => {
        const d = j.detail;
        if (typeof d === "string") return d;
        if (Array.isArray(d))
          return d
            .map((x: { msg?: string }) => x.msg)
            .filter(Boolean)
            .join(" / ");
        return null;
      };
      if (!res.ok) {
        showToast(
          detailErr() ||
            (typeof j.message === "string" ? j.message : null) ||
            `${label} に失敗しました (${res.status})`,
        );
      } else if (j.ok === false && typeof j.message === "string") {
        showToast(j.message);
        await refreshData();
      } else {
        showToast(
          successMsg ||
            (typeof j.message === "string" ? j.message : null) ||
            `${label} 完了`,
        );
        await refreshData();
      }
    } catch (e) {
      showToast(e instanceof Error ? e.message : "通信エラー");
    } finally {
      setBusy(null);
    }
  };

  const open = useMemo(
    () => positions.filter((r) => r.status !== "CLOSED"),
    [positions],
  );
  const closed = useMemo(
    () => positions.filter((r) => r.status === "CLOSED").slice(0, 30),
    [positions],
  );

  const asOfLocal = useMemo(() => {
    if (!quotes?.as_of) return null;
    try {
      return new Date(quotes.as_of).toLocaleString("ja-JP");
    } catch {
      return quotes.as_of;
    }
  }, [quotes?.as_of]);

  return (
    <div className="mx-auto min-h-screen max-w-6xl px-3 pb-16 pt-6 sm:px-5">
      {prodApiMisconfigured && (
        <div
          role="alert"
          className="mb-6 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-950"
        >
          <strong className="font-semibold">API の URL が未設定です。</strong>
          本番サイトからは{" "}
          <code className="rounded bg-amber-100/80 px-1 font-mono">http://127.0.0.1:8000</code>{" "}
          に届きません。Vercel の環境変数{" "}
          <code className="rounded bg-amber-100/80 px-1 font-mono">
            NEXT_PUBLIC_API_URL
          </code>{" "}
          に、公開中の FastAPI の URL を設定して再デプロイしてください。
        </div>
      )}
      {toast && (
        <div
          role="status"
          className="fixed bottom-5 left-1/2 z-50 max-w-[min(100%,28rem)] -translate-x-1/2 rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 text-center text-sm text-white shadow-lg"
        >
          {toast}
        </div>
      )}

      {/* ページタイトル */}
      <header className="mb-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-xs font-semibold text-indigo-600">
              ConnorsRSI(2) コントロールパネル
            </p>
            <h1 className="mt-1 text-2xl font-bold text-slate-900 sm:text-3xl">
              株のウォッチ・保有・監視をまとめて操作
            </h1>
            <p className="mt-2 max-w-2xl text-sm text-slate-600">
              下のセクションは<strong>上から順に</strong>読むと流れが分かります。
              {marketSource?.source === "excel" ? (
                <>
                  株価は <strong>config.yaml の Excel パス</strong>
                  （MarketSpeed の記帳保存ファイルなど）を数秒ごとに読みます。
                  ファイルを Excel で開きっぱなしにすると保存・読取に失敗することがあります。
                </>
              ) : (
                <>
                  株価は主に <strong>yfinance（遅延）</strong> です。
                  即時性が必要なときは <code className="rounded bg-slate-100 px-1">market_data.source: excel</code>{" "}
                  で MarketSpeed の Excel に切り替えてください。
                </>
              )}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-sm font-medium ${
                apiOk
                  ? "bg-emerald-100 text-emerald-900"
                  : "bg-rose-100 text-rose-900"
              }`}
            >
              <span
                className={`h-2 w-2 rounded-full ${apiOk ? "bg-emerald-500" : "bg-rose-500"}`}
              />
              API {apiOk ? "接続OK" : "未接続"}
            </span>
            <span
              className={`inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-sm font-medium ${
                mon?.running
                  ? "bg-amber-100 text-amber-900"
                  : "bg-slate-100 text-slate-700"
              }`}
            >
              監視プロセス {mon?.running ? "動作中" : "停止中"}
            </span>
            <a
              className="btn-secondary !py-2 !text-xs"
              href={`${API_BASE}/docs`}
              target="_blank"
              rel="noreferrer"
            >
              API ドキュメント
            </a>
          </div>
        </div>

        {/* 操作の流れ（目次） */}
        <ol className="mt-5 grid gap-2 rounded-xl bg-slate-50 p-4 text-sm text-slate-700 sm:grid-cols-2 lg:grid-cols-4">
          <li>
            <span className="font-bold text-indigo-600">①</span> 接続確認（API
            緑）
          </li>
          <li>
            <span className="font-bold text-indigo-600">②</span>{" "}
            銘柄をウォッチに登録
          </li>
          <li>
            <span className="font-bold text-indigo-600">③</span> 必要なら保有化・デモ
          </li>
          <li>
            <span className="font-bold text-indigo-600">④</span>{" "}
            一覧で株価・ルールを確認
          </li>
        </ol>
      </header>

      {marketSource?.source === "excel" && (
        <div
          className="mb-6 rounded-2xl border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm text-indigo-950 shadow-sm"
          role="region"
          aria-label="Excel 株価モード"
        >
          <p className="font-bold">株価ソース: MarketSpeed / Excel</p>
          <p className="mt-1 break-all text-xs sm:text-sm">
            参照ファイル:{" "}
            <code className="rounded bg-white/80 px-1 py-0.5">
              {marketSource.excel_resolved_path || "（パス未解決）"}
            </code>
            {marketSource.excel_exists ? "（見つかりました）" : "（ファイルがありません）"}
            {marketSource.file_age_sec != null && (
              <span className="ml-2 text-indigo-800">
                最終更新から約 {Math.round(marketSource.file_age_sec)} 秒前
              </span>
            )}
          </p>
          {marketSource.last_read_error && (
            <p className="mt-2 text-rose-700">
              読み込みエラー: {marketSource.last_read_error}
            </p>
          )}
        </div>
      )}

      {/* ① 状況の数字 */}
      <Section
        step="①"
        title="いまの件数と投資額（サマリー）"
        description="ウォッチは「気になる銘柄リスト」、保有は「ルールで監視・売買の対象」。エクスポージャーは保有のエントリー価格×株数の合計（参考）です。"
      >
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[
            {
              k: "ウォッチ中",
              v: summary?.watching ?? "—",
              sub: "まだ買っていない候補",
            },
            {
              k: "保有中",
              v: summary?.holding ?? "—",
              sub: "ポジションあり",
            },
            {
              k: "決済済み",
              v: summary?.closed ?? "—",
              sub: "過去にクローズした件数",
            },
            {
              k: "エクスポージャー",
              v:
                summary != null
                  ? `$${summary.exposure_usd.toLocaleString()}`
                  : "—",
              sub: "保有の合計元本（USD）",
            },
          ].map((c) => (
            <div
              key={c.k}
              className="rounded-xl border border-slate-200 bg-slate-50/80 p-4"
            >
              <p className="text-xs font-bold text-slate-500">{c.k}</p>
              <p className="tabular-nums mt-1 text-2xl font-bold text-slate-900">
                {c.v}
              </p>
              <p className="mt-1 text-xs text-slate-500">{c.sub}</p>
            </div>
          ))}
        </div>
        {mon?.running && (
          <p className="mt-4 text-sm text-amber-800">
            監視プロセス起動中（PID {mon.pid}
            {mon.demo
              ? "・デモ用の仮想価格"
              : marketSource?.source === "excel"
                ? "・Excel の最新値で出口判定"
                : "・Excel 未使用時はエントリー価格スタブ（要: market_data.source=excel）"}
            ）
          </p>
        )}
      </Section>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section
          step="②"
          title="銘柄の登録と「実際に買った」への切り替え"
          description="TradingView のスクリーニングは手動で行い、メモした銘柄コードをここに入力してください。ウォッチ登録後、実際に買ったら同じ銘柄を保有（HOLDING）にすると、Excel の株価で監視・損益の目安が出ます（Excel モード時）。"
        >
          <div className="space-y-5">
            <div>
              <label className="mb-1 block text-sm font-bold text-slate-800">
                ウォッチに銘柄を追加
              </label>
              <p className="mb-2 text-xs text-slate-500">
                カンマ区切り。例: 国内株コード 7203, 9984 ／ 米株 AAPL, MSFT
              </p>
              <div className="flex flex-col gap-2 sm:flex-row">
                <input
                  className="input-field font-mono tabular-nums sm:flex-1"
                  value={symbolsInput}
                  onChange={(e) => setSymbolsInput(e.target.value)}
                  placeholder="例: 7203, 9984 または AAPL, MSFT"
                />
                <button
                  type="button"
                  className="btn-primary shrink-0"
                  disabled={busy !== null || apiOk !== true}
                  onClick={() =>
                    runAction(
                      "登録",
                      () =>
                        api("/api/screen", {
                          method: "POST",
                          body: JSON.stringify({ symbols: symbolsInput }),
                        }),
                      "ウォッチに追加しました",
                    )
                  }
                >
                  {busy === "登録" ? "送信中…" : "追加する"}
                </button>
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-sm font-bold text-slate-800">
                ウォッチ → 保有にする（エントリー入力）
              </p>
              <p className="mt-1 text-xs text-slate-600">
                対象は「同じ銘柄のウォッチ行」のうち<strong>最新</strong>の1件です。
              </p>
              <div className="mt-3 grid gap-2 sm:grid-cols-3">
                <div>
                  <label className="mb-1 block text-xs font-medium text-slate-600">
                    銘柄
                  </label>
                  <input
                    className="input-field font-mono"
                    value={promote.symbol}
                    onChange={(e) =>
                      setPromote((p) => ({ ...p, symbol: e.target.value }))
                    }
                    placeholder="AAPL"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-slate-600">
                    買った価格（1株）
                  </label>
                  <input
                    className="input-field font-mono tabular-nums"
                    value={promote.entry}
                    onChange={(e) =>
                      setPromote((p) => ({ ...p, entry: e.target.value }))
                    }
                    placeholder="185.50"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-slate-600">
                    株数
                  </label>
                  <input
                    className="input-field font-mono tabular-nums"
                    value={promote.shares}
                    onChange={(e) =>
                      setPromote((p) => ({ ...p, shares: e.target.value }))
                    }
                    placeholder="10"
                  />
                </div>
              </div>
              <button
                type="button"
                className="btn-secondary mt-3"
                disabled={busy !== null || apiOk !== true}
                onClick={() => {
                  const ep = parseFloat(promote.entry);
                  const sh = parseInt(promote.shares, 10);
                  if (
                    !promote.symbol.trim() ||
                    Number.isNaN(ep) ||
                    Number.isNaN(sh)
                  ) {
                    showToast("銘柄・価格・株数をすべて入力してください");
                    return;
                  }
                  runAction(
                    "保有化",
                    () =>
                      api("/api/position/promote", {
                        method: "POST",
                        body: JSON.stringify({
                          symbol: promote.symbol.trim(),
                          entry_price: ep,
                          shares: sh,
                        }),
                      }),
                    "保有に切り替えました",
                  );
                }}
              >
                {busy === "保有化" ? "処理中…" : "この内容で保有にする"}
              </button>
            </div>
          </div>
        </Section>

        <Section
          step="③"
          title="デモと自動監視（バックグラウンド）"
          description="デモは仮想銘柄 DEMO で「目標到達→売却」までを試せます。実モードでは config で market_data.source=excel にすると、保存済み Excel の価格で損切り・目標を判定します（MarketSpeed 記帳を定期的に保存してください）。Excel 未使用時はエントリー価格スタブです。止めるときは監視停止を押してください。"
        >
          <div className="flex flex-col gap-3">
            <button
              type="button"
              className="btn-primary w-full sm:w-auto"
              disabled={busy !== null || apiOk !== true}
              onClick={() =>
                runAction(
                  "デモシード",
                  () => api("/api/demo/seed", { method: "POST", body: "{}" }),
                  "デモ用の DEMO ポジションを用意しました",
                )
              }
            >
              {busy === "デモシード" ? "作成中…" : "デモ用ポジションを用意（DEMO）"}
            </button>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className="btn-secondary"
                disabled={busy !== null || apiOk !== true}
                onClick={() =>
                  runAction(
                    "監視デモ",
                    () =>
                      api("/api/monitor/start?demo=true", {
                        method: "POST",
                        body: "{}",
                      }),
                    "デモ監視を開始しました",
                  )
                }
              >
                {busy === "監視デモ" ? "起動中…" : "監視開始（デモ価格）"}
              </button>
              <button
                type="button"
                className="btn-secondary"
                disabled={busy !== null || apiOk !== true}
                onClick={() =>
                  runAction(
                    "監視実",
                    () =>
                      api("/api/monitor/start?demo=false", {
                        method: "POST",
                        body: "{}",
                      }),
                    "実モード監視を開始しました",
                  )
                }
              >
                {busy === "監視実" ? "起動中…" : "監視開始（実モード）"}
              </button>
              <button
                type="button"
                className="btn-danger"
                disabled={busy !== null || apiOk !== true}
                onClick={() =>
                  runAction(
                    "監視停止",
                    () => api("/api/monitor/stop", { method: "POST", body: "{}" }),
                    "監視を停止しました",
                  )
                }
              >
                {busy === "監視停止" ? "停止中…" : "監視を停止"}
              </button>
            </div>
          </div>
        </Section>
      </div>

      {/* ④ 一覧 */}
      <Section
        step="④"
        title="登録済み銘柄の一覧（株価つき）"
        description={
          marketSource?.source === "excel"
            ? "株価は MarketSpeed 等から保存した Excel を読みます（config の excel_path）。Excel に銘柄行がないと「—」になります。保有中は評価損益の目安を表示します。"
            : "株価は主に yfinance（遅延）です。即時性が必要なら market_data.source を excel にしてください。保有中は評価損益の目安を表示します。"
        }
      >
        {quotes?.error && (
          <p className="mb-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-800">
            株価の取得に失敗しました: {quotes.error}
          </p>
        )}
        {quotes?.warning && (
          <p className="mb-3 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">
            {quotes.warning}
          </p>
        )}
        <p className="mb-3 text-xs text-slate-500">
          株価更新: {asOfLocal ?? "—"}（ソース:{" "}
          {quotes?.source === "marketspeed_excel"
            ? "Excel（MarketSpeed 記帳ファイル等）"
            : quotes?.source === "yfinance_delayed"
              ? "yfinance（遅延）"
              : quotes?.source === "yahoo_http_delayed"
                ? "Yahoo HTTP（遅延）"
                : quotes?.source ?? "—"}
          ）
          {quotes?.file_age_sec != null && (
            <span className="ml-2">
              ・ファイル更新から約 {Math.round(quotes.file_age_sec)} 秒
            </span>
          )}
          ・約5秒ごとに再取得
        </p>
        <div className="overflow-x-auto rounded-xl border border-slate-200">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="bg-slate-100">
              <tr className="border-b border-slate-200">
                <Th hint="例: 7203 や AAPL">銘柄</Th>
                <Th hint="ウォッチ＝候補、保有＝ルール監視対象">状態の意味</Th>
                <Th hint="Excel または yfinance の参照価格">現在株価</Th>
                <Th hint="前日終値列がある場合のみ（Excel）">前日比</Th>
                <Th hint="買ったときの1株あたりの価格">エントリー</Th>
                <Th hint="利確の目安価格（システム計算）">利確目標</Th>
                <Th hint="損切りライン（システム計算）">損切り</Th>
                <Th hint="エントリー後の最高値（トレール売りの基準）">追跡高値</Th>
                <Th hint="保有中のみ（通貨は株価ソースに合わせます）">評価損益</Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {open.length === 0 && (
                <tr>
                  <td
                    colSpan={9}
                    className="px-3 py-10 text-center text-slate-500"
                  >
                    まだ行がありません。②で銘柄を追加するか、③でデモを用意してください。
                  </td>
                </tr>
              )}
              {open.map((r, i) => {
                const q = quotes?.quotes?.[r.symbol.toUpperCase()];
                const cur =
                  q?.currency ||
                  (marketSource?.source === "excel" ? "JPY" : "USD");
                const price =
                  typeof q?.price === "number" && !Number.isNaN(q.price)
                    ? q.price
                    : null;
                const chg =
                  typeof q?.change_pct === "number" && !Number.isNaN(q.change_pct)
                    ? q.change_pct
                    : null;
                let unreal: number | null = null;
                if (
                  r.status === "HOLDING" &&
                  price != null &&
                  r.entry_price != null &&
                  r.shares != null
                ) {
                  unreal = (price - r.entry_price) * r.shares;
                }
                return (
                  <tr
                    key={`${r.id}-${r.symbol}`}
                    className={i % 2 === 0 ? "bg-white" : "bg-slate-50/80"}
                  >
                    <td className="px-3 py-3 font-mono text-base font-bold text-slate-900">
                      {r.symbol}
                      {q?.error && (
                        <span className="ml-1 text-xs font-normal text-rose-600">
                          ({q.error})
                        </span>
                      )}
                    </td>
                    <td className="max-w-[10rem] px-3 py-3 text-xs leading-snug text-slate-700">
                      {statusLabel(r.status)}
                    </td>
                    <td className="px-3 py-3 font-mono tabular-nums text-base font-semibold text-slate-900">
                      {formatPrice(price, cur)}
                    </td>
                    <td
                      className={`px-3 py-3 font-mono tabular-nums text-sm ${
                        chg == null
                          ? "text-slate-400"
                          : chg >= 0
                            ? "text-emerald-700"
                            : "text-rose-700"
                      }`}
                    >
                      {chg != null ? `${chg >= 0 ? "+" : ""}${chg.toFixed(2)}%` : "—"}
                    </td>
                    <td className="px-3 py-3 font-mono tabular-nums text-slate-800">
                      {r.entry_price != null
                        ? formatPrice(r.entry_price, cur)
                        : "—"}
                    </td>
                    <td className="px-3 py-3 font-mono tabular-nums text-emerald-800">
                      {r.target_price != null
                        ? formatPrice(r.target_price, cur)
                        : "—"}
                    </td>
                    <td className="px-3 py-3 font-mono tabular-nums text-rose-800">
                      {r.stop_price != null
                        ? formatPrice(r.stop_price, cur)
                        : "—"}
                    </td>
                    <td className="px-3 py-3 font-mono tabular-nums text-violet-900">
                      {r.peak_price != null
                        ? formatPrice(r.peak_price, cur)
                        : "—"}
                    </td>
                    <td
                      className={`px-3 py-3 font-mono tabular-nums text-sm font-semibold ${
                        unreal == null
                          ? "text-slate-400"
                          : unreal >= 0
                            ? "text-emerald-700"
                            : "text-rose-700"
                      }`}
                    >
                      {formatSignedPnl(unreal, cur)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Section>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section
          step="補足"
          title="直近の決済履歴"
          description="すでにクローズしたトレードです。出口理由と損益を確認できます。"
        >
          <div className="overflow-x-auto rounded-xl border border-slate-200">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-100">
                <tr className="border-b border-slate-200">
                  <Th hint="銘柄コード">銘柄</Th>
                  <Th hint="システムが記録した決済理由">出口理由</Th>
                  <Th hint="そのトレードの損益（USD）">損益</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {closed.length === 0 && (
                  <tr>
                    <td
                      colSpan={3}
                      className="px-3 py-8 text-center text-slate-500"
                    >
                      まだありません
                    </td>
                  </tr>
                )}
                {closed.map((r, i) => (
                  <tr
                    key={`${r.id}-${r.symbol}-c`}
                    className={i % 2 === 0 ? "bg-white" : "bg-slate-50/80"}
                  >
                    <td className="px-3 py-2.5 font-mono font-semibold text-slate-900">
                      {r.symbol}
                    </td>
                    <td className="px-3 py-2.5 text-xs text-slate-600">
                      {r.exit_reason ?? "—"}
                    </td>
                    <td
                      className={`px-3 py-2.5 font-mono tabular-nums font-semibold ${
                        (r.pnl ?? 0) >= 0 ? "text-emerald-700" : "text-rose-700"
                      }`}
                    >
                      {r.pnl != null ? `$${r.pnl.toFixed(2)}` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>

        <Section
          step="ログ"
          title="操作と監視のログ"
          description="画面から実行した操作や、バックグラウンド監視の標準出力がここに溜まります。不具合調査のときに使います。"
        >
          <pre className="max-h-64 overflow-auto rounded-xl border border-slate-200 bg-slate-900 p-4 font-mono text-xs leading-relaxed text-slate-100">
            {logs.length ? logs.join("\n") : "まだログがありません"}
          </pre>
        </Section>
      </div>

      <footer className="mt-8 text-center text-xs text-slate-500">
        バックエンドは{" "}
        <code className="rounded bg-slate-200 px-1 py-0.5 text-slate-800">
          python main.py api
        </code>{" "}
        、フロントは{" "}
        <code className="rounded bg-slate-200 px-1 py-0.5 text-slate-800">
          npm run dev
        </code>{" "}
        （フォルダは{" "}
        <code className="rounded bg-slate-200 px-1 py-0.5 text-slate-800">
          connors-rsi-system/dashboard
        </code>
        ）
      </footer>
    </div>
  );
}
