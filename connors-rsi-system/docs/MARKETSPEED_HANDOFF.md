# MarketSpeed（Excel）と本システムの「つなぎ方」

MarketSpeed 本体とこのリポジトリは **直接 API 連携していません**。  
**Excel ファイルを共通の受け渡し場所にする**形です。

## 全体の流れ

1. **TradingView** でスクリーニング（手動）→ 銘柄コードをメモする  
2. **MarketSpeed** で銘柄を登録し、**記帳（Excel）** に株価を出す  
3. **Excel をファイルとして保存**する（パスを `config.yaml` の `market_data.excel_path` に書く）  
4. 本システムの **ダッシュボード** に銘柄コードを入力してウォッチ登録 → 必要なら **保有化**  
5. **`python main.py api`** を起動 → 画面で **Excel 由来の株価**・評価損益を確認  
6. **`python main.py monitor`**（またはダッシュボードの「監視開始」）で **出口ルール**（損切り・高値トレール等）を評価  

## Excel 側の用意

### 推奨列（列名は自動認識しやすい）

| 列の意味 | 例（列名） |
|----------|------------|
| 銘柄コード | `銘柄コード` / `コード` / `Symbol` など |
| 現在値 | `現在値` / `株価` など |
| 前日終値（任意） | `前日終値`（前日比表示用） |

サンプルは `reference/marketspeed_excel_sample.csv` を参照してください。  
Excel に貼り付けて保存しても構いません。

### 列が合わないとき

`config.yaml` の `market_data` で指定します。

```yaml
market_data:
  source: excel
  excel_path: "C:/Users/あなた/.../marketspeed.xlsx"
  sheet: 0
  symbol_column: "銘柄コード"
  price_column: "現在値"
  prev_close_column: "前日終値"
  currency_hint: JPY
  stale_warn_sec: 120
```

## 保存の注意

- 本システムは **保存済みの `.xlsx` を読みます**（`openpyxl`）。  
- **Excel でファイルを開いているだけで未保存**だと、古いデータのまま／ロックで読めないことがあります。  
- **MarketSpeed から記帳を更新したら保存**し、可能なら**編集用に閉じる**時間を作ると安全です。

## 本システム側の設定

1. `config.yaml` で `market_data.source: excel` と `excel_path` を設定  
2. `pip install -r requirements.txt`（`openpyxl` 含む）  
3. `python main.py api` で API を起動し、ダッシュボードから銘柄を登録  

## 監視の価格ソース

- **`market_data.source: excel`** のとき、監視ループ（`monitor`）も **同じ Excel** から最新値を読み取ります。  
- トレーリング（高値から ○％下落）の **高値**は **DB の `peak_price`** に更新され、監視のたびに **現在値と比較**されます。

## 高値トレール（全株売却）

`config.yaml` の `exit` セクション:

```yaml
exit:
  trail_from_peak_pct: 0.05   # 高値から 5% 下落で売り（0 で無効）
```

- エントリー以降の **最高値** を `peak_price` として保持します。  
- **現在値 ≤ 高値 × (1 − 上記の割合)** になったら **全株** 売却シグナル（部分売りではありません）。  
- 固定の `stop_price` より **後** の優先順位ではなく、実装では **固定損切りの次** に評価されます。

詳細はコード内 `monitor/exit_engine.py` を参照してください。
