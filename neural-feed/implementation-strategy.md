# NEURAL FEED — 実装方針書

> 作成日: 2026-02-22
> 最終更新: 2026-02-22
> ブランチ: `claude/neural-feed-led-app-wZivB`
> 要件定義書: `neural-feed/requirements.md`

---

## 1. 基本方針

### 1.1 独立したWebアプリケーションとして設計する

NEURAL FEED は Watson News RAG UI とは**完全に独立したWebアプリ**として実装する。
データソース（OpenSearch）のみを共有し、UIフレームワーク・ビルドシステム・デプロイ単位はすべて分離する。

| 項目 | Watson News RAG UI | NEURAL FEED |
|---|---|---|
| フレームワーク | Next.js 15 | **Vite + React 18** |
| デザインシステム | IBM Carbon Design System | カスタム（ダーク・近未来テーマ） |
| スタイリング | Tailwind CSS / Carbon | **CSS Modules + CSS Custom Properties** |
| ルーティング | Next.js App Router | 単一ページ（SPAルーティング不要） |
| デプロイ | Next.js サーバー | **Nginx 静的配信** |

Vite を採用する理由:
- 静的ビルド（`vite build`）で Nginx 配信できる → サーバーサイドレンダリング不要
- 開発時のHMRが高速でグラフ描画コードの調整サイクルを短くできる
- Three.js・d3-force などの大きなライブラリのバンドル最適化（tree-shaking）が効く

### 1.2 既存openRAGバックエンドを拡張してAPIを追加する

新規バックエンドサーバーは立てず、既存の **Starlette バックエンド**（`src/main.py`）に NEURAL FEED 専用の読み取りAPIルートを追加する。

```
openRAG Starlette Backend（既存）
    ├── /api/documents/...     ← 既存
    ├── /api/search/...        ← 既存
    └── /api/neural-feed/...   ← 新規追加
```

### 1.3 Watson NLPはデータソース経由で活用する

Watson NLP の解析結果（エンティティ・センチメント・トピック分類）は、**Watson News ETL パイプラインがすでに `watson_news_enriched` インデックスに格納**している。
NEURAL FEED バックエンドはこのインデックスを読み取るだけであり、Watson NLP SDK を直接呼び出す実装は原則不要。

```
Watson NLP Container
       ↓（Watson News ETLが処理）
OpenSearch: watson_news_enriched
       ↓（NEURAL FEED バックエンドが読み取り）
/api/neural-feed/* エンドポイント
       ↓（SSE / REST）
NEURAL FEED フロントエンド（Three.js 可視化）
```

ただし将来的に「処理中ステータス」のリアルタイム反映が必要になった場合は、Watson News ETL 側にステータス通知フックを追加する（NEURAL FEEDから直接 Watson NLP を呼び出すのではなく）。

---

## 2. ディレクトリ構成

