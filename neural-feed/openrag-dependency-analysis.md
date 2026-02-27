# NEURAL FEED — OpenRAG 依存度分析レポート

> 作成日: 2026-02-27  
> 分析対象: Neural Feed アプリケーション  
> 関連ドキュメント: `requirements.md`, `implementation-strategy.md`

---

## 📊 エグゼクティブサマリー

### 依存度評価: **10-15% (非常に低い)**

Neural Feed は設計段階から**高い独立性**を持ち、OpenRAGへの依存は最小限です。別システムへの移植は**3日程度**で完了可能です。

| 評価項目 | スコア | 説明 |
|---------|--------|------|
| **フロントエンド独立性** | 100% | 完全に独立したSPA |
| **データソース独立性** | 90% | OpenSearch読み取りのみ |
| **ビジネスロジック独立性** | 100% | OpenRAG固有機能を使用せず |
| **デプロイ独立性** | 85% | バックエンドAPIのみ統合 |
| **総合依存度** | **10-15%** | **非常に低い** |
| **移植可能性** | **95%** | **非常に高い** |

---

## 🔍 詳細分析

### 1. フロントエンドアプリケーション

#### 独立性: **100%** ✅

**技術スタック**:
```
- Vite 5.x (バンドラー)
- React 18.x (UIフレームワーク)
- TypeScript 5.x
- Three.js r165+ (WebGL 3D描画)
- d3-force 3.x (物理演算)
- Tone.js 14.x (音響演出)
- Zustand 4.x (状態管理)
```

**OpenRAG依存**: なし

**特徴**:
- OpenRAGのNext.jsフロントエンドとは**完全に別のアプリケーション**
- 静的ビルド (`vite build`) → Nginx配信
- OpenRAG固有のコンポーネント・ライブラリを使用せず
- IBM Carbon Design Systemも使用せず（カスタムデザイン）

**ディレクトリ構成**:
```
neural-feed-app/
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── components/
│   │   ├── left-panel/    # パイプライン表示
│   │   ├── center-panel/  # Three.jsグラフ
│   │   └── right-panel/   # 記事キュー
│   ├── hooks/
│   │   ├── useArticleStream.ts  # SSE接続
│   │   └── useKpiMetrics.ts     # REST API
│   └── store/
│       └── neuralFeedStore.ts   # Zustand
├── vite.config.ts
└── package.json
```

---

### 2. データソース

#### 独立性: **90%** ✅

**使用データベース**:
- **OpenSearch**: `watson_news_enriched` インデックス（読み取り専用）

**OpenRAG依存**: 
- OpenSearchコンテナへの接続設定のみ
- OpenRAG固有のインデックス構造は使用せず

**必要なデータフィールド**:
```json
{
  "id": "記事ID",
  "title": "記事タイトル",
  "domain": "ドメイン名",
  "source_type": "gdelt | ibm_official | box",
  "sentiment_label": "POSITIVE | NEUTRAL | NEGATIVE",
  "sentiment_score": -1.0 ~ 1.0,
  "topic": "Politics | Tech | Finance | ...",
  "published": "ISO 8601 日時",
  "entities": [
    {
      "text": "エンティティ名",
      "type": "PERSON | ORG | LOCATION"
    }
  ]
}
```

**データアクセスパターン**:
```python
# 標準的なOpenSearch APIのみ使用
- search() : 記事検索
- aggregations : 集計クエリ
- range query : 時間範囲フィルタ
- terms aggregation : カテゴリ集計
```

**Watson NLP依存**: なし
- Watson NLPの解析結果は既にOpenSearchに格納済み
- Neural Feedは結果を可視化するだけ
- Watson NLP SDKを直接呼び出す実装なし

---

### 3. バックエンドAPI

#### 独立性: **85%** ⚠️

**現在の実装**:
```python
# OpenRAGのStarletteバックエンドに統合
src/api/neural_feed/
├── __init__.py
├── routes.py              # APIエンドポイント
├── schemas.py             # Pydanticスキーマ
└── opensearch_queries.py  # クエリ定義
```

**OpenRAG依存箇所**:

