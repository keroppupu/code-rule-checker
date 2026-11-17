import os
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

COBOL_EXTENSIONS = ('.cbl', '.cob', '.pco', '.cpy', '.cobol')

def decode_source_code_bytes(raw_bytes: bytes, filename: str, encoding_hint: Optional[str] = None) -> tuple[str, str]:
    """
    ソースコードの生バイト列を適切な文字コードでデコードします。
    COBOLファイルまたはShift_JIS指定時はShift_JIS(CP932)を優先し、UTF-8への意図しない変換を防ぎます。
    戻り値: (デコード済みテキスト, 適用された文字コード表記)
    """
    is_cobol = any(filename.lower().endswith(ext) for ext in COBOL_EXTENSIONS)
    
    # ユーザー指定ヒントがある場合
    if encoding_hint:
        normalized = encoding_hint.lower().replace("-", "_").replace(" ", "")
        if normalized in ("sjis", "shift_jis", "cp932", "ms932", "windows_31j"):
            return raw_bytes.decode("cp932", errors="replace"), "Shift_JIS (CP932)"
        elif normalized in ("utf8", "utf_8"):
            return raw_bytes.decode("utf-8", errors="replace"), "UTF-8"
        elif normalized in ("eucjp", "euc_jp"):
            return raw_bytes.decode("euc_jp", errors="replace"), "EUC-JP"

    # COBOLファイルの場合はShift_JIS(CP932)を最優先
    if is_cobol:
        try:
            return raw_bytes.decode("cp932"), "Shift_JIS (CP932)"
        except UnicodeDecodeError:
            pass

    # 通常ファイルの自動判定 (UTF-8 -> CP932 -> EUC-JP)
    for enc, label in (("utf-8", "UTF-8"), ("cp932", "Shift_JIS (CP932)"), ("euc_jp", "EUC-JP")):
        try:
            return raw_bytes.decode(enc), label
        except UnicodeDecodeError:
            continue

    # フォールバック
    if is_cobol:
        return raw_bytes.decode("cp932", errors="replace"), "Shift_JIS (CP932)"
    return raw_bytes.decode("utf-8", errors="replace"), "UTF-8"

