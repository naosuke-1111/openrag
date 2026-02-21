# OpenRAGへの貢献

![Contributions Welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg)
![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.13+-blue.svg)
![Node.js](https://img.shields.io/badge/node.js-18+-green.svg)

**OpenRAGへのご貢献に興味をお持ちいただきありがとうございます！** 🎉

バグ修正、機能追加、ドキュメントの改善、または単なる調査など、あらゆる貢献が重要であり、OpenRAGをより良いものにする助けとなります。

このガイドでは、開発環境のセットアップと、素早く貢献を始めるための手順を説明します。

## 目次

- [クイックスタート](#クイックスタート)
- [前提条件](#前提条件)
- [初期セットアップ](#初期セットアップ)
- [開発ワークフロー](#開発ワークフロー)
- [サービス管理](#サービス管理)
- [リセットとクリーンアップ](#リセットとクリーンアップ)
- [Makefileヘルプシステム](#makefileヘルプシステム)
- [テスト](#テスト)
- [プロジェクト構成](#プロジェクト構成)
- [トラブルシューティング](#トラブルシューティング)
- [コードスタイル](#コードスタイル)
- [プルリクエストの作成](#プルリクエストの作成)

---

## クイックスタート

3つのコマンドでOpenRAGを起動します：

```bash
make check_tools  # 前提条件がすべて揃っているか確認
make setup        # 依存関係をインストールし .env を作成
make dev          # OpenRAGを起動
```

OpenRAGが以下のポートでローカルに起動します：

- **フロントエンド**: http://localhost:3000
- **Langflow**: http://localhost:7860

---

## 前提条件

### 必要なツール

| ツール | バージョン | インストール |
|------|---------|--------------|
| Docker または Podman | 最新版 | [Docker](https://docs.docker.com/get-docker/) または [Podman](https://podman.io/getting-started/installation) |
| Python | 3.13+ | [uv](https://github.com/astral-sh/uv) パッケージマネージャーと共に |
| Node.js | 18+ | npm と共に |
| Make | 任意 | macOS/Linux では通常プリインストール済み |

### Podmanのセットアップ（macOS）

macOSでPodmanを使用する場合、VMに十分なメモリを割り当てます（8GB推奨）：

```bash
# 既存のマシンを停止・削除（ある場合）
podman machine stop
podman machine rm

# 8GB RAM と 4 CPU で新しいマシンを作成
podman machine init --memory 8192 --cpus 4
podman machine start
```

> [!IMPORTANT]
> OpenRAGをスムーズに動作させるための最小推奨RAMは8GBです。クラッシュや動作が遅い場合は、メモリ割り当てを増やしてください。

### 前提条件の確認

```bash
make check_tools
```

`All required tools are installed.` と表示されれば成功です。

---

## 初期セットアップ


1. リポジトリをクローンしてプロジェクトをセットアップします：

   ```bash
   git clone https://github.com/langflow-ai/openrag.git
   cd openrag
   make setup
   ```

2. OpenRAGを起動する前に、必要な環境変数を設定します：

   ```env
   OPENAI_API_KEY=
   OPENSEARCH_PASSWORD=
   LANGFLOW_SUPERUSER=admin
   LANGFLOW_SUPERUSER_PASSWORD=
   ```

   `OPENSEARCH_PASSWORD` は [OpenSearchのパスワード複雑さ要件](https://docs.opensearch.org/latest/security/configuration/demo-configuration/#setting-up-a-custom-admin-password) に従う必要があります。

   `LANGFLOW_SUPERUSER_PASSWORD` を設定しない場合、Langflowインスタンスは認証なしで起動します。

   詳細については、[OpenRAG環境変数リファレンス](https://docs.openr.ag/reference/configuration)をご覧ください。

3. 次のセクションで説明するいずれかのオプションを使用してOpenRAGを起動します。
    ```bash
    make dev      # GPUサポートあり
    # または
    make dev-cpu  # CPUのみ
    ```

---

## 開発ワークフロー

ユースケースに応じて、OpenRAGを起動する方法が複数あります：

* ローカル開発環境：開発に推奨。
* フルDockerスタック：すべてをコンテナで実行するシンプルなビルド。開発には不向き。フルシステムのテストに最適。
* ブランチ開発：[Langflowリポジトリ](https://github.com/langflow-ai/langflow)のフォークまたはブランチを使用してOpenRAGをビルド。
* Doclingのみ：Doclingサービス単独で実行。

### A) フルDockerスタック（最もシンプル）

すべてをコンテナで実行。フルシステムのテストに最適。

```bash
make dev          # GPUサポートで起動
make dev-cpu      # CPUのみで起動
make stop         # 全コンテナを停止・削除
```

### B) ローカル開発（開発時推奨）

> [!TIP]
> これはアクティブな開発における**推奨ワークフロー**です。高速なコードリロードと容易なデバッグが可能です。

インフラをDockerで実行しつつ、バックエンド・フロントエンドをローカルで動かすことで、より速い反復が可能です。

```bash
# ターミナル1：インフラを起動（OpenSearch、Langflow、Dashboards）
make dev-local-cpu

# ターミナル2：バックエンドをローカルで実行
make backend

# ターミナル3：フロントエンドをローカルで実行
make frontend

# ターミナル4（オプション）：ドキュメント処理用にdoclingを起動
make docling
```

**メリット：**
- 高速なコードリロード
- ログとデバッグへの直接アクセス
- テストと反復が容易

### C) ブランチ開発（カスタムLangflow）

カスタムLangflowブランチでOpenRAGをビルド・実行：

```bash
# 特定のブランチを使用
make dev-branch BRANCH=my-feature-branch

# 別のリポジトリを使用
make dev-branch BRANCH=feature-x REPO=https://github.com/myorg/langflow.git
```

> [!NOTE]
> 初回ビルドはLangflowをソースからコンパイルするため、数分かかる場合があります。

**追加のブランチコマンド：**
```bash
make build-langflow-dev  # Langflowイメージを再ビルド（キャッシュなし）
make stop-dev            # ブランチ開発コンテナを停止
make restart-dev         # ブランチ開発環境を再起動
make clean-dev           # ブランチ開発コンテナとボリュームをクリーン
make logs-lf-dev         # Langflow開発ログを表示
make shell-lf-dev        # Langflow開発コンテナにシェルアクセス
```

### D) Doclingサービス（ドキュメント処理）

DoclingはドキュメントのパースとOCRを処理します：

```bash
make docling       # docling-serve を起動
make docling-stop  # docling-serve を停止
```

---

## サービス管理

### 全サービスの停止

```bash
make stop  # 全OpenRAGコンテナを停止・削除
```

### ステータス確認

```bash
make status  # コンテナのステータスを表示
make health  # 全サービスのヘルスチェック
```

### ログの表示

```bash
make logs     # 全コンテナのログ
make logs-be  # バックエンドのログのみ
make logs-fe  # フロントエンドのログのみ
make logs-lf  # Langflowのログのみ
make logs-os  # OpenSearchのログのみ
```

### シェルアクセス

```bash
make shell-be  # バックエンドコンテナにシェルアクセス
make shell-lf  # Langflowコンテナにシェルアクセス
make shell-os  # OpenSearchコンテナにシェルアクセス
```

---

## リセットとクリーンアップ

### コンテナの停止とクリーン

```bash
make stop   # コンテナを停止・削除
make clean  # コンテナを停止・削除し、ボリュームも削除
```

### データベースのリセット

```bash
make db-reset       # OpenSearchインデックスをリセット（データディレクトリは保持）
make clear-os-data  # OpenSearchデータディレクトリを完全に削除
```

### 完全ファクトリーリセット

> [!CAUTION]
> これにより、全データ、コンテナ、ボリュームが削除されます。完全に新しい状態から始める必要がある場合にのみ使用してください。

```bash
make factory-reset  # 完全リセット：コンテナ、ボリューム、データ
```

---

## Makefileヘルプシステム

> [!TIP]
> Makefileはすべてのコマンドに対してカラーコード付きの整理されたヘルプを提供します。`make help` を実行して始めましょう！

```bash
make help         # よく使うコマンドのメインヘルプ
make help_dev     # 開発環境コマンド
make help_docker  # DockerおよびコンテナコマンD
make help_test    # テストコマンド
make help_local   # ローカル開発コマンド
make help_utils   # ユーティリティコマンド（ログ、クリーンアップ等）
```

---

## テスト

### テストの実行

```bash
make test              # 全バックエンドテストを実行
make test-integration  # 統合テストを実行（インフラが必要）
make test-sdk          # SDKテストを実行（OpenRAGの起動が必要）
make lint              # リンティングチェックを実行
```

### CIテスト

```bash
make test-ci        # フルCI：インフラ起動、テスト実行、終了処理
make test-ci-local  # 上記と同様だが、ローカルでイメージをビルド
```

---

## プロジェクト構成

```
openrag/
├── src/                    # バックエンドPythonコード
│   ├── api/               # REST APIエンドポイント
│   ├── services/          # ビジネスロジック
│   ├── models/            # データモデル
│   ├── connectors/        # 外部連携
│   └── config/            # 設定
├── frontend/              # Next.jsフロントエンド
│   ├── app/              # Appルーターページ
│   ├── components/       # Reactコンポーネント
│   └── contexts/         # 状態管理
├── flows/                 # Langflowフロー定義
├── docs/                  # ドキュメント
├── tests/                 # テストファイル
├── Makefile              # 開発コマンド
└── docker-compose.yml    # コンテナオーケストレーション
```

---

## トラブルシューティング

### ポートの競合

> [!NOTE]
> OpenRAGを起動する前に、以下のポートが使用可能であることを確認してください：

| ポート | サービス |
|------|---------|
| 3000 | フロントエンド |
| 7860 | Langflow |
| 8000 | バックエンド |
| 9200 | OpenSearch |
| 5601 | OpenSearch Dashboards |

### メモリの問題

コンテナがクラッシュしたり動作が遅い場合：

```bash
# macOS上のPodmanの場合、VMメモリを増やす
podman machine stop
podman machine rm
podman machine init --memory 8192 --cpus 4
podman machine start
```

### 環境のリセット

> [!TIP]
> うまく動作しない場合は、完全リセットを試みてください：

```bash
make stop
make clean
cp .env.example .env  # 必要に応じて再設定
make setup
make dev
```

### サービスヘルスの確認

```bash
make health
```

### さらにヘルプが必要な場合

- `make help` を実行して利用可能な全コマンドを確認
- 既存の[Issues](https://github.com/langflow-ai/openrag/issues)を確認
- [ドキュメント](docs/)を参照
- デバッグには `make status` と `make health` を使用
- `make logs` でログを確認

---

## コードスタイル

### バックエンド（Python）
- PEP 8スタイルガイドラインに従う
- 型ヒントを使用する
- docstringでドキュメントを記述する
- ロギングには `structlog` を使用する

### フロントエンド（TypeScript/React）
- React/Next.jsのベストプラクティスに従う
- 型安全性のためにTypeScriptを使用する
- スタイリングにはTailwind CSSを使用する
- 既存のコンポーネントパターンに従う

---

## プルリクエストの作成

変更をOpenRAGメンテナーに提案したい場合は、コードが完全にテストされ、レビューの準備ができていることを確認してください：

1. **フォークとブランチ**: `main` からフィーチャーブランチを作成
2. **テスト**: `make test` と `make lint` でテストが通ることを確認
3. **ドキュメント**: 関連するドキュメントを更新する。
ドキュメント変更のビルドとテストについては、[OpenRAGドキュメントへの貢献](https://docs.openr.ag/support/contribute#contribute-documentation)を参照。
4. **コミット**: 明確で説明的なコミットメッセージを使用する
5. **PR説明**: 変更内容とテスト手順を説明する

> [!IMPORTANT]
> すべてのPRはマージ前にCIテストを通過する必要があります。

詳細情報と成功する貢献のための提案については、[OpenRAGへの貢献](https://docs.openr.ag/support/contribute#contribute-to-the-codebase)をご覧ください。


OpenRAGへのご貢献ありがとうございます！ 🚀
