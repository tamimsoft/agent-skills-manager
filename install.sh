#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_BIN="${HOME}/.local/bin"
INSTALL_LIB="${HOME}/.local/lib/agent-skills"
SRC="${REPO_DIR}/src/agent_skills"

mkdir -p "${INSTALL_BIN}" "${INSTALL_LIB}"

# Copy package.
rm -rf "${INSTALL_LIB}/agent_skills"
cp -R "${SRC}" "${INSTALL_LIB}/agent_skills"

# Launcher.
cat > "${INSTALL_BIN}/agent-skills" <<'EOF'
#!/usr/bin/env bash
exec python3 -m agent_skills "$@"
EOF
chmod +x "${INSTALL_BIN}/agent-skills"

# Ensure ~/.local/lib on PYTHONPATH via launcher wrapper instead.
cat > "${INSTALL_BIN}/agent-skills" <<EOF
#!/usr/bin/env bash
export PYTHONPATH="${INSTALL_LIB}:\${PYTHONPATH:-}"
exec python3 -m agent_skills "\$@"
EOF
chmod +x "${INSTALL_BIN}/agent-skills"

echo "Installed agent-skills to ${INSTALL_BIN}/agent-skills"
echo "Ensure ${INSTALL_BIN} is on PATH (doctor checks this)."