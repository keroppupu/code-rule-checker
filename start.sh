#!/bin/bash
set -e

# ==============================================================================
# AI Code Rule Checker - RHEL / Linux 起動スクリプト
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

IMAGE_TAR="code-rule-checker-v0.1-linux-amd64.tar.gz"
IMAGE_NAME="code-rule-checker:v0.1"
CONTAINER_NAME="code_rule_checker_app"
PORT=8030

echo "=== AI Code Rule Checker 起動処理を開始します ==="

# 1. コンテナエンジンの判定 (podman または docker)
if command -v podman &> /dev/null; then
    CONTAINER_CLI="podman"
elif command -v docker &> /dev/null; then
    CONTAINER_CLI="docker"
else
    echo "エラー: podman または docker がインストールされていません。" >&2
    exit 1
fi
echo "使用コンテナエンジン: ${CONTAINER_CLI}"

# 2. イメージのロード (tar.gz が存在する場合)
if [ -f "${IMAGE_TAR}" ]; then
    echo "コンテナイメージアーカイブ (${IMAGE_TAR}) を読み込み中..."
    ${CONTAINER_CLI} load < <(gzip -dc "${IMAGE_TAR}")
elif [ -f "code-rule-checker-v0.1-linux-amd64.tar" ]; then
    echo "コンテナイメージアーカイブ (code-rule-checker-v0.1-linux-amd64.tar) を読み込み中..."
    ${CONTAINER_CLI} load -i code-rule-checker-v0.1-linux-amd64.tar
else
    # アーカイブがない場合はビルドを試みる
    if [ -f "Dockerfile" ]; then
        echo "イメージファイルが見つからないため、ローカルでビルドします: ${IMAGE_NAME}..."
        ${CONTAINER_CLI} build -t ${IMAGE_NAME} .
    else
        echo "エラー: イメージアーカイブ (${IMAGE_TAR}) または Dockerfile が見つかりません。" >&2
        exit 1
    fi
fi

# 3. 既存の同名コンテナがあれば停止・削除
if ${CONTAINER_CLI} ps -a --format '{{.Names}}' | grep -Eq "^${CONTAINER_NAME}\$"; then
    echo "既存のコンテナ '${CONTAINER_NAME}' を停止・削除します..."
    ${CONTAINER_CLI} rm -f "${CONTAINER_NAME}" || true
fi

# 4. コンテナ起動 (SELinux環境対応、ホストゲートウェイ追加)
echo "コンテナ '${CONTAINER_NAME}' をポート ${PORT} で起動します..."
if [ "${CONTAINER_CLI}" = "podman" ]; then
    # Podman用の起動
    ${CONTAINER_CLI} run -d \
        --name "${CONTAINER_NAME}" \
        --security-opt label=disable \
        -p ${PORT}:8000 \
        --add-host host.docker.internal:host-gateway \
        -e PYTHONUNBUFFERED=1 \
        --restart unless-stopped \
        "${IMAGE_NAME}"
else
    # Docker用の起動
    ${CONTAINER_CLI} run -d \
        --name "${CONTAINER_NAME}" \
        --security-opt label=disable \
        -p ${PORT}:8000 \
        --add-host host.docker.internal:host-gateway \
        -e PYTHONUNBUFFERED=1 \
        --restart unless-stopped \
        "${IMAGE_NAME}"
fi

echo "=========================================================="
echo "AI Code Rule Checker が正常に起動しました！"
echo "Web UI: http://localhost:${PORT}"
echo "MCP SSE: http://localhost:${PORT}/mcp/sse"
echo "=========================================================="
