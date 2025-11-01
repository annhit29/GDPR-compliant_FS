#!/bin/bash
# ───────────────────────────────────────────────
# Clean up and reset FUSE mount for GDPR-FS
# Author: ann20010929 helper script ❤️

# chmod +x reset_myfs.sh
# ./reset_myfs.sh
# ───────────────────────────────────────────────

MNT="/tmp/mnt"
echo "🧹 [GDPRFS] Cleaning up any previous mounts..."

# 1️⃣ Find and kill any running myfs.py process
PID=$(ps aux | grep "[m]yfs.py" | awk '{print $2}')
if [ -n "$PID" ]; then
    echo "⚠️  Killing stuck myfs.py process (PID: $PID)..."
    kill -9 $PID 2>/dev/null || true
else
    echo "✅ No running myfs.py process found."
fi

# 2️⃣ Try to unmount /tmp/mnt
echo "📦 Unmounting /tmp/mnt if mounted..."
sudo umount -l "$MNT" 2>/dev/null || true
sudo fusermount3 -u "$MNT" 2>/dev/null || true

# 3️⃣ Clean up and recreate the folder
if [ -d "$MNT" ]; then
    echo "🗑 Removing existing mount folder..."
    sudo rm -rf "$MNT"
fi

echo "📁 Creating fresh /tmp/mnt..."
mkdir -p "$MNT"
sudo chown $USER:$USER "$MNT"

# 4️⃣ Print ready message
echo "✨ [GDPRFS] Cleanup complete. In another terminal, you can now run:"
echo "PYTHONPATH=. python3 gdprfs/myfs.py /tmp/mnt -f"
