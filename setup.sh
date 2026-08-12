#!/usr/bin/env bash
# twin. v0 — local setup. Run once: bash setup.sh
set -euo pipefail

echo "==> python"
python3 --version

echo "==> venv"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> deps"
python -m pip install --quiet -r requirements.txt

echo "==> package markers"
touch decode/__init__.py eval/__init__.py

echo "==> scratch dirs"
mkdir -p inbox runs eval/golden_set/images

echo "==> tests (offline, no API key needed)"
python -m eval.test_schema
echo
python -m eval.test_score
echo
python -m eval.test_pipeline
echo
python -m eval.test_predicates

cat <<'EOF'

------------------------------------------------------------
Setup complete.

Activate in future sessions:
  source .venv/bin/activate

Next:
  1. Drop 100 outfit screenshots into ./inbox/
  2. export ANTHROPIC_API_KEY=sk-...
  3. python -m eval.label --images inbox/ --provider sonnet --labeller editor_01
  4. python -m eval.run --providers sonnet,haiku

Tests must stay green. Nothing ships red.
------------------------------------------------------------
EOF
