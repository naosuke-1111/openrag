# SNSクロール実装方針書

> 作成日: 2026-02-22
> ブランチ: `claude/add-social-media-crawling-C3kXu`
> 関連ファイル: `watson-news/implementation-strategy.md`, `watson-news/ibm_crawl_targets.yaml`

---

## 1. 概要

IBM公式SNSアカウントの投稿データをクロールし、openRAG の既存 ETL パイプラインへ統合する。
YouTube・Podcast については音声トランスクリプト処理（取得または音声認識）と日本語翻訳を行う。

### 対象プラットフォームと取得方式の一覧

| プラットフォーム | 取得方式 | 認証 | 難易度 |
|---|---|---|---|
| X (Twitter) | Twitter API v2 | OAuth 2.0 Bearer Token | 中 |
| Instagram | Instagram Graph API (Meta) | Page Access Token | 高 |
| Facebook | Facebook Graph API (Meta) | Page Access Token | 中 |
| YouTube | YouTube Data API v3 + 字幕/Whisper | API Key / OAuth 2.0 | 中 |
| Podcast | RSS フィード解析 + Whisper | なし（公開フィード） | 低 |
| LinkedIn | LinkedIn API v2 | OAuth 2.0（要パートナー審査） | 高 |

> **注意:** 各プラットフォームの利用規約（ToS）を遵守する。スクレイピング（非公式クロール）は
> ToS 違反・アカウント停止リスクがあるため、**すべて公式APIを使用する**。

---

## 2. ディレクトリ構成

```
openrag/
├── watson-news/
│   ├── ibm_crawl_targets.yaml            # 既存（WebクロールターゲットYAML）
│   ├── ibm_sns_targets.yaml              # 新規追加（SNSアカウント設定）
│   ├── implementation-strategy.md        # 既存（Watson News 全体方針）
│   └── sns-crawling-strategy.md          # 本ファイル
└── src/
    └── connectors/
        └── watson_news/
            ├── ibm_crawl_connector.py    # 既存
            ├── gdelt_connector.py        # 既存
            ├── etl_pipeline.py           # 既存（SNSを組み込む）
            ├── scheduler.py              # 既存（SNSジョブを追加）
            ├── enricher.py               # 既存（翻訳処理を追加）
            ├── sns/                      # 新規追加
            │   ├── __init__.py
            │   ├── x_connector.py        # X (Twitter) API v2
            │   ├── instagram_connector.py# Instagram Graph API
            │   ├── facebook_connector.py # Facebook Graph API
            │   ├── youtube_connector.py  # YouTube Data API v3
            │   ├── podcast_connector.py  # RSS + 音声処理
            │   ├── linkedin_connector.py # LinkedIn API v2
            │   └── transcript_pipeline.py# 音声認識・翻訳共通パイプライン
            └── cleaner.py                # 既存（SNSテキスト正規化を追加）
```

---

## 3. 各プラットフォーム実装方針

### 3.1 X (Twitter)

#### 対象アカウント
```
https://x.com/IBM
https://x.com/IBM_JAPAN
https://x.com/IBM_UK_news
https://x.com/IBMDACH
https://x.com/IBM_France
```

#### API・認証
- **Twitter API v2** を使用
- 認証: **OAuth 2.0 Bearer Token**（App-only）
- 必要なスコープ: `tweet.read`, `users.read`
- プラン: **Basic（$100/月）** 推奨（Free は月500ツイート読み取りのみ）
- ライブラリ: `tweepy>=4.14`

#### 取得フロー
```
1. GET /2/users/by?usernames=IBM,IBM_JAPAN,...
   → ユーザーIDを取得

2. GET /2/users/:id/tweets
   → 最新ツイートを取得（デフォルト最大100件、ページネーションで全件）
   → フィールド: id, text, created_at, entities, public_metrics, attachments

3. 差分検知: tweet.id を OpenSearch に保存し、既知IDを除外
```

#### 取得フィールド
| フィールド | 説明 |
|---|---|
| `id` | ツイートID |
| `text` | 本文 |
| `created_at` | 投稿日時 |
| `entities.urls` | リンク展開URL |
| `entities.hashtags` | ハッシュタグ |
| `public_metrics` | いいね数・RT数・リプライ数・インプレッション数 |
| `attachments.media_keys` | 添付メディア（画像・動画）参照 |

#### レートリミット対応
- Basic プラン: 15分ごとに15リクエスト（`GET /2/users/:id/tweets`）
- `429 Too Many Requests` 受信時: `Retry-After` ヘッダーに従い待機
- クロール間隔: 各アカウント 4時間ごと