1. **ルートマウント**:
```python
# src/main.py
from api.neural_feed.routes import neural_feed_router
app.mount("/api/neural-feed", neural_feed_router)
```

2. **環境変数共有**:
```python
OPENSEARCH_HOST = os.getenv("OPENSEARCH_HOST")
OPENSEARCH_PORT = os.getenv("OPENSEARCH_PORT")
OPENSEARCH_USERNAME = os.getenv("OPENSEARCH_USERNAME")
OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD")
```

3. **ロギング設定**:
```python
from utils.logging_config import get_logger
logger = get_logger(__name__)
```

**提供エンドポイント**:
```
GET /api/neural-feed/articles/stream   # SSE: リアルタイム記事配信
GET /api/neural-feed/articles/recent   # 直近記事リスト
GET /api/neural-feed/kpi               # KPIメトリクス
GET /api/neural-feed/categories        # トピック別集計
GET /api/neural-feed/tone              # Global Tone Index
GET /api/neural-feed/entities/top      # トップエンティティ
```

**OpenRAG固有機能の使用**: なし
- Langflow: 不使用
- RAG機能: 不使用
- ドキュメント管理: 不使用
- 認証システム: 不使用
- セッション管理: 不使用

---

### 4. ビジネスロジック

#### 独立性: **100%** ✅

**実装場所**: すべてフロントエンド内で完結

**主要機能**:

1. **ニューラルグラフ描画** (Three.js)
```typescript
// graphEngine.ts
- シーン・カメラ・レンダラー初期化
- InstancedMesh による500ノード描画
- カメラ自動回転（公転アニメーション）
```

2. **物理演算レイアウト** (d3-force)
```typescript
// forceSimulation.ts
- ノード間の引力・斥力計算
- クラスター配置
- リアルタイム位置更新
```

3. **パイプラインステートマシン**
```typescript
// usePipelineState.ts
- 7ステップの状態管理
- アニメーション制御
- 処理フロー可視化
```

4. **音響演出** (Tone.js)
```typescript
// useAudio.ts
- ノード発火音
- コンフリクト検出音
- 音量制御
```

**OpenRAG依存**: なし

---

## 🔄 移植可能性分析

### 総合評価: **95% (非常に高い)** ⭐⭐⭐⭐⭐

### 移植が容易な理由

#### 1. データベース依存が単純
- **PostgreSQL RDB**: 不要
- **ベクターDB**: 不要
- **OpenSearch**: 読み取り専用、標準APIのみ

#### 2. OpenRAG固有機能を使用していない
- Langflow統合なし
- RAG機能なし
- ドキュメント管理なし
- 認証システムなし

#### 3. 疎結合な設計
- フロントエンド: 完全独立
- バックエンド: REST/SSE APIのみ
- データソース: 標準クエリのみ

#### 4. 明確な責務分離
```
Watson News ETL → OpenSearch → Neural Feed Backend → Neural Feed Frontend
     (既存)        (共有)         (独立可能)           (完全独立)
```

---

## 📋 移植に必要な変更点

### 変更レベル: **小 (3日程度)**

### 1. バックエンドAPIの独立化 (必須)

#### 変更前
```python
# OpenRAGに統合
src/api/neural_feed/routes.py
src/main.py に mount
```

#### 変更後
```python
# 独立したStarlette/FastAPIアプリ
neural-feed-backend/
├── main.py                    # 新規作成
├── api/
│   ├── routes.py             # 既存コードを移植
│   ├── schemas.py            # 既存コードをコピー
│   └── opensearch_queries.py # 既存コードをコピー
├── requirements.txt
└── Dockerfile
```

**main.py (新規作成)**:
```python
from starlette.applications import Starlette
from starlette.routing import Route
from api.routes import (
    stream_articles, get_recent_articles,
    get_kpi, get_categories, get_tone, get_top_entities
)

app = Starlette(
    debug=False,
    routes=[
        Route('/articles/stream', stream_articles),
        Route('/articles/recent', get_recent_articles),
        Route('/kpi', get_kpi),
        Route('/categories', get_categories),
        Route('/tone', get_tone),
        Route('/entities/top', get_top_entities),
    ]
)
```

