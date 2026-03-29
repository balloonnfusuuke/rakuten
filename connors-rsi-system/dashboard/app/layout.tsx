import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import { SiteHeader } from "@/components/SiteHeader";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
});

const siteUrl = process.env.VERCEL_URL
  ? `https://${process.env.VERCEL_URL}`
  : undefined;

export const metadata: Metadata = {
  title: {
    default: "ConnorsRSI(2) パネル",
    template: "%s | ConnorsRSI",
  },
  description:
    "ウォッチリスト・保有・監視。FastAPI バックエンドと連携するトレード補助 UI。",
  metadataBase: siteUrl ? new URL(siteUrl) : undefined,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ja" className={`${inter.variable} ${mono.variable}`}>
      <body className={`${inter.className} min-h-screen font-sans`}>
        <SiteHeader />
        {children}
        <footer className="border-t border-slate-200 bg-white py-8 text-center text-xs text-slate-500">
          <p>
            フロントのみ Vercel。API は{" "}
            <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-slate-700">
              NEXT_PUBLIC_API_URL
            </code>{" "}
            で指定。
          </p>
        </footer>
      </body>
    </html>
  );
}
