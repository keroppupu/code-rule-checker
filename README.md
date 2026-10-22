# AI Code Rule Checker

ソースコードと複数のコーディング規約（JSONファイル）を受け取り、LAN上のOllamaまたはvLLMによる生成AI推論を用いて規約準拠チェックを実施・レポート出力するアプリケーションです。

## 主な特徴
- **複数規約JSON対応**: セキュリティ規約、命名規約、スタイル規約など複数のJSON定義をまとめてアップロード可能。
- **LAN上LLM連携**: Ollama (native API) および vLLM (OpenAI互換API) のエンドポイントとモデル名を自由に指定可能。
- **Docker対応**: `docker-compose up` 一発でWebUI・APIサーバーが起動。
- **Web UI & REST API & MCP**:
  - Web UI: ドラッグ＆ドロップ対応、Markdownプレビュー、Markdown/HTML形式でのダウンロード機能。
  - REST API: CI/CDパイプラインなどから呼び出し可能なエンドポイント (`/api/check`, `/api/v1/verify`)。
  - MCP: **SSE (Server-Sent Events) トランスポート** に対応 (`/mcp/sse`)。Claude Desktop / Antigravity等のMCPクライアントからリモートまたはローカル接続可能。
  - **プロンプト外部ファイル対応**: テキストファイル（`.txt` / `.md`）に記述したカスタムプロンプトをWebUI・API・MCPから指定可能。
- **高度なコード文脈理解（トランスフォーマー Self-Attention）**: 従来の構文チェックにとどまらず、因果関係や状態遷移（トランザクション境界、未定義ホスト変数の逆算推論など）を解析可能。詳細は [docs/context_understanding.md](docs/context_understanding.md) を参照。

---

## ディレクトリ構成
```
code-rule-checker/
├── Dockerfile              # コンテナイメージ定義
├── docker-compose.yml      # コンテナ起動定義
├── requirements.txt        # 依存ライブラリ
├── app.py                  # FastAPI + FastMCP SSE サーバー
├── checker.py              # LLM連携 & プロンプト構築ロジック
├── mcp_server.py           # スタンドアロン用MCPサーバー
├── templates/
│   └── index.html          # Web UI テンプレート
├── sample_rules/           # サンプル規約JSON & プロンプト
│   ├── security_rules.json
│   ├── style_rules.json
│   └── custom_audit_prompt.txt
└── README.md
```

---

## 起動方法 (Docker)

```bash
cd /Users/pupu/.gemini/antigravity/scratch/code-rule-checker
docker compose up -d --build
```

ブラウザで `http://localhost:8030` にアクセスしてください。

---

## RHEL (Red Hat Enterprise Linux) / Podman 実行時の注意事項

RHEL環境（RHEL 8 / 9）では、macOS / Ubuntu等と異なる特有のセキュリティおよびコンテナ仕様があります。以下のポイントに対応済み・設定可能です。

### 1. SELinux による権限制限
- RHEL環境ではSELinuxがデフォルト有効（Enforcing）になっています。
- コンテナ内の通信やボリュームアクセスを阻害しないよう、`docker-compose.yml` に `security_opt: ["label=disable"]` をあらかじめ定義済みです。

### 2. Podman / podman-compose での実行
- RHEL標準の `podman` / `podman-compose` でもそのまま動作します：
  ```bash
  podman-compose up -d --build
  ```

### 3. firewalld (ポート開放)
- RHELで外部クライアントからアクセスする場合、8030ポートを開放してください：
  ```bash
  sudo firewall-cmd --add-port=8030/tcp --permanent
  sudo firewall-cmd --reload
  ```

### 4. 完全オフライン / 閉域網 (イントラネット) 対応
- RHEL環境が外部インターネットと遮断されている場合でもWebUIが正常に動作するよう、Tailwind CSS、Marked.js、FontAwesomeの静的リソースをコンテナローカル（`/static/vendor/`）に同梱済みです。外部CDNへの通信なしで動作します。

