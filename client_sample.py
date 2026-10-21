#!/usr/bin/env python3
"""
AI Code Rule Checker - API 呼び出しサンプルスクリプト

本スクリプトは、FastAPIで公開されている以下の2つのエンドポイントを呼び出すサンプルです:
1. /api/v1/verify : JSONボディによる直接呼び出し（規約JSONオブジェクトを直接送信）
2. /api/check     : multipart/form-data による呼び出し（ローカルのファイル一式をアップロード）
"""

import sys
import json
import urllib.request
import urllib.error
from pathlib import Path

# API サーバーのURL（ローカルまたはRHELサーバーのIP）
SERVER_URL = "http://localhost:8030"

def sample_verify_json():
    """
    エンドポイント: POST /api/v1/verify
    JSONペイロードを送信してチェックを実行する例
    """
    print("\n==========================================")
    print("1. JSON API (/api/v1/verify) の呼び出しテスト")
    print("==========================================")

    url = f"{SERVER_URL}/api/v1/verify"

    # チェック対象のコード (例: C言語)
    target_code = """
#include <stdio.h>
#include <string.h>

void process_data(char *input) {
    char buffer[64];
    // 脆弱性: バッファサイズを考慮しないstrcpy
    strcpy(buffer, input);
    printf("Processed: %s\\n", buffer);
}
"""

    # 適用する複数の規約 (JSONリスト)
    rules = [
        {
            "id": "SEC-C-001",
            "name": "安全でない文字列関数の禁止",
            "severity": "critical",
            "description": "バッファオーバーフロー防止のため、strcpyやstrcatの使用を禁止し、strncpyやsnprintfを使用すること。"
        },
        {
            "id": "STYLE-C-002",
            "name": "ポインタ引数のNULLチェック",
            "severity": "warning",
            "description": "ポインタを受け取る関数では処理開始時にNULLポインタ検証を行うこと。"
        }
    ]

    payload = {
        "code": target_code,
        "filename": "sample_buffer.c",
        "rules": rules,
        "backend_type": "ollama",
        "base_url": "http://host.docker.internal:11434",
        "model": "qwen3.5:9b"
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    try:
        print(f"送信中: {url} (対象ファイル: sample_buffer.c)...")
        with urllib.request.urlopen(req, timeout=300) as res:
            res_data = json.loads(res.read().decode("utf-8"))
            print("\n[レスポンスステータス]:", res_data.get("status"))
            print("[ファイル名]:", res_data.get("filename"))
            print("\n--- レポート内容 (先頭一部抜粋) ---")
            report = res_data.get("report", "")
            print(report[:800] + ("..." if len(report) > 800 else ""))
            
            # 結果をMarkdownファイルとしてローカル保存
            output_file = "verify_result.md"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(report)
            print(f"\n=> 完全なレポートを '{output_file}' に保存しました。")
    except urllib.error.HTTPError as e:
        print(f"HTTPエラー発生 ({e.code}):", e.read().decode("utf-8", errors="replace"))
    except Exception as e:
        print("エラー発生:", str(e))


def sample_check_multipart():
    """
    エンドポイント: POST /api/check
    実際のファイルを multipart/form-data でアップロードしてチェックを実行する例
    """
    print("\n==========================================")
    print("2. Multipart API (/api/check) ファイルアップロードテスト")
    print("==========================================")

    url = f"{SERVER_URL}/api/check"

    # サンプルファイル群のパス (存在確認)
    base_dir = Path(__file__).resolve().parent
    sec_rule = base_dir / "sample_rules" / "security_rules.json"
    style_rule = base_dir / "sample_rules" / "style_rules.json"
    prompt_file = base_dir / "sample_rules" / "custom_audit_prompt.txt"

    if not sec_rule.exists():
        print(f"スキップ: サンプル規約ファイル {sec_rule} が見つかりません。")
        return

    # Python の requests や httpx を使わない標準ライブラリでの multipart 構築例
    import mimetypes
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    
    body = bytearray()

    def add_field(name, value):
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        body.extend(f"{value}\r\n".encode("utf-8"))

    def add_file(field_name, file_path):
        filename = Path(file_path).name
        content = Path(file_path).read_bytes()
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode("utf-8"))
        body.extend(b"Content-Type: application/octet-stream\r\n\r\n")
        body.extend(content)
        body.extend(b"\r\n")

    add_field("backend_type", "ollama")
    add_field("base_url", "http://host.docker.internal:11434")
    add_field("model", "qwen3.5:9b")
    add_field("code_text", "def unsafe(u):\n    return f'SELECT * FROM acc WHERE id={u}'")
    add_field("code_filename", "account_query.py")

    # 複数ルールのアップロード
    add_file("rule_files", sec_rule)
    add_file("rule_files", style_rule)

    # プロンプトファイルのアップロード
    if prompt_file.exists():
        add_file("prompt_file", prompt_file)

    body.extend(f"--{boundary}--\r\n".encode("utf-8"))

    req = urllib.request.Request(
        url,
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )

    try:
        print(f"アップロード中: {url}...")
        with urllib.request.urlopen(req, timeout=300) as res:
            res_data = json.loads(res.read().decode("utf-8"))
            print("\n[レスポンスステータス]:", res_data.get("status"))
            print("\n--- レポート内容 (先頭一部抜粋) ---")
            report = res_data.get("report", "")
            print(report[:800] + ("..." if len(report) > 800 else ""))
    except urllib.error.HTTPError as e:
        print(f"HTTPエラー発生 ({e.code}):", e.read().decode("utf-8", errors="replace"))
    except Exception as e:
        print("エラー発生:", str(e))


if __name__ == "__main__":
    sample_verify_json()
    sample_check_multipart()
