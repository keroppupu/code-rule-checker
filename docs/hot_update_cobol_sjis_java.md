# 稼働中Dockerコンテナのコード差し替え手順（COBOL SJIS対応 & Java対応）

本ドキュメントは、**Dockerイメージを再ビルド（`docker compose build`）せずに、稼働中のコンテナ（`code_rule_checker_app`）内のコードファイルのみを直接上書き差し替え**して、以下の最新機能を即座に反映させる手順書です。

### 反映される機能
1. **COBOLのShift_JIS (CP932) 自動判定 & 破損防止**:
   - 生バイト列のまま受信し、`.cbl`, `.cob`, `.pco`, `.cpy`, `.cobol` は自動でShift_JISデコード。
   - LLMプロンプトに「文字コード前提: Shift_JIS (CP932)」を明示し、全角2バイト長などの規約を正確に検査。
   - Web UI上に文字コード選択（Auto / Shift_JIS / UTF-8 / EUC-JP）および検出文字コードバッジを追加。
2. **Java言語チェック対応**:
   - try-with-resources（リソース解放漏れ防止）、PreparedStatement（SQLインジェクション対策）、例外処理（空catch/printStackTrace禁止）、標準命名規約（CamelCase）、NPE対策の検証強化。
   - Java用サンプル規約（`sample_rules/java_rules.json`）の提供。

---

## 差分ファイル一覧

コンテナ内（`/app` 配下）に差し替える対象ファイルは以下の **4点** です：

| ファイルパス | 役割・変更概要 |
| :--- | :--- |
| `app.py` | 生バイト列保持、COBOLのCP932優先判定、文字コード引数対応 |
| `checker.py` | プロンプトへの文字コード前提注入、Java等の言語特性評価指示の追加 |
| `mcp_server.py` | MCPツール引数に `code_encoding` 追加、COBOL自動判定 |
| `templates/index.html` | 文字コード選択プルダウン、検出文字コードバッジ表示 |

※ `requirements.txt` の追加パッケージはありません。そのため、**コンテナの再ビルドは一切不要**です。

---

## 差し替え手順（ホットアップデート）

### ステップ 1: リポジトリの最新コードを取得
別サーバーの作業ディレクトリにて、GitHubから最新コードをプルします。

```bash
cd /path/to/code-rule-checker
git pull origin main
```

### ステップ 2: コンテナ内へファイルを直接コピー (`docker cp` / `podman cp`)

稼働中のコンテナ名 `code_rule_checker_app` に対してファイルを上書きコピーします：

#### Docker の場合
```bash
# 1. バックエンドPythonコードの差し替え
docker cp app.py code_rule_checker_app:/app/app.py
docker cp checker.py code_rule_checker_app:/app/checker.py
docker cp mcp_server.py code_rule_checker_app:/app/mcp_server.py

# 2. Web UIテンプレートの差し替え
docker cp templates/index.html code_rule_checker_app:/app/templates/index.html
```

#### Podman (RHEL環境等) の場合
```bash
# 1. バックエンドPythonコードの差し替え
podman cp app.py code_rule_checker_app:/app/app.py
podman cp checker.py code_rule_checker_app:/app/checker.py
podman cp mcp_server.py code_rule_checker_app:/app/mcp_server.py

# 2. Web UIテンプレートの差し替え
podman cp templates/index.html code_rule_checker_app:/app/templates/index.html
```

---

### ステップ 3: コンテナの再起動（約2〜3秒）

メモリ上のPythonプロセス（uvicorn）に修正コードを読み込ませるため、コンテナを再起動します。

```bash
# Docker
docker restart code_rule_checker_app

# Podman
podman restart code_rule_checker_app
```

---

## 動作確認・検証コマンド

### ① APIの疎通確認
```bash
curl -s http://localhost:8030/api/settings
```
JSONレスポンスが正常に返却されればサーバーは起動しています。

### ② COBOL (Shift_JIS) チェックの動作確認
付属のShift_JISバイナリCOBOLファイルで検証します：
```bash
python3 upload_check_sample.py \
  --code sample_rules/sample_sjis_cobol.cbl \
  --rules sample_rules/cobol_rules.json \
  --server http://localhost:8030
```
レスポンスに `Shift_JIS (CP932)` として認識され、文字化けなく日本語コメントと規約が検証されることを確認してください。

### ③ Java規約チェックの動作確認
付属のJavaサンプルファイルと規約で検証します：
```bash
python3 upload_check_sample.py \
  --code sample_rules/sample_user_service.java \
  --rules sample_rules/java_rules.json \
  --server http://localhost:8030
```
SQLインジェクション、try-with-resources、命名規約、printStackTraceの各違反が検出されることを確認してください。

### ④ Web UIでの確認
ブラウザで `http://<サーバーIP>:8030` にアクセスします。
- ソースコード入力欄の右上に **「文字コード: 自動判定 (COBOLはSJIS優先)」** のプルダウンが表示されていることを確認します。
- ファイルをアップロードしてチェック実行後、検証レポート見出しの横に `Shift_JIS (CP932)` などの文字コードバッジが表示されれば完了です。
