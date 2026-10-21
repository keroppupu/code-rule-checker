import json
import httpx
from typing import List, Dict, Any, Optional

DEFAULT_PROMPT_TEMPLATE = """あなたは厳格かつ実用的なコードレビュアーです。
以下の「コーディング規約（JSON定義）」に基づいて、提出された「ソースコード」を詳細に検証してください。

### 【コーディング規約定義】
{rules_content}

### 【対象ソースコード】
ファイル名: {code_filename}
```
{code_content}
```

### 【指示事項】
1. ソースコードが提示された各規約に準拠しているかを精査してください。
2. 規約違反または改善推奨箇所がある場合、該当行番号・違反内容・理由・具体的な修正コード案（Before / After）を明示してください。
3. 規約に準拠している良い点についても評価してください。
4. 全体の適合度スコア（0〜100%）および総合サマリーを提示してください。
5. 出力フォーマットは読みやすいMarkdown形式（表や見出し、コードブロックを活用）で回答してください。
"""

async def call_llm(
    backend_type: str,
    base_url: str,
    model: str,
    prompt: str,
    system_prompt: Optional[str] = None,
    api_key: Optional[str] = "not-needed"
) -> str:
    """
    Ollama または vLLM (OpenAI互換API) にリクエストを送信して推論結果を取得します。
    """
    clean_base = base_url.rstrip("/")
    # LLMの生成処理時間に余裕を持たせるためタイムアウトを300秒(5分)に設定
    timeout = httpx.Timeout(300.0, connect=15.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        if backend_type.lower() == "ollama":
            # Ollama native API: /api/generate または /api/chat
            # ここでは標準的な /api/chat または OpenAI互換 /v1/chat/completions が使えるが、汎用的に /api/chat を利用
            endpoint = f"{clean_base}/api/chat"
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            payload = {
                "model": model,
                "messages": messages,
                "stream": False
            }
            res = await client.post(endpoint, json=payload)
            res.raise_for_status()
            data = res.json()
            return data.get("message", {}).get("content", "")

        elif backend_type.lower() == "vllm" or backend_type.lower() == "openai":
            # vLLM / OpenAI compatible chat completions
            endpoint = f"{clean_base}/v1/chat/completions"
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            headers = {
                "Authorization": f"Bearer {api_key or 'EMPTY'}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": model,
                "messages": messages,
                "stream": False,
                "temperature": 0.2
            }
            res = await client.post(endpoint, json=payload, headers=headers)
            res.raise_for_status()
            data = res.json()
            return data["choices"][0]["message"]["content"]
        else:
            raise ValueError(f"サポートされていないバックエンドです: {backend_type}")

async def run_code_check(
    code_filename: str,
    code_content: str,
    rules: List[Dict[str, Any]],
    backend_type: str,
    base_url: str,
    model: str,
    custom_prompt: Optional[str] = None,
    prompt_file_path: Optional[str] = None
) -> str:
    formatted_rules = []
    for idx, rule in enumerate(rules, 1):
        rule_name = rule.get("name", f"Rule-{idx}")
        rule_json = json.dumps(rule, ensure_ascii=False, indent=2)
        formatted_rules.append(f"--- 規約 {idx}: {rule_name} ---\n{rule_json}")

    rules_content = "\n\n".join(formatted_rules)

    # プロンプトファイル指定がある場合は最優先で読み込み
    prompt_template = None
    if prompt_file_path and prompt_file_path.strip():
        try:
            with open(prompt_file_path, "r", encoding="utf-8") as f:
                prompt_template = f.read()
        except Exception as e:
            raise ValueError(f"プロンプトファイル '{prompt_file_path}' の読み込みに失敗しました: {str(e)}")
    elif custom_prompt and custom_prompt.strip():
        prompt_template = custom_prompt

    if prompt_template:
        # プレースホルダがある場合は安全に置換、なければ末尾に追加
        # str.format だとプロンプト中の {json_key} 等で KeyError や ValueError が発生するため安全に replace
        if "{code_content}" in prompt_template or "{rules_content}" in prompt_template or "{code_filename}" in prompt_template:
            prompt = (
                prompt_template
                .replace("{code_filename}", code_filename)
                .replace("{code_content}", code_content)
                .replace("{rules_content}", rules_content)
            )
        else:
            prompt = f"{prompt_template}\n\n### 規約:\n{rules_content}\n\n### 対象コード({code_filename}):\n{code_content}"
    else:
        prompt = (
            DEFAULT_PROMPT_TEMPLATE
            .replace("{code_filename}", code_filename)
            .replace("{code_content}", code_content)
            .replace("{rules_content}", rules_content)
        )

    system_prompt = "あなたはソフトウェア品質とコーディング標準の専門家です。客観的かつ建設的なフィードバックを提示してください。"
    return await call_llm(backend_type, base_url, model, prompt, system_prompt=system_prompt)
