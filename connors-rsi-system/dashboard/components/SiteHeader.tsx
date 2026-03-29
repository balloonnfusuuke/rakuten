import Link from "next/link";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-slate-200/80 bg-white/95 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-4 px-4 sm:px-5">
        <Link
          href="/"
          className="text-sm font-bold tracking-tight text-slate-900 sm:text-base"
        >
          <span className="text-indigo-600">ConnorsRSI</span>
          <span className="text-slate-600">(2)</span>
        </Link>
        <nav className="flex items-center gap-1 sm:gap-3">
          <Link
            href="/"
            className="rounded-lg px-3 py-2 text-sm font-medium text-slate-600 transition hover:bg-slate-100 hover:text-slate-900"
          >
            ホーム
          </Link>
          <Link
            href="/control"
            className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700"
          >
            コントロール
          </Link>
        </nav>
      </div>
    </header>
  );
}