---

### 3.2 Instagram

#### 対象アカウント
```
https://www.instagram.com/ibm/
https://www.instagram.com/ibm_japan/
https://www.instagram.com/ibm_dach/
```

#### API・認証
- **Instagram Graph API**（Meta for Developers）を使用
- 前提条件:
  1. Meta Business Suiteで Facebook ページと Instagram アカウントを連携
  2. Meta Developer App を作成し `instagram_basic`・`pages_read_engagement` 権限を取得
  3. Page Access Token（長期トークン）を取得
- ライブラリ: `httpx`（直接 REST 呼び出し）

#### 取得フロー
```
1. GET /{ig-user-id}/media
   ?fields=id,caption,media_type,media_url,thumbnail_url,timestamp,permalink,like_count,comments_count
   → 投稿リストを取得（カーソルベースページネーション）

2. 差分検知: media.id を OpenSearch に保存し、既知IDを除外

3. 動画投稿: media_url (動画URL) を記録、キャプションをテキストとして使用
```

#### 注意事項
- Instagram Graph API は **Business アカウント / Creator アカウントのみ対応**
- `ibm/`・`ibm_japan/`・`ibm_dach/` が Business アカウントであることを事前確認する必要がある
- 個人アカウントは Basic Display API（2024年12月廃止）で対応不可 → API 経由では取得不可

---

### 3.3 Facebook

#### 対象アカウント
```
https://www.facebook.com/IBM/
https://www.facebook.com/IBMJapan/
https://www.facebook.com/IBMUK/
https://www.facebook.com/IBMDeutschland/
```

#### API・認証
- **Facebook Graph API v21.0** を使用
- 認証: Page Access Token（`pages_read_engagement` 権限）
- 取得方法:
  1. Facebook Developer App を作成
  2. ページ管理者から `pages_read_engagement` 権限付き Token を取得
  3. 長期 Page Access Token に変換（60日有効）して保存
- ライブラリ: `httpx`

#### 取得フロー
```
1. GET /{page-id}/posts
   ?fields=id,message,story,created_time,full_picture,permalink_url,
           attachments{media,type},reactions.summary(true),comments.summary(true)
   → 投稿リストを取得（カーソルベースページネーション）

2. 差分検知: post.id を OpenSearch に保存し、既知IDを除外
```

#### 注意事項
- ページ ID は URL スラッグ（例: `IBM`）から Graph API で解決する
  ```
  GET /IBM?fields=id,name
  ```
- `pages_read_engagement` は通常の App Review で取得可能
- ページ投稿の公開設定によっては取得できないものがある

---

### 3.4 YouTube

#### 対象チャンネル
```
https://www.youtube.com/user/IBM             → @IBM
https://www.youtube.com/user/IBMJapanChannel → @IBMJapan
https://www.youtube.com/user/IBMDeutschland  → @IBMDeutschland
```

#### API・認証
- **YouTube Data API v3**（`google-api-python-client` は `pyproject.toml` に既存）
- 認証: API Key（読み取り専用）
- 無料クォータ: 10,000 ユニット/日（動画リスト: 1ユニット/リクエスト）
- ライブラリ: `google-api-python-client`, `youtube-transcript-api>=0.6`, `yt-dlp>=2024.1`, `faster-whisper>=1.0`

#### 取得フロー
```
1. channels.list?part=contentDetails&forHandle=IBM
   → チャンネルの uploads プレイリスト ID を取得

2. playlistItems.list?part=contentDetails&playlistId={uploadsId}
   → 動画IDリストを取得（ページネーション）

3. videos.list?part=snippet,contentDetails&id={video_ids}
   → 動画メタデータを取得（タイトル・説明・公開日時・字幕有無）

4. 差分検知: video.id を OpenSearch に保存し、既知IDを除外

5. トランスクリプト取得（後述の 4章 参照）

6. 翻訳: 日本語以外のトランスクリプトを日本語に翻訳（watsonx.ai）
```

#### トランスクリプト取得戦略
```
[優先順位]
1. 公式字幕 (youtube-transcript-api)
   └─ captions が存在 → transcript_api.get_transcript(video_id, languages=['ja', 'en', ...])

2. 自動生成字幕 (Auto-generated captions)
   └─ 自動字幕が存在 → transcript_api.get_transcript(video_id, languages=['ja', 'en', ...])

3. 音声認識 (Whisper)
   └─ 字幕なし → yt-dlp で音声抽出 (mp3/wav) → faster-whisper で文字起こし
```

---

