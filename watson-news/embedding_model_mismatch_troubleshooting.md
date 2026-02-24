# 埋め込みモデルミスマッチのトラブルシューティング

## エラー概要

```
Failed to generate embeddings for any model. 
Index has models: ['granite-embedding-170m-multilingual']
Available embedding identifiers: ['text-embedding-3-small', 'text-embedding-3-large', 'text-embedding-ada-002', 'text-embedding-ada-002:text-embedding-3-small']
```

**発生日時**: 2026-02-24  
**影響範囲**: nudgesエンドポイント、検索機能

---

## 問題の根本原因

### 1. 設定の不一致

#### `.env`ファイルの設定
```env
EMBEDDING_PROVIDER=ibm
EMBEDDING_MODEL=granite-embedding-170m-multilingual
WATSONX_API_KEY=gDVTt7BeNz8lqNBb1xC1k9wyOSmlW4TdigoI4yKJ
WATSONX_ENDPOINT=https://cpd-cpd.apps.watsonx2.lab.japan.ibm.com
WATSONX_PROJECT_ID=be87baf8-e1b5-4247-a9ee-b95aa3e3fbb1
```

#### Langflowフローの設定 (`openrag_nudges.json`)
```json
{
  "provider": "OpenAI",
  "model": "text-embedding-3-small",
  "fail_safe_mode": true
}
```

### 2. 問題の詳細

1. **OpenSearchインデックス**: ドキュメントは `granite-embedding-170m-multilingual` (WatsonX) でインデックス化されている
2. **Langflowフロー**: 埋め込みモデルコンポーネントは **OpenAI** プロバイダーに設定されている
3. **マッチング失敗**: クエリ時にOpenSearchから検出されたモデル (`granite-embedding-170m-multilingual`) に対応する埋め込みオブジェクトが見つからない

### 3. 技術的な背景

`flows/components/opensearch_multimodal.py` のマルチモデル検索機能:

```python
# 行1334-1550: search()メソッド
# 1. OpenSearchインデックスから利用可能なモデルを検出
available_models = self._detect_available_models(client, filter_clauses)
# 例: ['granite-embedding-170m-multilingual']

# 2. 各モデルに対応する埋め込みオブジェクトを検索
embedding_by_model = {}  # モデル名 -> 埋め込みオブジェクトのマッピング

# 3. マッチングに失敗した場合
if not query_embeddings:
    raise ValueError(
        f"Failed to generate embeddings for any model. "
        f"Index has models: {available_models}, "
        f"but no matching embedding objects found. "
        f"Available embedding identifiers: {list(embedding_by_model.keys())}"
    )
```

---

## 解決策

### オプション1: Langflowフローを修正（推奨）

#### 手順

1. **Langflow UIにアクセス**
   ```
   http://localhost:7860
   ```

2. **修正が必要なフロー**
   - `openrag_nudges`
   - `openrag_agent`
   - `ingestion_flow`
   - `openrag_url_mcp`

3. **各フローの埋め込みモデルコンポーネントを修正**

   | 設定項目 | 変更前 | 変更後 |
   |---------|--------|--------|
   | Model Provider | `OpenAI` | `IBM watsonx.ai` |
   | Model Name | `text-embedding-3-small` | `granite-embedding-170m-multilingual` |
   | IBM watsonx.ai API Key | (空) | `gDVTt7BeNz8lqNBb1xC1k9wyOSmlW4TdigoI4yKJ` |
   | Project ID | (空) | `be87baf8-e1b5-4247-a9ee-b95aa3e3fbb1` |
   | watsonx API Endpoint | (デフォルト) | `https://cpd-cpd.apps.watsonx2.lab.japan.ibm.com` |
   | Fail-Safe Mode | `true` | `false` (推奨) |

4. **フローを保存**

#### 注意事項

- **Fail-Safe Mode**: 現在 `true` に設定されているため、エラーが発生してもNoneを返すだけで例外が発生しません。これにより問題の診断が難しくなっています。修正後は `false` に設定することを推奨します。

- **複数の埋め込みモデルコンポーネント**: 各フローには通常3つの埋め込みモデルコンポーネントがあります（OpenAI、Ollama、WatsonX用）。すべてを適切に設定する必要があります。

### オプション2: OpenSearchデータをクリアして再インデックス

既存のデータを削除し、OpenAI埋め込みモデルで再インデックスする場合:

