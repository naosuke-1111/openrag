# フロントエンド接続エラーの修正方法

## 問題の概要

`npm run dev`でフロントエンドを起動すると、以下のエラーが発生：

```
Proxy error: TypeError: fetch failed
  [cause]: [AggregateError: ] { code: 'ECONNREFUSED' }
```

## 原因

1. **フロントエンド**: ホストマシンで`npm run dev`により`localhost:3001`で実行
2. **バックエンド**: Dockerコンテナ内で実行（`openrag-backend`コンテナ、ポート8000）
3. **問題**: フロントエンドのプロキシ（`app/api/[...path]/route.ts`）が`localhost:8000`に接続しようとしているが、バックエンドはDockerコンテナ内にあるため接続できない

## 解決策

### オプション1: フロントエンド用の環境変数ファイルを作成（推奨）

`frontend/.env.local`ファイルを作成し、以下の内容を設定：

```env
# OpenRAG Backend Configuration for Local Development
# バックエンドがDockerコンテナで動作している場合

# バックエンドのホスト名
# Dockerコンテナ名を使用（docker-compose.ymlで定義されている）
OPENRAG_BACKEND_HOST=localhost

# または、バックエンドコンテナがポート8000を公開している場合
# docker-compose.ymlを確認すると、openrag-backendはポートを公開していないため、
# ポートフォワーディングを追加する必要があります
```

### オプション2: docker-compose.ymlを修正してバックエンドポートを公開

`docker-compose.yml`の`openrag-backend`セクションに以下を追加：

```yaml
openrag-backend:
  # ... 既存の設定 ...
  ports:
    - "8000:8000"  # この行を追加
```

その後、以下のコマンドでコンテナを再起動：

```bash
docker compose down
docker compose up -d
```

### オプション3: フロントエンドもDockerで実行

フロントエンドをDockerコンテナで実行する場合は、以下のコマンドを使用：

```bash
docker compose up openrag-frontend
```

この場合、フロントエンドは`http://localhost:3000`でアクセス可能になります。

## 推奨される修正手順

1. **docker-compose.ymlを修正**してバックエンドポートを公開
2. **コンテナを再起動**
3. **フロントエンドを起動**して動作確認

## 実装が必要な変更

### 1. docker-compose.ymlの修正

`openrag-backend`サービスに`ports`セクションを追加：

```yaml
openrag-backend:
  image: langflowai/openrag-backend:${OPENRAG_VERSION:-latest}
  build:
    context: .
    dockerfile: Dockerfile.backend
  container_name: openrag-backend
  depends_on:
    - langflow
  ports:
    - "8000:8000"  # ← この行を追加
  environment:
    # ... 既存の環境変数 ...
```

### 2. コンテナの再起動

```bash
# コンテナを停止
docker compose down

# コンテナを再起動
docker compose up -d

# バックエンドのログを確認
make logs-be
```

### 3. フロントエンドの起動と確認

```bash
cd frontend
npm run dev
```

ブラウザで`http://localhost:3001`にアクセスして動作確認。

## 確認事項

- バックエンドが`http://localhost:8000`でアクセス可能か確認
- フロントエンドのプロキシエラーが解消されているか確認
- `/api/auth/me`などのAPIエンドポイントが正常に動作するか確認