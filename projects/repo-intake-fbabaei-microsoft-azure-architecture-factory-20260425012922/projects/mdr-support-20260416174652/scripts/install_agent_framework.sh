#!/usr/bin/env bash
# Install the Microsoft Agent Framework SDK in the two phases required by
# the preview packaging. The azure-ai-agentserver-* packages pin
# agent-framework-core<=rc3, so the rc6 packages MUST be installed second
# so their version wins dependency resolution.
set -euo pipefail

PYTHON_BIN="${PYTHON_EXECUTABLE:-python}"
echo "Using Python: ${PYTHON_BIN}"
echo

echo "Phase 1/2: install azure-ai-agentserver stack (pins agent-framework-core<=rc3)..."
"${PYTHON_BIN}" -m pip install \
    "azure-ai-agentserver-agentframework==1.0.0b16" \
    "azure-ai-agentserver-core==1.0.0b16" \
    "agent-dev-cli==0.0.1b260316"

echo
echo "Phase 2/2: upgrade agent-framework packages to rc6..."
"${PYTHON_BIN}" -m pip install --upgrade \
    "agent-framework-core==1.0.0rc6" \
    "agent-framework-foundry==1.0.0rc6" \
    "agent-framework-openai==1.0.0rc6"

echo
echo "Verifying install..."
"${PYTHON_BIN}" -c "import agent_framework, agent_framework.foundry; print('agent_framework OK')"

cat <<'EOF'

Done. Enable the Foundry runtime with:
  export AGENT_FRAMEWORK_ENABLED=1
  export FOUNDRY_PROJECT_ENDPOINT="https://<project>.services.ai.azure.com/api/projects/<project>"
  export FOUNDRY_MODEL_DEPLOYMENT_NAME="gpt-5.2"
EOF
