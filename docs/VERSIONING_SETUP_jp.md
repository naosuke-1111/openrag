# Docusaurusバージョニングのセットアップ

ドキュメントのバージョニングは現在**無効**ですが、設定済みで有効化する準備ができています。
設定は `docusaurus.config.js` のコメントアウトされたセクションに記載されています。

バージョニングを有効にするには、以下の手順を実行します：

1. `docusaurus.config.js` を開く
2. バージョニング設定セクションを見つける（57行目付近）
3. バージョニング設定のコメントを解除する：

```javascript
docs: {
  // ... その他の設定
  lastVersion: 'current', // 'current' を使用して ./docs を最新バージョンにする
  versions: {
    current: {
      label: 'Next (unreleased)',
      path: 'next',
    },
  },
  onlyIncludeVersions: ['current'], // ビルドを高速化するためにバージョンを制限
},
```

## ドキュメントバージョンの作成

詳細については、[Docusaurusのドキュメント](https://docusaurus.io/docs/versioning)を参照してください。

1. DocusaurusCLIコマンドを使用してバージョンを作成します。
```bash
# 現在のドキュメントからバージョン1.0.0を作成
npm run docusaurus docs:version 1.0.0
```

このコマンドは以下を実行します：
- `docs/` フォルダの内容全体を `versioned_docs/version-1.0.0/` にコピー
- `versioned_sidebars/version-1.0.0-sidebars.json` にバージョン管理されたサイドバーファイルを作成
- `versions.json` に新しいバージョンを追記

2. バージョンを作成したら、複数のバージョンを含むようにDocusaurusの設定を更新します。
`lastVersion:'1.0.0'` は「1.0.0」リリースを `latest` バージョンにします。
`current` は `/docs/next` でアクセス可能な作業中のドキュメントセットです。
バージョンを削除するには、`onlyIncludeVersions` から削除します。

```javascript
docs: {
  // ... その他の設定
  lastVersion: '1.0.0', // 1.0.0を最新バージョンにする
  versions: {
    current: {
      label: 'Next (unreleased)',
      path: 'next',
    },
    '1.0.0': {
      label: '1.0.0',
      path: '1.0.0',
    },
  },
  onlyIncludeVersions: ['current', '1.0.0'], // 両方のバージョンを含む
},
```

3. ローカルでデプロイをテストします。

```bash
npm run build
npm run serve
```

4. 続くバージョンを追加するには、CLIコマンドを実行してから `docusaurus.config.js` を更新する手順を繰り返します。

```bash
# 現在のドキュメントからバージョン2.0.0を作成
npm run docusaurus docs:version 2.0.0
```

新しいバージョンを作成したら、`docusaurus.config.js` を更新します。

```javascript
docs: {
  lastVersion: '2.0.0', // 2.0.0を最新バージョンにする
  versions: {
    current: {
      label: 'Next (unreleased)',
      path: 'next',
    },
    '2.0.0': {
      label: '2.0.0',
      path: '2.0.0',
    },
    '1.0.0': {
      label: '1.0.0',
      path: '1.0.0',
    },
  },
  onlyIncludeVersions: ['current', '2.0.0', '1.0.0'], // 全バージョンを含む
},
```

## バージョニングの無効化

1. `docusaurus.config.js` から `versions` 設定を削除します。
2. `docs/versioned_docs/` および `docs/versioned_sidebars/` ディレクトリを削除します。
3. `docs/versions.json` を削除します。

## 参考資料

- [Docusaurus公式バージョニングドキュメント](https://docusaurus.io/docs/versioning)
- [Docusaurusバージョニングのベストプラクティス](https://docusaurus.io/docs/versioning#recommended-practices)