**依存削除**:
```python
# 変更前
from utils.logging_config import get_logger

# 変更後
import logging
logger = logging.getLogger(__name__)
```

---

### 2. Docker構成の作成 (必須)

**docker-compose.yml (新規作成)**:
```yaml
version: '3.8'

services:
  neural-feed-backend:
    build: ./neural-feed-backend
    ports:
      - "8001:8000"
    environment:
      - OPENSEARCH_HOST=${OPENSEARCH_HOST}
      - OPENSEARCH_PORT=${OPENSEARCH_PORT}
      - OPENSEARCH_USERNAME=${OPENSEARCH_USERNAME}
      - OPENSEARCH_PASSWORD=${OPENSEARCH_PASSWORD}
      - NEURAL_FEED_SSE_INTERVAL=5
    depends_on:
      - opensearch
    restart: unless-stopped

  neural-feed-frontend:
    build: ./neural-feed-app
    ports:
      - "3100:80"
    environment:
      - VITE_API_BASE_URL=http://neural-feed-backend:8000
    depends_on:
      - neural-feed-backend
    restart: unless-stopped

  opensearch:
    image: opensearchproject/opensearch:2.11.0
    environment:
      - discovery.type=single-node
      - OPENSEARCH_INITIAL_ADMIN_PASSWORD=${OPENSEARCH_PASSWORD}
    ports:
      - "9200:9200"
    volumes:
      - opensearch-data:/usr/share/opensearch/data

volumes:
  opensearch-data:
```

**Dockerfile (バックエンド)**:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

### 3. 環境変数設定 (必須)

**.env.example**:
```bash
# OpenSearch接続
OPENSEARCH_HOST=opensearch
OPENSEARCH_PORT=9200
OPENSEARCH_USERNAME=admin
OPENSEARCH_PASSWORD=your_secure_password

# Neural Feed設定
NEURAL_FEED_SSE_INTERVAL=5

# フロントエンド
VITE_API_BASE_URL=http://localhost:8001
```

---

### 4. フロントエンドの接続先変更 (必須)

**neural-feed-app/src/lib/api.ts**:
```typescript
// 変更前
const API_BASE_URL = '/api/neural-feed';

// 変更後
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';
```

**nginx.conf**:
```nginx
server {
  listen 80;
  root /usr/share/nginx/html;
  index index.html;

  location / {
    try_files $uri $uri/ /index.html;
  }

  # バックエンドAPIへのプロキシ
  location /api/ {
    proxy_pass http://neural-feed-backend:8000/;
    proxy_buffering off;
    proxy_cache off;
    proxy_set_header Connection '';
    chunked_transfer_encoding on;
  }
}
```

---

## 🎯 移植戦略: 3つのオプション

### オプション1: OpenSearch継続使用 (推奨 ⭐)

**概要**: OpenSearchを読み取り専用で継続使用

**工数**: **3日**

**変更内容**:
1. バックエンドAPIを独立化 (1日)
2. Docker構成作成 (0.5日)
3. フロントエンド接続変更 (0.5日)
4. 統合テスト (1日)

**メリット**:
- 変更最小
- 既存のWatson News ETLパイプラインを活用
- OpenSearchの高速な集計クエリを継続使用
- リスク最小

**デメリット**:
- OpenSearchへの依存が残る

**適用ケース**:
- 新システムでもOpenSearchを使用している
- Watson News ETLパイプラインを継続使用する
- 早期に移植を完了したい

**アーキテクチャ**:
```
新システム
├── PostgreSQL (メインDB)
├── ベクターDB (RAG用)
└── OpenSearch (Neural Feed専用・読み取り専用)
     ↑
Watson News ETL (既存)
     ↑
Neural Feed Backend (独立)
     ↑
Neural Feed Frontend
```

---

### オプション2: PostgreSQL + ベクターDBに完全移行

**概要**: 新システムのDBに完全統合

**工数**: **6日**

**変更内容**:
1. バックエンドAPIを独立化 (1日)
2. PostgreSQLスキーマ設計 (1日)
3. データ移行スクリプト作成 (1日)
4. クエリをSQLに書き換え (1日)
5. フロントエンド接続変更 (0.5日)
6. 統合テスト (1.5日)