```
openrag/
├── neural-feed/                         ← ドキュメント
│   ├── requirements.md
│   └── implementation-strategy.md      ← 本ファイル
│
├── neural-feed-app/                     ← フロントエンドアプリ（新規）
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── package.json
│   └── src/
│       ├── main.tsx                     # エントリポイント
│       ├── App.tsx                      # ルートコンポーネント
│       ├── styles/
│       │   ├── global.css               # CSS Custom Properties・全画面スタイル
│       │   └── safe-area.css            # セーフエリア制御
│       ├── components/
│       │   ├── layout/
│       │   │   ├── FullscreenCanvas.tsx # 7680×2160 背景レイヤー（パーティクル）
│       │   │   └── SafeAreaContainer.tsx # 7680×1890 コンテンツレイヤー
│       │   ├── left-panel/
│       │   │   ├── LeftPanel.tsx
│       │   │   ├── PipelineStep.tsx     # 1ステップ（状態・ラベル・アニメーション）
│       │   │   ├── PipelineFlow.tsx     # 7ステップリスト
│       │   │   └── KpiMetrics.tsx       # スループット・接続状態など
│       │   ├── center-panel/
│       │   │   ├── CenterPanel.tsx
│       │   │   ├── NeuralGraph.tsx      # Three.js マウントポイント
│       │   │   ├── graphEngine.ts       # Three.js シーン・カメラ・レンダラー
│       │   │   ├── nodeManager.ts       # ノード追加・削除・発火アニメーション
│       │   │   ├── edgeManager.ts       # エッジ・シグナルドット
│       │   │   ├── forceSimulation.ts   # d3-force レイアウト
│       │   │   └── fallingLabels.ts     # フォーリングラベル（CSS Animations）
│       │   └── right-panel/
│       │       ├── RightPanel.tsx
│       │       ├── ArticleQueue.tsx     # 記事キューリスト
│       │       ├── ArticleCard.tsx      # 1記事カード（処理状態・センチメント）
│       │       ├── CategoryBar.tsx      # トピック別割合バー
│       │       └── ToneGauge.tsx        # Global Tone Index ゲージ
│       ├── hooks/
│       │   ├── useArticleStream.ts      # SSE でリアルタイム記事受信
│       │   ├── useKpiMetrics.ts         # KPI ポーリング（10秒間隔）
│       │   ├── usePipelineState.ts      # パイプラインステートマシン
│       │   └── useAudio.ts              # Tone.js 音響制御
│       ├── store/
│       │   └── neuralFeedStore.ts       # Zustand ストア（グローバル状態）
│       └── lib/
│           ├── api.ts                   # バックエンドAPI クライアント
│           └── mockData.ts              # フォールバック用モックデータ
│
└── src/
    └── api/
        └── neural_feed/                 ← バックエンドAPI（新規追加）
            ├── __init__.py
            ├── routes.py                # Starlette ルート定義
            ├── schemas.py               # Pydantic スキーマ
            └── opensearch_queries.py    # OpenSearch クエリ定義
```

---

## 3. フロントエンド実装方針

### 3.1 技術スタック

| ライブラリ | バージョン | 用途 |
|---|---|---|
| React | 18.x | UIコンポーネント |
| TypeScript | 5.x | 型安全性 |
| Vite | 5.x | バンドラー・開発サーバー |
| Three.js | r165+ | WebGL 3Dニューラルグラフ描画 |
| d3-force | 3.x | ノードの物理演算レイアウト |
| Tone.js | 14.x | 音響演出 |
| Zustand | 4.x | グローバル状態管理（軽量） |
| SWR | 2.x | REST ポーリング（KPIメトリクス） |

### 3.2 レイヤー構造と描画戦略

```
Z-index レイヤー構成（前面 → 背面）

z-index: 30  フォーリングラベル（CSS アニメーション DOM要素）
z-index: 20  UIパネル（左・右）                DOM
z-index: 10  Three.js Canvas（ニューラルグラフ） WebGL
z-index:  1  パーティクル背景                  Canvas 2D
z-index:  0  黒背景（body）
```

中央パネルの Three.js キャンバスはセーフエリア全体（3840 × 1890px）を占有する。左右パネルはその上にオーバーレイとして配置する（`position: absolute`）。

### 3.3 ニューラルグラフ実装（Three.js + d3-force）

#### 3.3.1 シーン構成

```typescript
// graphEngine.ts

const GRAPH_WIDTH  = 3840;  // 中央パネル幅（px）
const GRAPH_HEIGHT = 1890;  // セーフエリア高さ（px）
const CAMERA_FOV   = 60;

// シーン初期化
const scene    = new THREE.Scene();
const camera   = new THREE.PerspectiveCamera(CAMERA_FOV, GRAPH_WIDTH / GRAPH_HEIGHT, 1, 5000);
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setSize(GRAPH_WIDTH, GRAPH_HEIGHT);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));  // 高DPIで描画負荷を抑制
```

#### 3.3.2 ノード描画（InstancedMesh）

500ノードを60fpsで描画するため、`THREE.InstancedMesh` を使用する。
個別の `Mesh` を500個作成するより描画コールを1回に集約できる。

