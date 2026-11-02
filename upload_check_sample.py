#!/usr/bin/env python3
"""
AI Code Rule Checker - ファイルアップロード実行スクリプト (Multipart/Form-Data)

ローカルに実在する以下の実ファイルを直接 API サーバー (/api/check) へアップロードして
コード規約チェックを実行するPythonサンプルスクリプトです:
1. ソースコードファイル (--code)
2. 複数の規約JSONファイル (--rules または --rules-dir)
3. プロンプトテキストファイル (--prompt, 任意)

※外部ライブラリ (requests/httpx等) は不要で、Python標準ライブラリのみで動作します。

【実行例】
  # 規約ファイルを個別に複数指定
  python3 upload_check_sample.py \
    --code sample_rules/../app.py \
    --rules sample_rules/security_rules.json sample_rules/style_rules.json \
    --prompt sample_rules/custom_audit_prompt.txt

  # 規約ディレクトリを指定 (配下の全 .json を自動アップロード)
  python3 upload_check_sample.py \
    --code /path/to/my_code.c \
    --rules-dir sample_rules \
    --prompt sample_rules/custom_audit_prompt.txt \
    --backend litellm \
    --base-url http://host.docker.internal:4000 \
    --model gpt-4o-mini \
    --api-key sk-your-key
"""

import sys
import os
import json
import argparse
import urllib.request
import urllib.error
import mimetypes
from pathlib import Path
from typing import List, Optional


