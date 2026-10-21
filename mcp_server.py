import json
import asyncio
from typing import List, Optional

try:
    from mcp.server.mcpserver import MCPServer
    mcp = MCPServer(
        name="CodeRuleChecker",
        description="ソースコードと複数のコーディング規約JSONを受け取り、AIで検証するMCPサーバー"
    )
except ImportError:
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("CodeRuleChecker")

from checker import run_code_check

@mcp.tool()
async def check_code_against_rules(
    code: str,
    rules_json_strings: List[str],
    filename: str = "sample.py",
    backend_type: str = "ollama",
    base_url: str = "http://host.docker.internal:11434",
    model: str = "qwen3.5:9b",
    custom_instructions: Optional[str] = None,
    prompt_file_path: Optional[str] = None
) -> str:
    """
    ソースコードと複数のコーディング規約JSON文字列を受け取り、AIで整合性をチェックしてMarkdownレポートを返します。
    - code: チェック対象のソースコード
    - rules_json_strings: 各規約JSONの文字列表現のリスト
    - filename: ソースコードのファイル名 (例: main.py)
    - backend_type: 'ollama' または 'vllm'
    - base_url: エンドポイント (例: http://host.docker.internal:11434)
    - model: 使用するモデル名 (例: qwen3.5:9b)
    - custom_instructions: 直接指定する追加プロンプト・指示
    - prompt_file_path: プロンプトが書かれたテキストファイルのパス (指定時はこちらを優先して読み込み)
    """
    parsed_rules = []
    for s in rules_json_strings:
        try:
            val = json.loads(s)
            if isinstance(val, list):
                parsed_rules.extend(val)
            else:
                parsed_rules.append(val)
        except Exception as e:
            return f"Error parsing rule JSON: {str(e)}"

    report = await run_code_check(
        code_filename=filename,
        code_content=code,
        rules=parsed_rules,
        backend_type=backend_type,
        base_url=base_url,
        model=model,
        custom_prompt=custom_instructions,
        prompt_file_path=prompt_file_path
    )
    return report

if __name__ == "__main__":
    # スタンドアロン起動時はstdioまたはSSEで動作
    mcp.run()
