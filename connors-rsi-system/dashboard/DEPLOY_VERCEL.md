# Vercel デプロイ手順

## 1. リポジトリのルート

- Git のルートが `Rakuten` の直下で、`connors-rsi-system` がサブフォルダにある場合、Vercel の **Root Directory** を次に設定します。

```
connors-rsi-system/dashboard
```

- `dashboard` フォルダだけを別リポジトリにしている場合は、そのままプロジェクトルートでよいです。

## 2. 環境変数（必須）

| 名前 | 例 | 説明 |
|------|-----|------|
| `NEXT_PUBLIC_API_URL` | `https://your-api.railway.app` | 公開している FastAPI の URL（末尾スラッシュなし） |

ブラウザから `http://127.0.0.1:8000` には届かないため、本番では **Railway / Render / 自宅サーバの HTTPS** など、**インターネットから届く URL** を設定してください。

## 3. API 側の CORS

`api/server.py` では `allow_origins=["*"]` なので、Vercel のドメインはそのまま通りやすいです。制限する場合は FastAPI の CORS を Vercel の URL だけに絞ってください。

## 4. ビルド

Vercel が Next.js を自動検出します。`package.json` の `npm run build` で問題なければ完了です。

## 5. ページ構成

| パス | 内容 |
|------|------|
| `/` | ランディング（説明・デプロイ注意） |
| `/control` | コントロールパネル（従来のダッシュボード） |