### 3.5 Podcast

#### 対象フィード
```
https://podcasts.apple.com/jp/podcast/smart-talks-with-ibm/id1558889546
https://www.ibm.com/think/podcasts/smart-talks
```

#### API・認証
- 公開 RSS フィードのため認証不要
- Apple Podcasts ID → RSS URL 解決: iTunes Search API
  ```
  GET https://itunes.apple.com/lookup?id=1558889546
  → feedUrl フィールドに RSS URL が含まれる
  ```
- ライブラリ: `feedparser>=6.0`, `httpx`, `yt-dlp>=2024.1`, `faster-whisper>=1.0`

#### 取得フロー
```
1. iTunes Lookup API で RSS フィード URL を解決

2. feedparser でエピソードリストを取得
   → フィールド: title, summary, published, enclosure(audio URL), duration, link

3. Podcasting 2.0 namespace でトランスクリプト確認:
   <podcast:transcript url="..." type="text/vtt" /> または "text/plain"

4. 差分検知: episode.link または episode の guid を OpenSearch に保存

5. トランスクリプト取得（後述の 4章 参照）

6. 翻訳: 英語トランスクリプトを日本語に翻訳（watsonx.ai）
```

---

### 3.6 LinkedIn

#### 対象プロフィール
```
https://www.linkedin.com/in/arvindkrishna    # IBM CEO
https://www.linkedin.com/in/robertdthomas    # IBM CCO
https://www.linkedin.com/in/dariogil         # IBM CRO
https://www.linkedin.com/in/nickle-lamoreaux # IBM VP
https://www.linkedin.com/in/jaygambetta      # IBM VP, Quantum
```

#### API・認証と制約

> ⚠️ **LinkedIn は個人プロフィールの投稿取得において最も制約が多い。**

- **LinkedIn API v2** を使用
- 認証: OAuth 2.0（個人メンバーが認証する必要がある）
- **課題**: 個人プロフィールの投稿（`/ugcPosts`）を読み取るには、投稿者本人のアクセストークンが必要
- 会社ページの投稿は `Marketing Developer Platform`（パートナー審査が必要）で取得可能

#### 現実的な取得方針

**フェーズ1（MVP）: IBM公式ページ投稿の取得**

LinkedIn Company Pages API を利用して、IBM公式ページの投稿のみを取得する。
個人プロフィールは後フェーズに先送りする。

```
Company Page URN: urn:li:organization:{organization_id}

GET /v2/ugcPosts?q=authors&authors=List(urn:li:organization:{id})
   → 投稿リスト取得（requires: Marketing Developer Platform Partner approval）
```

**フェーズ2（正式対応）: 個人プロフィール**

IBM の担当者と連携し、対象幹部が自身のアクセストークンを発行する運用フローを整備する。
または LinkedIn Sales Navigator API（有償）の利用を検討する。

**フェーズ1 代替案: RSSフィード**

LinkedIn は個人プロフィールの公開 RSS フィードを現在提供していない。
`https://www.linkedin.com/in/{username}/recent-activity/shares/rss/` は認証が必要。

> **結論**: LinkedIn 個人プロフィールの自動クロールは、LinkedIn のポリシー上 Phase 1 では非推奨。
> Phase 1 は「LinkedIn コネクタの認証基盤と会社ページ取得」のみ実装し、個人プロフィールは Phase 2 以降とする。

---