**メリット**:
- OpenSearch不要
- 新システムのDBに統合
- 一元管理

**デメリット**:
- 工数増加
- データ移行が必要
- 集計クエリのパフォーマンス調整が必要

**必要な作業**:

1. **PostgreSQLスキーマ設計**:
```sql
CREATE TABLE neural_feed_articles (
    id VARCHAR(255) PRIMARY KEY,
    title TEXT NOT NULL,
    domain VARCHAR(255),
    source_type VARCHAR(50),
    sentiment_label VARCHAR(20),
    sentiment_score FLOAT,
    topic VARCHAR(100),
    published TIMESTAMP WITH TIME ZONE,
    entities JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_published ON neural_feed_articles(published DESC);
CREATE INDEX idx_topic ON neural_feed_articles(topic);
CREATE INDEX idx_sentiment ON neural_feed_articles(sentiment_score);
CREATE INDEX idx_entities ON neural_feed_articles USING GIN(entities);
```

2. **クエリ変換例**:
```python
# OpenSearch → PostgreSQL

# 変更前 (OpenSearch)
RECENT_ARTICLES_QUERY = {
    "size": 15,
    "sort": [{"published": {"order": "desc"}}],
}

# 変更後 (PostgreSQL)
async def get_recent_articles():
    query = """
        SELECT id, title, domain, source_type,
               sentiment_label, sentiment_score, topic, published
        FROM neural_feed_articles
        ORDER BY published DESC
        LIMIT 15
    """
    return await db.fetch_all(query)
```

3. **データアダプターレイヤー**:
```python
# api/data_adapter.py
from abc import ABC, abstractmethod

class DataAdapter(ABC):
    @abstractmethod
    async def get_recent_articles(self): pass
    
    @abstractmethod
    async def get_categories(self): pass

class OpenSearchAdapter(DataAdapter):
    # OpenSearch実装
    pass

class PostgreSQLAdapter(DataAdapter):
    # PostgreSQL実装
    pass

# 環境変数で切り替え
adapter = OpenSearchAdapter() if USE_OPENSEARCH else PostgreSQLAdapter()
```

---

### オプション3: ハイブリッド構成

**概要**: 段階的な移行

**工数**: **4日**

**変更内容**:
1. バックエンドAPIを独立化 (1日)
2. データアダプターレイヤー実装 (1日)
3. PostgreSQL統合 (1日)
4. 統合テスト (1日)

**メリット**:
- 段階的な移行が可能
- リスク分散
- 柔軟性が高い

**デメリット**:
- 複雑性が増す
- 2つのDBを管理

**アーキテクチャ**:
```
新システムのPostgreSQL/ベクターDB
    ↓ (記事メタデータ)
Neural Feed Backend (データアダプター)
    ↓ (集計・可視化用)
OpenSearch (読み取り専用・段階的に廃止)
```

---

## 🗓️ 詳細実装計画

### 推奨: オプション1 (OpenSearch継続使用)

### Phase 1: バックエンドAPIの独立化 (1日)

#### タスク
```
□ neural-feed-backend/ ディレクトリ作成
  └── main.py (Starlette/FastAPIアプリ)
  └── api/
      ├── routes.py (既存コードを移植)
      ├── schemas.py (既存コードをコピー)
      └── opensearch_queries.py (既存コードをコピー)
  └── requirements.txt
  └── Dockerfile

□ OpenRAG依存の削除
  - utils.logging_config → 標準loggingに置き換え
  - 環境変数を.envファイルで管理

□ 動作確認
  - 単体でAPIサーバーが起動すること
  - OpenSearchに接続できること
  - 全エンドポイントが正常に応答すること
```

#### 成果物
- 独立したバックエンドAPIサーバー
- requirements.txt
- Dockerfile

---

### Phase 2: Docker構成の作成 (0.5日)

