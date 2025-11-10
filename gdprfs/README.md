# GDPR-compliant file system

```
INSTRLIB/
├── gdprfs/
│   ├── myfs.py                 ← has the poller inside 
│   ├── db_utils.py
│   ├── models.py
│   └── ...
│
└── external_consent_platform/  ← external Data Subject (DS) Flask portal
│   ├── app.py                  ← Flask app (main entrypoint)
│   ├── api.py                  ← REST API routes for this FS
│   ├── models.py               ← DB models
│   ├── poller.py               ← FS-side poller
│   └── templates/
│   │   └── index.html          ← DS's webpage (HTML UI)
│   └── instance/
        └── external_purpose_platform.db
│
└── internal_purpose_platform/
    ├── __init__.py
    ├── app.py
    ├── api.py
    ├── models.py
    ├── templates/
    │   └── index.html
    └── instance/
        └── internal_purpose_platform.db
```

Please refresh the page `http://127.0.0.1:5000/` to see the update.


Commands to run:
terminal3:
```
cd ~/MA3/Building_a_GDPR-compliant_file_system/instrlib/external_consent_platform
source ~/awscli-venv/bin/activate
```

If I want to remove `external_consent_platform`'s existing db in order to create a new one automatically on the startup of app.py 
```
sudo rm instance/external_consent_platform.db 
```

Otherwise, I can directly:
```
python app.py
```
Ctrl+C to stop running app.py


then terminal2:
```
cd ~/MA3/Building_a_GDPR-compliant_file_system/instrlib
sudo rm gdprfs.db # remove GDPR FS' database 
sudo python3 gdprfs/setup_db.py # initialize GDPR FS database's all tables
```

then terminal1:
```
cd ~/MA3/Building_a_GDPR-compliant_file_system/instrlib
. ~/awscli-venv/bin/activate
./setup_fuse_env.sh
./reset_myfs_sudo.sh

# Run my FUSE filesystem with the FUSE daemon
sudo PYTHONPATH=. python3 gdprfs/myfs.py /tmp/mnt -f -o allow_other
```

then terminal2:
to stop the FUSE daemon:
```
cd ~/MA3/Building_a_GDPR-compliant_file_system/instrlib
./reset_myfs_sudo.sh
```