## 4. トランスクリプト処理パイプライン（YouTube・Podcast 共通）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       transcript_pipeline.py                                │
│                                                                             │
│  Input: video_id (YouTube) または audio_url (Podcast)                      │
│                                                                             │
│  ┌────────────────────────────────┐                                         │
│  │ Step 1: トランスクリプト確認   │                                         │
│  │                                │                                         │
│  │ YouTube:                       │                                         │
│  │   youtube-transcript-api       │                                         │
│  │   ├─ 公式字幕あり → 取得       │                                         │
│  │   ├─ 自動字幕あり → 取得       │                                         │
│  │   └─ なし → Step 2へ          │                                         │
│  │                                │                                         │
│  │ Podcast:                       │                                         │
│  │   RSS の podcast:transcript    │                                         │
│  │   ├─ URL あり → ダウンロード   │                                         │
│  │   └─ なし → Step 2へ          │                                         │
│  └────────────────────────────────┘                                         │
│             │ なし                                                           │
│             ▼                                                               │
│  ┌────────────────────────────────┐                                         │
│  │ Step 2: 音声ダウンロード       │                                         │
│  │   yt-dlp                       │                                         │
│  │   ├─ YouTube: 音声のみ抽出     │                                         │
│  │   │   (format: bestaudio/mp3)  │                                         │
│  │   └─ Podcast: 添付 URL から    │                                         │
│  │       mp3 直接ダウンロード     │                                         │
│  └────────────────────────────────┘                                         │
│             │                                                               │
│             ▼                                                               │
│  ┌────────────────────────────────┐                                         │
│  │ Step 3: 音声認識 (Whisper)     │                                         │
│  │   faster-whisper               │                                         │
│  │   ├─ モデル: medium / large-v3 │                                         │
│  │   ├─ 言語: 自動検出            │                                         │
│  │   └─ 出力: テキスト + タイムスタンプ│                                    │
│  └────────────────────────────────┘                                         │
│             │                                                               │
│             ▼ (どちらのパスも合流)                                          │
│  ┌────────────────────────────────┐                                         │
│  │ Step 4: 言語検出               │                                         │
│  │   langdetect                   │                                         │
│  │   ├─ 日本語(ja) → 翻訳スキップ │                                         │
│  │   └─ 非日本語 → Step 5へ      │                                         │
│  └────────────────────────────────┘                                         │
│             │ 非日本語                                                       │
│             ▼                                                               │
│  ┌────────────────────────────────┐                                         │
│  │ Step 5: 日本語翻訳             │                                         │
│  │   watsonx.ai (既存 enricher)   │                                         │
│  │   ├─ 入力: 元言語テキスト      │                                         │
│  │   └─ 出力: 日本語翻訳テキスト  │                                         │
│  └────────────────────────────────┘                                         │
│             │                                                               │
│             ▼                                                               │
│  Output:                                                                    │
│   - transcript_original: str  (元言語テキスト)                              │
│   - transcript_ja: str        (日本語翻訳テキスト、元言語が ja の場合は同値) │
│   - transcript_lang: str      (元言語コード, e.g. "en", "de")               │
│   - transcript_source: str    ("official" | "auto" | "whisper")             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Whisper モデル選定

| モデル | VRAM目安 | 精度 | 推奨用途 |
|---|---|---|---|
| `tiny` | ~1GB | 低 | 開発・テスト用 |
| `medium` | ~5GB | 中 | CPU環境本番 |
| `large-v3` | ~10GB | 高 | GPU環境本番（推奨） |

> GPU 利用可能な場合は `large-v3` を推奨。CPU のみの場合は `medium` を使用し、
> `compute_type="int8"` で量子化して速度を改善する。

---

## 5. データスキーマ

### 5.1 SNS共通 ConnectorDocument メタデータ

既存の `ConnectorDocument` を流用し、`metadata` フィールドに以下を格納する。

```python
metadata = {
    # 共通
    "source_type": "sns",                    # 固定値
    "platform": "x" | "instagram" | ...,    # プラットフォーム識別子
    "account_id": "IBM",                     # アカウント識別子
    "account_url": "https://x.com/IBM",      # アカウントURL
    "post_id": "...",                        # プラットフォーム固有ID
    "post_url": "...",                       # 投稿URL
    "published_at": "2026-02-22T00:00:00Z",  # 投稿日時 (ISO 8601)
    "language": "en",                        # 投稿言語
    "engagement": {                          # エンゲージメント指標
        "likes": 123,
        "shares": 45,
        "comments": 12,
    },

    # YouTube・Podcast 追加フィールド
    "media_type": "video" | "podcast",
    "duration_seconds": 1234,
    "transcript_source": "official" | "auto" | "whisper",
    "transcript_lang": "en",
    "has_ja_translation": True,
}
```

### 5.2 OpenSearch インデックス

SNS データは新規インデックス `watson_news_sns` に格納する。

```json
{
  "mappings": {
    "properties": {
      "id":                  { "type": "keyword" },
      "platform":            { "type": "keyword" },
      "account_id":          { "type": "keyword" },
      "post_id":             { "type": "keyword" },
      "post_url":            { "type": "keyword" },
      "text":                { "type": "text", "analyzer": "standard" },
      "text_ja":             { "type": "text", "analyzer": "kuromoji" },
      "transcript_original": { "type": "text", "analyzer": "standard" },
      "transcript_ja":       { "type": "text", "analyzer": "kuromoji" },
      "transcript_source":   { "type": "keyword" },
      "published_at":        { "type": "date" },
      "language":            { "type": "keyword" },
      "embedding":           { "type": "knn_vector", "dimension": 384 },
      "metadata":            { "type": "object", "dynamic": true }
    }
  }
}
```

---