```typescript
// nodeManager.ts

const SPHERE_GEOMETRY = new THREE.SphereGeometry(8, 16, 16);
const NODE_MATERIAL   = new THREE.MeshBasicMaterial({ color: 0xffffff });

// 最大500ノードを1つの InstancedMesh で管理
const instancedMesh = new THREE.InstancedMesh(SPHERE_GEOMETRY, NODE_MATERIAL, 500);
scene.add(instancedMesh);

// 各ノードの位置・カラーを行列で更新
function updateNodeMatrix(index: number, x: number, y: number, z: number, color: THREE.Color) {
  const matrix = new THREE.Matrix4();
  matrix.setPosition(x, y, z);
  instancedMesh.setMatrixAt(index, matrix);
  instancedMesh.setColorAt(index, color);
  instancedMesh.instanceMatrix.needsUpdate = true;
  instancedMesh.instanceColor!.needsUpdate = true;
}
```

#### 3.3.3 d3-force レイアウト

```typescript
// forceSimulation.ts
import * as d3 from 'd3-force';

const simulation = d3.forceSimulation(nodes)
  .force('link',   d3.forceLink(edges).id(d => d.id).distance(120))
  .force('charge', d3.forceManyBody().strength(-80))
  .force('center', d3.forceCenter(0, 0))
  .force('collision', d3.forceCollide(20))
  .alphaDecay(0.01)   // ゆっくり安定させる（動きを長く残す）
  .on('tick', () => {
    // d3の計算結果を Three.js の instancedMesh 位置へ反映
    nodes.forEach((node, i) => updateNodeMatrix(i, node.x, node.y, 0, node.color));
  });
```

#### 3.3.4 シグナルドット（エッジアニメーション）

エッジ上を動くシグナルドットは Three.js の `Line` ではなく、
`THREE.Points`（ポイントスプライト）を使ってエッジに沿って位置を補間する。

```typescript
// edgeManager.ts

// 各エッジに対してシグナルドットの t（0→1）を管理
const signalDots: Map<string, { t: number; speed: number }> = new Map();

function animateSignals(delta: number) {
  signalDots.forEach((dot, edgeId) => {
    dot.t = (dot.t + dot.speed * delta) % 1.0;
    const edge = edgeMap.get(edgeId)!;
    const pos  = lerpVec3(edge.source.position, edge.target.position, dot.t);
    updateDotPosition(edgeId, pos);
  });
}
```

#### 3.3.5 フォーリングラベル

3D空間内でのテキスト描画（`THREE.TextGeometry`）はWebGLのフォントロードが重いため、
**CSSアニメーションのDOM要素**として実装し、Three.js キャンバスの上にオーバーレイする。

```typescript
// fallingLabels.ts

function spawnFallingLabel(text: string, color: string, x: number) {
  const el = document.createElement('div');
  el.className = 'falling-label';
  el.textContent = text + '▼';
  el.style.left = `${x}px`;
  el.style.color = color;
  el.style.setProperty('--fall-duration', `${2 + Math.random() * 2}s`);
  document.getElementById('falling-labels-container')!.appendChild(el);
  el.addEventListener('animationend', () => el.remove());
}
```

```css
/* global.css */
.falling-label {
  position: absolute;
  top: -60px;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 28px;
  font-weight: 700;
  letter-spacing: 0.1em;
  pointer-events: none;
  animation: fall var(--fall-duration) linear forwards;
}

@keyframes fall {
  from { transform: translateY(0);    opacity: 1; }
  80%  { opacity: 1; }
  to   { transform: translateY(1950px); opacity: 0; }
}
```

#### 3.3.6 カメラ自動回転

```typescript
// graphEngine.ts

const ORBIT_RADIUS = 1200;
const ORBIT_SPEED  = 0.0003; // rad/ms

let theta = 0;
function rotateCameraOrbit(delta: number) {
  theta += ORBIT_SPEED * delta;
  camera.position.set(
    Math.sin(theta) * ORBIT_RADIUS,
    200,                              // 俯角を少しつける
    Math.cos(theta) * ORBIT_RADIUS,
  );
  camera.lookAt(0, 0, 0);
}
```