```bash
# 1. OpenSearchデータをクリア
python scripts/clear_opensearch_data.py

# 2. .envファイルを更新
# EMBEDDING_PROVIDER=openai
# EMBEDDING_MODEL=text-embedding-3-small

# 3. コンテナを再起動
docker-compose restart

# 4. サンプルデータが自動的に再インデックスされる
```

**注意**: この方法では既存のすべてのドキュメントが削除されます。

---

## 検証方法

### 1. Langflowログを確認

```bash
docker-compose logs -f langflow
```

以下のようなログが表示されれば成功:
```
[SEARCH] Models detected in index: ['granite-embedding-170m-multilingual']
[SEARCH] Available embedding identifiers: ['granite-embedding-170m-multilingual', ...]
[MATCH] Model 'granite-embedding-170m-multilingual' - generated 768-dim embedding
```

### 2. APIエンドポイントをテスト

```bash
curl -X POST http://localhost:8000/nudges \
  -H "Content-Type: application/json" \
  -d '{"message": "test query"}'
```

成功すれば、エラーなしでレスポンスが返されます。

### 3. OpenSearchインデックスを確認

```bash
# インデックス内のモデルを確認
curl -X GET "http://localhost:9200/documents/_search?pretty" \
  -H "Content-Type: application/json" \
  -u "admin:OpenRag@2026!" \
  -d '{
    "size": 0,
    "aggs": {
      "embedding_models": {
        "terms": {
          "field": "embedding_model",
          "size": 10
        }
      }
    }
  }'
```

---

## 関連ファイル

- **設定ファイル**: `.env`
- **Langflowフロー**:
  - `flows/openrag_nudges.json`
  - `flows/openrag_agent.json`
  - `flows/ingestion_flow.json`
  - `flows/openrag_url_mcp.json`
- **カスタムコンポーネント**: `flows/components/opensearch_multimodal.py`
- **モデルサービス**: `src/services/models_service.py`

---

## 予防策

### 1. 設定の一貫性を保つ

`.env`ファイルとLangflowフローの設定を常に同期させる:

```bash
# .envの設定を確認
grep "EMBEDDING_" .env

# Langflowフローの設定を確認
# Langflow UIで各フローの埋め込みモデルコンポーネントを確認
```

### 2. 環境変数を使用

Langflowフローで環境変数を使用することで、設定の一貫性を保つ:

```json
{
  "api_key": "{WATSONX_API_KEY}",
  "project_id": "{WATSONX_PROJECT_ID}",
  "base_url_ibm_watsonx": "{WATSONX_ENDPOINT}"
}
```

### 3. デプロイ前のチェックリスト

- [ ] `.env`ファイルの `EMBEDDING_PROVIDER` と `EMBEDDING_MODEL` を確認
- [ ] すべてのLangflowフローの埋め込みモデルコンポーネントを確認
- [ ] OpenSearchインデックスのモデルを確認
- [ ] テストクエリを実行して動作を確認

---

## トラブルシューティングコマンド

```bash
# 1. OpenSearchインデックスのモデルを確認
curl -X GET "http://localhost:9200/documents/_search?pretty" \
  -u "admin:OpenRag@2026!" \
  -d '{"size":0,"aggs":{"models":{"terms":{"field":"embedding_model"}}}}'

# 2. Langflowログをリアルタイムで確認
docker-compose logs -f langflow | grep -i "embedding\|model"

# 3. バックエンドログを確認
docker-compose logs -f openrag-backend | grep -i "error\|embedding"

# 4. OpenSearchデータをクリア（必要な場合のみ）
python scripts/clear_opensearch_data.py

# 5. コンテナを再起動
docker-compose restart
```

---

## 参考情報

### マルチモデル埋め込みの仕組み

OpenRAGのマルチモデル埋め込み機能:

1. **インデックス時**: 各ドキュメントに `embedding_model` フィールドを保存
2. **検索時**: 
   - OpenSearchから利用可能なモデルを自動検出
   - 各モデルに対応する埋め込みオブジェクトを検索
   - 複数のKNNクエリを並列実行（dis_max）
   - 結果を統合して返す

### 埋め込みモデルの識別子

埋め込みオブジェクトは以下の優先順位で識別されます:

1. `deployment` 属性
2. `model` 属性
3. `model_id` 属性
4. `model_name` 属性

WatsonXの場合、通常は `model` または `model_id` が使用されます。

---

**作成日**: 2026-02-24  
**最終更新**: 2026-02-24  
**作成者**: OpenRAG Troubleshooting Team