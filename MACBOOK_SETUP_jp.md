# MacBook 開発環境セットアップガイド

このガイドでは、MacBook（Apple Silicon / Intel）でOpenRAGの開発環境を初回から構築し、アプリケーションを利用可能にするまでの手順を説明します。

---

## 目次

1. [システム要件](#1-システム要件)
2. [前提ツールのインストール](#2-前提ツールのインストール)
   - 2.1 [Homebrew](#21-homebrew)
   - 2.2 [コンテナランタイム（Docker Desktop または Podman）](#22-コンテナランタイムdocker-desktop-または-podman)
   - 2.3 [uv（Pythonパッケージマネージャー）](#23-uvpythonパッケージマネージャー)
   - 2.4 [Python 3.13](#24-python-313)
   - 2.5 [Node.js](#25-nodejs)
3. [リポジトリのクローン](#3-リポジトリのクローン)
4. [環境変数の設定](#4-環境変数の設定)
5. [前提条件の確認](#5-前提条件の確認)
6. [依存関係のインストール](#6-依存関係のインストール)
7. [（オプション）初回ウィザードのスキップ](#7-オプション初回ウィザードのスキップ)
8. [アプリケーションの起動](#8-アプリケーションの起動)
   - 8.1 [方法A: フルDockerスタック（最もシンプル）](#81-方法a-フルdockerスタック最もシンプル)
   - 8.2 [方法B: ローカル開発（推奨）](#82-方法b-ローカル開発推奨)
9. [動作確認](#9-動作確認)
10. [日常的な操作](#10-日常的な操作)
11. [トラブルシューティング](#11-トラブルシューティング)

---

## 1. システム要件

| 項目 | 要件 |
|------|------|
| macOS | 13 Ventura 以上推奨 |
| CPU | Apple Silicon（M1/M2/M3/M4）または Intel |
| RAM | **16GB 以上推奨**（最低 8GB） |
| ストレージ | 20GB 以上の空き容量 |

> **注意:** OpenSearchやLangflowなど複数のサービスを同時に動作させるため、RAMが少ないとパフォーマンスが低下します。

---

## 2. 前提ツールのインストール

### 2.1 Homebrew

macOSのパッケージマネージャーです。ターミナルを開いて以下を実行します。

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

インストール後、表示される指示に従って `PATH` を設定してください（Apple Siliconの場合は通常 `~/.zprofile` に追記が必要です）。

```bash
# Apple Silicon の場合
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"

# インストール確認
brew --version
```

---

### 2.2 コンテナランタイム（Docker Desktop または Podman）

OpenRAGのインフラ（OpenSearch、Langflowなど）はコンテナで動作します。
**Docker Desktop** または **Podman** のどちらかをインストールしてください。Makefileはどちらも自動検出します。

---

#### オプション A: Docker Desktop（推奨・簡単）

1. [Docker Desktop for Mac](https://docs.docker.com/desktop/install/mac-install/) からインストーラーをダウンロード
   - Apple Siliconの場合: **Apple Chip** 版を選択
   - Intelの場合: **Intel Chip** 版を選択

2. ダウンロードした `.dmg` ファイルを開き、Docker.app をアプリケーションフォルダへドラッグ

3. Docker Desktop を起動（メニューバーにDockerアイコンが表示されます）

4. **Docker Desktop の設定でリソースを増やす（重要）**:
   - Docker Desktop を開く → 右上の歯車アイコン（Settings）→ **Resources**
   - **Memory**: 8GB 以上に設定（推奨: 12GB以上）
   - **CPUs**: 4以上に設定
   - **Apply & Restart** をクリック

5. インストール確認:

```bash
docker --version
docker compose version
```

---

#### オプション B: Podman + Compose（Docker代替）

Podmanはデーモンレス・rootlessで動作するOCIコンテナランタイムです。企業ポリシーなどの理由でDockerが使えない場合に選択してください。

Composeプラグインは **`podman compose`**（組み込み）と **`podman-compose`**（Python製）の2種類があります。いずれか1つインストールすれば動作します。

**① Podman 本体のインストール:**

```bash
brew install podman
```

**② Podman Machine の初期化（macOS必須）:**

macOSではLinux VMが必要です。8GB RAM・4 CPU を割り当てて作成します。

```bash
# 既存マシンがある場合は削除
podman machine stop 2>/dev/null || true
podman machine rm   2>/dev/null || true

# 8GB RAM・4 CPU で新しいマシンを作成・起動
podman machine init --memory 8192 --cpus 4
podman machine start
```

> **注意:** メモリが不足するとOpenSearchやLangflowがクラッシュします。16GB RAM搭載MacBookでは `--memory 12288`（12GB）推奨です。

**③ Compose プラグインのインストール（どちらか1つ）:**

| 方法 | コマンド | 特徴 |
|------|---------|------|
| `podman compose`（組み込み） | `brew install podman-compose` | Podman公式ラッパー |
| `podman-compose`（Python製） | `pip install podman-compose` または `brew install podman-compose` | より互換性が高い |

**組み込みCompose（推奨）:**
```bash
# podman compose は podman >= 4.7 で組み込み済み
podman compose version
```

**Python製 podman-compose（代替）:**
```bash
pip install podman-compose
# または
brew install podman-compose

podman-compose --version
```

**④ インストール確認:**

```bash
podman --version
podman machine list        # マシンが Running 状態であることを確認
podman compose version     # 組み込みComposeの場合
# または
podman-compose --version   # Python製の場合
```

> **Makefileの動作:** OpenRAGのMakefileはDockerが見つからない場合、自動的にPodmanを使用します。追加設定は不要です。

---

### 2.3 uv（Pythonパッケージマネージャー）

OpenRAGはPythonパッケージマネージャーとして `uv` を使用します。

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

インストール後、シェルを再起動するか以下を実行します:

```bash
source ~/.zshrc  # または source ~/.bash_profile

# インストール確認
uv --version
```

---

### 2.4 Python 3.13

`uv` を使ってPython 3.13をインストールします。

```bash
uv python install 3.13

# インストール確認
uv run python --version
```

---

### 2.5 Node.js

フロントエンド（Next.js）の実行に必要です。Node.js 20以上が必要です。

```bash
# Homebrewでインストール
brew install node@20

# PATHに追加（Apple Siliconの場合）
echo 'export PATH="/opt/homebrew/opt/node@20/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# インストール確認
node --version   # v20.x.x 以上であることを確認
npm --version
```

> **代替方法:** [Node.js公式サイト](https://nodejs.org/)からLTS版（v20以上）をダウンロードしてインストールすることもできます。

---

## 3. リポジトリのクローン

```bash
git clone https://github.com/langflow-ai/openrag.git
cd openrag
```

---

## 4. 環境変数の設定

`.env.example` をコピーして `.env` ファイルを作成します。

```bash
cp .env.example .env
```

`.env` ファイルをテキストエディタで開き、以下の必須項目を設定します:

```bash
# お好みのエディタで編集
open -e .env      # TextEdit で開く
# または
code .env         # VS Code で開く（要インストール）
```

### 必須の設定項目

#### OpenSearch・Langflow（共通）

```env
# OpenSearch 管理者パスワード（必須）
# 以下のすべてを含む8文字以上: 大文字・小文字・数字・記号
OPENSEARCH_PASSWORD=MyStr0ng!Pass

# Langflow スーパーユーザー設定
LANGFLOW_SUPERUSER=admin
LANGFLOW_SUPERUSER_PASSWORD=MyStr0ng!Pass
```

> **パスワードのルール:** `OPENSEARCH_PASSWORD` は以下をすべて含む必要があります:
> - 8文字以上
> - 大文字1文字以上
> - 小文字1文字以上
> - 数字1文字以上
> - 記号（`!@#$%` など）1文字以上

---

#### LLM / Embedding: オンプレミス OCP watsonx.ai を使用する場合

このプロジェクトでは **IBM Cloud Pak for Data（CP4D）上の watsonx.ai** をLLMおよびEmbeddingプロバイダーとして使用します。

```env
# ─── LLM 設定 ───────────────────────────────────────────────
# LLMプロバイダー（on-prem OCP watsonx.ai 経由で OpenAI互換エンドポイントを使用）
LLM_PROVIDER=openai
LLM_MODEL=gpt-oss-120b

# ─── Embedding 設定 ─────────────────────────────────────────
# EmbeddingプロバイダーとモデルはIBM Graniteを使用
EMBEDDING_PROVIDER=ibm
EMBEDDING_MODEL=granite-embedding-107m-multilingual

# ─── watsonx.ai on-prem OCP 接続設定 ────────────────────────
# CP4D インスタンスのベースURL（例: https://cpd.your-cluster.example.com）
WATSONX_API_URL=https://<CP4D_HOST>

# CP4D 認証エンドポイント（例: https://cpd.your-cluster.example.com/icp4d-api/v1/authorize）
WATSONX_AUTH_URL=https://<CP4D_HOST>/icp4d-api/v1/authorize

# CP4D のユーザー名とパスワード
WATSONX_USERNAME=<your-cp4d-username>
WATSONX_PASSWORD=<your-cp4d-password>

# watsonx.ai プロジェクトID（CP4DのプロジェクトページのURLから取得）
WATSONX_PROJECT_ID=<your-project-id>

# API バージョン（通常変更不要）
WATSONX_API_VERSION=2025-02-06

# 自己署名証明書を使用している場合は false に設定
WATSONX_SSL_VERIFY=true
# CA証明書バンドルのパス（自己署名の場合に指定、不要なら空欄）
WATSONX_CA_BUNDLE_PATH=
```

> **`WATSONX_API_KEY` について:** API Keyを使う認証方式（IBMCloud SaaS）の場合は `WATSONX_API_KEY` を設定します。CP4Dのユーザー名/パスワード認証を使う場合は `WATSONX_USERNAME` / `WATSONX_PASSWORD` を設定します。両方は不要です。

> **Watson News用モデル設定:** Watson Newsの記事エンリッチメントとEmbeddingに使用するモデルも同じモデルを参照するよう以下を設定してください:
> ```env
> WATSON_NEWS_ENRICH_MODEL=openai/gpt-oss-120b
> WATSON_NEWS_EMBED_MODEL=ibm/granite-embedding-107m-multilingual
> ```

---

#### 他のLLMプロバイダーを使う場合（参考）

| プロバイダー | 設定例 |
|-------------|-------|
| OpenAI（クラウド） | `OPENAI_API_KEY=sk-...` |
| Anthropic Claude | `ANTHROPIC_API_KEY=sk-ant-...` |
| Ollama（ローカル） | `OLLAMA_ENDPOINT=http://localhost:11434` |

---

### オプション設定

```env
# ポート設定（他サービスと競合する場合に変更）
FRONTEND_PORT=3000    # フロントエンド（デフォルト: 3000）
LANGFLOW_PORT=7860    # Langflow（デフォルト: 7860）
```

---

## 5. 前提条件の確認

すべてのツールが正しくインストールされているか確認します:

```bash
make check_tools
```

以下のように表示されれば成功です:

```
Checking required tools...

✓ Python 3.13.x
✓ uv x.x.x
✓ Node.js 20.x.x
✓ npm x.x.x
✓ Docker version x.x.x    # Podmanの場合は "podman version x.x.x"
✓ Make x.x.x

All required tools are installed and meet version requirements!
```

エラーが表示された場合は、該当するセクションに戻ってインストールを確認してください。

---

## 6. 依存関係のインストール

```bash
make setup
```

このコマンドは以下を実行します:
- Pythonバックエンドの依存関係をインストール（`uv sync`）
- フロントエンドの依存関係をインストール（`npm install`）
- `.env` ファイルの確認

---

## 7. （オプション）初回ウィザードのスキップ

OpenRAGは初回起動時に **セットアップウィザード**（モデルプロバイダーの選択・設定を行う4ステップのUI）が表示されます。`.env` に設定済みの情報を使って起動前にウィザードをスキップすることができます。

### 仕組み

ウィザードの表示は `config/config.yaml` の2つのフィールドで制御されています:

| フィールド | 役割 |
|-----------|------|
| `onboarding.current_step` | `4` 未満のときウィザードを表示（4以上でスキップ） |
| `edited` | `true` のとき `.env` の環境変数上書きを無効化 |

> **重要:** `edited: true` にすると `.env` の `LLM_PROVIDER` / `LLM_MODEL` / `EMBEDDING_*` / `WATSONX_*` などが**すべて無視**されます。`.env` の値を活かしたまま起動するには `edited: false` のままにしてください。

### 手順

**① `config/` ディレクトリと `config.yaml` を作成します:**

```bash
mkdir -p config
```

`config/config.yaml` を以下の内容で作成します:

```yaml
# config/config.yaml
# edited: false にすることで .env の環境変数が引き続き適用される
edited: false

onboarding:
  current_step: 4      # 4 以上でウィザードをスキップ
  assistant_message: null
  card_steps: null
  upload_steps: null
  selected_nudge: null
  openrag_docs_filter_id: null
  user_doc_filter_id: null

agent:
  llm_provider: openai          # .env の LLM_PROVIDER で上書きされる
  llm_model: gpt-oss-120b       # .env の LLM_MODEL で上書きされる
  system_prompt: ""             # 空欄でデフォルトのシステムプロンプトを使用

knowledge:
  embedding_provider: ibm                              # .env の EMBEDDING_PROVIDER で上書きされる
  embedding_model: granite-embedding-107m-multilingual # .env の EMBEDDING_MODEL で上書きされる
  chunk_size: 1000
  chunk_overlap: 200
  table_structure: true
  ocr: false
  picture_descriptions: false
  index_name: documents

providers:
  openai:
    api_key: ""
    configured: false
  anthropic:
    api_key: ""
    configured: false
  watsonx:
    api_key: ""
    endpoint: ""
    project_id: ""
    configured: false
  ollama:
    endpoint: ""
    configured: false
```

**② 設定の優先順位を確認します:**

```
起動時の読み込み順（edited: false の場合）:

1. config/config.yaml を読み込む
   → onboarding.current_step: 4 が設定される（ウィザードスキップ）
2. .env の環境変数で上書き
   → LLM_PROVIDER, LLM_MODEL, EMBEDDING_*, WATSONX_* 等が適用される
3. フロントエンドが current_step >= 4 を確認
   → ウィザードをスキップしてチャット画面を直接表示
```

**③ アプリケーションを起動します（次のセクションへ進む）:**

```bash
make dev-mac
```

### OpenSearch インデックスについて

ウィザードを完了すると通常 OpenSearch インデックスが自動初期化されます。ウィザードをスキップした場合、初回起動後にインデックスが空の状態になることがあります。その場合は以下で手動初期化してください:

```bash
make db-reset
```

---

## 8. アプリケーションの起動

MacBook（Apple Silicon）向けには **`make dev-mac`** を使います。このコマンドはARM64アーキテクチャに最適化されています。

### 8.1 方法A: フルDockerスタック（最もシンプル）

すべてのサービスをDockerコンテナとして起動します。初めての方や動作確認には最適です。

```bash
make dev-mac
```

初回起動時はDockerイメージのダウンロードに数分かかります。以下のように表示されれば成功です:

```
Starting OpenRAG for macOS Apple Silicon (ARM64)...
Services started!
   Frontend:   http://localhost:3000
   Langflow:   http://localhost:7860
   OpenSearch: http://localhost:9200
   Dashboards: http://localhost:5601
```

サービスの起動状況を確認します:

```bash
make status   # コンテナの起動状態を確認
make health   # 各サービスのヘルスチェック
```

#### `make status` の出力例

**正常時 — すべてのコンテナが `Up` または `(healthy)` 状態:**

```
Container status:
NAME              IMAGE                                           CREATED          STATUS                   PORTS
langflow          langflowai/openrag-langflow:latest              2 minutes ago    Up 2 minutes             0.0.0.0:7860->7860/tcp
openrag-backend   langflowai/openrag-backend:latest               2 minutes ago    Up 2 minutes             0.0.0.0:8000->8000/tcp
openrag-frontend  langflowai/openrag-frontend:latest              2 minutes ago    Up 2 minutes             0.0.0.0:3000->3000/tcp
os                langflowai/openrag-opensearch:latest            2 minutes ago    Up 2 minutes (healthy)   0.0.0.0:9200->9200/tcp
osdash            opensearchproject/opensearch-dashboards:3.0.0   2 minutes ago    Up 2 minutes             0.0.0.0:5601->5601/tcp
```

> **Podman をお使いの場合:** 出力の最初に以下のメッセージが表示されますが正常です。
> ```
> >>>> Executing external compose provider "/opt/homebrew/bin/podman-compose". Please see podman-compose(1) for how to disable this message. <<<<
> ```

**エラー例 1 — コンテナが再起動ループ中（メモリ不足など）:**

```
Container status:
NAME              IMAGE                                           CREATED         STATUS
langflow          langflowai/openrag-langflow:latest              5 minutes ago   Up 4 minutes             0.0.0.0:7860->7860/tcp
openrag-backend   langflowai/openrag-backend:latest               5 minutes ago   Up 4 minutes             0.0.0.0:8000->8000/tcp
openrag-frontend  langflowai/openrag-frontend:latest              5 minutes ago   Up 4 minutes             0.0.0.0:3000->3000/tcp
os                langflowai/openrag-opensearch:latest            5 minutes ago   Restarting (1) 3 seconds ago
osdash            opensearchproject/opensearch-dashboards:3.0.0   5 minutes ago   Up 4 minutes             0.0.0.0:5601->5601/tcp
```

→ `Restarting` が表示されているコンテナはクラッシュしています。`make logs-os` でログを確認してください。

**エラー例 2 — コンテナが起動していない:**

```
Container status:
No containers running
```

→ `make dev-mac` でコンテナを起動してください。

---

#### `make health` の出力例

**正常時 — すべてのサービスが応答している:**

```
Health check:
Backend:    {"status":"ok"}
Langflow:   {"status":"ok"}
OpenSearch: You Know, for Search
```

**エラー例 1 — 一部のサービスが未起動（起動直後など）:**

```
Health check:
Backend:    Not responding
Langflow:   Not responding
OpenSearch: You Know, for Search
```

→ コンテナが起動中の可能性があります。1〜2分待ってから再度実行してください。

**エラー例 2 — すべてのサービスが応答しない:**

```
Health check:
Backend:    Not responding
Langflow:   Not responding
OpenSearch: Not responding
```

→ Docker/Podman が起動しているか確認し、`make status` でコンテナ状態を確認してください。

---

すべてのサービスが `Up` または `healthy` になるまで1〜2分お待ちください。

---

### 8.2 方法B: ローカル開発（推奨）

コードを頻繁に編集する開発者向けです。インフラはDockerで動かしつつ、バックエンドとフロントエンドはローカルで実行することで、コード変更を即座に反映できます。

**4つのターミナルウィンドウを開いて、それぞれで以下を実行します:**

**ターミナル 1 — インフラ起動:**
```bash
make dev-local-mac
```

すべてのインフラサービス（OpenSearch、Langflow、Dashboards）が起動するまで待ちます（1〜2分）。

**ターミナル 2 — バックエンド起動:**
```bash
make backend
```

**ターミナル 3 — フロントエンド起動:**
```bash
make frontend
```

**ターミナル 4（オプション）— Doclingサービス起動:**
```bash
make docling
```

> **Doclingとは:** PDFや画像からテキストを抽出するドキュメント処理サービスです。PDFのアップロード機能を使う場合は起動が必要です。

---

## 9. 動作確認

### サービスへのアクセス

| サービス | URL | 説明 |
|---------|-----|------|
| **フロントエンド（OpenRAG UI）** | http://localhost:3000 | メインのチャットUI |
| **Langflow** | http://localhost:7860 | AIフローの管理・編集 |
| **OpenSearch Dashboards** | http://localhost:5601 | 検索インデックスの管理 |
| **バックエンドAPI** | http://localhost:8000 | REST API（直接アクセス用） |

### 動作確認手順

1. ブラウザで http://localhost:3000 を開く
2. OpenRAGのチャット画面が表示されることを確認
3. チャット欄に質問を入力して送信し、AIからの回答が返ってくることを確認
4. 画面左側からドキュメントをアップロードして、そのドキュメントについて質問できることを確認

---

## 10. 日常的な操作

### サービスの停止

```bash
make stop
```

### サービスの再起動

```bash
# 方法A（フルスタック）の場合
make stop
make dev-mac

# 方法B（ローカル開発）の場合
# 各ターミナルで Ctrl+C を押して停止した後、再度起動
```

### ログの確認

```bash
make logs        # 全サービスのログ
make logs-be     # バックエンドのみ
make logs-fe     # フロントエンドのみ
make logs-lf     # Langflowのみ
make logs-os     # OpenSearchのみ
```

### コンテナの状態確認

```bash
make status      # コンテナ一覧と状態
make health      # ヘルスチェック
```

**`make status` の正常な出力（すべて `Up`）:**

```
Container status:
NAME              IMAGE                                           STATUS
langflow          langflowai/openrag-langflow:latest              Up X minutes
openrag-backend   langflowai/openrag-backend:latest               Up X minutes
openrag-frontend  langflowai/openrag-frontend:latest              Up X minutes
os                langflowai/openrag-opensearch:latest            Up X minutes (healthy)
osdash            opensearchproject/opensearch-dashboards:3.0.0   Up X minutes
```

**`make health` の正常な出力（すべてのサービスが応答）:**

```
Health check:
Backend:    {"status":"ok"}
Langflow:   {"status":"ok"}
OpenSearch: You Know, for Search
```

いずれかのサービスが `Not responding` と表示される場合は、`make logs` でエラーを確認してください。

---

## 11. トラブルシューティング

### ポートが使用中のエラー

```
Error: port is already allocated
```

他のアプリが同じポートを使っている場合、`.env` でポートを変更します:

```env
FRONTEND_PORT=3001    # 3000 が使われている場合
LANGFLOW_PORT=7861    # 7860 が使われている場合
```

使用中のポートを確認するには:

```bash
lsof -i :3000   # ポート3000を使っているプロセスを表示
lsof -i :7860   # ポート7860を使っているプロセスを表示
```

---

### コンテナがクラッシュする / 動作が遅い

割り当てメモリが不足している可能性があります。

**Docker Desktop の場合:**

1. Docker Desktop を開く
2. **Settings（歯車アイコン）** → **Resources** → **Memory** を増やす（12GB以上推奨）
3. **Apply & Restart**

**Podman の場合:**

```bash
# 現在のマシン設定を確認
podman machine inspect

# マシンを停止・削除して、より多くのメモリで再作成
podman machine stop
podman machine rm
podman machine init --memory 12288 --cpus 4   # 12GB RAM
podman machine start
```

---

### Podman 固有のトラブルシューティング

**`podman machine` が起動しない:**

```bash
# マシンのステータス確認
podman machine list

# ログ確認
podman machine ssh -- journalctl -xe
```

**`podman compose` コマンドが見つからない:**

```bash
# podman のバージョン確認（4.7以上が必要）
podman --version

# バージョンが古い場合はアップデート
brew upgrade podman

# または Python製 podman-compose をインストール
pip install podman-compose
# インストール後は "podman-compose" コマンドを使う
podman-compose -f docker-compose.yml -f docker-compose.mac.yml up -d
```

**`host.docker.internal` が解決できない（Podman）:**

PodmanではデフォルトでDockerのホスト名解決が使えない場合があります。`.env` に以下を追加してください:

```env
HOST_DOCKER_INTERNAL=host.containers.internal
```

**`podman-compose` を使う場合の `make` コマンドについて:**

MakefileはDockerが存在しない場合に自動的に `podman` を使用します。ただし、`podman-compose`（Python製）はMakefileが自動認識しないため、直接コマンドを実行する必要があります:

```bash
# make dev-mac の代わり（podman-compose を使う場合）
podman-compose -f docker-compose.yml -f docker-compose.mac.yml up -d
```

---

### OpenSearchが起動しない

```bash
# ログを確認
make logs-os

# データをリセット（既存データが消えます）
make clear-os-data
make dev-mac
```

---

### `.env` ファイルの設定ミス

環境変数を変更した後は、コンテナを再起動する必要があります:

```bash
make stop
make dev-mac
```

---

### Doclingサービスが起動しない / PDFがアップロードできない

バックエンドログ（`make logs-be`）に以下のエラーが繰り返し出力される場合、Doclingサービスが起動していません。

```
[ERROR] [docling.py:122] Docling health check failed
                         - url: http://host.containers.internal:5001/health
                         - error: All connection attempts failed
INFO:  "GET /docling/health HTTP/1.1" 503 Service Unavailable
```

**Doclingとは:** PDFや画像からテキストを抽出するドキュメント処理サービスで、**別ターミナルで手動起動**が必要です（自動起動しません）。

#### 対処方法

**新しいターミナルウィンドウを開いて実行します:**

```bash
make docling
```

**正常に起動した場合の出力:**

```
Starting docling-serve...
Starting docling-serve on auto-detected host:5001...
Docling-serve is running
Endpoint: http://host.containers.internal:5001
PID: 12345
Docling-serve started! Use 'make docling-stop' to stop it.
```

起動後、バックエンドログのエラーが止まり、PDFのアップロードが可能になります。

#### Doclingの起動に失敗する場合

**依存ライブラリが未インストール:**

```bash
# 依存関係を再インストール
make setup
# 再度起動
make docling
```

**ポート 5001 が使用中:**

```bash
# 使用中のプロセスを確認
lsof -i :5001

# プロセスを終了してから再起動
kill <PID>
make docling
```

**Podman で `host.containers.internal` が解決できない場合:**

`.env` に以下を追加してください:

```env
HOST_DOCKER_INTERNAL=host.containers.internal
```

> **注意:** Doclingは PDF処理にのみ使用します。テキストファイルや通常のRAGクエリには影響しません。PDFアップロードを使用しない場合は起動不要です。

---

### 完全リセット（最終手段）

うまく動かない場合は、すべてをリセットして最初からやり直します:

> **警告:** すべてのデータ（アップロードしたドキュメント、インデックスなど）が削除されます。

```bash
make factory-reset   # 確認プロンプトで "yes" と入力
cp .env.example .env  # .env を再作成
# .env を編集して必要な値を設定
make setup
make dev-mac
```

---

### よくある質問

**Q: `make check_tools` で Python のバージョンエラーが出る**

```
✗ Python 3.x.x found, but 3.13+ required
```

`uv` でインストールした Python 3.13 が使われていない可能性があります。以下を確認してください:

```bash
uv run python --version   # uv 経由で確認
```

**Q: `OPENSEARCH_PASSWORD` のエラーが出る**

OpenSearchのパスワードは複雑さ要件があります。大文字・小文字・数字・記号をそれぞれ1文字以上含む8文字以上のパスワードを設定してください。

例: `OpenRag@2024!`

**Q: 初回起動に時間がかかる**

初回起動時はDockerイメージのダウンロード（数GB）があるため、ネットワーク速度によっては10〜20分かかることがあります。2回目以降はキャッシュが使われるため高速です。

**Q: watsonx.ai に接続できない（SSL証明書エラー）**

オンプレミスOCPで自己署名証明書を使用している場合は以下を設定してください:

```env
# 証明書検証を無効にする（開発環境向け）
WATSONX_SSL_VERIFY=false

# または CA バンドルを指定する（本番環境向け）
WATSONX_CA_BUNDLE_PATH=/path/to/your/ca-bundle.pem
```

**Q: `LLM_PROVIDER=openai` なのに watsonx.ai が使われるのか？**

はい。OpenRAGでは on-prem OCP の watsonx.ai が OpenAI互換 API エンドポイントを提供するため、`LLM_PROVIDER=openai` と設定します。実際のリクエストは `WATSONX_API_URL` で指定したCP4Dホストへ送信されます。

**Q: `WATSONX_PROJECT_ID` の確認方法は？**

CP4Dの管理コンソールにログイン → 左メニューの **Projects** → 該当プロジェクトを選択 → ブラウザのURLに含まれるUUID（例: `...projects/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`）がProject IDです。

---

## 参考リンク

- [CONTRIBUTING_jp.md](CONTRIBUTING_jp.md) — 開発への貢献ガイド
- [.env.example](.env.example) — 全環境変数のリファレンス
- [OpenRAGドキュメント](https://docs.openr.ag/) — 公式ドキュメント（英語）
- [Issues](https://github.com/langflow-ai/openrag/issues) — バグ報告・質問
