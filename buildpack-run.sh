curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
uv pip compile pyproject.toml -o requirements.txt