#### タスク
```
□ docker-compose.yml 作成
  - neural-feed-backend サービス
  - neural-feed-frontend サービス
  - opensearch サービス

□ Dockerfile作成
  - バックエンド: Python 3.11 + Starlette
  - フロントエンド: Node 20 + Nginx (既存を流用)

□ 環境変数設定
  - .env.example 作成
  - OpenSearch接続情報
  - SSEポーリング間隔

□ 動作確認
  - docker-compose up で全サービスが起動
  - サービス間通信が正常
```

#### 成果物
- docker-compose.yml
- .env.example
- README.md (セットアップ手順)

---

### Phase 3: フロントエンドの接続先変更 (0.5日)

#### タスク
```
□ neural-feed-app/src/lib/api.ts
  - API_BASE_URL を環境変数から取得
  - 新バックエンドのエンドポイントに接続

□ nginx.conf 更新
  - プロキシ先を neural-feed-backend に変更

□ vite.config.ts 更新
  - 環境変数の読み込み設定

□ 動作確認
  - SSEストリームが正常に動作
  - REST APIが正常に動作
  - Three.jsグラフが正常に描画
```

#### 成果物
- 更新されたフロントエンド設定
- 動作確認済みのアプリケーション

---

### Phase 4: 統合テスト (1日)

#### タスク
```
□ エンドツーエンドテスト
  - docker-compose up で全サービスが起動
  - フロントエンドがバックエンドに接続
  - OpenSearchからデータを取得
  - リアルタイム更新が動作

□ パフォーマンステスト
  - 60fps維持確認 (500ノード)
  - 8時間連続稼働テスト
  - メモリリーク確認

□ フォールバックテスト
  - OpenSearch停止時のモックデータ動作確認
  - API障害時の自動復旧確認

□ ドキュメント作成
  - README.md (セットアップ手順)
  - MIGRATION.md (移行手順)
  - TROUBLESHOOTING.md (トラブルシューティング)
```

#### 成果物
- テスト完了報告書
- 完全なドキュメント
- 本番デプロイ可能なシステム

---

## 📦 最終成果物

### 1. 独立したNeural Feedシステム

```
neural-feed-system/
├── neural-feed-backend/
│   ├── main.py
│   ├── api/
│   │   ├── routes.py
│   │   ├── schemas.py
│   │   └── opensearch_queries.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── neural-feed-app/
│   ├── src/
│   ├── vite.config.ts
│   ├── package.json
│   ├── Dockerfile
│   └── nginx.conf
│
├── docker-compose.yml
├── .env.example
├── README.md
├── MIGRATION.md
└── TROUBLESHOOTING.md
```

### 2. ドキュメント

#### README.md
```markdown
# Neural Feed System

## 概要
Watson Newsの記事をリアルタイムで可視化するLEDスクリーン専用アプリケーション

## セットアップ
1. 環境変数設定: `cp .env.example .env`
2. 起動: `docker-compose up -d`
3. アクセス: http://localhost:3100

## システム要件
- Docker 20.10+
- Docker Compose 2.0+
- OpenSearch 2.11+
```

#### MIGRATION.md
```markdown
# OpenRAGからの移行手順

## 前提条件
- OpenSearchが稼働していること
- watson_news_enriched インデックスが存在すること

## 移行手順
1. バックエンドAPIの独立化
2. Docker構成の作成
3. 環境変数の設定
4. 動作確認

## 新システムへの統合
- オプションA: 完全独立運用
- オプションB: 新システムに統合
- オプションC: データソース統合
```

---

## 🔧 新システムへの統合方法

### オプションA: 完全独立運用

**デプロイ構成**:
```
新システム (別サーバー)
├── PostgreSQL
├── ベクターDB
├── アプリケーション
└── フロントエンド

Neural Feed (専用サーバー)
├── neural-feed-backend:8001
├── neural-feed-frontend:3100
└── opensearch:9200
```

**メリット**:
- 完全に独立
- 新システムへの影響なし
- 個別にスケール可能

**デメリット**:
- サーバーリソースが別途必要

---

### オプションB: 新システムに統合