## 6. 設定ファイル (`watson-news/ibm_sns_targets.yaml`)

```yaml
# IBM SNSアカウント クロール対象設定

defaults:
  enabled: true
  interval_hours: 4
  max_posts_per_run: 50

platforms:
  x:
    accounts:
      - id: IBM
        url: "https://x.com/IBM"
        language: en
      - id: IBM_JAPAN
        url: "https://x.com/IBM_JAPAN"
        language: ja
      - id: IBM_UK_news
        url: "https://x.com/IBM_UK_news"
        language: en
      - id: IBMDACH
        url: "https://x.com/IBMDACH"
        language: de
      - id: IBM_France
        url: "https://x.com/IBM_France"
        language: fr

  instagram:
    accounts:
      - id: ibm
        url: "https://www.instagram.com/ibm/"
        language: en
      - id: ibm_japan
        url: "https://www.instagram.com/ibm_japan/"
        language: ja
      - id: ibm_dach
        url: "https://www.instagram.com/ibm_dach/"
        language: de

  facebook:
    accounts:
      - id: IBM
        url: "https://www.facebook.com/IBM/"
        language: en
      - id: IBMJapan
        url: "https://www.facebook.com/IBMJapan/"
        language: ja
      - id: IBMUK
        url: "https://www.facebook.com/IBMUK/"
        language: en
      - id: IBMDeutschland
        url: "https://www.facebook.com/IBMDeutschland/"
        language: de

  youtube:
    whisper_model: "large-v3"      # tiny / medium / large-v3
    compute_type: "float16"        # float16 (GPU) / int8 (CPU)
    interval_hours: 24
    channels:
      - id: IBM
        handle: "@IBM"
        url: "https://www.youtube.com/user/IBM"
        language: en
      - id: IBMJapan
        handle: "@IBMJapan"
        url: "https://www.youtube.com/user/IBMJapanChannel"
        language: ja
      - id: IBMDeutschland
        handle: "@IBMDeutschland"
        url: "https://www.youtube.com/user/IBMDeutschland"
        language: de

  podcast:
    whisper_model: "large-v3"
    compute_type: "float16"
    interval_hours: 24
    feeds:
      - id: smart_talks_with_ibm
        name: "Smart Talks with IBM"
        apple_podcast_id: "1558889546"
        apple_url: "https://podcasts.apple.com/jp/podcast/smart-talks-with-ibm/id1558889546"
        ibm_url: "https://www.ibm.com/think/podcasts/smart-talks"
        language: en

  linkedin:
    enabled: false   # Phase 1 は無効。Phase 2 で個人プロフィール対応を実装する
    profiles:
      - id: arvindkrishna
        url: "https://www.linkedin.com/in/arvindkrishna"
        name: "Arvind Krishna (IBM CEO)"
      - id: robertdthomas
        url: "https://www.linkedin.com/in/robertdthomas"
        name: "Robert D. Thomas (IBM CCO)"
      - id: dariogil
        url: "https://www.linkedin.com/in/dariogil"
        name: "Dario Gil (IBM CRO)"
      - id: nickle-lamoreaux
        url: "https://www.linkedin.com/in/nickle-lamoreaux"
        name: "Nickle LaMoreaux (IBM VP, HR)"
      - id: jaygambetta
        url: "https://www.linkedin.com/in/jaygambetta"
        name: "Jay Gambetta (IBM VP, Quantum)"
```

---

## 7. 環境変数（`.env` への追加）

```bash
# ── X (Twitter) ──────────────────────────────────────────────
TWITTER_BEARER_TOKEN=           # OAuth 2.0 Bearer Token（必須）

# ── Instagram / Facebook (Meta Graph API) ────────────────────
META_APP_ID=                    # Meta Developer App ID（必須）
META_APP_SECRET=                # Meta Developer App Secret（必須）
META_PAGE_ACCESS_TOKEN_IBM=     # IBM Facebook Page Token
META_PAGE_ACCESS_TOKEN_IBMJP=   # IBMJapan Facebook Page Token
META_PAGE_ACCESS_TOKEN_IBMUK=   # IBMUK Facebook Page Token
META_PAGE_ACCESS_TOKEN_IBMDE=   # IBMDeutschland Facebook Page Token
META_IG_USER_ID_IBM=            # Instagram User ID (ibm/)
META_IG_USER_ID_IBMJP=          # Instagram User ID (ibm_japan/)
META_IG_USER_ID_IBMDE=          # Instagram User ID (ibm_dach/)

# ── YouTube ──────────────────────────────────────────────────
YOUTUBE_API_KEY=                # YouTube Data API v3 キー（必須）

# ── LinkedIn ─────────────────────────────────────────────────
LINKEDIN_CLIENT_ID=             # LinkedIn App Client ID（Phase 2）
LINKEDIN_CLIENT_SECRET=         # LinkedIn App Client Secret（Phase 2）
LINKEDIN_ACCESS_TOKEN=          # OAuth 2.0 Access Token（Phase 2）

# ── Whisper / 音声認識 ────────────────────────────────────────
WHISPER_MODEL_SIZE=large-v3     # tiny / medium / large-v3
WHISPER_COMPUTE_TYPE=float16    # float16 (GPU) / int8 (CPU)
WHISPER_DEVICE=cuda             # cuda / cpu
WHISPER_AUDIO_TMP_DIR=/tmp/watson_news_audio  # 一時音声ファイルの保存先

# ── SNS 設定 ─────────────────────────────────────────────────
WATSON_NEWS_SNS_CONFIG=         # 未設定時: watson-news/ibm_sns_targets.yaml を使用
```