@mcp_server.tool()
async def check_code_against_rules(
    code: str,
    rules_json_strings: List[str],
    filename: str = "sample.py",
    backend_type: str = "ollama",
    base_url: str = "http://host.docker.internal:11434",
    model: str = "qwen3.5:9b",
    custom_instructions: Optional[str] = None,
    prompt_file_path: Optional[str] = None,
    api_key: Optional[str] = None,
    code_encoding: Optional[str] = None
) -> str:
    """
    ソースコードと複数のコーディング規約JSON文字列を受け取り、AIで整合性をチェックしてMarkdownレポートを返します。
    - code: チェック対象のソースコード
    - rules_json_strings: 各規約JSONの文字列表現のリスト
    - filename: ソースコードのファイル名 (例: main.py, sample.cbl, proc.pco)
    - backend_type: 'ollama', 'vllm', または 'litellm'
    - base_url: エンドポイント (例: http://host.docker.internal:11434, http://localhost:4000)
    - model: 使用するモデル名 (例: qwen3.5:9b, gpt-4o, claude-3-5-sonnet)
    - custom_instructions: 直接指定する追加プロンプト・指示
    - prompt_file_path: プロンプトが書かれたテキストファイルのパス (指定時はこちらを優先して読み込み)
    - api_key: LiteLLM等の認証用APIキー (任意)
    - code_encoding: 文字コード前提 (例: "Shift_JIS (CP932)", "UTF-8"。COBOL拡張子の場合は自動でShift_JISと判定)
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

    is_cobol = any(filename.lower().endswith(ext) for ext in COBOL_EXTENSIONS)
    eff_encoding = code_encoding or ("Shift_JIS (CP932)" if is_cobol else "UTF-8 / Shift_JIS")

    report = await run_code_check(
        code_filename=filename,
        code_content=code,
        rules=parsed_rules,
        backend_type=backend_type,
        base_url=base_url,
        model=model,
        custom_prompt=custom_instructions,
        prompt_file_path=prompt_file_path,
        api_key=api_key,
        code_encoding=eff_encoding
    )
    return report

app = FastAPI(title="AI Code Rule Checker", version="1.0.0")
templates = Jinja2Templates(directory="templates")

# 静的ファイルの提供 (オフライン環境・イントラネット対応)
app.mount("/static", StaticFiles(directory="static"), name="static")

# MCP SSE アプリを /mcp にマウント
mcp_sse_app = mcp_server.sse_app(transport_security=None)
app.mount("/mcp", mcp_sse_app)

SETTINGS_FILE = "settings.json"

class SettingsModel(BaseModel):
    backend_type: str = "ollama"
    base_url: str = "http://host.docker.internal:11434"
    model: str = "qwen3.5:9b"
    api_key: Optional[str] = ""

def load_settings() -> dict:
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "backend_type": "ollama",
        "base_url": "http://host.docker.internal:11434",
        "model": "qwen3.5:9b",
        "api_key": ""
    }

def save_settings(settings: dict):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

@app.get("/api/settings")
async def get_settings():
    return load_settings()

@app.post("/api/settings")
async def update_settings(payload: SettingsModel):
    settings_dict = payload.model_dump()
    save_settings(settings_dict)
    return {"status": "success", "settings": settings_dict}

class CheckRequestJSON(BaseModel):
    code: str
    filename: Optional[str] = "input_code.txt"
    rules: List[dict]
    backend_type: Optional[str] = None  # "ollama", "vllm", "litellm"
    base_url: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    custom_prompt: Optional[str] = None
    prompt_file_path: Optional[str] = None
    code_encoding: Optional[str] = None  # "Shift_JIS", "UTF-8" 等

@app.get("/", response_class=HTMLResponse)
async def serve_ui(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.post("/api/check")
async def api_check_form(
    code_file: Optional[UploadFile] = File(None),
    code_text: Optional[str] = Form(None),
    code_filename: Optional[str] = Form("source_code.txt"),
    code_encoding: Optional[str] = Form(None),
    rule_files: List[UploadFile] = File(...),
    prompt_file: Optional[UploadFile] = File(None),
    prompt_file_path: Optional[str] = Form(None),
    backend_type: Optional[str] = Form(None),
    base_url: Optional[str] = Form(None),
    model: Optional[str] = Form(None),
    api_key: Optional[str] = Form(None),
    custom_prompt: Optional[str] = Form(None)
):
    """WebUIからのMultipart/Formアップロード処理"""
    # ソースコードの読み出し（Shift_JIS/CP932を優先判定・保持）
    if code_file and code_file.filename:
        actual_filename = code_file.filename
        raw_code = await code_file.read()
        code_str, detected_encoding = decode_source_code_bytes(raw_code, actual_filename, code_encoding)
    elif code_text and code_text.strip():
        actual_filename = code_filename or "direct_input.txt"
        code_str = code_text
        is_cobol = any(actual_filename.lower().endswith(ext) for ext in COBOL_EXTENSIONS)
        detected_encoding = code_encoding or ("Shift_JIS (CP932)" if is_cobol else "UTF-8 / Shift_JIS")
    else:
        raise HTTPException(status_code=400, detail="ソースコードファイルまたはテキストを入力してください。")

    # プロンプトファイルのアップロードがある場合
    effective_custom_prompt = custom_prompt
    if prompt_file and prompt_file.filename:
        prompt_bytes = await prompt_file.read()
        # プロンプトファイルもShift_JIS / UTF-8の両方に対応
        p_text, _ = decode_source_code_bytes(prompt_bytes, prompt_file.filename)
        effective_custom_prompt = p_text

    # 複数ルールJSONの読み出し
    rules_list = []
    for r_file in rule_files:
        try:
            content_bytes = await r_file.read()
            # JSONファイルもUTF-8またはCP932でデコード
            try:
                json_str = content_bytes.decode("utf-8")
            except UnicodeDecodeError:
                json_str = content_bytes.decode("cp932", errors="replace")
            parsed_json = json.loads(json_str)
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

    # 設定値のフォールバック (保存されたデフォルト設定)
    saved = load_settings()
    eff_backend = backend_type or saved.get("backend_type", "ollama")
    eff_base_url = base_url or saved.get("base_url", "http://host.docker.internal:11434")
    eff_model = model or saved.get("model", "qwen3.5:9b")
    eff_api_key = api_key if api_key is not None else saved.get("api_key", "")

    try:
        report = await run_code_check(
            code_filename=actual_filename,
            code_content=code_str,
            rules=rules_list,
            backend_type=eff_backend,
            base_url=eff_base_url,
            model=eff_model,
            custom_prompt=effective_custom_prompt,
            prompt_file_path=prompt_file_path,
            api_key=eff_api_key,
            code_encoding=detected_encoding
        )
        return {
            "status": "success",
            "filename": actual_filename,
            "encoding": detected_encoding,
            "report": report
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI検証処理中にエラーが発生しました: {str(e)}")

@app.post("/api/v1/verify")
async def api_verify_json(payload: CheckRequestJSON):
    """API直接呼び出し用エンドポイント"""
    saved = load_settings()
    eff_backend = payload.backend_type or saved.get("backend_type", "ollama")
    eff_base_url = payload.base_url or saved.get("base_url", "http://host.docker.internal:11434")
    eff_model = payload.model or saved.get("model", "qwen3.5:9b")
    eff_api_key = payload.api_key if payload.api_key is not None else saved.get("api_key", "")

    actual_filename = payload.filename or "input_code.txt"
    is_cobol = any(actual_filename.lower().endswith(ext) for ext in COBOL_EXTENSIONS)
    eff_encoding = payload.code_encoding or ("Shift_JIS (CP932)" if is_cobol else "UTF-8 / Shift_JIS")

    try:
        report = await run_code_check(
            code_filename=actual_filename,
            code_content=payload.code,
            rules=payload.rules,
            backend_type=eff_backend,
            base_url=eff_base_url,
            model=eff_model,
            custom_prompt=payload.custom_prompt,
            prompt_file_path=payload.prompt_file_path,
            api_key=eff_api_key,
            code_encoding=eff_encoding
        )
        return {
            "status": "success",
            "filename": actual_filename,
            "encoding": eff_encoding,
            "report": report
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e) or repr(e))