**デプロイ構成**:
```yaml
# 新システムのdocker-compose.ymlに追加
services:
  # 既存サービス
  postgres:
    ...
  vector-db:
    ...
  your-backend:
    ...
  your-frontend:
    ...
  
  # Neural Feed追加
  neural-feed-backend:
    build: ./neural-feed-backend
    ports:
      - "8001:8000"
    depends_on:
      - opensearch
  
  neural-feed-frontend:
    build: ./neural-feed-app
    ports:
      - "3100:80"
    depends_on:
      - neural-feed-backend
  
  opensearch:
    image: opensearchproject/opensearch:2.11.0
    ...
```

**メリット**:
- 一元管理
- リソース共有
- ネットワーク統合

**デメリット**:
- docker-composeが複雑化

---

### オプションC: データソース統合

**実装例**:
```python
# neural-feed-backend/api/data_adapter.py

from abc import ABC, abstractmethod
from typing import List
import os

class DataAdapter(ABC):
    """データソース抽象化レイヤー"""
    
    @abstractmethod
    async def get_recent_articles(self) -> List[dict]:
        pass
    
    @abstractmethod
    async def get_categories(self) -> dict:
        pass
    
    @abstractmethod
    async def get_tone(self) -> dict:
        pass

class OpenSearchAdapter(DataAdapter):
    """OpenSearch実装"""
    
    async def get_recent_articles(self):
        # 既存のOpenSearchクエリ
        pass

class PostgreSQLAdapter(DataAdapter):
    """PostgreSQL実装"""
    
    async def get_recent_articles(self):
        query = """
            SELECT id, title, domain, source_type,
                   sentiment_label, sentiment_score, topic, published
            FROM neural_feed_articles
            ORDER BY published DESC
            LIMIT 15
        """
        return await db.fetch_all(query)

# 環境変数で切り替え
def get_adapter() -> DataAdapter:
    adapter_type = os.getenv("DATA_ADAPTER", "opensearch")
    if adapter_type == "postgresql":
        return PostgreSQLAdapter()
    return OpenSearchAdapter()
```

**メリット**:
- 段階的な移行が可能
- 柔軟性が高い
- テストが容易

**デメリット**:
- 実装が複雑
- 2つのDBを管理

---

## ⚠️ 注意事項と推奨事項

### 1. データスキーマの互換性

新システムのDBスキーマが以下のフィールドを持つことを確認:

**必須フィールド**:
```json
{
  "id": "string",
  "title": "string",
  "domain": "string",
  "source_type": "string",
  "sentiment_label": "POSITIVE | NEUTRAL | NEGATIVE",
  "sentiment_score": "float (-1.0 ~ 1.0)",
  "topic": "string",
  "published": "ISO 8601 datetime"
}
```

**オプションフィールド**:
```json
{
  "entities": [
    {
      "text": "string",
      "type": "PERSON | ORG | LOCATION"
    }
  ]
}
```

---

### 2. リアルタイム更新の実装

#### OpenSearchの場合
```python
# SSEポーリング (5秒間隔)
async def stream_articles():
    while True:
        new_articles = await query_new_articles()
        for article in new_articles:
            yield article
        await asyncio.sleep(5)
```

#### PostgreSQLの場合
```python
# LISTEN/NOTIFY
async def stream_articles():
    conn = await asyncpg.connect(...)
    await conn.add_listener('new_article', callback)
    
    # または定期ポーリング
    while True:
        new_articles = await query_new_articles()
        for article in new_articles:
            yield article
        await asyncio.sleep(5)
```

---

### 3. パフォーマンス考慮事項

#### OpenSearchの場合
- 集計クエリが高速
- インデックス最適化済み
- スケーラブル

#### PostgreSQLの場合
- 適切なインデックスが必要:
```sql
CREATE INDEX idx_published ON articles(published DESC);
CREATE INDEX idx_topic ON articles(topic);
CREATE INDEX idx_sentiment ON articles(sentiment_score);
CREATE INDEX idx_entities ON articles USING GIN(entities);
```

- パーティショニング検討:
```sql
CREATE TABLE articles (
    ...
) PARTITION BY RANGE (published);

CREATE TABLE articles_2026_01 PARTITION OF articles
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
```

---

### 4. セキュリティ

