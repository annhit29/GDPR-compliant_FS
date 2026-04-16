#!/bin/bash
# setup_fuse_env.sh
# Purpose: Configure fuse-python for a virtual environment and ensure /dev/fuse permissions.

set -e

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
    echo "poppler-utils installed"
else
    echo "poppler-utils already present"
fi

echo "🔹 Checking FUSE device group and permissions..."
sudo groupadd fuse 2>/dev/null || true
sudo usermod -aG fuse "$USER"
sudo chown root:fuse /dev/fuse
sudo chmod 660 /dev/fuse
echo "/dev/fuse permissions:"
ls -l /dev/fuse

echo "🔹 Ensuring user is part of the fuse group..."
groups "$USER" | grep -q fuse || echo "Please log out and log back in to apply group membership."

echo "🔹 Cleaning any conflicting local fuse.py..."
rm -f "$SITE_PACKAGES/fuse.py"

echo "🔹 Creating symlinks for fuse and fuseparts..."
sudo ln -sf "$SYSTEM_FUSE_PATH/fuseparts" "$SITE_PACKAGES/fuseparts"
ln -sf "$SYSTEM_FUSE_PATH/fuse.py" "$SITE_PACKAGES/fuse.py"

echo "Symlink verification:"
ls -l "$SITE_PACKAGES/fuse.py" "$SITE_PACKAGES/fuseparts"

echo "🔹 Testing FUSE import..."
python3 -c "from fuse import Fuse; print('Fuse imported successfully')"


echo "🔹 Installing SQLAlchemy in the virtual environment..."
pip install --upgrade pip
pip install sqlalchemy

echo "Verifying SQLAlchemy import..."
python3 -c "import sqlalchemy; print('SQLAlchemy imported successfully, version:', sqlalchemy.__version__)"
echo "---🔹 SQLAlchemy package details:---"
pip show sqlalchemy

echo "🔹 Installing Flask + Requests in the virtual environment..."
pip install flask requests 

echo "Verifying Flask installation..."
python3 -c "import flask; import requests; print('Flask version:', flask.__version__)"

echo "🔹 Installing Flask-SQLAlchemy in the virtual environment..."
pip install flask_sqlalchemy

echo "Verifying Flask-SQLAlchemy installation..."
python3 -c "import importlib.metadata; print('Flask-SQLAlchemy version:', importlib.metadata.version('flask-sqlalchemy'))"

echo "🔹 Installing Pydantic + Pydantic-AI..."
pip install "pydantic>=2" pydantic-ai openai python-docx odfpy pandas openpyxl pdfminer.six

python3 -c "import pydantic; print('Pydantic version:', pydantic.__version__)"
python3 -c "import pydantic_ai; print('Pydantic-AI imported successfully')"
python3 -c "import openai; print('OpenAI package version:', openai.__version__)"
python3 -c "import docx; print('python-docx package version:', docx.__version__)"
python3 -c "import odf; print('odfpy imported successfully')"
python3 -c "import pandas; print('pandas package version:', pandas.__version__)"
python3 -c "import openpyxl; print('openpyxl package version:', openpyxl.__version__)"
python3 -c "import pdfminer; print('pdfminer.six package version:', pdfminer.__version__)"

echo "Installing Levenshtein for improved string matching..."
pip install python-Levenshtein

echo "🔹 Installing pypdf..."
pip install pypdf
echo "🔹 Generating redacted_template.pdf..."

python3 <<'EOF'
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

c = canvas.Canvas("/tmp/redacted_template.pdf", pagesize=A4)
c.setFont("Helvetica-Bold", 48)
c.drawCentredString(A4[0] / 2, A4[1] / 2, "REDACTED")
c.save()
EOF

# Move into place with correct permissions
sudo mv /tmp/redacted_template.pdf /var/lib/gdprfs/redacted_template.pdf
sudo chmod 644 /var/lib/gdprfs/redacted_template.pdf #permission: root: read/write, group: read, others: read
sudo chown root:root /var/lib/gdprfs/redacted_template.pdf
echo "redacted_template.pdf installed."

echo "🔹 Creating /var/lib/gdprfs/.gdprowner (if not already present) ..."
if [ ! -f /var/lib/gdprfs/.gdprowner ]; then
    echo "# GDPR manual PII declaration patterns" | sudo tee /var/lib/gdprfs/.gdprowner > /dev/null
    sudo chmod 600 /var/lib/gdprfs/.gdprowner
    sudo chown root:root /var/lib/gdprfs/.gdprowner
    echo ".gdprowner created at /var/lib/gdprfs/.gdprowner (root-only, API-managed)"
else
    echo ".gdprowner already exists, preserving existing rules"
fi

echo "Setup complete!"
