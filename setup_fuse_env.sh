#!/bin/bash
# setup_fuse_env.sh
# Purpose: Configure fuse-python for a virtual environment and ensure /dev/fuse permissions.

set -e

# VENV_DIR=~/awscli-venv
VENV_DIR=~/gdprfs-venv
PYTHON_VERSION=python3.12
SITE_PACKAGES="$VENV_DIR/lib/$PYTHON_VERSION/site-packages"
SYSTEM_FUSE_PATH="/usr/local/lib/$PYTHON_VERSION/dist-packages/fuse_python-1.0.9-py3.12-linux-x86_64.egg"

echo "🔹 Activating virtual environment..."
source "$VENV_DIR/bin/activate"

echo "🔹 Checking/Installing poppler-utils (pdftotext)..."
if ! command -v pdftotext &> /dev/null; then
    echo "Installing poppler-utils..."
    sudo apt update -y
    sudo apt install -y poppler-utils
    echo "✅ poppler-utils installed"
else
    echo "✅ poppler-utils already present"
fi

echo "🔹 Checking FUSE device group and permissions..."
sudo groupadd fuse 2>/dev/null || true
sudo usermod -aG fuse "$USER"
sudo chown root:fuse /dev/fuse
sudo chmod 660 /dev/fuse
echo "✅ /dev/fuse permissions:"
ls -l /dev/fuse

echo "🔹 Ensuring user is part of the fuse group..."
groups "$USER" | grep -q fuse || echo "⚠️ Please log out and log back in to apply group membership."

echo "🔹 Cleaning any conflicting local fuse.py..."
rm -f "$SITE_PACKAGES/fuse.py"

echo "🔹 Creating symlinks for fuse and fuseparts..."
sudo ln -sf "$SYSTEM_FUSE_PATH/fuseparts" "$SITE_PACKAGES/fuseparts"
ln -sf "$SYSTEM_FUSE_PATH/fuse.py" "$SITE_PACKAGES/fuse.py"

echo "✅ Symlink verification:"
ls -l "$SITE_PACKAGES/fuse.py" "$SITE_PACKAGES/fuseparts"

echo "🔹 Testing FUSE import..."
python3 -c "from fuse import Fuse; print('✅ Fuse imported successfully')"


echo "🔹 Installing SQLAlchemy in the virtual environment..."
pip install --upgrade pip
pip install sqlalchemy

echo "Verifying SQLAlchemy import..."
python3 -c "import sqlalchemy; print('✅ SQLAlchemy imported successfully, version:', sqlalchemy.__version__)"
echo "---🔹 SQLAlchemy package details:---"
pip show sqlalchemy

# echo "[GDPRFS] Checking Python dependency: psutil..."
# if ! python3 -c "import psutil" &>/dev/null; then
#     echo "📦 Installing psutil..."
#     sudo apt update -y && sudo apt install -y python3-psutil
# else
#     echo "✅ psutil already installed."
# fi

# Flask (werkzeug is automatically included) + dependencies
echo "🔹 Installing Flask + Requests in the virtual environment..."
pip install flask requests 

echo "Verifying Flask installation..."
python3 -c "import flask; import requests; print('✅ Flask version:', flask.__version__)"

echo "🔹 Installing Flask-SQLAlchemy in the virtual environment..."
pip install flask_sqlalchemy

echo "Verifying Flask-SQLAlchemy installation..."
python3 -c "import importlib.metadata; print('✅ Flask-SQLAlchemy version:', importlib.metadata.version('flask-sqlalchemy'))"

echo "🔹 Installing Pydantic + Pydantic-AI..."
# pip install "pydantic>=2" pydantic-ai
pip install "pydantic>=2" pydantic-ai openai python-docx odfpy pandas openpyxl pdfminer.six

python3 -c "import pydantic; print('✅ Pydantic version:', pydantic.__version__)"
python3 -c "import pydantic_ai; print('✅ Pydantic-AI imported successfully')"
python3 -c "import openai; print('✅ OpenAI package version:', openai.__version__)"
python3 -c "import docx; print('✅ python-docx package version:', docx.__version__)"
python3 -c "import odf; print('✅ odfpy imported successfully')"
python3 -c "import pandas; print('✅ pandas package version:', pandas.__version__)"
python3 -c "import openpyxl; print('✅ openpyxl package version:', openpyxl.__version__)"
python3 -c "import pdfminer; print('✅ pdfminer.six package version:', pdfminer.__version__)"

echo "🎉 Setup complete!"
