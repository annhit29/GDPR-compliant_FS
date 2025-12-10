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
Dec 3 2025
## Folder name, then filename, only then file content!
See `def update_file_mapping_for_upper`
1. If gdprowner matches, then we should NOT run folder-name logic.
We use Strong **Inheritance**:
2. `[Lazy DB Folder]`: Folder name determines the owner, so all files inside a folder belong to that external person. 
3. Else, If the filename contains a name, then the file clearly belongs to that external person.
4. Else, if folder or filename have not already identified the external person, then file content is scanned. 

## `.gdprowner` file
internal users use the internal platform interface to declare the PII manually. These declarations will be stored in the `.gdprowner` file (a `.gitignore`-like file).
| Feature           |  |
| ----------------- | --------------------------------- |
| Purpose           | manually declare PII ownership    |
| Effect            | file becomes PERSONAL data        |
| Enforcer behavior | controlled by consent             |
| Mapping           | MUST map file → person            |
| Analogy           | `.gdprowner`                      |

Eg: An intenal user manually declares `.gdprowner` to contain
```
jdoe: doe/**
```
with the folder structure
```
upper/
 └── doe/
      ├── dd.txt
      └── d.txt
```

This means
> “Any file inside the folder `doe/` (and all its subfolders) is owned by user `jdoe` because the internal user manually declared it so.”

Thus, the system says "No need to scan filename or content. We override automatically: these files belong to `jdoe`."

Csq:
“EVERY file in folder `doe/` belongs to `jdoe` because an intenral user explicitly said so.”

## Lazy DB Folder
`[Lazy DB Folder]` is only triggered when folder looks like a person, based on name matching logic.
> “The folder name looks like it belongs to John Doe, so all files inherit ownership from the folder.”

This is weaker than `.gdprowner` where internal user declares manually and explicitely through the internal platform interface.

Eg:
1. If an internal user creates a folder `basin/`
```
[MKDIR] Creating directory /var/lib/gdprfs/upper/basin
[lazy DB folder] Folder 'basin' recognized as belonging to David Basin
[lazy DB folder] Folder-level inheritance activated (context=mkdir)
```
then the system uses the name matching logic to determine if this folder belongs to DS `dbasin`.
In this case, Yes. So all everything inside `basin/` will be mapped to personid `dbasin` in the `person_file_map` table.

2. Indeed
2.1. Inside this folder, we create a file,
```
[CREATE] Synced /var/lib/gdprfs/upper/basin/Empty Document → mirror
[lazy DB folder] Linked (folder) David Basin ↔ Empty Document
[lazy DB folder] Finished mapping for folder `basin` (dbasin ↔ Empty Document, context=create), folder-based only
[DB] Updated metadata for Empty Document (last_action=create)
```
And we see it is immidiately mapped to user `dbasin`. This mapping is stored in the `person_file_map` table.

2.2. After renaming the filename,
```
[DB] Detected rename Empty Document → b.txt
[lazy DB folder] Finished mapping for folder `basin` (dbasin ↔ b.txt, context=rename), folder-based only
[DB] Updated metadata for b.txt (last_action=rename)
[DB] Mapped after rename → /basin/b.txt
```
We see the `dbasin ↔ b.txt` mapping. And this is stored in the `person_file_map` table.


Note: for static testing, i .e. assuming internal user interacts via the internal platform to declare manually, but in the reality, use `sudo nano /var/lib/gdprfs/.gdprowner` to declare ownership of a folder or a file of a DS, eg:
An intenal user manually declares `.gdprowner` to contain
```
jdoe: doe/**
```
then ctrl+O, Enter, ctrl+X