### 5. LAN上Ollama / vLLMへのホスト名解決
- RHEL上のDocker / Podman環境では `host.docker.internal` ではなく、ホスト自身のLAN内IPアドレス（例: `http://192.168.1.100:11434`）を直接指定して接続することを推奨します。

---

## MCP (Server-Sent Events) 接続設定

コンテナ稼働中、FastAPI上に統合されたMCP SSEエンドポイントが利用可能です。

- **SSE URL**: `http://localhost:8030/mcp/sse`

### Claude Desktop / MCPクライアント設定例 (SSE接続)
```json
{
  "mcpServers": {
    "code-rule-checker": {
      "url": "http://localhost:8030/mcp/sse"
    }
  }
}
```

---

## プロンプトファイル機能の使い方

テキストファイル内にはプレースホルダ `{code_content}` および `{rules_content}` を埋め込むことができます（プレースホルダがない場合は自動的に末尾に規約とコードが付与されます）。

- **Web UI**: プロンプト欄で `.txt` ファイルをドラッグ＆ドロップするか、サーバ上のパスを指定
- **API (`/api/check`)**: `-F "prompt_file=@/path/to/prompt.txt"` または `-F "prompt_file_path=/path/to/prompt.txt"`
- **API (`/api/v1/verify`)**: JSONボディに `"prompt_file_path": "/path/to/prompt.txt"` を指定
- **MCP**: 引数 `prompt_file_path` にテキストファイルのパスを指定
```

---

## 起動方法 (Docker)

```bash
cd /Users/pupu/.gemini/antigravity/scratch/code-rule-checker
docker compose up -d --build
```

ブラウザで `http://localhost:8030` にアクセスしてください。

---

## RHEL (Red Hat Enterprise Linux) / Podman 実行時の注意事項

RHEL環境（RHEL 8 / 9）では、macOS / Ubuntu等と異なる特有のセキュリティおよびコンテナ仕様があります。以下のポイントに対応済み・設定可能です。

### 1. SELinux による権限制限
- RHEL環境ではSELinuxがデフォルト有効（Enforcing）になっています。
- コンテナ内の通信やボリュームアクセスを阻害しないよう、`docker-compose.yml` に `security_opt: ["label=disable"]` をあらかじめ定義済みです。

### 2. Podman / podman-compose での実行
- RHEL標準の `podman` / `podman-compose` でもそのまま動作します：
  ```bash
  podman-compose up -d --build
  ```

### 3. firewalld (ポート開放)
- RHELで外部クライアントからアクセスする場合、8030ポートを開放してください：
  ```bash
  sudo firewall-cmd --add-port=8030/tcp --permanent
  sudo firewall-cmd --reload
  ```

### 4. 完全オフライン / 閉域網 (イントラネット) 対応
- RHEL環境が外部インターネットと遮断されている場合でもWebUIが正常に動作するよう、Tailwind CSS、Marked.js、FontAwesomeの静的リソースをコンテナローカル（`/static/vendor/`）に同梱済みです。外部CDNへの通信なしで動作します。

### 5. LAN上Ollama / vLLMへのホスト名解決
- RHEL上のDocker / Podman環境では `host.docker.internal` ではなく、ホスト自身のLAN内IPアドレス（例: `http://192.168.1.100:11434`）を直接指定して接続することを推奨します。

> **LAN上のOllama/vLLMへの接続:**
> - Dockerコンテナ内からホストマシン上で起動中のOllamaに接続する場合は、エンドポイントに `http://host.docker.internal:11434` を指定します。
> - 別のLAN内マシンの場合は `http://192.168.x.x:11434` などを指定してください。

---

## ローカル実行 (Python)

```bash
pip install -r requirements.txt
uvicorn app:app --reload --port 8030
```

---

## MCP サーバーとしての利用

FastMCPプロトコルに対応しており、以下のコマンドまたはMCP設定ファイルに登録して利用できます。

```bash
python mcp_server.py
```