### 3.4 状態管理（Zustand）

```typescript
// store/neuralFeedStore.ts

interface NeuralFeedStore {
  // 記事キュー
  articleQueue:    Article[];
  addArticle:      (article: Article) => void;

  // パイプライン状態
  pipelineSteps:   PipelineStep[];
  setPipelineStep: (stepId: number, status: StepStatus) => void;

  // KPIメトリクス
  kpi:             KpiMetrics;
  setKpi:          (kpi: KpiMetrics) => void;

  // ニューラルグラフ用ノードキュー
  pendingNodes:    NodeData[];
  consumeNodes:    () => NodeData[];

  // オーディオ
  audioEnabled:    boolean;
  toggleAudio:     () => void;
}
```

### 3.5 パイプラインステートマシン

パイプラインの7ステップは、新規記事受信イベントをトリガーとしてステートマシンが駆動する。
実際の Watson NLP 処理ステータスを取得するのではなく、**OpenSearch の enriched データ完成を検知したタイミングで各ステップをアニメーション的に進行させる**。

```typescript
// hooks/usePipelineState.ts

const STEP_DURATIONS_MS = [300, 200, 800, 600, 700, 500, 200]; // 各ステップの演出時間

async function simulatePipelineForArticle(articleId: string, dispatch) {
  for (let i = 0; i < 7; i++) {
    dispatch({ type: 'SET_STEP_ACTIVE', stepIndex: i });
    await delay(STEP_DURATIONS_MS[i]);
    dispatch({ type: 'SET_STEP_DONE', stepIndex: i });
  }
  // ステップ7完了後、ニューラルグラフにノードを追加
  dispatch({ type: 'ADD_NODE', articleId });
}
```

### 3.6 音響演出（Tone.js）

```typescript
// hooks/useAudio.ts
import * as Tone from 'tone';

const synth = new Tone.Synth({
  oscillator: { type: 'sine' },
  envelope: { attack: 0.01, decay: 0.3, sustain: 0, release: 0.2 },
}).toDestination();

export function playNodeFire(clusterIndex: number) {
  const notes = ['C2','D2','E2','G2','A2','B2','C3'];
  synth.triggerAttackRelease(notes[clusterIndex % notes.length], '16n');
}
```

デフォルトはミュート（`Tone.getDestination().mute = true`）。
URL パラメータ `?audio=1` または管理者パネルで有効化する。

---

## 4. バックエンドAPI実装方針

### 4.1 新規追加エンドポイント（Starlette）

```
src/api/neural_feed/routes.py
```

| Method | Path | 説明 | データソース |
|---|---|---|---|
| `GET` | `/api/neural-feed/articles/stream` | SSE: 新規記事を即時プッシュ | OpenSearch（ポーリング/変更検知） |
| `GET` | `/api/neural-feed/kpi` | KPIメトリクス（スループット・件数など） | OpenSearch aggregation |
| `GET` | `/api/neural-feed/articles/recent` | 直近N件の記事リスト | `watson_news_enriched` |
| `GET` | `/api/neural-feed/categories` | トピック別件数の集計 | `watson_news_enriched` |
| `GET` | `/api/neural-feed/tone` | Global Tone Index（平均 sentiment_score） | `watson_news_enriched` |
| `GET` | `/api/neural-feed/entities/top` | トップエンティティ Top N | `watson_news_enriched` |

### 4.2 SSE エンドポイント設計

```python
# src/api/neural_feed/routes.py

from starlette.responses import EventSourceResponse
import asyncio

async def stream_new_articles(request):
    """
    OpenSearch を5秒ごとにポーリングし、
    前回取得より新しい記事を SSE でプッシュする。
    """
    last_seen_id = None

    async def event_generator():
        nonlocal last_seen_id
        while True:
            articles = await query_new_articles_since(last_seen_id)
            for article in articles:
                yield {
                    "event": "new_article",
                    "data": article.model_dump_json(),
                }
                last_seen_id = article.id
            await asyncio.sleep(5)

    return EventSourceResponse(event_generator())
```

