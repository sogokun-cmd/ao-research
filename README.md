# AOリサーチ

塾講師のための総合型選抜（AO入試）公式情報確認インフラ。

大学・学部を指定するだけで、公式サイト・PDF・パスナビから募集要項を自動収集し、選考方法・定員・倍率・出願条件をまとめて表示します。

## 機能

- **大学別公式情報** — 選考方法・定員・倍率・出願条件・アドミッションポリシーを自動収集
- **前年比・ニュース** — 募集要項の変更点・注目トピックを分析
- **競合分析** — 競合大学のSNS戦略・ポジションを比較
- **類似校提案** — 入試方式・難易度・地域が近い大学を AI が提案
- **大学比較** — 複数の調査結果を横並びで比較（最大4校）
- **Notion 保存** — 調査結果・比較表を Notion に自動保存
- **Google / メール認証** — JWT Cookie ベースのセッション管理

## 技術スタック

- **Backend**: FastAPI + SQLite（WAL モード）
- **認証**: Google OAuth2 + メール/パスワード + JWT Cookie
- **AI**: Claude API（Haiku）— 類似校提案に使用
- **フロントエンド**: Vanilla JS（バンドラー不要）

## セットアップ

### 1. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 2. 環境変数の設定

`.env.example` をコピーして `.env` を作成：

```bash
cp .env.example .env
```

| 変数名 | 説明 |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API キー（必須） |
| `GOOGLE_CLIENT_ID` | Google OAuth2 クライアント ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth2 クライアントシークレット |
| `GOOGLE_REDIRECT_URI` | OAuth2 コールバック URI（例: `http://localhost:8000/auth/callback`） |
| `JWT_SECRET_KEY` | JWT 署名キー（`openssl rand -hex 32` で生成） |
| `NOTION_TOKEN` | Notion インテグレーショントークン（Notion 保存を使う場合） |

### 3. 起動

```bash
uvicorn main:app --reload --port 8000
```

ブラウザで `http://localhost:8000` を開く。

## Railway デプロイ

### 環境変数の設定

Railway のダッシュボードで以下を設定：

```
ANTHROPIC_API_KEY=...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=https://<your-app>.railway.app/auth/callback
JWT_SECRET_KEY=...
NOTION_TOKEN=...
```

### デプロイ手順

```bash
# Railway CLI でデプロイ
railway login
railway init
railway up
```

または GitHub リポジトリを Railway に連携して自動デプロイ。

> **注意**: `ao_product.db`（SQLite）はサーバー再起動でリセットされます。本番環境では PostgreSQL などの永続 DB への移行を推奨します。

## API エンドポイント

| メソッド | パス | 説明 |
|---|---|---|
| `POST` | `/api/research` | リサーチジョブを開始 |
| `GET` | `/api/research/{job_id}` | ジョブのステータス・結果を取得 |
| `POST` | `/api/research/{job_id}/notion` | 結果を Notion に保存 |
| `POST` | `/api/similar-schools` | 類似校を提案（Claude Haiku） |
| `POST` | `/api/compare` | 複数大学の比較表を生成 |
| `POST` | `/api/compare/notion` | 比較表を Notion に保存 |
| `GET` | `/api/me` | ログイン中のユーザー情報 |
| `GET` | `/api/health` | ヘルスチェック |

## ディレクトリ構成

```
ao-product/
├── main.py              # FastAPI エントリーポイント
├── database.py          # SQLite 管理
├── api/
│   └── research.py      # /api/* エンドポイント
├── auth/
│   ├── routes.py        # /auth/* エンドポイント
│   ├── deps.py          # JWT 認証依存関係
│   ├── email_auth.py    # メール/パスワード認証
│   └── google.py        # Google OAuth2
├── core/
│   ├── university.py    # リサーチジョブ管理
│   └── similar_schools.py # 類似校提案（Claude API）
├── static/
│   ├── index.html       # メイン画面
│   ├── login.html       # ログイン画面
│   └── register.html    # 登録画面
├── Procfile             # Railway 用プロセス定義
└── requirements.txt     # 依存パッケージ
```
