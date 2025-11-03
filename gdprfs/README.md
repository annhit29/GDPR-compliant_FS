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
    ├── app.py                  ← Flask app (main entrypoint)
    ├── api.py                  ← REST API routes for this FS
    ├── models.py               ← DB models
    ├── poller.py               ← FS-side poller
    └── templates/
        └── index.html          ← DS's webpage (HTML UI)
```

Please refresh the page `http://127.0.0.1:5000/` to see the update.