### 4.3 OpenSearchクエリ（主要なもの）

```python
# src/api/neural_feed/opensearch_queries.py

RECENT_ARTICLES_QUERY = {
    "size": 15,
    "sort": [{"published": {"order": "desc"}}],
    "_source": ["id", "title", "domain", "source_type",
                "sentiment_label", "sentiment_score", "topic", "published"],
}

CATEGORY_AGGREGATION_QUERY = {
    "size": 0,
    "query": {"range": {"published": {"gte": "now-1h"}}},
    "aggs": {
        "by_topic": {
            "terms": {"field": "topic.keyword", "size": 10}
        }
    },
}

GLOBAL_TONE_QUERY = {
    "size": 0,
    "query": {"range": {"published": {"gte": "now-1h"}}},
    "aggs": {
        "avg_sentiment": {"avg": {"field": "sentiment_score"}}
    },
}

TOP_ENTITIES_QUERY = {
    "size": 0,
    "query": {"range": {"published": {"gte": "now-15m"}}},
    "aggs": {
        "top_entities": {
            "nested": {"path": "entities"},
            "aggs": {
                "entity_names": {
                    "terms": {"field": "entities.text.keyword", "size": 5}
                }
            }
        }
    },
}
```

### 4.4 既存 main.py へのルート登録

```python
# src/main.py への追加（既存コードへの変更最小化）

from api.neural_feed.routes import neural_feed_router

# 既存ルーターマウントの後に追加
app.mount("/api/neural-feed", neural_feed_router)
```

### 4.5 フォールバック（APIなし時のデモモード）

```typescript
// lib/mockData.ts

// API接続失敗時に自動的に使用するモックデータジェネレーター
export function startMockArticleStream(callback: (article: Article) => void) {
  const titles = [
    "IBM Announces New Quantum Computing Milestone",
    "watsonx.ai Updates: Enhanced RAG Capabilities",
    "IBM Cloud Security Report 2026",
    // ...
  ];
  setInterval(() => {
    const article = generateMockArticle(titles);
    callback(article);
  }, 3000 + Math.random() * 5000);
}
```

---

## 5. スタイリング方針

### 5.1 カラーシステム（CSS Custom Properties）

```css
/* styles/global.css */

:root {
  /* ベースカラー */
  --color-bg:         #000000;
  --color-surface:    #0a0a0f;
  --color-border:     rgba(255, 255, 255, 0.08);

  /* アクセントカラー */
  --color-blue:       #0f62fe;  /* IBM Blue */
  --color-cyan:       #33b1ff;
  --color-green:      #42be65;
  --color-orange:     #ff832b;
  --color-red:        #fa4d56;
  --color-purple:     #d4bbff;
  --color-yellow:     #f1c21b;

  /* クラスターカラー（ニューラルグラフ） */
  --cluster-input:     #6fdc8c;
  --cluster-parse:     #82cfff;
  --cluster-sentiment: #ffafd2;
  --cluster-topic:     #d4bbff;
  --cluster-entity:    #ffd6a5;
  --cluster-conflict:  #ff8389;
  --cluster-output:    #ffffff;

  /* タイポグラフィ */
  --font-mono:  'IBM Plex Mono', 'Courier New', monospace;
  --font-sans:  'IBM Plex Sans', system-ui, sans-serif;

  /* 7680px横スクリーン用フォントスケール */
  --font-size-xs:  20px;
  --font-size-sm:  24px;
  --font-size-md:  32px;
  --font-size-lg:  48px;
  --font-size-xl:  72px;
  --font-size-2xl: 120px;
}
```

### 5.2 フォント

`IBM Plex Mono`（モノスペース）を全体的に使用し、端末・ターミナル的な近未来感を演出する。
Google Fonts CDN または self-hosted フォントファイルで読み込む。

### 5.3 グロー・発光エフェクト

CSS `box-shadow` + `filter: blur()` + `text-shadow` の組み合わせでネオン発光を表現する。
WebGL のポストプロセス（bloom）は描画コストが高いため、UIパネル部分は CSS で代替する。