def build_multipart_data(fields: dict, files: List[tuple]) -> tuple[bytes, str]:
    """
    Python標準ライブラリで multipart/form-data のボディとヘッダーを構築します。
    - fields: { "field_name": "value", ... }
    - files: [ ("field_name", Path_object), ... ]
    """
    boundary = "----WebKitFormBoundary" + os.urandom(16).hex()
    body = bytearray()

    # 通常のテキストフィールド
    for key, value in fields.items():
        if value is None:
            continue
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
        body.extend(str(value).encode("utf-8"))
        body.extend(b"\r\n")

    # ファイルフィールド
    for field_name, file_path in files:
        if not file_path.is_file():
            print(f"警告: ファイルが見つかりません (スキップ): {file_path}", file=sys.stderr)
            continue
        
        filename = file_path.name
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        file_bytes = file_path.read_bytes()

        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(
            f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode("utf-8")
        )
        body.extend(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
        body.extend(file_bytes)
        body.extend(b"\r\n")

    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    content_type_header = f"multipart/form-data; boundary={boundary}"
    return bytes(body), content_type_header


def run_upload_check(
    code_path: Path,
    rule_paths: List[Path],
    prompt_path: Optional[Path] = None,
    server_url: str = "http://localhost:8030",
    backend_type: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    output_path: Optional[Path] = None
):
    # 1. ソースコードの存在確認
    if not code_path.is_file():
        print(f"エラー: ソースコードファイルが存在しません: {code_path}", file=sys.stderr)
        sys.exit(1)

    # 2. 規約ファイルの存在確認
    valid_rules = [p for p in rule_paths if p.is_file() and p.suffix.lower() == ".json"]
    if not valid_rules:
        print("エラー: 有効な規約JSONファイルが指定されていません。", file=sys.stderr)
        sys.exit(1)

    print("=" * 65)
    print("AI Code Rule Checker - ファイルアップロード検証実行")
    print("=" * 65)
    print(f"API エンドポイント: {server_url.rstrip('/')}/api/check")
    print(f"対象コードファイル: {code_path.resolve()} ({code_path.stat().st_size} bytes)")
    print(f"アップロード規約数: {len(valid_rules)} ファイル")
    for r in valid_rules:
        print(f"  - {r.name} ({r.stat().st_size} bytes)")
    
    if prompt_path and prompt_path.is_file():
        print(f"プロンプトファイル: {prompt_path.resolve()} ({prompt_path.stat().st_size} bytes)")
    else:
        print("プロンプトファイル: 未指定 (標準デフォルトプロンプトを使用)")
    print("-" * 65)

    # 3. フォームフィールドの組み立て
    fields = {}
    if backend_type:
        fields["backend_type"] = backend_type
    if base_url:
        fields["base_url"] = base_url
    if model:
        fields["model"] = model
    if api_key:
        fields["api_key"] = api_key

    # 4. アップロード対象ファイルの組み立て
    files = [("code_file", code_path)]
    for r in valid_rules:
        files.append(("rule_files", r))
    if prompt_path and prompt_path.is_file():
        files.append(("prompt_file", prompt_path))

    body_bytes, content_type = build_multipart_data(fields, files)

    # 5. APIリクエストの送信
    endpoint = f"{server_url.rstrip('/')}/api/check"
    req = urllib.request.Request(
        endpoint,
        data=body_bytes,
        headers={
            "Content-Type": content_type,
            "Content-Length": str(len(body_bytes))
        }
    )

    print(f"\nサーバーへファイルをアップロード中 (ペイロード合計: {len(body_bytes)} bytes)...")
    print("生成AIによるコード規約検証を実行中 (最大タイムアウト: 300秒)...")

    try:
        with urllib.request.urlopen(req, timeout=300) as response:
            result = json.loads(response.read().decode("utf-8"))
            report = result.get("report", "")

            print("\n" + "=" * 65)
            print("【検証結果レポート (プレビュー)】")
            print("=" * 65)
            print(report[:1200] + ("\n...[以下省略]..." if len(report) > 1200 else ""))
            print("=" * 65)

            # ファイル出力保存
            out_file = output_path or Path(f"upload_report_{code_path.stem}.md")
            out_file.write_text(report, encoding="utf-8")
            print(f"\n✅ 完全な検証レポートを保存しました: {out_file.resolve()}\n")

    except urllib.error.HTTPError as e:
        error_msg = e.read().decode("utf-8", errors="replace")
        print(f"\n❌ APIエラー発生 (HTTP {e.code}): {error_msg}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"\n❌ 接続エラー: APIサーバー ({server_url}) に接続できませんでした: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 予期せぬエラー: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="ソースコード、複数の規約JSON、プロンプトファイルをアップロードして検証するスクリプト",
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument(
        "-c", "--code",
        required=True,
        type=Path,
        help="【必須】チェック対象ソースコードのファイルパス (例: /path/to/main.c, proc.pco)"
    )
    
    # 規約ファイルの指定（個別複数またはディレクトリ）
    rule_group = parser.add_mutually_exclusive_group(required=True)
    rule_group.add_argument(
        "-r", "--rules",
        nargs="+",
        type=Path,
        help="【必須】規約JSONファイルパス (複数指定可能: -r rule1.json rule2.json)"
    )
    rule_group.add_argument(
        "-rd", "--rules-dir",
        type=Path,
        help="【必須】規約JSONが格納されたディレクトリ (直下の全 *.json を自動アップロード)"
    )

    parser.add_argument(
        "-p", "--prompt",
        type=Path,
        default=None,
        help="【任意】プロンプトテキストファイルパス (例: custom_prompt.txt)"
    )
    parser.add_argument(
        "-s", "--server",
        default="http://localhost:8030",
        help="APIサーバーのURL (デフォルト: http://localhost:8030)"
    )
    parser.add_argument(
        "--backend",
        choices=["ollama", "vllm", "litellm"],
        default=None,
        help="LLMバックエンド種別 (未指定時はサーバー設定値を使用)"
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="LLMエンドポイントURL (未指定時はサーバー設定値を使用)"
    )
    parser.add_argument(
        "-m", "--model",
        default=None,
        help="使用モデル名 (未指定時はサーバー設定値を使用)"
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="APIキー (LiteLLM等で必要な場合。未指定時はサーバー設定値を使用)"
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="レポート保存先ファイルパス (デフォルト: upload_report_<コード名>.md)"
    )

    args = parser.parse_args()

    # 規約ファイルリストの決定
    if args.rules:
        target_rules = args.rules
    else:
        if not args.rules_dir.is_dir():
            print(f"エラー: 指定された規約ディレクトリが存在しません: {args.rules_dir}", file=sys.stderr)
            sys.exit(1)
        target_rules = sorted(args.rules_dir.glob("*.json"))

    run_upload_check(
        code_path=args.code,
        rule_paths=target_rules,
        prompt_path=args.prompt,
        server_url=args.server,
        backend_type=args.backend,
        base_url=args.base_url,
        model=args.model,
        api_key=args.api_key,
        output_path=args.output
    )


if __name__ == "__main__":
    main()
