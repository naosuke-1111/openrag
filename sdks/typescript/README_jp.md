# OpenRAG TypeScript SDK

[OpenRAG](https://openr.ag) API の公式TypeScript/JavaScript SDKです。

## インストール

```bash
npm install openrag-sdk
# または
yarn add openrag-sdk
# または
pnpm add openrag-sdk
```

## クイックスタート

```typescript
import { OpenRAGClient } from "openrag-sdk";

// クライアントは環境変数からOPENRAG_API_KEYとOPENRAG_URLを自動検出
const client = new OpenRAGClient();

// シンプルなチャット
const response = await client.chat.create({ message: "What is RAG?" });
console.log(response.response);
console.log(`Chat ID: ${response.chatId}`);
```

## 設定

SDKは環境変数またはコンストラクタ引数で設定できます：

| 環境変数 | コンストラクタオプション | 説明 |
|---------------------|-------------------|-------------|
| `OPENRAG_API_KEY` | `apiKey` | 認証用APIキー（必須） |
| `OPENRAG_URL` | `baseUrl` | OpenRAGフロントエンドのベースURL（デフォルト：`http://localhost:3000`） |

```typescript
// 環境変数を使用
const client = new OpenRAGClient();

// 明示的な引数を使用
const client = new OpenRAGClient({
  apiKey: "orag_...",
  baseUrl: "https://api.example.com",
});
```

## チャット

### ストリームなし

```typescript
const response = await client.chat.create({ message: "What is RAG?" });
console.log(response.response);
console.log(`Chat ID: ${response.chatId}`);

// 会話を続ける
const followup = await client.chat.create({
  message: "Tell me more",
  chatId: response.chatId,
});
```

### `create({ stream: true })` を使用したストリーミング

非同期イテレータを直接返します：

```typescript
let chatId: string | null = null;
for await (const event of await client.chat.create({
  message: "Explain RAG",
  stream: true,
})) {
  if (event.type === "content") {
    process.stdout.write(event.delta);
  } else if (event.type === "sources") {
    for (const source of event.sources) {
      console.log(`\nSource: ${source.filename}`);
    }
  } else if (event.type === "done") {
    chatId = event.chatId;
  }
}
```

### `stream()` を使用したストリーミング

便利なヘルパーメソッドを提供します：

```typescript
// 全イベントのイテレーション
const stream = await client.chat.stream({ message: "Explain RAG" });
try {
  for await (const event of stream) {
    if (event.type === "content") {
      process.stdout.write(event.delta);
    }
  }

  // イテレーション後に集計データにアクセス
  console.log(`\nChat ID: ${stream.chatId}`);
  console.log(`Full text: ${stream.text}`);
  console.log(`Sources: ${stream.sources}`);
} finally {
  stream.close();
}

// テキストデルタのみ
const stream = await client.chat.stream({ message: "Explain RAG" });
try {
  for await (const text of stream.textStream) {
    process.stdout.write(text);
  }
} finally {
  stream.close();
}

// 最終テキストを直接取得
const stream = await client.chat.stream({ message: "Explain RAG" });
try {
  const text = await stream.finalText();
  console.log(text);
} finally {
  stream.close();
}
```

### 会話履歴

```typescript
// 全会話を一覧表示
const conversations = await client.chat.list();
for (const conv of conversations.conversations) {
  console.log(`${conv.chatId}: ${conv.title}`);
}

// メッセージ付きで特定の会話を取得
const conversation = await client.chat.get(chatId);
for (const msg of conversation.messages) {
  console.log(`${msg.role}: ${msg.content}`);
}

// 会話を削除
await client.chat.delete(chatId);
```

## 検索

```typescript
// 基本的な検索
const results = await client.search.query("document processing");
for (const result of results.results) {
  console.log(`${result.filename} (score: ${result.score})`);
  console.log(`  ${result.text.slice(0, 100)}...`);
}

// フィルター付き検索
const results = await client.search.query("API documentation", {
  filters: {
    data_sources: ["api-docs.pdf"],
    document_types: ["application/pdf"],
  },
  limit: 5,
  scoreThreshold: 0.5,
});
```

## ドキュメント

```typescript
// ファイルを取り込む（デフォルトで完了まで待機）
const result = await client.documents.ingest({
  filePath: "./report.pdf",
});
console.log(`Status: ${result.status}`);
console.log(`Successful files: ${result.successful_files}`);

// 待機せずに取り込む（task_idを持つ即時返却）
const result = await client.documents.ingest({
  filePath: "./report.pdf",
  wait: false,
});
console.log(`Task ID: ${result.task_id}`);

// 手動で完了をポーリング
const finalStatus = await client.documents.waitForTask(result.task_id);
console.log(`Status: ${finalStatus.status}`);
console.log(`Successful files: ${finalStatus.successful_files}`);

// Fileオブジェクトから取り込む（ブラウザ）
const file = new File([...], "report.pdf");
const result = await client.documents.ingest({
  file,
  filename: "report.pdf",
});

// ドキュメントを削除
const result = await client.documents.delete("report.pdf");
console.log(`Success: ${result.success}`);
```

## 設定

```typescript
// 設定を取得
const settings = await client.settings.get();
console.log(`LLM Provider: ${settings.agent.llm_provider}`);
console.log(`LLM Model: ${settings.agent.llm_model}`);
console.log(`Embedding Model: ${settings.knowledge.embedding_model}`);

// 設定を更新
await client.settings.update({
  chunk_size: 1000,
  chunk_overlap: 200,
});
```

## ナレッジフィルター

ナレッジフィルターは、チャットと検索操作に適用できる再利用可能な名前付きフィルター設定です。

```typescript
// ナレッジフィルターを作成
const result = await client.knowledgeFilters.create({
  name: "Technical Docs",
  description: "Filter for technical documentation",
  queryData: {
    query: "technical",
    filters: {
      document_types: ["application/pdf"],
    },
    limit: 10,
    scoreThreshold: 0.5,
  },
});
const filterId = result.id;

// フィルターを検索
const filters = await client.knowledgeFilters.search("Technical");
for (const filter of filters) {
  console.log(`${filter.name}: ${filter.description}`);
}

// 特定のフィルターを取得
const filter = await client.knowledgeFilters.get(filterId);

// フィルターを更新
await client.knowledgeFilters.update(filterId, {
  description: "Updated description",
});

// フィルターを削除
await client.knowledgeFilters.delete(filterId);

// チャットでフィルターを使用
const response = await client.chat.create({
  message: "Explain the API",
  filterId,
});

// 検索でフィルターを使用
const results = await client.search.query("API endpoints", { filterId });
```

## エラーハンドリング

```typescript
import {
  OpenRAGError,
  AuthenticationError,
  NotFoundError,
  ValidationError,
  RateLimitError,
  ServerError,
} from "openrag-sdk";

try {
  const response = await client.chat.create({ message: "Hello" });
} catch (e) {
  if (e instanceof AuthenticationError) {
    console.log(`Invalid API key: ${e.message}`);
  } else if (e instanceof NotFoundError) {
    console.log(`Resource not found: ${e.message}`);
  } else if (e instanceof ValidationError) {
    console.log(`Invalid request: ${e.message}`);
  } else if (e instanceof RateLimitError) {
    console.log(`Rate limited: ${e.message}`);
  } else if (e instanceof ServerError) {
    console.log(`Server error: ${e.message}`);
  } else if (e instanceof OpenRAGError) {
    console.log(`API error: ${e.message} (status: ${e.statusCode})`);
  }
}
```

## ブラウザサポート

このSDKはNode.jsとブラウザ環境の両方で動作します。主な違いはファイルの取り込みです：

- **Node.js**: `filePath` オプションを使用
- **ブラウザ**: `File` または `Blob` オブジェクトを使用した `file` オプションを使用

## TypeScript

このSDKはTypeScriptで書かれており、完全な型定義を提供します。すべての型はメインモジュールからエクスポートされます：

```typescript
import type {
  ChatResponse,
  StreamEvent,
  SearchResponse,
  IngestResponse,
  SettingsResponse,
} from "openrag-sdk";
```

## ライセンス

MIT