```css
/* 発光テキスト */
.glow-text {
  text-shadow: 0 0 10px currentColor, 0 0 30px currentColor;
}

/* 発光ボーダー（アクティブ記事カード） */
.article-card--active {
  border-left: 3px solid var(--color-blue);
  box-shadow: -4px 0 20px var(--color-blue);
}
```

---

## 6. Dockerコンテナ設計

### 6.1 マルチステージビルド

```dockerfile
# neural-feed-app/Dockerfile

# --- Build Stage ---
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build
# → /app/dist/ に静的ファイル生成

# --- Production Stage ---
FROM nginx:1.27-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

### 6.2 Nginx設定

```nginx
# neural-feed-app/nginx.conf

server {
  listen 80;
  root /usr/share/nginx/html;
  index index.html;

  # SPA フォールバック
  location / {
    try_files $uri $uri/ /index.html;
  }

  # バックエンドAPIへのリバースプロキシ
  location /api/neural-feed/ {
    proxy_pass http://openrag-backend:8000;
    proxy_buffering off;             # SSE に必要
    proxy_cache off;
    proxy_set_header Connection '';  # SSE の keep-alive
    chunked_transfer_encoding on;
  }
}
```

### 6.3 docker-compose への追加

```yaml
# docker-compose.yml への追加

neural-feed:
  build:
    context: ./neural-feed-app
    dockerfile: Dockerfile
  ports:
    - "3100:80"
  environment:
    - VITE_API_BASE_URL=/api
  depends_on:
    - openrag-backend
  restart: unless-stopped
```

---

## 7. 依存パッケージ

### 7.1 フロントエンド（neural-feed-app/package.json）

```json
{
  "dependencies": {
    "react":          "^18.3.0",
    "react-dom":      "^18.3.0",
    "three":          "^0.165.0",
    "d3-force":       "^3.0.0",
    "tone":           "^14.7.0",
    "zustand":        "^4.5.0",
    "swr":            "^2.2.0"
  },
  "devDependencies": {
    "@types/react":   "^18.3.0",
    "@types/three":   "^0.165.0",
    "@types/d3-force":"^3.0.0",
    "typescript":     "^5.4.0",
    "vite":           "^5.2.0",
    "@vitejs/plugin-react": "^4.2.0"
  }
}
```

### 7.2 バックエンド追加依存（pyproject.toml）

```toml
# SSE レスポンス（starlette-sse または sse-starlette）
sse-starlette = ">=1.8"
```

---

## 8. パフォーマンス最適化方針

### 8.1 WebGL描画最適化

| 最適化 | 内容 |
|---|---|
| InstancedMesh | 500ノードを1ドローコールで描画 |
| LOD | カメラから遠いノードは低解像度ジオメトリに切替（`THREE.LOD`） |
| FrustumCulling | カメラ視錐台外のオブジェクトは自動スキップ（Three.js デフォルト） |
| アニメーションloop | `requestAnimationFrame` + delta time ベースの更新（固定フレームレートに依存しない） |
| テクスチャ圧縮 | パーティクルスプライトは WebP / KTX2 形式 |

### 8.2 メモリリーク対策（8時間連続稼働）

```typescript
// 古いノードの定期削除（上限500ノードを維持）
const MAX_NODES = 500;

function pruneOldNodes() {
  if (nodes.length > MAX_NODES) {
    const toRemove = nodes.splice(0, nodes.length - MAX_NODES);
    toRemove.forEach(n => scene.remove(n.mesh));
    // Three.js のジオメトリ・マテリアルを dispose して GPU メモリを解放
    toRemove.forEach(n => {
      n.mesh.geometry.dispose();
      (n.mesh.material as THREE.Material).dispose();
    });
  }
}