---

## 8. 依存パッケージ（`pyproject.toml` への追加）

```toml
# SNS コネクタ
tweepy = ">=4.14"              # X (Twitter) API v2
feedparser = ">=6.0"           # Podcast RSS 解析

# YouTube トランスクリプト
youtube-transcript-api = ">=0.6" # YouTube 字幕取得
yt-dlp = ">=2024.1"            # 音声・動画ダウンロード
faster-whisper = ">=1.0"       # Whisper 音声認識（CUDA/CPU 最適化版）
```

> **注意:** `faster-whisper` は GPU 環境で `torch` + CUDA が利用可能な場合に自動で GPU を使用する。
> `torch` は既存 `pyproject.toml` に記載済みのため、追加不要。

---

## 9. スケジューリング

`scheduler.py` に以下のジョブを追加する（APScheduler 利用、既存方式と統一）。

| ジョブID | コネクタ | 間隔 | 備考 |
|---|---|---|---|
| `sns_x` | X コネクタ（全5アカウント） | 4時間 | レートリミット考慮 |
| `sns_instagram` | Instagram コネクタ（全3アカウント） | 4時間 | |
| `sns_facebook` | Facebook コネクタ（全4ページ） | 4時間 | |
| `sns_youtube` | YouTube コネクタ（全3チャンネル） | 24時間 | Whisper 処理は重いため頻度低め |
| `sns_podcast` | Podcast コネクタ（Smart Talks） | 24時間 | 週1-2回更新が多いため |

---

## 10. 認証情報未設定時のスキップ方針

### 10.1 基本方針

各 SNS コネクタは、**必要な認証情報（API キー・トークン）が環境変数に設定されていない場合、そのプラットフォームのクロールを静かにスキップ**する。
アプリケーション全体を停止させず、他のプラットフォームのクロールは継続する。

- **スキップ = 空リストを返す**（例外を投げない）
- スキップ発生時は `WARNING` レベルでログを記録する
- Podcast は公開 RSS フィードのため認証不要 ＝ 常にクロールを実行する

### 10.2 プラットフォームごとの必須環境変数と未設定時の動作

| プラットフォーム | 必須環境変数 | 未設定時の動作 |
|---|---|---|
| X (Twitter) | `TWITTER_BEARER_TOKEN` | X クロール全体をスキップ・WARNING ログ |
| Instagram | `META_APP_ID`, `META_APP_SECRET`, `META_IG_USER_ID_*` | Instagram クロール全体をスキップ・WARNING ログ |
| Facebook | `META_APP_ID`, `META_PAGE_ACCESS_TOKEN_*` | トークン未設定アカウントのみスキップ・他継続 |
| YouTube | `YOUTUBE_API_KEY` | YouTube クロール全体をスキップ・WARNING ログ |
| Podcast | なし（公開 RSS のため不要） | 常に有効（スキップなし） |
| LinkedIn | `LINKEDIN_ACCESS_TOKEN` | LinkedIn クロールをスキップ（Phase 2・デフォルト無効） |

### 10.3 コネクタ実装パターン

コネクタ初期化時に必要な環境変数を検証し、未設定の場合はコネクタを無効状態としてスキップする。

```python
# 例: x_connector.py
class XConnector:
    PLATFORM = "x"

    def __init__(self) -> None:
        self._token = os.getenv("TWITTER_BEARER_TOKEN")
        self.is_enabled = bool(self._token)
        if not self.is_enabled:
            logger.warning(
                "X コネクタをスキップ: TWITTER_BEARER_TOKEN が未設定",
                connector=self.PLATFORM,
            )

    async def run(self, accounts: list) -> list[ConnectorDocument]:
        if not self.is_enabled:
            return []   # 空リストを返す（例外を投げない）
        ...
```

