# Box RAG Service

Box 共有リンクから OpenSearch へドキュメントを取り込み、watsonx.ai で RAG 検索を行うスタンドアロンサービスです。

## アーキテクチャ

```
┌──────────────────────────────────────────────────────────┐
│  Box RAG Service (疎結合・OpenRAG を直接改変しない)           │
│                                                          │
│  ┌─────────────┐   ┌──────────────┐   ┌──────────────┐  │
│  │  Frontend   │──▶│  FastAPI     │──▶│ watsonx.ai   │  │
│  │  (HTML/JS)  │   │  Backend     │   │ (LLM + Embed)│  │
│  └─────────────┘   └──────┬───────┘   └──────────────┘  │
│                           │                              │
│                    ┌──────▼───────┐   ┌──────────────┐  │
│                    │  Box SDK v10 │   │  OpenSearch  │  │
│                    │  (共有リンク)  │   │  box_docs    │  │
│                    └─────────────┘   │  box_chunks  │  │
│                                      └──────────────┘  │
└──────────────────────────────────────────────────────────┘
        ▲ OpenSearch を共有 (別インデックス使用)
        │
┌──────────────────────────────────────────────────────────┐
│  OpenRAG (既存スタック・無改変)                               │
│  opensearch, openrag-backend, langflow, ...              │
└──────────────────────────────────────────────────────────┘
```

**疎結合の実現方法:**
- OpenRAG のソースコードを一切改変しない
- OpenSearch の別インデックス (`box_documents`, `box_chunks`) を使用
- Box RAG 専用の FastAPI バックエンドを独立して起動
- Docker Compose オーバーライドで既存スタックに追加

## 前提条件

- Ubuntu 22.04 + Podman (または Docker)
- OpenRAG ベーススタックが起動済み
- watsonx.ai (OCP on-premise) へのアクセス
- Box アカウント (共有リンクが使える環境)

## セットアップ

### 1. 認証情報ファイルの準備

```bash
# プロジェクトルートの .creds_example をコピーして編集
cp .creds_example box-rag/.env
# box-rag/.env.example の項目を参照して追記
```

必須設定:
```bash
# watsonx.ai
WATSONX_API_URL=https://cpd-cpd.apps.watsonx2.lab.japan.ibm.com
WATSONX_AUTH_URL=https://cpd-cpd.apps.watsonx2.lab.japan.ibm.com/icp4d-api/v1/authorize
WATSONX_PROJECT_ID=<your-project-id>
WATSONX_USERNAME=<username>
WATSONX_PASSWORD=<password>
WATSONX_SSL_VERIFY=false    # OCP 自己署名証明書対応

# OpenSearch (OpenRAG のパスワードと合わせる)
OPENSEARCH_PASSWORD=<opensearch-password>

# Box (公開共有リンクのみなら BOX_AUTH_MODE=none のまま)
BOX_AUTH_MODE=none
```

### 2. OpenRAG ベーススタックと合わせて起動

```bash
cd /path/to/openrag

# Podman の場合
podman-compose \
  -f docker-compose.yml \
  -f box-rag/docker-compose.box-rag.yml \
  up -d

# Docker Compose の場合
docker compose \
  -f docker-compose.yml \
  -f box-rag/docker-compose.box-rag.yml \
  up -d
```

### 3. Box RAG のみ起動（OpenRAG 起動済みの場合）

```bash
cd /path/to/openrag

podman-compose \
  -f box-rag/docker-compose.box-rag.yml \
  up -d box-rag-backend
```

### 4. アクセス

| サービス          | URL                        |
|-----------------|----------------------------|
| Box RAG UI      | http://localhost:8100/      |
| Box RAG API     | http://localhost:8100/docs  |
| Health check    | http://localhost:8100/health|

## Box 認証モード

| モード | 説明 |
|--------|------|
| `none` | 公開共有リンクのみ (Box アカウント不要) |
| `ccg`  | Client Credentials Grant (サーバー間認証・推奨) |
| `jwt`  | JWT (本番デフォルト・要 RSA 鍵ペア) |

### JWT 設定 (BOX_AUTH_MODE=jwt)

```bash
BOX_JWT_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"
BOX_JWT_PRIVATE_KEY_PASSPHRASE=optional-passphrase
BOX_JWT_PUBLIC_KEY_ID=<key-id-from-box-developer-console>
```

## API エンドポイント

```
POST /shared-link/resolve    # 共有リンク解決 (ファイル/フォルダツリー取得)
POST /ingest/selection       # 取り込みジョブ開始
GET  /ingest/jobs/{job_id}   # ジョブ状態確認
GET  /documents              # 取り込み済みドキュメント一覧
DELETE /documents/{id}       # ドキュメント削除
POST /search                 # RAG 検索 (ベクター検索 + LLM 回答生成)
GET  /health                 # ヘルスチェック
```

## OpenSearch インデックス設計

### box_documents (ドキュメントメタデータ)
| フィールド | 型 | 説明 |
|-----------|-----|------|
| document_id | keyword | UUID (主キー) |
| box_file_id | keyword | Box ファイル ID |
| file_name | text | ファイル名 |
| tags | keyword[] | タグリスト |
| modified_at | keyword | Box の更新日時 (重複検知キー) |
| status | keyword | pending / indexed / failed |
| chunk_count | integer | チャンク数 |

### box_chunks (チャンク + ベクター)
| フィールド | 型 | 説明 |
|-----------|-----|------|
| chunk_id | keyword | UUID |
| document_id | keyword | 親ドキュメント ID |
| text | text | フォーマット済みチャンクテキスト |
| embedding | knn_vector(384) | `ibm/granite-embedding-107m-multilingual` |
| chunk_index | integer | チャンク順序 |

## タグ仕様

- 許可: 全角文字 (CJK・かな・ハングル等)、半角英数字
- 禁止: 半角記号、全角記号
- 半角英字は自動小文字化
- 最大 20 タグ、各 64 文字
- 入力時に即時バリデーション

## 重複取り込み防止

判定キー: `box_file_id + modified_at`

- 同一ファイルが既にインデックス済みで `modified_at` が変わっていない → スキップ
- `modified_at` が変わっていれば → 旧チャンク全削除 → 再生成 → 再インデックス

## 設定変数一覧

`box-rag/.env.example` を参照してください。
