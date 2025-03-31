curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
uv pip compile backend/pyproject.toml -o requirements.txt
