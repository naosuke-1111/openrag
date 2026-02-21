# OpenRAG Python SDK

[OpenRAG](https://openr.ag) API の公式Python SDKです。

## インストール

```bash
pip install openrag-sdk
```

## クイックスタート

```python
import asyncio
from openrag_sdk import OpenRAGClient

async def main():
    # クライアントは環境変数からOPENRAG_API_KEYとOPENRAG_URLを自動検出
    async with OpenRAGClient() as client:
        # シンプルなチャット
        response = await client.chat.create(message="What is RAG?")
        print(response.response)
        print(f"Chat ID: {response.chat_id}")

asyncio.run(main())
```

## 設定

SDKは環境変数またはコンストラクタ引数で設定できます：

| 環境変数 | コンストラクタ引数 | 説明 |
|---------------------|---------------------|-------------|
| `OPENRAG_API_KEY` | `api_key` | 認証用APIキー（必須） |
| `OPENRAG_URL` | `base_url` | OpenRAGフロントエンドのベースURL（デフォルト：`http://localhost:3000`） |

```python
# 環境変数を使用
client = OpenRAGClient()

# 明示的な引数を使用
client = OpenRAGClient(
    api_key="orag_...",
    base_url="https://api.example.com"
)
```

## チャット

### ストリームなし

```python
response = await client.chat.create(message="What is RAG?")
print(response.response)
print(f"Chat ID: {response.chat_id}")

# 会話を続ける
followup = await client.chat.create(
    message="Tell me more",
    chat_id=response.chat_id
)
```

### `create(stream=True)` を使用したストリーミング

非同期イテレータを直接返します：

```python
chat_id = None
async for event in await client.chat.create(message="Explain RAG", stream=True):
    if event.type == "content":
        print(event.delta, end="", flush=True)
    elif event.type == "sources":
        for source in event.sources:
            print(f"\nSource: {source.filename}")
    elif event.type == "done":
        chat_id = event.chat_id
```

### `stream()` コンテキストマネージャを使用したストリーミング

便利なヘルパーメソッドを提供します：

```python
# 全イベントのイテレーション
async with client.chat.stream(message="Explain RAG") as stream:
    async for event in stream:
        if event.type == "content":
            print(event.delta, end="", flush=True)

    # イテレーション後に集計データにアクセス
    print(f"\nChat ID: {stream.chat_id}")
    print(f"Full text: {stream.text}")
    print(f"Sources: {stream.sources}")

# テキストデルタのみ
async with client.chat.stream(message="Explain RAG") as stream:
    async for text in stream.text_stream:
        print(text, end="", flush=True)

# 最終テキストを直接取得
async with client.chat.stream(message="Explain RAG") as stream:
    text = await stream.final_text()
    print(text)
```

### 会話履歴

```python
# 全会話を一覧表示
conversations = await client.chat.list()
for conv in conversations.conversations:
    print(f"{conv.chat_id}: {conv.title}")

# メッセージ付きで特定の会話を取得
conversation = await client.chat.get(chat_id)
for msg in conversation.messages:
    print(f"{msg.role}: {msg.content}")

# 会話を削除
await client.chat.delete(chat_id)
```

## 検索

```python
# 基本的な検索
results = await client.search.query("document processing")
for result in results.results:
    print(f"{result.filename} (score: {result.score})")
    print(f"  {result.text[:100]}...")

# フィルター付き検索
from openrag_sdk import SearchFilters

results = await client.search.query(
    "API documentation",
    filters=SearchFilters(
        data_sources=["api-docs.pdf"],
        document_types=["application/pdf"]
    ),
    limit=5,
    score_threshold=0.5
)
```

## ドキュメント

```python
# ファイルを取り込む（デフォルトで完了まで待機）
result = await client.documents.ingest(file_path="./report.pdf")
print(f"Status: {result.status}")
print(f"Successful files: {result.successful_files}")

# 待機せずに取り込む（task_idを持つ即時返却）
result = await client.documents.ingest(file_path="./report.pdf", wait=False)
print(f"Task ID: {result.task_id}")

# 手動で完了をポーリング
final_status = await client.documents.wait_for_task(result.task_id)
print(f"Status: {final_status.status}")
print(f"Successful files: {final_status.successful_files}")

# ファイルオブジェクトから取り込む
with open("./report.pdf", "rb") as f:
    result = await client.documents.ingest(file=f, filename="report.pdf")

# ドキュメントを削除
result = await client.documents.delete("report.pdf")
print(f"Success: {result.success}")
```

## 設定

```python
# 設定を取得
settings = await client.settings.get()
print(f"LLM Provider: {settings.agent.llm_provider}")
print(f"LLM Model: {settings.agent.llm_model}")
print(f"Embedding Model: {settings.knowledge.embedding_model}")

# 設定を更新
await client.settings.update({
    "chunk_size": 1000,
    "chunk_overlap": 200,
})
```

## ナレッジフィルター

ナレッジフィルターは、チャットと検索操作に適用できる再利用可能な名前付きフィルター設定です。

```python
# ナレッジフィルターを作成
result = await client.knowledge_filters.create({
    "name": "Technical Docs",
    "description": "Filter for technical documentation",
    "queryData": {
        "query": "technical",
        "filters": {
            "document_types": ["application/pdf"],
        },
        "limit": 10,
        "scoreThreshold": 0.5,
    },
})
filter_id = result.id

# フィルターを検索
filters = await client.knowledge_filters.search("Technical")
for f in filters:
    print(f"{f.name}: {f.description}")

# 特定のフィルターを取得
filter_obj = await client.knowledge_filters.get(filter_id)

# フィルターを更新
await client.knowledge_filters.update(filter_id, {
    "description": "Updated description",
})

# フィルターを削除
await client.knowledge_filters.delete(filter_id)

# チャットでフィルターを使用
response = await client.chat.create(
    message="Explain the API",
    filter_id=filter_id,
)

# 検索でフィルターを使用
results = await client.search.query("API endpoints", filter_id=filter_id)
```

## エラーハンドリング

```python
from openrag_sdk import (
    OpenRAGError,
    AuthenticationError,
    NotFoundError,
    ValidationError,
    RateLimitError,
    ServerError,
)

try:
    response = await client.chat.create(message="Hello")
except AuthenticationError as e:
    print(f"Invalid API key: {e.message}")
except NotFoundError as e:
    print(f"Resource not found: {e.message}")
except ValidationError as e:
    print(f"Invalid request: {e.message}")
except RateLimitError as e:
    print(f"Rate limited: {e.message}")
except ServerError as e:
    print(f"Server error: {e.message}")
except OpenRAGError as e:
    print(f"API error: {e.message} (status: {e.status_code})")
```

## ライセンス

MIT
