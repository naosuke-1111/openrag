# OpenRAG MCPサーバー

[Model Context Protocol](https://modelcontextprotocol.io/)（MCP）サーバーで、OpenRAGのナレッジベースをAIアシスタントに公開します。Cursor、Claude Desktop、IBM Watson OrchestrateなどのMCP互換アプリが、OpenRAGのRAG機能（チャット、検索、設定）を標準プロトコル経由で利用できるようになります。プラットフォームごとのカスタム統合は不要です。

---

## OpenRAG MCPとは？

OpenRAG MCPは、OpenRAGインスタンスとAIアプリケーションの間の**接続レイヤー**です。ホストアプリ（例：CursorやClaude Desktop）がMCPサーバーをサブプロセスとして実行し、JSON-RPCを使用してstdio経由で通信します。サーバーはAPIキーを使用してOpenRAG APIを呼び出します。ナレッジベースは唯一の情報源として維持され、接続された全アプリが同じRAGバックのチャットと検索機能を利用できます。

---

## クイックスタート

**uvx**でサーバーを実行します（ローカルインストール不要；Python 3.10+と[uv](https://docs.astral.sh/uv/)が必要）：

```bash
uvx openrag-mcp
```

最初に必要な環境変数を設定します（またはMCPクライアントの設定で渡します）：

```bash
export OPENRAG_URL="https://your-openrag-instance.com"
export OPENRAG_API_KEY="orag_your_api_key"
uvx openrag-mcp
```

バージョンを固定する場合：

```bash
uvx --from openrag-mcp==0.2.1 openrag-mcp
```

### 前提条件

- Python 3.10+
- 動作しているOpenRAGインスタンス
- OpenRAG APIキー（OpenRAGの**Settings → API Keys**で作成）
- `uv` がインストール済み（`uvx` のため）

---

## 利用可能なツール

サーバーが現在公開しているツールは以下の通りです：

| ツール | 説明 |
|:-----|:------------|
| `openrag_chat` | メッセージを送信してRAG強化レスポンスを取得。オプション：`chat_id`、`filter_id`、`limit`、`score_threshold`。 |
| `openrag_search` | ナレッジベースのセマンティック検索。オプション：`limit`、`score_threshold`、`filter_id`、`data_sources`、`document_types`。 |
| `openrag_get_settings` | 現在のOpenRAG設定を取得（LLM、埋め込み、チャンク設定、システムプロンプト等）。 |
| `openrag_update_settings` | OpenRAG設定を更新（LLMモデル、埋め込みモデル、チャンクサイズ/オーバーラップ、システムプロンプト、テーブル構造、OCR、画像説明）。 |
| `openrag_list_models` | プロバイダー（`openai`、`anthropic`、`ollama`、`watsonx`）の利用可能な言語モデルと埋め込みモデルを一覧表示。 |

### 今後追加予定（ドキュメントツール）

ドキュメント取り込みと管理ツール（`openrag_ingest_file`、`openrag_ingest_url`、`openrag_delete_document`、`openrag_get_task_status`、`openrag_wait_for_task`）は実装済みですが、このサーバーにはまだ登録されておらず、将来のリリースで有効化される予定です。

---

## 環境変数

| 変数 | 説明 | 必須 | デフォルト |
|:---------|:------------|:--------:|:--------|
| `OPENRAG_API_KEY` | OpenRAG APIキー | はい | — |
| `OPENRAG_URL` | OpenRAGインスタンスのベースURL | いいえ | `http://localhost:3000` |

**MCP HTTPクライアント（オプション）：**

| 変数 | 説明 | 必須 | デフォルト |
|:---------|:------------|:--------:|:--------|
| `OPENRAG_MCP_TIMEOUT` | リクエストタイムアウト（秒） | いいえ | `60.0` |
| `OPENRAG_MCP_MAX_CONNECTIONS` | 最大同時接続数 | いいえ | `100` |
| `OPENRAG_MCP_MAX_KEEPALIVE_CONNECTIONS` | 最大キープアライブ接続数 | いいえ | `20` |
| `OPENRAG_MCP_MAX_RETRIES` | 失敗したリクエストの最大リトライ回数 | いいえ | `3` |
| `OPENRAG_MCP_FOLLOW_REDIRECTS` | HTTPリダイレクトに従うかどうか | いいえ | `true` |

これらはMCPサーバー実行時の環境（例：MCPクライアント設定の `env` ブロック）で設定する必要があります。

---

## 使用方法

### Cursor

**設定ファイル：** `~/.cursor/mcp.json`

```json
{
  "mcpServers": {
    "openrag": {
      "command": "uvx",
      "args": ["openrag-mcp"],
      "env": {
        "OPENRAG_URL": "https://your-openrag-instance.com",
        "OPENRAG_API_KEY": "orag_your_api_key_here"
      }
    }
  }
}
```

設定変更後はCursorを再起動してください。

### Claude Desktop

**macOS：** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows：** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "openrag": {
      "command": "uvx",
      "args": ["openrag-mcp"],
      "env": {
        "OPENRAG_URL": "https://your-openrag-instance.com",
        "OPENRAG_API_KEY": "orag_your_api_key_here"
      }
    }
  }
}
```

ファイルを編集したらClaude Desktopを再起動してください。

---

## ソースから実行（開発用）

リポジトリからの**最新のMCPコード**を使用するには（設定およびモデルツールを含む）、ソースから実行します。ローカルの編集を反映させたい場合は、パッケージをインストール**しないでください**。

### 手順

| ステップ | 内容 | コマンド | 必要な場面 |
|------|------|---------|---------------|
| 1 | OpenRAGバックエンド | OpenRAGアプリを実行（例：フロントエンド + API） | 全ツール |
| 2 | ソースからMCP | `cd sdks/mcp && uv sync` | 全ツール；wheelは不要 |
| 3 | （オプション）リポジトリからSDK | `cd sdks/python && uv pip install -e .` | 未リリースのチャット/検索SDKの変更が必要な場合のみ |

設定とモデルツール（`openrag_get_settings`、`openrag_update_settings`、`openrag_list_models`）は直接HTTPを使用します。チャットと検索にはOpenRAG SDK（未リリースのSDK変更が必要でない限り、PyPIバージョンで十分）を使用します。

### ソースからMCPを実行する

```bash
cd sdks/mcp
uv sync
export OPENRAG_URL="http://localhost:3000"
export OPENRAG_API_KEY="orag_your_api_key"
uv run openrag-mcp
```

### Cursor：リポジトリパスを使用してコードを実行する

`~/.cursor/mcp.json` で、`--directory` を**実際のリポジトリパス**に設定して、CursorがソースからMCPを実行するようにします：

```json
{
  "mcpServers": {
    "openrag": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/openrag/sdks/mcp",
        "openrag-mcp"
      ],
      "env": {
        "OPENRAG_URL": "https://your-openrag-instance.com",
        "OPENRAG_API_KEY": "orag_your_api_key_here"
      }
    }
  }
}
```

`/path/to/openrag` を実際のパス（例：`/Users/edwin.jose/Documents/openrag`）に置き換えてください。

以前にMCPをインストールした場合（`pip install openrag-mcp` またはwheelで）、Cursorがリポジトリを使用するようにアンインストールしてください：

```bash
uv pip uninstall openrag-mcp
```

その後Cursorを再起動してください。

---

## ユースケースとメリット

- **一つの統合で多くのアプリに対応** – 同じMCPサーバーがCursor、Claude Desktop、Watson Orchestrate、あらゆるMCPクライアントで動作。
- **RAGを活用** – チャットと検索がOpenRAGナレッジベースに基づき、オプションのフィルターとスコアリングを備える。
- **エージェントフレンドリー** – エージェントがカスタムAPIなしにOpenRAGに回答を問い合わせ、モデルを一覧表示し、設定の読み取り/更新が可能。
- **軽量** – デプロイするサービスは不要；ホストアプリがサーバーをサブプロセスとして起動しstdio経由で通信。
- **セキュア** – 環境変数経由で `OPENRAG_API_KEY` を持つクライアントのみがサーバーを通じてOpenRAGにアクセス可能。

**使用シナリオの例：** IDEから内部ドキュメントやランブックをクエリ；製品ドキュメントでサポートボットを強化；取り込み済みドキュメントを横断的に検索・要約；RAGが必要なワークフローを自動化（ドキュメントツールが有効な場合）。

---


## プロンプト例

サーバーが設定されると、AIに以下を尋ねることができます：

- *「認証のベストプラクティスについてナレッジベースを検索して」*
- *「Q4ロードマップについてOpenRAGとチャットして」*
- *「現在のOpenRAG設定は何ですか？」*
- *「openaiプロバイダーの利用可能なモデルを一覧表示して」*
- *「OpenRAGのチャンクサイズを512に更新して」*

---

## トラブルシューティング

### 「OPENRAG_API_KEY environment variable is required」

MCPの設定（CursorまたはClaude Desktop）の `env` セクションに `OPENRAG_API_KEY` を設定してください。サーバーは起動時にこれを読み取ります。

### 「Connection refused」またはネットワークエラー

1. OpenRAGインスタンスが実行中でアクセス可能であることを確認してください。
2. `OPENRAG_URL` を確認してください（末尾のスラッシュなし；該当する場合は `https://` を含める）。
3. クライアントマシンからOpenRAGへの接続をファイアウォールやプロキシがブロックしていないことを確認してください。

### ツールが表示されない

1. MCP設定を変更した後、ホストアプリ（CursorまたはClaude Desktop）を再起動してください。
2. アプリのMCP/ログ出力でエラーを確認してください（例：`command`/`args` が間違っているか、`uv`/`uvx` が見つからない）。
3. 「ソースから実行」を使用している場合、`args` に `--directory` と `sdks/mcp` への正しいパスが含まれていることを確認してください。

---

## ライセンス

Apache 2.0 - 詳細は [LICENSE](../../LICENSE) を参照してください。
