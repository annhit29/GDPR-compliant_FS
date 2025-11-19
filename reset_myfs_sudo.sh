#!/bin/bash
# ───────────────────────────────────────────────
# Clean up and reset FUSE mount for GDPR-FS

# chmod +x reset_myfs_sudo.sh
# ./reset_myfs_sudo.sh
# ───────────────────────────────────────────────

MNT="/tmp/mnt"
echo "[GDPRFS] Cleaning up any previous mounts..."

# 1. Find and kill any running myfs.py process
PID=$(ps aux | grep "[m]yfs.py" | awk '{print $2}')
if [ -n "$PID" ]; then
    echo "Killing stuck myfs.py process (PID: $PID)..."
    sudo kill -9 $PID 2>/dev/null || true
else
    echo "No running myfs.py process found."
fi

# 2. Try to unmount /tmp/mnt
echo "Unmounting /tmp/mnt if mounted..."
sudo umount -l "$MNT" 2>/dev/null || true
sudo fusermount3 -u "$MNT" 2>/dev/null || true

# 3. Clean up and recreate the folder
if [ -d "$MNT" ]; then
    echo "Removing existing mount folder..."
    sudo rm -rf "$MNT"
fi

echo "Creating fresh /tmp/mnt..."
sudo mkdir -p "$MNT"
sudo chown $USER:$USER "$MNT"

# 4. Print ready message
echo "Cleanup complete. In another terminal, you can now run:"
echo "sudo PYTHONPATH=. python3 gdprfs/myfs.py /tmp/mnt -f -o allow_other" # Use sudo to run the FUSE daemon as root in order to 1)Open /dev/fuse (to register and communicate with the kernel), and 2) Read/write /var/lib/gdprfs/upper and so make a copy in /var/lib/gdprfs/mirror
echo "or in venv:"
echo "sudo -E PYTHONPATH=. ~/gdprfs-venv/bin/python3 gdprfs/myfs.py /tmp/mnt -f -o allow_other"
