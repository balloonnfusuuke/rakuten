import Link from "next/link";

export function LandingPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 pb-20 pt-12 sm:px-6 sm:pt-16">
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-indigo-600">
        Rakuten / 個人向けトレード補助
      </p>
      <h1 className="mt-1 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
        ConnorsRSI(2) コントロール
      </h1>
      <p className="mt-4 text-base leading-relaxed text-slate-600">
        ウォッチリスト登録・保有管理・監視（出口ルール）のための Web パネルです。
        本番の API（FastAPI）は{" "}
        <strong className="text-slate-800">別ホストで起動</strong>
        し、ここから接続します。
      </p>

      <div className="mt-10 flex flex-col gap-3 sm:flex-row sm:items-center">
        <Link
          href="/control"
          className="inline-flex items-center justify-center rounded-xl bg-indigo-600 px-6 py-3.5 text-center text-base font-semibold text-white shadow-lg shadow-indigo-500/25 transition hover:bg-indigo-700"
        >
          コントロールを開く
        </Link>
        <p className="text-sm text-slate-500">
          株価・監視の実データは API が動いている必要があります。
        </p>
      </div>

      <section className="mt-14 space-y-4">
        <h2 className="text-lg font-bold text-slate-900">Vercel での注意</h2>
        <ul className="list-inside list-disc space-y-2 text-sm leading-relaxed text-slate-600">
          <li>
            プロジェクトの{" "}
            <strong className="text-slate-800">Root Directory</strong> を{" "}
            <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-cyan-800">
              connors-rsi-system/dashboard
            </code>{" "}
            に設定してください（リポジトリが親フォルダの場合）。
          </li>
          <li>
            環境変数{" "}
            <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-cyan-800">
              NEXT_PUBLIC_API_URL
            </code>{" "}
            に、公開中の API の URL（例:{" "}
            <code className="font-mono text-cyan-800">https://api.example.com</code>
            ）を設定してください。
          </li>
          <li>
            <code className="text-cyan-800">http://127.0.0.1:8000</code>{" "}
            のままでは、ブラウザ上の本番サイトからは API に届きません。
          </li>
        </ul>
      </section>

      <section className="mt-10 rounded-2xl border border-slate-200 bg-slate-50/80 p-6">
        <h2 className="text-sm font-bold text-slate-800">リポジトリの構成</h2>
        <p className="mt-2 text-sm leading-relaxed text-slate-600">
          このフォルダ（<code className="font-mono text-cyan-800">dashboard</code>
          ）は Next.js のみです。Python の API・監視は{" "}
          <code className="font-mono text-cyan-800">connors-rsi-system</code>{" "}
          直下で別途実行してください。
        </p>
      </section>
    </div>
  );
}