#### OpenSearch
```yaml
environment:
  - OPENSEARCH_USERNAME=admin
  - OPENSEARCH_PASSWORD=${OPENSEARCH_PASSWORD}
  - OPENSEARCH_SSL_VERIFY=false  # 開発環境のみ
```

#### PostgreSQL
```yaml
environment:
  - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
  - POSTGRES_SSL_MODE=require  # 本番環境
```

---

### 5. モニタリング

#### 推奨メトリクス
```
- API応答時間
- SSE接続数
- OpenSearch/PostgreSQLクエリ時間
- フロントエンドFPS
- メモリ使用量
- エラーレート
```

#### ヘルスチェック
```python
# /health エンドポイント
@app.route('/health')
async def health_check():
    return {
        "status": "healthy",
        "opensearch": await check_opensearch(),
        "version": "1.0.0"
    }
```

---

## 📊 工数見積もり詳細

### オプション1: OpenSearch継続使用

| フェーズ | タスク | 工数 | 担当 |
|---------|--------|------|------|
| Phase 1 | バックエンドAPI独立化 | 1日 | バックエンド |
| Phase 2 | Docker構成作成 | 0.5日 | DevOps |
| Phase 3 | フロントエンド接続変更 | 0.5日 | フロントエンド |
| Phase 4 | 統合テスト | 1日 | QA |
| **合計** | | **3日** | |

### オプション2: PostgreSQL完全移行

| フェーズ | タスク | 工数 | 担当 |
|---------|--------|------|------|
| Phase 1 | バックエンドAPI独立化 | 1日 | バックエンド |
| Phase 2 | PostgreSQLスキーマ設計 | 1日 | DB |
| Phase 3 | データ移行スクリプト | 1日 | バックエンド |
| Phase 4 | クエリSQL変換 | 1日 | バックエンド |
| Phase 5 | フロントエンド接続変更 | 0.5日 | フロントエンド |
| Phase 6 | 統合テスト | 1.5日 | QA |
| **合計** | | **6日** | |

### オプション3: ハイブリッド構成

| フェーズ | タスク | 工数 | 担当 |
|---------|--------|------|------|
| Phase 1 | バックエンドAPI独立化 | 1日 | バックエンド |
| Phase 2 | データアダプター実装 | 1日 | バックエンド |
| Phase 3 | PostgreSQL統合 | 1日 | バックエンド |
| Phase 4 | 統合テスト | 1日 | QA |
| **合計** | | **4日** | |

---

## ✅ チェックリスト

### 移植前の確認事項

```
□ OpenSearchが稼働している
□ watson_news_enriched インデックスが存在する
□ 必要なフィールドがすべて存在する
□ 新システムの要件を理解している
□ 移植戦略を決定している
```

### 移植中の確認事項

```
□ バックエンドAPIが独立して動作する
□ OpenSearchに接続できる
□ 全エンドポイントが正常に応答する
□ SSEストリームが動作する
□ フロントエンドがバックエンドに接続できる
□ Three.jsグラフが正常に描画される
```

### 移植後の確認事項

```
□ 60fps維持 (500ノード)
□ 8時間連続稼働
□ メモリリークなし
□ エラーハンドリング動作
□ フォールバック動作
□ ドキュメント完備
```

---

## 🎯 結論

### OpenRAG依存度: **10-15% (非常に低い)**

Neural Feedは設計段階から**高い独立性**を持ち、OpenRAGへの依存は最小限です。

### 移植可能性: **95% (非常に高い)**

バックエンドAPIを独立化するだけで、別システムへの移植が可能です。

### 推奨移植戦略

**短期 (3日)**:
- バックエンドAPIを独立化
- OpenSearchを継続使用
- 最小限の変更で移植完了

**中長期 (必要に応じて)**:
- 新システムのDB統合を検討
- データアダプターレイヤーで抽象化
- 段階的な移行

### 次のステップ

1. 移植戦略の決定 (オプション1/2/3)
2. 実装計画の承認
3. Phase 1の開始
4. 段階的な実装とテスト

---

**作成者**: AI Assistant  
**最終更新**: 2026-02-27  
**バージョン**: 1.0