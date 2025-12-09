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


TL;DR: t
step1: in terminal3:
```
cd ~/MA3/Building_a_GDPR-compliant_file_system/instrlib/external_consent_platform
source ~/awscli-venv/bin/activate
python app.py
```

step2: in terminal4:
```
cd ~/MA3/Building_a_GDPR-compliant_file_system/instrlib/internal_purpose_platform
source ~/awscli-venv/bin/activate
python app.py
```

step3: in terminal1:
```
cd ~/MA3/Building_a_GDPR-compliant_file_system/instrlib
. ~/awscli-venv/bin/activate
./reset_myfs_sudo.sh
```

i.e.

1. Run in terminal1:
```
./setup_fuse_env.sh;
./run_all.sh
```
2. Run in terminal2: `sudo PYTHONPATH=. python3 gdprfs/myfs.py /tmp/mnt -f -o allow_other`

Whenever we want to stop the external consent platform and the internal purpose platform, do Ctrl+C on both terminals.
Whenever we want to stop the FUSE daemon, do in terminal1: `./reset_myfs_sudo.sh`


# Ports:
External: 5000
Internal: 8000
LLM analyzer: 5005 (why not, because it is not used)


# LLM Analyzer
For this, one needs an API key for the LLM model.


# System Design (Assumption/Choices)
## Folder name, then filename, only then file content!
We use Strong **Inheritance**:
1. Folder name determines the owner, so all files inside a folder belong to that external person.
2. Else, If the filename contains a name, then the file clearly belongs to that external person.
3. Else, if folder or filename have not already identified the external person, then file content is scanned. 