### 10.4 アカウント単位のスキップ（Facebook・Instagram）

Facebook・Instagram はアカウントごとにトークンを管理するため、**トークン未設定のアカウントのみスキップ**し、設定済みのアカウントは継続する。

```python
# 例: facebook_connector.py
_ACCOUNT_TOKEN_MAP = {
    "IBM":            os.getenv("META_PAGE_ACCESS_TOKEN_IBM"),
    "IBMJapan":       os.getenv("META_PAGE_ACCESS_TOKEN_IBMJP"),
    "IBMUK":          os.getenv("META_PAGE_ACCESS_TOKEN_IBMUK"),
    "IBMDeutschland": os.getenv("META_PAGE_ACCESS_TOKEN_IBMDE"),
}

async def run(self, accounts: list) -> list[ConnectorDocument]:
    results = []
    for account in accounts:
        token = _ACCOUNT_TOKEN_MAP.get(account.id)
        if not token:
            logger.warning(
                "Facebook アカウントをスキップ: トークン未設定",
                account=account.id,
            )
            continue   # このアカウントのみスキップ、他は継続
        results.extend(await self._fetch_account(account, token))
    return results
```

### 10.5 スケジューラへの反映

スケジューラはコネクタの有効・無効状態をジョブ登録時に確認し、**無効コネクタのジョブを登録しない**（ジョブが存在しないためエラーは発生しない）。

```python
# scheduler.py
def register_sns_jobs(scheduler: AsyncIOScheduler) -> None:
    for connector_cls, job_id, hours in [
        (XConnector,        "sns_x",         4),
        (FacebookConnector, "sns_facebook",   4),
        (YouTubeConnector,  "sns_youtube",   24),
        (PodcastConnector,  "sns_podcast",   24),
    ]:
        connector = connector_cls()
        if connector.is_enabled:
            scheduler.add_job(connector.run, "interval", hours=hours, id=job_id)
        else:
            logger.info(
                "SNS ジョブをスキップ（認証情報未設定）",
                job_id=job_id,
            )
```

---

## 11. アプリケーション側の耐障害性

### 11.1 基本方針

SNS データが存在しない（インデックスが空・未作成）場合でも、**検索 API・フロントエンドはエラーを返さず、空の結果を正常レスポンスとして返す**。

- OpenSearch の `index_not_found_exception` はサービス層で吸収し HTTP 200 を返す
- ETL パイプライン内で各コネクタは独立して実行し、1 コネクタの失敗が他に波及しない
- フロントエンドはデータなし状態を専用 UI で表示する

### 11.2 OpenSearch インデックス未作成への対応

`watson_news_sns` インデックスが存在しない場合、OpenSearch は `NotFoundError` を返す。
サービス層でハンドリングし、空リストを返す。

```python
# services/watson_news_service.py
async def search_sns(query: str, ...) -> dict:
    try:
        response = await opensearch.search(index="watson_news_sns", body=...)
        hits = response["hits"]["hits"]
        return {
            "results": hits,
            "total": len(hits),
            "platforms_available": _extract_platforms(hits),
            "message": None,
        }
    except NotFoundError:
        # インデックス未作成 = SNS クロール未実行 → 空を返す
        logger.info("watson_news_sns インデックスが未作成。SNS データなし。")
        return _empty_sns_response("SNS データはまだクロールされていません")
    except Exception as exc:
        logger.error("SNS 検索エラー", error=str(exc))
        return _empty_sns_response("SNS データの取得に失敗しました")


def _empty_sns_response(message: str) -> dict:
    return {"results": [], "total": 0, "platforms_available": [], "message": message}
```

### 11.3 API レスポンスの設計

SNS データが存在しない場合でも **HTTP 200** で空配列を返す。

```json
// SNS データなし（インデックス未作成 or クロール未実行）
{
  "results": [],
  "total": 0,
  "platforms_available": [],
  "message": "SNSデータはまだクロールされていません"
}

// SNS データあり（一部プラットフォームのみ設定済みの場合も含む）
{
  "results": [...],
  "total": 42,
  "platforms_available": ["x", "youtube", "podcast"],
  "message": null
}
```

### 11.4 ETL パイプラインの分離実行

各 SNS コネクタはパイプライン内で**独立して実行**する。1 つのコネクタが例外を投げても他は継続する。

