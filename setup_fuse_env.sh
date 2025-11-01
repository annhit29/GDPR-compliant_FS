#!/bin/bash
# setup_fuse_env.sh
# Purpose: Configure fuse-python for a virtual environment and ensure /dev/fuse permissions.

set -e

VENV_DIR=~/awscli-venv
PYTHON_VERSION=python3.12
SITE_PACKAGES="$VENV_DIR/lib/$PYTHON_VERSION/site-packages"
SYSTEM_FUSE_PATH="/usr/local/lib/$PYTHON_VERSION/dist-packages/fuse_python-1.0.9-py3.12-linux-x86_64.egg"

echo "🔹 Activating virtual environment..."
source "$VENV_DIR/bin/activate"

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

echo "🎉 Setup complete!"
