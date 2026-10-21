import json
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from checker import run_code_check

# MCP 2.x MCPServer support
from mcp.server.mcpserver import MCPServer

mcp_server = MCPServer(
    name="CodeRuleChecker",
    description="ソースコードと複数のコーディング規約JSONを受け取り、AIで検証するMCPサーバー"
)

@mcp_server.tool()
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

app = FastAPI(title="AI Code Rule Checker", version="1.0.0")
templates = Jinja2Templates(directory="templates")

# 静的ファイルの提供 (オフライン環境・イントラネット対応)
app.mount("/static", StaticFiles(directory="static"), name="static")

# MCP SSE アプリを /mcp にマウント
mcp_sse_app = mcp_server.sse_app(transport_security=None)
app.mount("/mcp", mcp_sse_app)

class CheckRequestJSON(BaseModel):
    code: str
    filename: Optional[str] = "input_code.txt"
    rules: List[dict]
    backend_type: str = "ollama"  # "ollama" または "vllm"
    base_url: str = "http://host.docker.internal:11434"
    model: str = "qwen3.5:9b"
    custom_prompt: Optional[str] = None
    prompt_file_path: Optional[str] = None

@app.get("/", response_class=HTMLResponse)
async def serve_ui(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.post("/api/check")
async def api_check_form(
    code_file: Optional[UploadFile] = File(None),
    code_text: Optional[str] = Form(None),
    code_filename: Optional[str] = Form("source_code.txt"),
    rule_files: List[UploadFile] = File(...),
    prompt_file: Optional[UploadFile] = File(None),
    prompt_file_path: Optional[str] = Form(None),
    backend_type: str = Form("ollama"),
    base_url: str = Form("http://host.docker.internal:11434"),
    model: str = Form("qwen3.5:9b"),
    custom_prompt: Optional[str] = Form(None)
):
    """WebUIからのMultipart/Formアップロード処理"""
    # ソースコードの読み出し
    if code_file and code_file.filename:
        actual_filename = code_file.filename
        raw_code = await code_file.read()
        code_str = raw_code.decode("utf-8", errors="replace")
    elif code_text and code_text.strip():
        actual_filename = code_filename or "direct_input.txt"
        code_str = code_text
    else:
        raise HTTPException(status_code=400, detail="ソースコードファイルまたはテキストを入力してください。")

    # プロンプトファイルのアップロードがある場合
    effective_custom_prompt = custom_prompt
    if prompt_file and prompt_file.filename:
        prompt_bytes = await prompt_file.read()
        effective_custom_prompt = prompt_bytes.decode("utf-8", errors="replace")

    # 複数ルールJSONの読み出し
    rules_list = []
    for r_file in rule_files:
        try:
            content_bytes = await r_file.read()
            parsed_json = json.loads(content_bytes.decode("utf-8", errors="replace"))
            if isinstance(parsed_json, list):
                rules_list.extend(parsed_json)
            elif isinstance(parsed_json, dict):
                rules_list.append(parsed_json)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"規約JSONファイル {r_file.filename} の解析に失敗しました: {str(e)}")
        finally:
            await r_file.close()

    if code_file:
        await code_file.close()
    if prompt_file:
        await prompt_file.close()

    if not rules_list:
        raise HTTPException(status_code=400, detail="規約JSONが空または指定されていません。")

    try:
        report = await run_code_check(
            code_filename=actual_filename,
            code_content=code_str,
            rules=rules_list,
            backend_type=backend_type,
            base_url=base_url,
            model=model,
            custom_prompt=effective_custom_prompt,
            prompt_file_path=prompt_file_path
        )
        return {"status": "success", "filename": actual_filename, "report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI検証処理中にエラーが発生しました: {str(e)}")

@app.post("/api/v1/verify")
async def api_verify_json(payload: CheckRequestJSON):
    """API直接呼び出し用エンドポイント"""
    try:
        report = await run_code_check(
            code_filename=payload.filename or "input_code.txt",
            code_content=payload.code,
            rules=payload.rules,
            backend_type=payload.backend_type,
            base_url=payload.base_url,
            model=payload.model,
            custom_prompt=payload.custom_prompt,
            prompt_file_path=payload.prompt_file_path
        )
        return {"status": "success", "filename": payload.filename, "report": report}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e) or repr(e))