// フォーリングラベル DOM の定期クリーンアップ
// → アニメーション終了時に `animationend` イベントで自動削除（前述）
```

### 8.3 フォント・アセットのプリロード

```html
<!-- index.html -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preload" as="font" href="/fonts/IBMPlexMono-Regular.woff2" crossorigin>
<link rel="preload" as="font" href="/fonts/IBMPlexMono-Bold.woff2" crossorigin>
```

---

## 9. 実装フェーズ

### Phase 0 — 環境構築

- [ ] `neural-feed-app/` ディレクトリ作成・Vite + React + TypeScript 初期設定
- [ ] `package.json` 作成・依存パッケージインストール
- [ ] `Dockerfile` / `nginx.conf` 作成
- [ ] `docker-compose.yml` に `neural-feed` サービス追加
- [ ] バックエンドに `src/api/neural_feed/` ディレクトリ作成・空ルート登録
- [ ] 7680×2160px の基本レイアウト（セーフエリア）確認

### Phase 1 — バックエンドAPI + モックUI

- [ ] `opensearch_queries.py` 実装（5クエリ）
- [ ] REST エンドポイント実装（`/kpi`, `/articles/recent`, `/categories`, `/tone`, `/entities/top`）
- [ ] SSE エンドポイント実装（`/articles/stream`）
- [ ] フォールバック用モックデータ実装（`mockData.ts`）
- [ ] `useArticleStream.ts` / `useKpiMetrics.ts` Hooksの実装
- [ ] Zustand ストア実装（`neuralFeedStore.ts`）

### Phase 2 — 左パネル + 右パネル

- [ ] `PipelineFlow.tsx` / `PipelineStep.tsx` 実装（7ステップ・4状態アニメーション）
- [ ] `usePipelineState.ts` ステートマシン実装
- [ ] `KpiMetrics.tsx` 実装（スループット・接続状態）
- [ ] `ArticleQueue.tsx` / `ArticleCard.tsx` 実装（スクロール・光ボーダー）
- [ ] `CategoryBar.tsx` 実装（アニメーション付き横棒グラフ）
- [ ] `ToneGauge.tsx` 実装（スペクトルゲージ）
- [ ] エンティティカウンター・タグクラウド実装

### Phase 3 — 中央パネル（ニューラルグラフ）

- [ ] `graphEngine.ts`：Three.js シーン・カメラ・レンダラー初期化
- [ ] `nodeManager.ts`：InstancedMesh ノード追加・発火アニメーション
- [ ] `edgeManager.ts`：エッジ描画・シグナルドット
- [ ] `forceSimulation.ts`：d3-force レイアウト統合
- [ ] ハブノード（中央 Watson NLU Core Engine）の同心リング発光
- [ ] 7クラスター配置・カラーリング
- [ ] カメラ自動回転（公転アニメーション）
- [ ] `fallingLabels.ts`：フォーリングラベル（CSSアニメーション）

### Phase 4 — 音響 + 統合 + 最適化

- [ ] `useAudio.ts`（Tone.js）実装・ノード発火音
- [ ] パーティクル背景（Canvas 2D）実装
- [ ] 8時間連続稼働テスト・メモリリーク確認
- [ ] 60fps 達成確認（500ノード時）
- [ ] APIダウン時フォールバック動作確認
- [ ] 管理者設定パネル（`?admin=true`）実装（音量・速度調整）

---

## 10. リスクと対策

| リスク | 影響度 | 対策 |
|---|---|---|
| 7680px での Three.js パフォーマンス不足 | 高 | InstancedMesh・LOD を最初から採用。実機での早期プロファイリング必須 |
| GPU搭載PCがない環境での表示 | 中 | ノード数を動的に削減する自動LOD（`Stats.js` でFPS監視） |
| OpenSearch からのデータ遅延 | 中 | SSE polling間隔を5秒に設定。モックデータで常にアニメーションを動かす |
| 8時間連続でのメモリリーク | 高 | ノード数上限・DOM要素の `animationend` 削除・Three.js `dispose()` を徹底 |
| LEDスクリーンの実際の発色差異 | 低 | CSSカラー値はLEDパネルの実機で調整。設計時はHSL値を使い輝度調整しやすくする |
| SSE接続断（長時間稼働） | 中 | EventSource の `onerror` で自動再接続（指数バックオフ） |
