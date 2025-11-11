# GDPR-compliant file system

```
INSTRLIB/
├── gdprfs/
│   ├── myfs.py                 ← has the poller inside 
│   ├── db_utils.py
│   ├── models.py               ← GDPR FS' DB models
│   ├── setup_db.py             ← set up the GDPR FS' DB  
│   └── ...
└── gdprfs.db
│
└── external_consent_platform/  ← external Data Subject (DS, = external users) Flask portal
│   ├── app.py                  ← Flask app (main entrypoint) for DS
│   ├── api.py                  ← REST API routes for this FS
│   ├── models.py               ← external consent platform's DB models
│   ├── poller.py               ← FS-side poller
│   ├── event_config.yaml       ← modularize the external consent platform and GDPR-compliant FS related part
│   └── templates/
│   │   ├── index.html          ← DS's webpage (HTML UI)
│   │   ├── signup.html
│   │   └── login.html
│   └── instance/
│       └── external_purpose_platform.db
│
└── internal_purpose_platform/
    ├── app.py v
    ├── models.py v
    ├── reasons.yaml v
    ├── templates/ v
    │   ├── index.html v
    │   ├── signup.html v
    │   └── login.html v
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