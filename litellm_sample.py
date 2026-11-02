#!/usr/bin/env python3
"""
AI Code Rule Checker - LiteLLM 連携サンプルスクリプト

LiteLLM プロキシサーバーを経由して、APIキー認証付きでコード規約チェックを実行するPythonサンプルです。
追加のサードパーティライブラリ（requests/httpx等）は不要で、Python標準ライブラリのみで動作します。

【構成イメージ】
[本スクリプト] -> [AI Code Rule Checker API (port 8030)] -> [LiteLLM Proxy (port 4000)] -> [LLM]
"""

import sys
import json
import urllib.request
import urllib.error
from pathlib import Path

# ==============================================================================
# 接続設定
# ==============================================================================
# AI Code Rule Checker サーバーのURL
CHECKER_API_URL = "http://localhost:8030/api/v1/verify"

# LiteLLM プロキシのエンドポイントURL
# ※ Dockerコンテナ内から同一ホストのLiteLLMを見る場合は host.docker.internal を指定
# ※ 外部LANマシンの場合は http://192.168.x.x:4000 などを指定
LITELLM_BASE_URL = "http://host.docker.internal:4000"

# LiteLLM で発行した仮想キー (Virtual Key) またはAPIキー
LITELLM_API_KEY = "sk-litellm-sample-key-12345"

# LiteLLM 側で設定されているモデル識別名 (例: gpt-4o, claude-3-5-sonnet, mistral, qwen等)
MODEL_NAME = "gpt-4o-mini"


def run_litellm_sample():
    print("=" * 65)
    print("AI Code Rule Checker - LiteLLM APIキー連携テスト")
    print("=" * 65)
    print(f"Checker API   : {CHECKER_API_URL}")
    print(f"LiteLLM URL   : {LITELLM_BASE_URL}")
    print(f"Model         : {MODEL_NAME}")
    print(f"API Key       : {LITELLM_API_KEY[:8]}... (マスキング)")
    print("-" * 65)

    # 1. チェック対象のサンプルソースコード (例: C言語)
    target_code = """
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

void execute_user_command(const char *user_input) {
    char command[128];
    // 脆弱性: バッファオーバーフローの危険性がある sprintf
    sprintf(command, "/usr/bin/process --input %s", user_input);
    system(command);
}
"""

    # 2. 検証するコーディング規約 (JSONリスト)
    rules = [
        {
            "id": "SEC-001",
            "name": "安全な文字列フォーマット関数の使用",
            "severity": "critical",
            "description": "バッファオーバーフロー防止のため、sprintf の使用を禁止し、snprintf を使用して書き込み上限バイト数を指定すること。"
        },
        {
            "id": "SEC-002",
            "name": "コマンドインジェクションの防止",
            "severity": "critical",
            "description": "system() 関数の呼び出しによるシェルコマンド実行を禁止し、execve などの安全なAPIまたは適切なエスケープを行うこと。"
        }
    ]

    # 3. リクエストペイロードの作成 (backend_type="litellm" と api_key を指定)
    payload = {
        "code": target_code,
        "filename": "command_handler.c",
        "rules": rules,
        "backend_type": "litellm",
        "base_url": LITELLM_BASE_URL,
        "model": MODEL_NAME,
        "api_key": LITELLM_API_KEY,
        "custom_prompt": "セキュリティ監査の専門家として、脆弱性の深刻度とBefore/Afterの修正コードを提示してください。"
    }

    req = urllib.request.Request(
        CHECKER_API_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    print("\nAPIサーバーへ検証リクエストを送信中 (最大タイムアウト: 300秒)...")

    try:
        with urllib.request.urlopen(req, timeout=300) as response:
            result = json.loads(response.read().decode("utf-8"))
            report = result.get("report", "")

            print("\n" + "=" * 65)
            print("【検証結果レポート】")
            print("=" * 65)
            print(report)
            print("=" * 65)

            # 結果をMarkdownファイルとして保存
            output_file = Path("litellm_check_report.md")
            output_file.write_text(report, encoding="utf-8")
            print(f"\n✅ 完全なレポートを保存しました: {output_file.resolve()}\n")

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        print(f"\n❌ HTTPエラー発生 (Status {e.code}):", file=sys.stderr)
        print(error_body, file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"\n❌ 接続エラー: {e.reason}", file=sys.stderr)
        print("Checker APIサーバー (http://localhost:8030) が起動していることを確認してください。", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 予期せぬエラー: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    run_litellm_sample()