```python
# etl_pipeline.py
async def run_sns_pipeline() -> None:
    connectors: list[BaseSnsConnector] = [
        XConnector(),
        FacebookConnector(),
        YouTubeConnector(),
        PodcastConnector(),
        # Phase 2 で追加:
        # InstagramConnector(),
        # LinkedInConnector(),
    ]
    for connector in connectors:
        try:
            docs = await connector.run()
            await index_documents(docs)
        except Exception as exc:
            # 1 コネクタの失敗が他に波及しない
            logger.error(
                "SNS コネクタ実行エラー（スキップして継続）",
                connector=connector.PLATFORM,
                error=str(exc),
            )
            continue
```

### 11.5 フロントエンドの対応

- SNS フィードコンポーネントは `results` が空配列のとき「データなし」プレースホルダーを表示する
- `platforms_available` が空のとき「SNS 連携が設定されていません」メッセージを表示する
- SNS タブは**常に表示**する（非表示にしない）。設定促進のためデータなし状態を明示する

```tsx
// 例: SNS フィードコンポーネント (Watson News UI)
function SnsFeed({ data }: { data: SnsSearchResponse }) {
  if (data.total === 0) {
    return (
      <EmptyState
        title="SNS データなし"
        description={data.message ?? "SNS クロールの設定を確認してください"}
      />
    );
  }
  return <PostList posts={data.results} />;
}
```

---

## 12. リスクと対策

| リスク | 影響度 | 対策 |
|---|---|---|
| X API のレートリミット超過 | 中 | `429` 受信時に `Retry-After` ヘッダーに従い自動待機。Basic プラン以上を利用 |
| Meta Token 期限切れ | 高 | 長期 Token（60日）を発行。期限前に自動更新ロジックを実装 |
| YouTube API クォータ枯渇 | 中 | クォータ使用量を監視。超過時はクロールをスキップして翌日に持ち越し |
| Whisper の処理時間・コスト | 高 | GPU 環境では `large-v3`、CPU 環境では `medium+int8` を使用。音声は処理後に削除 |
| LinkedIn パートナー審査の長期化 | 高 | Phase 1 は LinkedIn を無効化し、Phase 2 で審査通過後に有効化 |
| Instagram Business アカウント未認証 | 中 | 事前に対象アカウントが Business 設定であることを IBM 側に確認 |
| 各 ToS 変更による API 廃止 | 低 | 定期的に API ドキュメントを確認。廃止時は対象コネクタを `enabled: false` に設定 |
| 大量音声ファイルのストレージ | 中 | Whisper 処理後に一時ファイルを即時削除。`WHISPER_AUDIO_TMP_DIR` を `/tmp` に設定 |

---

## 13. 実装フェーズ

### Phase 1（優先実装）

| 対象 | タスク |
|---|---|
| 共通基盤 | `ibm_sns_targets.yaml` 作成。`watson_news_sns` OpenSearch インデックス定義 |
| YouTube | `youtube_connector.py` 実装。`transcript_pipeline.py` 実装（字幕取得 + Whisper + 翻訳） |
| Podcast | `podcast_connector.py` 実装。iTunes API → RSS → Whisper + 翻訳 |
| X | `x_connector.py` 実装。Bearer Token 認証 + ツイート取得 |
| Facebook | `facebook_connector.py` 実装。Page Access Token + 投稿取得 |
| スケジューラ | `scheduler.py` に SNS ジョブを追加 |
| ETL 統合 | `etl_pipeline.py` に SNS コネクタを組み込み |

### Phase 2

| 対象 | タスク |
|---|---|
| Instagram | `instagram_connector.py` 実装（Business アカウント確認後） |
| LinkedIn | `linkedin_connector.py` 実装（パートナー審査通過後） |
| フロントエンド | Watson News UI に SNS フィードタブを追加 |

---

## 14. 参照ドキュメント

- [Twitter API v2 ドキュメント](https://developer.twitter.com/en/docs/twitter-api)
- [Instagram Graph API ドキュメント](https://developers.facebook.com/docs/instagram-api)
- [Facebook Graph API ドキュメント](https://developers.facebook.com/docs/graph-api)
- [YouTube Data API v3 ドキュメント](https://developers.google.com/youtube/v3)
- [youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api)
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
- [LinkedIn API ドキュメント](https://learn.microsoft.com/en-us/linkedin/)
- [Podcasting 2.0 Transcript Namespace](https://github.com/Podcastindex-org/podcast-namespace/blob/main/docs/1.0.md#transcript)
