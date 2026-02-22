# MacBook 開発環境セットアップガイド

このガイドでは、MacBook（Apple Silicon / Intel）でOpenRAGの開発環境を初回から構築し、アプリケーションを利用可能にするまでの手順を説明します。

---

## 目次

1. [システム要件](#1-システム要件)
2. [前提ツールのインストール](#2-前提ツールのインストール)
   - 2.1 [Homebrew](#21-homebrew)
   - 2.2 [Docker Desktop](#22-docker-desktop)
   - 2.3 [uv（Pythonパッケージマネージャー）](#23-uvpythonパッケージマネージャー)
   - 2.4 [Python 3.13](#24-python-313)
   - 2.5 [Node.js](#25-nodejs)
3. [リポジトリのクローン](#3-リポジトリのクローン)
4. [環境変数の設定](#4-環境変数の設定)
5. [前提条件の確認](#5-前提条件の確認)
6. [依存関係のインストール](#6-依存関係のインストール)
7. [アプリケーションの起動](#7-アプリケーションの起動)
   - 7.1 [方法A: フルDockerスタック（最もシンプル）](#71-方法a-フルdockerスタック最もシンプル)
   - 7.2 [方法B: ローカル開発（推奨）](#72-方法b-ローカル開発推奨)
8. [動作確認](#8-動作確認)
9. [日常的な操作](#9-日常的な操作)
10. [トラブルシューティング](#10-トラブルシューティング)

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

### 2.2 Docker Desktop

OpenRAGのインフラ（OpenSearch、Langflowなど）はDockerコンテナで動作します。

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

```env
# LLMプロバイダーのAPIキー（最低1つ必須）
OPENAI_API_KEY=sk-...           # OpenAI を使う場合
ANTHROPIC_API_KEY=sk-ant-...    # Anthropic Claude を使う場合

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

### オプション設定

```env
# ポート設定（他サービスと競合する場合に変更）
FRONTEND_PORT=3000    # フロントエンド（デフォルト: 3000）
LANGFLOW_PORT=7860    # Langflow（デフォルト: 7860）

# ローカルでOllamaを使う場合
OLLAMA_ENDPOINT=http://localhost:11434
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
✓ Docker version x.x.x
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

## 7. アプリケーションの起動

MacBook（Apple Silicon）向けには **`make dev-mac`** を使います。このコマンドはARM64アーキテクチャに最適化されています。

### 7.1 方法A: フルDockerスタック（最もシンプル）

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

すべてのサービスが `Up` または `healthy` になるまで1〜2分お待ちください。

---

### 7.2 方法B: ローカル開発（推奨）

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

## 8. 動作確認

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

## 9. 日常的な操作

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

---

## 10. トラブルシューティング

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

### Dockerコンテナがクラッシュする / 動作が遅い

Dockerに割り当てているメモリが不足している可能性があります。

1. Docker Desktop を開く
2. **Settings（歯車アイコン）** → **Resources** → **Memory** を増やす（12GB以上推奨）
3. **Apply & Restart**

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

---

## 参考リンク

- [CONTRIBUTING_jp.md](CONTRIBUTING_jp.md) — 開発への貢献ガイド
- [.env.example](.env.example) — 全環境変数のリファレンス
- [OpenRAGドキュメント](https://docs.openr.ag/) — 公式ドキュメント（英語）
- [Issues](https://github.com/langflow-ai/openrag/issues) — バグ報告・質問
