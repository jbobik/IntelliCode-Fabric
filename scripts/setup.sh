#!/bin/bash
set -e

echo "============================================"
echo "  AI Code Partner — Setup Script"
echo "============================================"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 not found. Please install Python 3.9+"
    exit 1
fi

PYTHON=python3
PIP="$PYTHON -m pip"

echo ""
echo "[1/5] Creating Python virtual environment..."
cd "$(dirname "$0")/.."
$PYTHON -m venv .venv
source .venv/bin/activate

echo ""
echo "[2/5] Installing Python dependencies..."
$PIP install --upgrade pip
$PIP install -r backend/requirements.txt

echo ""
echo "[3/5] Creating directories..."
mkdir -p models data

echo ""
echo "[4/5] Installing VS Code extension dependencies..."
cd extension
if command -v npm &> /dev/null; then
    npm install
    npm run compile
    echo "Extension compiled successfully!"
else
    echo "WARNING: npm not found. Install Node.js to build the extension."
fi
cd ..

echo ""
echo "[5/5] Downloading embedding model..."
$PYTHON -c "
from sentence_transformers import SentenceTransformer
print('Downloading embedding model...')
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
print('Embedding model ready!')
"

echo ""
echo "============================================"
echo "  Setup Complete!"
echo "============================================"
echo ""
echo "Next steps:"
echo "  1. Activate venv:  source .venv/bin/activate"
echo "  2. Start backend:  cd backend && python server.py"
echo "  3. Open VS Code:   code ."
echo "  4. Press F5 to launch extension in debug mode"
echo "  5. Select a model in the sidebar and start chatting!"
echo ""
echo "To download a model manually:"
echo "  python scripts/download_model.py --model qwen2.5-coder-1.5b"
echo ""