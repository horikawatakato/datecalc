# 日数計算機

日数計算を行うWebアプリケーションです。  
AWS ECS on EC2でコンテナ運用し、GitHub ActionsによるCI/CDを構築しています。

**Webアプリケーション**  
http://ec2-3-114-247-73.ap-northeast-1.compute.amazonaws.com

---

## 主な機能

- 現在の日付と入力した日付の差分を日数で表示（365日以上は年数も併記）
- 紀元前999年から西暦9999年まで対応
- 紀元前の年は負数で入力（例：-100年1月1日 = 紀元前100年1月1日）
- 曜日の表示
- 計算履歴の表示（最大8件、重複は自動排除）

**テストカバレッジレポート**  
https://horikawatakato.github.io/datecalc/coverage-report.html

---

## ファイル構成

```
datecalc/
├── .github/
│   └── workflows/
│       └── cicd.yml            # GitHub Actions
├── app/
│   ├── DateCalc.html           # Webフロントエンド
│   ├── DateCalc.py             # 計算ロジック
│   ├── DateCalc_server.py      # Flask Webサーバー（API）
│   ├── Dockerfile              # Webコンテナイメージ用
│   ├── gunicorn.conf.py        # Gunicorn設定
│   ├── requirements.txt        # 依存パッケージ（Flask・Gunicorn）
│   ├── test_DateCalc.py        # ユニットテスト（pytest）
│   └── wsgi.py                 # Gunicornエントリポイント
├── docs/
│   └── coverage-report.html    # テストカバレッジレポート
├── nginx/
│   ├── Dockerfile              # Nginxコンテナイメージ用
│   └── nginx.conf              # リバースプロキシ設定
├── .gitignore                  # Git管理除外設定
├── LICENSE                     # MITライセンス
├── README.md                   # プロジェクト説明
├── cicd-workflow.svg           # CI/CDワークフロー図
├── container-architecture.svg  # コンテナ構成図
├── docker-compose.yml          # コンテナ構成定義（ローカル開発用）
└── task-definition.json        # AWS ECSタスク定義
```

---

## コンテナ構成

<img src="container-architecture.svg" alt="コンテナ構成図" width="100%">

---

## GitHub Actions（CI/CD）

mainへのpushとpull requestをトリガーに実行

- **push**：test → build → push → deployすべて実行
- **pull request**：test → buildのみ実行（pushとdeployはスキップ）

同時実行制御（concurrency）はジョブ単位で設定
 
- **test / build / push**：古いコミットの実行をキャンセルし、最新コミットを優先
- **deploy**：実行中はキャンセルせず、新しい実行は前のデプロイ完了まで待機

<img src="cicd-workflow.svg" alt="CI/CDワークフロー図" width="100%">

<br>
<br>
<br>
<br>
<br>

---

Copyright (c) 2026 Horikawa Takato  
Released under the MIT License
