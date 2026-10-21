#!/usr/bin/env python3
"""
AI Code Rule Checker - CLI クライアントスクリプト

引数で以下を指定して、コンテナ/APIサーバーへ検証リクエストを送信します:
1. ソースコードのフルパス (--code)
2. 規約JSONが格納されたディレクトリ (--rules-dir, 直下の全 .json を自動読み込み)
3. プロンプトテキストファイルのフルパス (--prompt, 任意)

利用例:
  python3 client_sample.py \
    --code /path/to/my_program.c \
    --rules-dir /path/to/rules \
    --prompt /path/to/custom_prompt.txt \
    --server http://localhost:8030 \
    --output result.md
"""

import sys
import json
import argparse
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional


def run_code_check(
    code_path: Path,
    rules_dir: Path,
    prompt_path: Optional[Path] = None,
    server_url: str = "http://localhost:8030",
    backend_type: str = "ollama",
    base_url: str = "http://host.docker.internal:11434",
    model: str = "qwen3.5:9b",
    output_path: Optional[Path] = None
):
    # 1. ソースコードファイルの存在確認と読み込み
    if not code_path.is_file():
        print(f"エラー: 指定されたソースコードファイルが存在しません: {code_path}", file=sys.stderr)
        sys.exit(1)

    print(f"[1/4] ソースコードを読み込み中: {code_path.resolve()}")
    try:
        code_content = code_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        print(f"エラー: ソースコードの読み取りに失敗しました: {e}", file=sys.stderr)
        sys.exit(1)

    # 2. 規約ディレクトリ内の全JSONファイルの走査と読み込み
    if not rules_dir.is_dir():
        print(f"エラー: 指定された規約ディレクトリが存在しません: {rules_dir}", file=sys.stderr)
        sys.exit(1)

    rule_files = sorted(rules_dir.glob("*.json"))
    if not rule_files:
        print(f"エラー: 指定ディレクトリ配下に .json ファイルが見つかりません: {rules_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"[2/4] 規約ディレクトリ配下の JSON ファイルを探索中: {rules_dir.resolve()}")
    combined_rules = []
    for r_file in rule_files:
        try:
            raw_data = json.loads(r_file.read_text(encoding="utf-8", errors="replace"))
            if isinstance(raw_data, list):
                combined_rules.extend(raw_data)
                print(f"  - {r_file.name}: {len(raw_data)} 件の規約をロード")
            elif isinstance(raw_data, dict):
                combined_rules.append(raw_data)
                print(f"  - {r_file.name}: 1 件の規約をロード")
        except Exception as e:
            print(f"警告: 規約ファイル '{r_file.name}' の解析をスキップしました: {e}", file=sys.stderr)

    if not combined_rules:
        print("エラー: 有効な規約定義が1件も読み込めませんでした。", file=sys.stderr)
        sys.exit(1)

    print(f"  => 合計 {len(combined_rules)} 件のコーディング規約を適用します。")

    # 3. プロンプトファイルの読み込み (指定がある場合)
    custom_prompt_text = None
    if prompt_path:
        if not prompt_path.is_file():
            print(f"エラー: 指定されたプロンプトファイルが存在しません: {prompt_path}", file=sys.stderr)
            sys.exit(1)
        print(f"[3/4] プロンプトファイルを読み込み中: {prompt_path.resolve()}")
        try:
            custom_prompt_text = prompt_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            print(f"エラー: プロンプトファイルの読み取りに失敗しました: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("[3/4] プロンプトファイル: 未指定 (標準デフォルトプロンプトを使用)")

    # 4. APIサーバーへリクエスト送信
    api_endpoint = f"{server_url.rstrip('/')}/api/v1/verify"
    payload = {
        "code": code_content,
        "filename": code_path.name,
        "rules": combined_rules,
        "backend_type": backend_type,
        "base_url": base_url,
        "model": model,
        "custom_prompt": custom_prompt_text
    }

    print(f"[4/4] APIサーバーへ検証リクエストを送信中 ({api_endpoint})...")
    print(f"      LLMバックエンド: {backend_type} ({model})")
    
    req = urllib.request.Request(
        api_endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    try:
        # LLM推論時間を考慮しタイムアウトを300秒に設定
        with urllib.request.urlopen(req, timeout=300) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            report = res_data.get("report", "")
            
            print("\n" + "=" * 60)
            print("                 検証レポート (プレビュー)")
            print("=" * 60)
            print(report[:1200] + ("\n...[以下省略]..." if len(report) > 1200 else ""))
            print("=" * 60)

            # ファイル出力指定がある場合、またはデフォルト保存
            out_file = output_path or Path(f"report_{code_path.stem}.md")
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
        print(f"\n❌ 予期せぬエラーが発生しました: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="AI Code Rule Checker - CLI実行スクリプト",
        formatter_class=argparse.RawTextHelpFormatter
    )

    # 必須の引数
    parser.add_argument(
        "-c", "--code",
        required=True,
        type=Path,
        help="【必須】チェック対象ソースコードのフルパス (例: /path/to/main.c, /path/to/proc.pco)"
    )
    parser.add_argument(
        "-r", "--rules-dir",
        required=True,
        type=Path,
        help="【必須】規約JSONが格納されたディレクトリパス (直下の全 *.json を自動統合)"
    )

    # 任意の引数
    parser.add_argument(
        "-p", "--prompt",
        type=Path,
        default=None,
        help="【任意】プロンプトテキストファイルのフルパス (未指定時は標準プロンプト)"
    )
    parser.add_argument(
        "-s", "--server",
        default="http://localhost:8030",
        help="APIサーバーのURL (デフォルト: http://localhost:8030)"
    )
    parser.add_argument(
        "--backend",
        choices=["ollama", "vllm"],
        default="ollama",
        help="LLMバックエンド種別 (デフォルト: ollama)"
    )
    parser.add_argument(
        "--base-url",
        default="http://host.docker.internal:11434",
        help="LLMサーバーのエンドポイントURL (デフォルト: http://host.docker.internal:11434)"
    )
    parser.add_argument(
        "-m", "--model",
        default="qwen3.5:9b",
        help="使用するモデル名 (デフォルト: qwen3.5:9b)"
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="レポートの保存先ファイルパス (デフォルト: report_<ソースコード名>.md)"
    )

    args = parser.parse_args()

    run_code_check(
        code_path=args.code,
        rules_dir=args.rules_dir,
        prompt_path=args.prompt,
        server_url=args.server,
        backend_type=args.backend,
        base_url=args.base_url,
        model=args.model,
        output_path=args.output
    )


if __name__ == "__main__":
    main()
