When a file is not a txt or csv file AND is empty:
Eg: filename: `ahlala`. We write the content `hof`
- write: write **then read**
So Collect **then Use** instead of Collect only.

When a file is not a txt or csv file AND when it is not empty
Eg: filename: `ahlala` with content `hof`
- go into the /mnt folder: go into the /mnt folder **then read**
So **Use** instead of no events.

Works on CLI when GUI closed. So possible reason: because of Nautilus.
I tried to kill the nautilus process, but it always fails.

```
(awscli-venv) ann20010929@ann20010929-ThinkPad-P16s-Gen-3:~/MA3/Building_a_GDPR-compliant_file_system/instrlib$ sudo PYTHONPATH=. python3 gdprfs/myfs.py /tmp/mnt -f -o allow_other
PEP mapping keys: [('MyFS', 'read'), ('MyFS', 'write')]
/home/ann20010929/MA3/Building_a_GDPR-compliant_file_system/enfguard/bin/enfguard.exe -sig /home/ann20010929/MA3/Building_a_GDPR-compliant_file_system/instrlib/gdprfs/policies/gdpr_draft.sig -formula /home/ann20010929/MA3/Building_a_GDPR-compliant_file_system/instrlib/gdprfs/policies/consent_draft.mfotl -json
[2025-11-01 12:56:38.416045] [timer     ]: Starting
[2025-11-01 12:56:38.416265] [timer     ]: tick(0)
[2025-11-01 12:56:38.416375] [writer    ]: Starting
[2025-11-01 12:56:38.416495] [reader    ]: Starting
[INIT] Running automatic rescan of existing /upper files...
[2025-11-01 12:56:38.416915] [writer    ]: Sent to enforcer: @0 tick();
in _is_temp_name
[2025-11-01 12:56:38.422562] [reader    ]: Skipping non-JSON: The formula
[2025-11-01 12:56:38.422652] [reader    ]: Skipping non-JSON:  □[0s,∞) (∀fid:string. ∀uid:string. Use(fid:string, "marketing", uid:string) → ¬Revoke(uid:string, "marketing") S[0s,∞) Consent(uid:string, "marketing"))
[2025-11-01 12:56:38.422667] [reader    ]: Skipping non-JSON: is enforceable and types to
[2025-11-01 12:56:38.422678] [reader    ]: Skipping non-JSON:  □[0s,∞) ((∀fid:string. (∀uid:string. ((Use(fid:string, "marketing", uid:string) : Sup) →:L ¬Revoke(uid:string, "marketing") S[0s,∞) Consent(uid:string, "marketing") : Cau) : Cau)) : Cau) : Cau
[DB] Updated mapping for dodo2.txt (context=rescan)
in _is_temp_name
[DB] Updated mapping for yoo0.txt (context=rescan)
in _is_temp_name
[DB] Updated mapping for Does_fait_dodo.txt (context=rescan)
in _is_temp_name
[DB] Updated mapping for do.txt (context=rescan)
in _is_temp_name
[DB] Updated mapping for ruby.txt (context=rescan)
in _is_temp_name
[DB] Updated mapping for Empty Document (context=rescan)
in _is_temp_name
[DB] Updated mapping for yolo.txt (context=rescan)
in _is_temp_name
[DB] Updated mapping for Ubermensch.txt (context=rescan)
[INIT] Rescan complete.
[2025-11-01 12:56:39.416476] [timer     ]: tick(1)
[2025-11-01 12:56:39.417042] [writer    ]: Sent to enforcer: @1 tick();
[2025-11-01 12:56:39.417421] [reader    ]: Received from enforcer: {'ts': 0, 'proactive': True}
[2025-11-01 12:56:39.417483] [reader    ]: Matching request: @1 tick();
[2025-11-01 12:56:40.416812] [timer     ]: tick(2)
[2025-11-01 12:56:40.417292] [writer    ]: Sent to enforcer: @2 tick();
[2025-11-01 12:56:40.417868] [reader    ]: Received from enforcer: {'ts': 1, 'proactive': True}
[2025-11-01 12:56:40.417925] [reader    ]: Matching request: @2 tick();
[2025-11-01 12:56:41.417164] [timer     ]: tick(3)
[2025-11-01 12:56:41.417342] [writer    ]: Sent to enforcer: @3 tick();
[2025-11-01 12:56:41.417714] [reader    ]: Received from enforcer: {'ts': 2, 'proactive': True}
[2025-11-01 12:56:41.417774] [reader    ]: Matching request: @3 tick();
[2025-11-01 12:56:42.417346] [timer     ]: tick(4)
[2025-11-01 12:56:42.417534] [writer    ]: Sent to enforcer: @4 tick();
[2025-11-01 12:56:42.417897] [reader    ]: Received from enforcer: {'ts': 3, 'proactive': True}
[2025-11-01 12:56:42.417951] [reader    ]: Matching request: @4 tick();
[2025-11-01 12:56:43.417535] [timer     ]: tick(5)
[2025-11-01 12:56:43.417708] [writer    ]: Sent to enforcer: @5 tick();
[2025-11-01 12:56:43.418098] [reader    ]: Received from enforcer: {'ts': 4, 'proactive': True}
[2025-11-01 12:56:43.418157] [reader    ]: Matching request: @5 tick();
[2025-11-01 12:56:44.417735] [timer     ]: tick(6)
[2025-11-01 12:56:44.417940] [writer    ]: Sent to enforcer: @6 tick();
[2025-11-01 12:56:44.418350] [reader    ]: Received from enforcer: {'ts': 5, 'proactive': True}
[2025-11-01 12:56:44.418381] [reader    ]: Matching request: @6 tick();
[2025-11-01 12:56:45.417925] [timer     ]: tick(7)
[2025-11-01 12:56:45.418104] [writer    ]: Sent to enforcer: @7 tick();
[2025-11-01 12:56:45.418353] [reader    ]: Received from enforcer: {'ts': 6, 'proactive': True}
[2025-11-01 12:56:45.418398] [reader    ]: Matching request: @7 tick();
in readdir
[DEBUG readdir] called with path=/
[2025-11-01 12:56:46.418118] [timer     ]: tick(8)
[2025-11-01 12:56:46.418303] [writer    ]: Sent to enforcer: @8 tick();
[2025-11-01 12:56:46.418717] [reader    ]: Received from enforcer: {'ts': 7, 'proactive': True}
[2025-11-01 12:56:46.418773] [reader    ]: Matching request: @8 tick();
[2025-11-01 12:56:47.418303] [timer     ]: tick(9)
[2025-11-01 12:56:47.418482] [writer    ]: Sent to enforcer: @9 tick();
[2025-11-01 12:56:47.418868] [reader    ]: Received from enforcer: {'ts': 8, 'proactive': True}
[2025-11-01 12:56:47.418921] [reader    ]: Matching request: @9 tick();
[2025-11-01 12:56:48.418482] [timer     ]: tick(10)
[2025-11-01 12:56:48.418671] [writer    ]: Sent to enforcer: @10 tick();
[2025-11-01 12:56:48.418980] [reader    ]: Received from enforcer: {'ts': 9, 'proactive': True}
[2025-11-01 12:56:48.419031] [reader    ]: Matching request: @10 tick();
[2025-11-01 12:56:49.418679] [timer     ]: tick(11)
[2025-11-01 12:56:49.418883] [writer    ]: Sent to enforcer: @11 tick();
[2025-11-01 12:56:49.419249] [reader    ]: Received from enforcer: {'ts': 10, 'proactive': True}
[2025-11-01 12:56:49.419305] [reader    ]: Matching request: @11 tick();
[2025-11-01 12:56:50.418889] [timer     ]: tick(12)
[2025-11-01 12:56:50.419078] [writer    ]: Sent to enforcer: @12 tick();
[2025-11-01 12:56:50.419201] [reader    ]: Received from enforcer: {'ts': 11, 'proactive': True}
[2025-11-01 12:56:50.419237] [reader    ]: Matching request: @12 tick();
[2025-11-01 12:56:51.419083] [timer     ]: tick(13)
[2025-11-01 12:56:51.419235] [writer    ]: Sent to enforcer: @13 tick();
[2025-11-01 12:56:51.419657] [reader    ]: Received from enforcer: {'ts': 12, 'proactive': True}
[2025-11-01 12:56:51.419692] [reader    ]: Matching request: @13 tick();
[CREATE] Synced /var/lib/gdprfs/upper/Empty Document (2) → mirror
in _is_temp_name
in _is_temp_name
[DB] Updated mapping for Empty Document (2) (context=create)
[DB] Updated metadata for Empty Document (2) (last_action=create)
[2025-11-01 12:56:52.419257] [timer     ]: tick(14)
[2025-11-01 12:56:52.419433] [writer    ]: Sent to enforcer: @14 tick();
[2025-11-01 12:56:52.419966] [reader    ]: Received from enforcer: {'ts': 13, 'proactive': True}
[2025-11-01 12:56:52.420029] [reader    ]: Matching request: @14 tick();
[2025-11-01 12:56:53.419424] [timer     ]: tick(15)
[2025-11-01 12:56:53.419600] [writer    ]: Sent to enforcer: @15 tick();
[2025-11-01 12:56:53.420061] [reader    ]: Received from enforcer: {'ts': 14, 'proactive': True}
[2025-11-01 12:56:53.420115] [reader    ]: Matching request: @15 tick();
[2025-11-01 12:56:54.419608] [timer     ]: tick(16)
[2025-11-01 12:56:54.419834] [writer    ]: Sent to enforcer: @16 tick();
[2025-11-01 12:56:54.420106] [reader    ]: Received from enforcer: {'ts': 15, 'proactive': True}
[2025-11-01 12:56:54.420131] [reader    ]: Matching request: @16 tick();
[2025-11-01 12:56:55.419845] [timer     ]: tick(17)
[2025-11-01 12:56:55.420160] [writer    ]: Sent to enforcer: @17 tick();
[2025-11-01 12:56:55.420423] [reader    ]: Received from enforcer: {'ts': 16, 'proactive': True}
[2025-11-01 12:56:55.420473] [reader    ]: Matching request: @17 tick();
[2025-11-01 12:56:56.420055] [timer     ]: tick(18)
[2025-11-01 12:56:56.420347] [writer    ]: Sent to enforcer: @18 tick();
[2025-11-01 12:56:56.420609] [reader    ]: Received from enforcer: {'ts': 17, 'proactive': True}
[2025-11-01 12:56:56.420634] [reader    ]: Matching request: @18 tick();
[2025-11-01 12:56:57.420238] [timer     ]: tick(19)
[2025-11-01 12:56:57.420527] [writer    ]: Sent to enforcer: @19 tick();
[2025-11-01 12:56:57.420858] [reader    ]: Received from enforcer: {'ts': 18, 'proactive': True}
[2025-11-01 12:56:57.420912] [reader    ]: Matching request: @19 tick();
[2025-11-01 12:56:58.420440] [timer     ]: tick(20)
[2025-11-01 12:56:58.420676] [writer    ]: Sent to enforcer: @20 tick();
[2025-11-01 12:56:58.421039] [reader    ]: Received from enforcer: {'ts': 19, 'proactive': True}
[2025-11-01 12:56:58.421094] [reader    ]: Matching request: @20 tick();
[2025-11-01 12:56:59.420663] [timer     ]: tick(21)
[2025-11-01 12:56:59.420964] [writer    ]: Sent to enforcer: @21 tick();
[2025-11-01 12:56:59.421292] [reader    ]: Received from enforcer: {'ts': 20, 'proactive': True}
[2025-11-01 12:56:59.421332] [reader    ]: Matching request: @21 tick();
[2025-11-01 12:57:00.421012] [timer     ]: tick(22)
[2025-11-01 12:57:00.421339] [writer    ]: Sent to enforcer: @22 tick();
[2025-11-01 12:57:00.422479] [reader    ]: Received from enforcer: {'ts': 21, 'proactive': True}
[2025-11-01 12:57:00.422542] [reader    ]: Matching request: @22 tick();
[2025-11-01 12:57:01.421417] [timer     ]: tick(23)
[2025-11-01 12:57:01.421741] [writer    ]: Sent to enforcer: @23 tick();
[2025-11-01 12:57:01.422132] [reader    ]: Received from enforcer: {'ts': 22, 'proactive': True}
[2025-11-01 12:57:01.422186] [reader    ]: Matching request: @23 tick();
[2025-11-01 12:57:02.421636] [timer     ]: tick(24)
[2025-11-01 12:57:02.421865] [writer    ]: Sent to enforcer: @24 tick();
[2025-11-01 12:57:02.422037] [reader    ]: Received from enforcer: {'ts': 23, 'proactive': True}
[2025-11-01 12:57:02.422085] [reader    ]: Matching request: @24 tick();
[UNLINK] path=/Empty Document → removed from upper and mirror
[DB] Marked Empty Document as deleted at 2025-11-01 12:57:02
[2025-11-01 12:57:03.421908] [timer     ]: tick(25)
[2025-11-01 12:57:03.422210] [writer    ]: Sent to enforcer: @25 tick();
[2025-11-01 12:57:03.422412] [reader    ]: Received from enforcer: {'ts': 24, 'proactive': True}
[2025-11-01 12:57:03.422463] [reader    ]: Matching request: @25 tick();
[2025-11-01 12:57:04.422105] [timer     ]: tick(26)
[2025-11-01 12:57:04.422411] [writer    ]: Sent to enforcer: @26 tick();
[2025-11-01 12:57:04.423009] [reader    ]: Received from enforcer: {'ts': 25, 'proactive': True}
[2025-11-01 12:57:04.423050] [reader    ]: Matching request: @26 tick();
in readdir
[DEBUG readdir] called with path=/
[2025-11-01 12:57:05.422356] [timer     ]: tick(27)
[2025-11-01 12:57:05.422831] [writer    ]: Sent to enforcer: @27 tick();
[2025-11-01 12:57:05.423266] [reader    ]: Received from enforcer: {'ts': 26, 'proactive': True}
[2025-11-01 12:57:05.423319] [reader    ]: Matching request: @27 tick();
[2025-11-01 12:57:06.422694] [timer     ]: tick(28)
[2025-11-01 12:57:06.423009] [writer    ]: Sent to enforcer: @28 tick();
[2025-11-01 12:57:06.423326] [reader    ]: Received from enforcer: {'ts': 27, 'proactive': True}
[2025-11-01 12:57:06.423382] [reader    ]: Matching request: @28 tick();
[2025-11-01 12:57:07.422931] [timer     ]: tick(29)
[2025-11-01 12:57:07.423196] [writer    ]: Sent to enforcer: @29 tick();
[2025-11-01 12:57:07.423510] [reader    ]: Received from enforcer: {'ts': 28, 'proactive': True}
[2025-11-01 12:57:07.423561] [reader    ]: Matching request: @29 tick();
[2025-11-01 12:57:08.423147] [timer     ]: tick(30)
[2025-11-01 12:57:08.423456] [writer    ]: Sent to enforcer: @30 tick();
[2025-11-01 12:57:08.423827] [reader    ]: Received from enforcer: {'ts': 29, 'proactive': True}
[2025-11-01 12:57:08.423893] [reader    ]: Matching request: @30 tick();
[2025-11-01 12:57:09.423402] [timer     ]: tick(31)
[2025-11-01 12:57:09.423766] [writer    ]: Sent to enforcer: @31 tick();
[2025-11-01 12:57:09.424109] [reader    ]: Received from enforcer: {'ts': 30, 'proactive': True}
[2025-11-01 12:57:09.424155] [reader    ]: Matching request: @31 tick();
[2025-11-01 12:57:10.423633] [timer     ]: tick(32)
[2025-11-01 12:57:10.423805] [writer    ]: Sent to enforcer: @32 tick();
[2025-11-01 12:57:10.424079] [reader    ]: Received from enforcer: {'ts': 31, 'proactive': True}
[2025-11-01 12:57:10.424136] [reader    ]: Matching request: @32 tick();
[2025-11-01 12:57:11.423814] [timer     ]: tick(33)
[2025-11-01 12:57:11.424083] [writer    ]: Sent to enforcer: @33 tick();
[2025-11-01 12:57:11.424430] [reader    ]: Received from enforcer: {'ts': 32, 'proactive': True}
[2025-11-01 12:57:11.424487] [reader    ]: Matching request: @33 tick();
in _is_temp_name
[DB] Detected rename Empty Document (2) → ahlala
[DB] Updated mapping for ahlala (context=rename)
[DB] Updated metadata for ahlala (last_action=rename)
[DB] Mapped after rename → /ahlala
[2025-11-01 12:57:12.423992] [timer     ]: tick(34)
[2025-11-01 12:57:12.424244] [writer    ]: Sent to enforcer: @34 tick();
[2025-11-01 12:57:12.424735] [reader    ]: Received from enforcer: {'ts': 33, 'proactive': True}
[2025-11-01 12:57:12.424808] [reader    ]: Matching request: @34 tick();
[2025-11-01 12:57:13.424161] [timer     ]: tick(35)
[2025-11-01 12:57:13.424459] [writer    ]: Sent to enforcer: @35 tick();
[2025-11-01 12:57:13.424839] [reader    ]: Received from enforcer: {'ts': 34, 'proactive': True}
[2025-11-01 12:57:13.424894] [reader    ]: Matching request: @35 tick();
[2025-11-01 12:57:14.424315] [timer     ]: tick(36)
[2025-11-01 12:57:14.424620] [writer    ]: Sent to enforcer: @36 tick();
[2025-11-01 12:57:14.425042] [reader    ]: Received from enforcer: {'ts': 35, 'proactive': True}
[2025-11-01 12:57:14.425095] [reader    ]: Matching request: @36 tick();
in readdir
[DEBUG readdir] called with path=/
[2025-11-01 12:57:15.424494] [timer     ]: tick(37)
[2025-11-01 12:57:15.424793] [writer    ]: Sent to enforcer: @37 tick();
[2025-11-01 12:57:15.425125] [reader    ]: Received from enforcer: {'ts': 36, 'proactive': True}
[2025-11-01 12:57:15.425162] [reader    ]: Matching request: @37 tick();
[2025-11-01 12:57:16.424698] [timer     ]: tick(38)
[2025-11-01 12:57:16.425006] [writer    ]: Sent to enforcer: @38 tick();
[2025-11-01 12:57:16.425312] [reader    ]: Received from enforcer: {'ts': 37, 'proactive': True}
[2025-11-01 12:57:16.425353] [reader    ]: Matching request: @38 tick();
[2025-11-01 12:57:17.424853] [timer     ]: tick(39)
[2025-11-01 12:57:17.425150] [writer    ]: Sent to enforcer: @39 tick();
[2025-11-01 12:57:17.425404] [reader    ]: Received from enforcer: {'ts': 38, 'proactive': True}
[2025-11-01 12:57:17.425456] [reader    ]: Matching request: @39 tick();
[2025-11-01 12:57:18.425030] [timer     ]: tick(40)
[2025-11-01 12:57:18.425209] [writer    ]: Sent to enforcer: @40 tick();
[2025-11-01 12:57:18.425517] [reader    ]: Received from enforcer: {'ts': 39, 'proactive': True}
[2025-11-01 12:57:18.425581] [reader    ]: Matching request: @40 tick();
[2025-11-01 12:57:19.425202] [timer     ]: tick(41)
[2025-11-01 12:57:19.425484] [writer    ]: Sent to enforcer: @41 tick();
[2025-11-01 12:57:19.425719] [reader    ]: Received from enforcer: {'ts': 40, 'proactive': True}
[2025-11-01 12:57:19.425773] [reader    ]: Matching request: @41 tick();
[2025-11-01 12:57:20.425382] [timer     ]: tick(42)
[2025-11-01 12:57:20.425643] [writer    ]: Sent to enforcer: @42 tick();
[2025-11-01 12:57:20.426658] [reader    ]: Received from enforcer: {'ts': 41, 'proactive': True}
[2025-11-01 12:57:20.426712] [reader    ]: Matching request: @42 tick();
[2025-11-01 12:57:21.425580] [timer     ]: tick(43)
[2025-11-01 12:57:21.426095] [writer    ]: Sent to enforcer: @43 tick();
[2025-11-01 12:57:21.426428] [reader    ]: Received from enforcer: {'ts': 42, 'proactive': True}
[2025-11-01 12:57:21.426484] [reader    ]: Matching request: @43 tick();
[2025-11-01 12:57:22.425798] [timer     ]: tick(44)
[2025-11-01 12:57:22.426068] [writer    ]: Sent to enforcer: @44 tick();
[2025-11-01 12:57:22.426338] [reader    ]: Received from enforcer: {'ts': 43, 'proactive': True}
[2025-11-01 12:57:22.426385] [reader    ]: Matching request: @44 tick();
[2025-11-01 12:57:23.426005] [timer     ]: tick(45)
[2025-11-01 12:57:23.426270] [writer    ]: Sent to enforcer: @45 tick();
[2025-11-01 12:57:23.426487] [reader    ]: Received from enforcer: {'ts': 44, 'proactive': True}
[2025-11-01 12:57:23.426543] [reader    ]: Matching request: @45 tick();
[2025-11-01 12:57:24.426242] [timer     ]: tick(46)
[2025-11-01 12:57:24.426541] [writer    ]: Sent to enforcer: @46 tick();
[2025-11-01 12:57:24.426873] [reader    ]: Received from enforcer: {'ts': 45, 'proactive': True}
[2025-11-01 12:57:24.426917] [reader    ]: Matching request: @46 tick();
[2025-11-01 12:57:25.426474] [timer     ]: tick(47)
[2025-11-01 12:57:25.426665] [writer    ]: Sent to enforcer: @47 tick();
[2025-11-01 12:57:25.426940] [reader    ]: Received from enforcer: {'ts': 46, 'proactive': True}
[2025-11-01 12:57:25.426988] [reader    ]: Matching request: @47 tick();
[CREATE] Synced /var/lib/gdprfs/upper/.goutputstream-IX3EF3 → mirror
in _is_temp_name
[DB] Skipped create() DB registration for temp file: <module 'posixpath' (frozen)>
[INSTRUMENT] → entering MyFS.read with args=('/.goutputstream-IX3EF3', b'hof\n', 0), kwargs={}
[DEBUG] Parent process: sudo (pid=10807)
[DEBUG] Parent process: sudo (pid=10806)
[DEBUG] Parent process: bash (pid=4317)
[DEBUG] Parent process: gnome-terminal-server (pid=4306)
[DEBUG] Parent process: systemd (pid=2939)
[DEBUG] Parent process: systemd (pid=1)
[INSTRUMENT] → events = []
read file
[DEBUG] Parent process: sudo (pid=10807)
[DEBUG] Parent process: sudo (pid=10806)
[DEBUG] Parent process: bash (pid=4317)
[DEBUG] Parent process: gnome-terminal-server (pid=4306)
[DEBUG] Parent process: systemd (pid=2939)
[DEBUG] Parent process: systemd (pid=1)
[WRITE] Misrouted write() detected: redirecting safely to raw write for /.goutputstream-IX3EF3
[DEBUG write] called with path=/.goutputstream-IX3EF3, data = b'hof\n', data_len=4, offset=0
in _is_temp_name
[DB] Skipped mapping for temporary file: /.goutputstream-IX3EF3
[WRITE] path=/.goutputstream-IX3EF3 → synced to mirror
[INSTRUMENT] ← leaving MyFS.read, returned 4
in _is_temp_name
in _is_temp_name
[DB] Updated mapping for ahlala (context=write)
[DB] Updated metadata for ahlala (last_action=write)
[2025-11-01 12:57:25.926564] [writer    ]: Sent to enforcer: @47 Collect("ahlala", "marketing");
[2025-11-01 12:57:25.926722] [reader    ]: Received from enforcer: {'ts': 47}
[2025-11-01 12:57:25.926775] [reader    ]: Matching request: @47 Collect("ahlala", "marketing");
[GDPR] Sent Collect event for final file /ahlala via Logger.log()
[INSTRUMENT] → entering MyFS.read with args=('/ahlala', 4096, 0), kwargs={}
[DEBUG] Parent process: sudo (pid=10807)
[DEBUG] Parent process: sudo (pid=10806)
[DEBUG] Parent process: bash (pid=4317)
[DEBUG] Parent process: gnome-terminal-server (pid=4306)
[DEBUG] Parent process: systemd (pid=2939)
[DEBUG] Parent process: systemd (pid=1)
[INSTRUMENT] → events = [Use("ahlala", "marketing", "anonymous")]
[2025-11-01 12:57:25.930568] [writer    ]: Sent to enforcer: @47 Use("ahlala", "marketing", "anonymous");
[2025-11-01 12:57:25.930724] [reader    ]: Received from enforcer: {'ts': 47, 'suppress': [{'name': 'Use', 'args': ['ahlala', 'marketing', 'anonymous']}]}
[2025-11-01 12:57:25.930776] [reader    ]: Matching request: @47 Use("ahlala", "marketing", "anonymous");
Calling function MyFS.read took 0 ms
[INSTRUMENT] → invoking suppression handler for MyFS.read
read file
[DEBUG] Parent process: sudo (pid=10807)
[DEBUG] Parent process: sudo (pid=10806)
[DEBUG] Parent process: bash (pid=4317)
[DEBUG] Parent process: gnome-terminal-server (pid=4306)
[DEBUG] Parent process: systemd (pid=2939)
[DEBUG] Parent process: systemd (pid=1)
opened file for reading
size: 4096
[READ] path=/ahlala reading from /var/lib/gdprfs/upper/ahlala, 4 bytes, size=4096, offset=0, returning=b'hof\n'
in _is_temp_name
[DB] Updated mapping for ahlala (context=read)
[DB] Updated metadata for ahlala (last_action=read)
max_element({('Use',)})={'Use'}
[2025-11-01 12:57:26.426679] [timer     ]: tick(48)
[2025-11-01 12:57:26.426959] [writer    ]: Sent to enforcer: @48 tick();
[2025-11-01 12:57:26.427123] [reader    ]: Received from enforcer: {'ts': 47, 'proactive': True}
[2025-11-01 12:57:26.427168] [reader    ]: Matching request: @48 tick();
[2025-11-01 12:57:27.426912] [timer     ]: tick(49)
[2025-11-01 12:57:27.427068] [writer    ]: Sent to enforcer: @49 tick();
[2025-11-01 12:57:27.427370] [reader    ]: Received from enforcer: {'ts': 48, 'proactive': True}
[2025-11-01 12:57:27.427427] [reader    ]: Matching request: @49 tick();
[2025-11-01 12:57:28.427107] [timer     ]: tick(50)
[2025-11-01 12:57:28.427294] [writer    ]: Sent to enforcer: @50 tick();
[2025-11-01 12:57:28.427563] [reader    ]: Received from enforcer: {'ts': 49, 'proactive': True}
[2025-11-01 12:57:28.427620] [reader    ]: Matching request: @50 tick();
[2025-11-01 12:57:29.427347] [timer     ]: tick(51)
[2025-11-01 12:57:29.427627] [writer    ]: Sent to enforcer: @51 tick();
[2025-11-01 12:57:29.428017] [reader    ]: Received from enforcer: {'ts': 50, 'proactive': True}
[2025-11-01 12:57:29.428076] [reader    ]: Matching request: @51 tick();
[2025-11-01 12:57:30.427659] [timer     ]: tick(52)
[2025-11-01 12:57:30.427965] [writer    ]: Sent to enforcer: @52 tick();
[2025-11-01 12:57:30.428321] [reader    ]: Received from enforcer: {'ts': 51, 'proactive': True}
[2025-11-01 12:57:30.428375] [reader    ]: Matching request: @52 tick();
[2025-11-01 12:57:31.427887] [timer     ]: tick(53)
[2025-11-01 12:57:31.428168] [writer    ]: Sent to enforcer: @53 tick();
[2025-11-01 12:57:31.428296] [reader    ]: Received from enforcer: {'ts': 52, 'proactive': True}
[2025-11-01 12:57:31.428335] [reader    ]: Matching request: @53 tick();
[2025-11-01 12:57:32.428093] [timer     ]: tick(54)
[2025-11-01 12:57:32.428481] [writer    ]: Sent to enforcer: @54 tick();
[2025-11-01 12:57:32.428859] [reader    ]: Received from enforcer: {'ts': 53, 'proactive': True}
[2025-11-01 12:57:32.428889] [reader    ]: Matching request: @54 tick();
[2025-11-01 12:57:33.428324] [timer     ]: tick(55)
[2025-11-01 12:57:33.428722] [writer    ]: Sent to enforcer: @55 tick();
[2025-11-01 12:57:33.428874] [reader    ]: Received from enforcer: {'ts': 54, 'proactive': True}
[2025-11-01 12:57:33.428903] [reader    ]: Matching request: @55 tick();
[2025-11-01 12:57:34.428544] [timer     ]: tick(56)
[2025-11-01 12:57:34.428899] [writer    ]: Sent to enforcer: @56 tick();
[2025-11-01 12:57:34.430987] [reader    ]: Received from enforcer: {'ts': 55, 'proactive': True}
[2025-11-01 12:57:34.431046] [reader    ]: Matching request: @56 tick();
[2025-11-01 12:57:35.428796] [timer     ]: tick(57)
[2025-11-01 12:57:35.429030] [writer    ]: Sent to enforcer: @57 tick();
[2025-11-01 12:57:35.429299] [reader    ]: Received from enforcer: {'ts': 56, 'proactive': True}
[2025-11-01 12:57:35.429350] [reader    ]: Matching request: @57 tick();
[2025-11-01 12:57:36.428997] [timer     ]: tick(58)
[2025-11-01 12:57:36.429240] [writer    ]: Sent to enforcer: @58 tick();
[2025-11-01 12:57:36.429478] [reader    ]: Received from enforcer: {'ts': 57, 'proactive': True}
[2025-11-01 12:57:36.429502] [reader    ]: Matching request: @58 tick();
[2025-11-01 12:57:37.429181] [timer     ]: tick(59)
[2025-11-01 12:57:37.429358] [writer    ]: Sent to enforcer: @59 tick();
[2025-11-01 12:57:37.429639] [reader    ]: Received from enforcer: {'ts': 58, 'proactive': True}
[2025-11-01 12:57:37.429696] [reader    ]: Matching request: @59 tick();
[2025-11-01 12:57:38.429367] [timer     ]: tick(60)
[2025-11-01 12:57:38.429516] [writer    ]: Sent to enforcer: @60 tick();
[2025-11-01 12:57:38.430316] [reader    ]: Received from enforcer: {'ts': 59, 'proactive': True}
[2025-11-01 12:57:38.430344] [reader    ]: Matching request: @60 tick();
[2025-11-01 12:57:39.429551] [timer     ]: tick(61)
[2025-11-01 12:57:39.429756] [writer    ]: Sent to enforcer: @61 tick();
[2025-11-01 12:57:39.429992] [reader    ]: Received from enforcer: {'ts': 60, 'proactive': True}
[2025-11-01 12:57:39.430019] [reader    ]: Matching request: @61 tick();
[2025-11-01 12:57:40.429736] [timer     ]: tick(62)
[2025-11-01 12:57:40.429917] [writer    ]: Sent to enforcer: @62 tick();
[2025-11-01 12:57:40.430047] [reader    ]: Received from enforcer: {'ts': 61, 'proactive': True}
[2025-11-01 12:57:40.430075] [reader    ]: Matching request: @62 tick();
[2025-11-01 12:57:41.429920] [timer     ]: tick(63)
[2025-11-01 12:57:41.430096] [writer    ]: Sent to enforcer: @63 tick();
[2025-11-01 12:57:41.430263] [reader    ]: Received from enforcer: {'ts': 62, 'proactive': True}
[2025-11-01 12:57:41.430305] [reader    ]: Matching request: @63 tick();
[2025-11-01 12:57:42.430128] [timer     ]: tick(64)
[2025-11-01 12:57:42.430335] [writer    ]: Sent to enforcer: @64 tick();
[2025-11-01 12:57:42.430859] [reader    ]: Received from enforcer: {'ts': 63, 'proactive': True}
[2025-11-01 12:57:42.430884] [reader    ]: Matching request: @64 tick();
[2025-11-01 12:57:43.430341] [timer     ]: tick(65)
[2025-11-01 12:57:43.430707] [writer    ]: Sent to enforcer: @65 tick();
[2025-11-01 12:57:43.431136] [reader    ]: Received from enforcer: {'ts': 64, 'proactive': True}
[2025-11-01 12:57:43.431160] [reader    ]: Matching request: @65 tick();
[2025-11-01 12:57:44.430538] [timer     ]: tick(66)
[2025-11-01 12:57:44.430843] [writer    ]: Sent to enforcer: @66 tick();
[2025-11-01 12:57:44.431207] [reader    ]: Received from enforcer: {'ts': 65, 'proactive': True}
[2025-11-01 12:57:44.431236] [reader    ]: Matching request: @66 tick();
[2025-11-01 12:57:45.430713] [timer     ]: tick(67)
[2025-11-01 12:57:45.430916] [writer    ]: Sent to enforcer: @67 tick();
[2025-11-01 12:57:45.431171] [reader    ]: Received from enforcer: {'ts': 66, 'proactive': True}
[2025-11-01 12:57:45.431202] [reader    ]: Matching request: @67 tick();
[2025-11-01 12:57:46.430860] [timer     ]: tick(68)
[2025-11-01 12:57:46.431170] [writer    ]: Sent to enforcer: @68 tick();
[2025-11-01 12:57:46.431865] [reader    ]: Received from enforcer: {'ts': 67, 'proactive': True}
[2025-11-01 12:57:46.431906] [reader    ]: Matching request: @68 tick();
[2025-11-01 12:57:47.431046] [timer     ]: tick(69)
[2025-11-01 12:57:47.431326] [writer    ]: Sent to enforcer: @69 tick();
[2025-11-01 12:57:47.431708] [reader    ]: Received from enforcer: {'ts': 68, 'proactive': True}
[2025-11-01 12:57:47.431749] [reader    ]: Matching request: @69 tick();
[2025-11-01 12:57:48.431223] [timer     ]: tick(70)
[2025-11-01 12:57:48.431403] [writer    ]: Sent to enforcer: @70 tick();
[2025-11-01 12:57:48.431659] [reader    ]: Received from enforcer: {'ts': 69, 'proactive': True}
[2025-11-01 12:57:48.431711] [reader    ]: Matching request: @70 tick();
[2025-11-01 12:57:49.431395] [timer     ]: tick(71)
[2025-11-01 12:57:49.431720] [writer    ]: Sent to enforcer: @71 tick();
[2025-11-01 12:57:49.431900] [reader    ]: Received from enforcer: {'ts': 70, 'proactive': True}
[2025-11-01 12:57:49.431926] [reader    ]: Matching request: @71 tick();
[2025-11-01 12:57:50.431672] [timer     ]: tick(72)
[2025-11-01 12:57:50.431833] [writer    ]: Sent to enforcer: @72 tick();
[2025-11-01 12:57:50.431983] [reader    ]: Received from enforcer: {'ts': 71, 'proactive': True}
[2025-11-01 12:57:50.432001] [reader    ]: Matching request: @72 tick();
in _is_temp_name
[DB] Detected rename ahlala → ahlala.txt
[DB] Updated mapping for ahlala.txt (context=rename)
[DB] Updated metadata for ahlala.txt (last_action=rename)
[DB] Mapped after rename → /ahlala.txt
[2025-11-01 12:57:51.431854] [timer     ]: tick(73)
[2025-11-01 12:57:51.432023] [writer    ]: Sent to enforcer: @73 tick();
[2025-11-01 12:57:51.432165] [reader    ]: Received from enforcer: {'ts': 72, 'proactive': True}
[2025-11-01 12:57:51.432185] [reader    ]: Matching request: @73 tick();
[2025-11-01 12:57:52.432054] [timer     ]: tick(74)
[2025-11-01 12:57:52.432371] [writer    ]: Sent to enforcer: @74 tick();
[2025-11-01 12:57:52.432880] [reader    ]: Received from enforcer: {'ts': 73, 'proactive': True}
[2025-11-01 12:57:52.432907] [reader    ]: Matching request: @74 tick();
[2025-11-01 12:57:53.432256] [timer     ]: tick(75)
[2025-11-01 12:57:53.432444] [writer    ]: Sent to enforcer: @75 tick();
[2025-11-01 12:57:53.432985] [reader    ]: Received from enforcer: {'ts': 74, 'proactive': True}
[2025-11-01 12:57:53.433038] [reader    ]: Matching request: @75 tick();
[2025-11-01 12:57:54.432438] [timer     ]: tick(76)
[2025-11-01 12:57:54.432682] [writer    ]: Sent to enforcer: @76 tick();
[2025-11-01 12:57:54.433161] [reader    ]: Received from enforcer: {'ts': 75, 'proactive': True}
[2025-11-01 12:57:54.433204] [reader    ]: Matching request: @76 tick();
[2025-11-01 12:57:55.432639] [timer     ]: tick(77)
[2025-11-01 12:57:55.432953] [writer    ]: Sent to enforcer: @77 tick();
[2025-11-01 12:57:55.433225] [reader    ]: Received from enforcer: {'ts': 76, 'proactive': True}
[2025-11-01 12:57:55.433252] [reader    ]: Matching request: @77 tick();
[2025-11-01 12:57:56.432882] [timer     ]: tick(78)
[2025-11-01 12:57:56.433274] [writer    ]: Sent to enforcer: @78 tick();
[2025-11-01 12:57:56.433602] [reader    ]: Received from enforcer: {'ts': 77, 'proactive': True}
[2025-11-01 12:57:56.433653] [reader    ]: Matching request: @78 tick();
[2025-11-01 12:57:57.433087] [timer     ]: tick(79)
[2025-11-01 12:57:57.433400] [writer    ]: Sent to enforcer: @79 tick();
[2025-11-01 12:57:57.433671] [reader    ]: Received from enforcer: {'ts': 78, 'proactive': True}
[2025-11-01 12:57:57.433725] [reader    ]: Matching request: @79 tick();
[2025-11-01 12:57:58.433246] [timer     ]: tick(80)
[2025-11-01 12:57:58.433575] [writer    ]: Sent to enforcer: @80 tick();
[2025-11-01 12:57:58.433911] [reader    ]: Received from enforcer: {'ts': 79, 'proactive': True}
[2025-11-01 12:57:58.433962] [reader    ]: Matching request: @80 tick();
[2025-11-01 12:57:59.433420] [timer     ]: tick(81)
[2025-11-01 12:57:59.433608] [writer    ]: Sent to enforcer: @81 tick();
[2025-11-01 12:57:59.433857] [reader    ]: Received from enforcer: {'ts': 80, 'proactive': True}
[2025-11-01 12:57:59.433878] [reader    ]: Matching request: @81 tick();
in readdir
[DEBUG readdir] called with path=/
[2025-11-01 12:58:00.433603] [timer     ]: tick(82)
[2025-11-01 12:58:00.433801] [writer    ]: Sent to enforcer: @82 tick();
[2025-11-01 12:58:00.434052] [reader    ]: Received from enforcer: {'ts': 81, 'proactive': True}
[2025-11-01 12:58:00.434098] [reader    ]: Matching request: @82 tick();
[2025-11-01 12:58:01.433806] [timer     ]: tick(83)
[2025-11-01 12:58:01.434097] [writer    ]: Sent to enforcer: @83 tick();
[2025-11-01 12:58:01.434355] [reader    ]: Received from enforcer: {'ts': 82, 'proactive': True}
[2025-11-01 12:58:01.434386] [reader    ]: Matching request: @83 tick();
[2025-11-01 12:58:02.434018] [timer     ]: tick(84)
[2025-11-01 12:58:02.434224] [writer    ]: Sent to enforcer: @84 tick();
[2025-11-01 12:58:02.436631] [reader    ]: Received from enforcer: {'ts': 83, 'proactive': True}
[2025-11-01 12:58:02.436682] [reader    ]: Matching request: @84 tick();
[2025-11-01 12:58:03.434236] [timer     ]: tick(85)
[2025-11-01 12:58:03.434552] [writer    ]: Sent to enforcer: @85 tick();
[2025-11-01 12:58:03.434823] [reader    ]: Received from enforcer: {'ts': 84, 'proactive': True}
[2025-11-01 12:58:03.434875] [reader    ]: Matching request: @85 tick();
[2025-11-01 12:58:04.434450] [timer     ]: tick(86)
[2025-11-01 12:58:04.434737] [writer    ]: Sent to enforcer: @86 tick();
[2025-11-01 12:58:04.435013] [reader    ]: Received from enforcer: {'ts': 85, 'proactive': True}
[2025-11-01 12:58:04.435056] [reader    ]: Matching request: @86 tick();
[2025-11-01 12:58:05.434650] [timer     ]: tick(87)
[2025-11-01 12:58:05.434872] [writer    ]: Sent to enforcer: @87 tick();
[2025-11-01 12:58:05.435311] [reader    ]: Received from enforcer: {'ts': 86, 'proactive': True}
[2025-11-01 12:58:05.435353] [reader    ]: Matching request: @87 tick();
[2025-11-01 12:58:06.434884] [timer     ]: tick(88)
[2025-11-01 12:58:06.435203] [writer    ]: Sent to enforcer: @88 tick();
[2025-11-01 12:58:06.435932] [reader    ]: Received from enforcer: {'ts': 87, 'proactive': True}
[2025-11-01 12:58:06.435961] [reader    ]: Matching request: @88 tick();
[2025-11-01 12:58:07.435105] [timer     ]: tick(89)
[2025-11-01 12:58:07.435454] [writer    ]: Sent to enforcer: @89 tick();
[2025-11-01 12:58:07.435731] [reader    ]: Received from enforcer: {'ts': 88, 'proactive': True}
[2025-11-01 12:58:07.435764] [reader    ]: Matching request: @89 tick();
[2025-11-01 12:58:08.435328] [timer     ]: tick(90)
[2025-11-01 12:58:08.435513] [writer    ]: Sent to enforcer: @90 tick();
[2025-11-01 12:58:08.435677] [reader    ]: Received from enforcer: {'ts': 89, 'proactive': True}
[2025-11-01 12:58:08.435711] [reader    ]: Matching request: @90 tick();
[2025-11-01 12:58:09.435526] [timer     ]: tick(91)
[2025-11-01 12:58:09.435732] [writer    ]: Sent to enforcer: @91 tick();
[2025-11-01 12:58:09.435885] [reader    ]: Received from enforcer: {'ts': 90, 'proactive': True}
[2025-11-01 12:58:09.435913] [reader    ]: Matching request: @91 tick();
[2025-11-01 12:58:10.435756] [timer     ]: tick(92)
[2025-11-01 12:58:10.435946] [writer    ]: Sent to enforcer: @92 tick();
[2025-11-01 12:58:10.436610] [reader    ]: Received from enforcer: {'ts': 91, 'proactive': True}
[2025-11-01 12:58:10.436653] [reader    ]: Matching request: @92 tick();
[2025-11-01 12:58:11.435979] [timer     ]: tick(93)
[2025-11-01 12:58:11.436299] [writer    ]: Sent to enforcer: @93 tick();
[2025-11-01 12:58:11.436567] [reader    ]: Received from enforcer: {'ts': 92, 'proactive': True}
[2025-11-01 12:58:11.436590] [reader    ]: Matching request: @93 tick();
in _is_temp_name
[DB] Detected rename ahlala.txt → ahlala
[DB] Updated mapping for ahlala (context=rename)
[DB] Updated metadata for ahlala (last_action=rename)
[DB] Mapped after rename → /ahlala
[INSTRUMENT] → entering MyFS.read with args=('/ahlala', 4096, 0), kwargs={}
[DEBUG] Parent process: sudo (pid=10807)
[DEBUG] Parent process: sudo (pid=10806)
[DEBUG] Parent process: bash (pid=4317)
[DEBUG] Parent process: gnome-terminal-server (pid=4306)
[DEBUG] Parent process: systemd (pid=2939)
[DEBUG] Parent process: systemd (pid=1)
[INSTRUMENT] → events = [Use("ahlala", "marketing", "anonymous")]
[2025-11-01 12:58:12.358790] [writer    ]: Sent to enforcer: @93 Use("ahlala", "marketing", "anonymous");
[2025-11-01 12:58:12.358978] [reader    ]: Received from enforcer: {'ts': 93, 'suppress': [{'name': 'Use', 'args': ['ahlala', 'marketing', 'anonymous']}]}
[2025-11-01 12:58:12.359007] [reader    ]: Matching request: @93 Use("ahlala", "marketing", "anonymous");
Calling function MyFS.read took 0 ms
[INSTRUMENT] → invoking suppression handler for MyFS.read
read file
[DEBUG] Parent process: sudo (pid=10807)
[DEBUG] Parent process: sudo (pid=10806)
[DEBUG] Parent process: bash (pid=4317)
[DEBUG] Parent process: gnome-terminal-server (pid=4306)
[DEBUG] Parent process: systemd (pid=2939)
[DEBUG] Parent process: systemd (pid=1)
opened file for reading
size: 4096
[READ] path=/ahlala reading from /var/lib/gdprfs/upper/ahlala, 4 bytes, size=4096, offset=0, returning=b'hof\n'
in _is_temp_name
[DB] Updated mapping for ahlala (context=read)
[DB] Updated metadata for ahlala (last_action=read)
max_element({('Use',)})={'Use'}
[INSTRUMENT] → entering MyFS.read with args=('/ahlala', 4096, 0), kwargs={}
[DEBUG] Parent process: sudo (pid=10807)
[DEBUG] Parent process: sudo (pid=10806)
[DEBUG] Parent process: bash (pid=4317)
[DEBUG] Parent process: gnome-terminal-server (pid=4306)
[DEBUG] Parent process: systemd (pid=2939)
[DEBUG] Parent process: systemd (pid=1)
[INSTRUMENT] → events = [Use("ahlala", "marketing", "anonymous")]
Calling function MyFS.read took 0 ms
[INSTRUMENT] → invoking suppression handler for MyFS.read
read file
[DEBUG] Parent process: sudo (pid=10807)
[DEBUG] Parent process: sudo (pid=10806)
[DEBUG] Parent process: bash (pid=4317)
[DEBUG] Parent process: gnome-terminal-server (pid=4306)
[DEBUG] Parent process: systemd (pid=2939)
[DEBUG] Parent process: systemd (pid=1)
opened file for reading
size: 4096
[READ] path=/ahlala reading from /var/lib/gdprfs/upper/ahlala, 4 bytes, size=4096, offset=0, returning=b'hof\n'
in _is_temp_name
[DB] Updated mapping for ahlala (context=read)
[DB] Updated metadata for ahlala (last_action=read)
max_element({('Use',)})={'Use'}
[2025-11-01 12:58:12.436177] [timer     ]: tick(94)
[2025-11-01 12:58:12.436364] [writer    ]: Sent to enforcer: @94 tick();
[2025-11-01 12:58:12.436605] [reader    ]: Received from enforcer: {'ts': 93, 'proactive': True}
[2025-11-01 12:58:12.436655] [reader    ]: Matching request: @94 tick();
[2025-11-01 12:58:13.436374] [timer     ]: tick(95)
[2025-11-01 12:58:13.436708] [writer    ]: Sent to enforcer: @95 tick();
[2025-11-01 12:58:13.437248] [reader    ]: Received from enforcer: {'ts': 94, 'proactive': True}
[2025-11-01 12:58:13.437278] [reader    ]: Matching request: @95 tick();
[2025-11-01 12:58:14.436617] [timer     ]: tick(96)
[2025-11-01 12:58:14.436966] [writer    ]: Sent to enforcer: @96 tick();
[2025-11-01 12:58:14.437222] [reader    ]: Received from enforcer: {'ts': 95, 'proactive': True}
[2025-11-01 12:58:14.437251] [reader    ]: Matching request: @96 tick();
[2025-11-01 12:58:15.436819] [timer     ]: tick(97)
[2025-11-01 12:58:15.437009] [writer    ]: Sent to enforcer: @97 tick();
[2025-11-01 12:58:15.437154] [reader    ]: Received from enforcer: {'ts': 96, 'proactive': True}
[2025-11-01 12:58:15.437179] [reader    ]: Matching request: @97 tick();
[2025-11-01 12:58:16.436984] [timer     ]: tick(98)
[2025-11-01 12:58:16.437268] [writer    ]: Sent to enforcer: @98 tick();
[2025-11-01 12:58:16.437565] [reader    ]: Received from enforcer: {'ts': 97, 'proactive': True}
[2025-11-01 12:58:16.437608] [reader    ]: Matching request: @98 tick();
[2025-11-01 12:58:17.437264] [timer     ]: tick(99)
[2025-11-01 12:58:17.437531] [writer    ]: Sent to enforcer: @99 tick();
[2025-11-01 12:58:17.437929] [reader    ]: Received from enforcer: {'ts': 98, 'proactive': True}
[2025-11-01 12:58:17.437980] [reader    ]: Matching request: @99 tick();
[2025-11-01 12:58:18.437456] [timer     ]: tick(100)
[2025-11-01 12:58:18.437662] [writer    ]: Sent to enforcer: @100 tick();
[2025-11-01 12:58:18.437925] [reader    ]: Received from enforcer: {'ts': 99, 'proactive': True}
[2025-11-01 12:58:18.437950] [reader    ]: Matching request: @100 tick();
[2025-11-01 12:58:19.437660] [timer     ]: tick(101)
[2025-11-01 12:58:19.437855] [writer    ]: Sent to enforcer: @101 tick();
[2025-11-01 12:58:19.438116] [reader    ]: Received from enforcer: {'ts': 100, 'proactive': True}
[2025-11-01 12:58:19.438174] [reader    ]: Matching request: @101 tick();
[2025-11-01 12:58:20.437898] [timer     ]: tick(102)
[2025-11-01 12:58:20.438263] [writer    ]: Sent to enforcer: @102 tick();
[2025-11-01 12:58:20.438551] [reader    ]: Received from enforcer: {'ts': 101, 'proactive': True}
[2025-11-01 12:58:20.438576] [reader    ]: Matching request: @102 tick();
[2025-11-01 12:58:21.438129] [timer     ]: tick(103)
[2025-11-01 12:58:21.438411] [writer    ]: Sent to enforcer: @103 tick();
[2025-11-01 12:58:21.438618] [reader    ]: Received from enforcer: {'ts': 102, 'proactive': True}
[2025-11-01 12:58:21.438662] [reader    ]: Matching request: @103 tick();
[2025-11-01 12:58:22.438374] [timer     ]: tick(104)
[2025-11-01 12:58:22.438747] [writer    ]: Sent to enforcer: @104 tick();
[2025-11-01 12:58:22.438968] [reader    ]: Received from enforcer: {'ts': 103, 'proactive': True}
[2025-11-01 12:58:22.439015] [reader    ]: Matching request: @104 tick();
[2025-11-01 12:58:23.438589] [timer     ]: tick(105)
[2025-11-01 12:58:23.438889] [writer    ]: Sent to enforcer: @105 tick();
[2025-11-01 12:58:23.439036] [reader    ]: Received from enforcer: {'ts': 104, 'proactive': True}
[2025-11-01 12:58:23.439083] [reader    ]: Matching request: @105 tick();
[2025-11-01 12:58:24.438773] [timer     ]: tick(106)
[2025-11-01 12:58:24.439004] [writer    ]: Sent to enforcer: @106 tick();
[2025-11-01 12:58:24.439151] [reader    ]: Received from enforcer: {'ts': 105, 'proactive': True}
[2025-11-01 12:58:24.439180] [reader    ]: Matching request: @106 tick();
[2025-11-01 12:58:25.438969] [timer     ]: tick(107)
[2025-11-01 12:58:25.439254] [writer    ]: Sent to enforcer: @107 tick();
[2025-11-01 12:58:25.439622] [reader    ]: Received from enforcer: {'ts': 106, 'proactive': True}
[2025-11-01 12:58:25.439647] [reader    ]: Matching request: @107 tick();
[2025-11-01 12:58:26.439174] [timer     ]: tick(108)
[2025-11-01 12:58:26.439452] [writer    ]: Sent to enforcer: @108 tick();
[2025-11-01 12:58:26.439837] [reader    ]: Received from enforcer: {'ts': 107, 'proactive': True}
[2025-11-01 12:58:26.439878] [reader    ]: Matching request: @108 tick();
[2025-11-01 12:58:27.439399] [timer     ]: tick(109)
[2025-11-01 12:58:27.439697] [writer    ]: Sent to enforcer: @109 tick();
[2025-11-01 12:58:27.439973] [reader    ]: Received from enforcer: {'ts': 108, 'proactive': True}
[2025-11-01 12:58:27.440017] [reader    ]: Matching request: @109 tick();
[2025-11-01 12:58:28.439639] [timer     ]: tick(110)
[2025-11-01 12:58:28.439978] [writer    ]: Sent to enforcer: @110 tick();
[2025-11-01 12:58:28.440253] [reader    ]: Received from enforcer: {'ts': 109, 'proactive': True}
[2025-11-01 12:58:28.440283] [reader    ]: Matching request: @110 tick();
[2025-11-01 12:58:29.439831] [timer     ]: tick(111)
[2025-11-01 12:58:29.448357] [writer    ]: Sent to enforcer: @111 tick();
[2025-11-01 12:58:29.449709] [reader    ]: Received from enforcer: {'ts': 110, 'proactive': True}
[2025-11-01 12:58:29.449741] [reader    ]: Matching request: @111 tick();
[2025-11-01 12:58:30.440042] [timer     ]: tick(112)
[2025-11-01 12:58:30.440319] [writer    ]: Sent to enforcer: @112 tick();
[2025-11-01 12:58:30.440579] [reader    ]: Received from enforcer: {'ts': 111, 'proactive': True}
[2025-11-01 12:58:30.440602] [reader    ]: Matching request: @112 tick();
[2025-11-01 12:58:31.440233] [timer     ]: tick(113)
[2025-11-01 12:58:31.440559] [writer    ]: Sent to enforcer: @113 tick();
[2025-11-01 12:58:31.441166] [reader    ]: Received from enforcer: {'ts': 112, 'proactive': True}
[2025-11-01 12:58:31.441227] [reader    ]: Matching request: @113 tick();
[2025-11-01 12:58:32.440490] [timer     ]: tick(114)
[2025-11-01 12:58:32.440775] [writer    ]: Sent to enforcer: @114 tick();
[2025-11-01 12:58:32.441131] [reader    ]: Received from enforcer: {'ts': 113, 'proactive': True}
[2025-11-01 12:58:32.441178] [reader    ]: Matching request: @114 tick();
[2025-11-01 12:58:33.440763] [timer     ]: tick(115)
[2025-11-01 12:58:33.441075] [writer    ]: Sent to enforcer: @115 tick();
[2025-11-01 12:58:33.442301] [reader    ]: Received from enforcer: {'ts': 114, 'proactive': True}
[2025-11-01 12:58:33.442342] [reader    ]: Matching request: @115 tick();
[2025-11-01 12:58:34.441120] [timer     ]: tick(116)
[2025-11-01 12:58:34.441453] [writer    ]: Sent to enforcer: @116 tick();
[2025-11-01 12:58:34.442071] [reader    ]: Received from enforcer: {'ts': 115, 'proactive': True}
[2025-11-01 12:58:34.442117] [reader    ]: Matching request: @116 tick();
[2025-11-01 12:58:35.441350] [timer     ]: tick(117)
[2025-11-01 12:58:35.441559] [writer    ]: Sent to enforcer: @117 tick();
[2025-11-01 12:58:35.442193] [reader    ]: Received from enforcer: {'ts': 116, 'proactive': True}
[2025-11-01 12:58:35.442223] [reader    ]: Matching request: @117 tick();
[2025-11-01 12:58:36.441616] [timer     ]: tick(118)
[2025-11-01 12:58:36.441920] [writer    ]: Sent to enforcer: @118 tick();
[2025-11-01 12:58:36.442217] [reader    ]: Received from enforcer: {'ts': 117, 'proactive': True}
[2025-11-01 12:58:36.442247] [reader    ]: Matching request: @118 tick();
[2025-11-01 12:58:37.441776] [timer     ]: tick(119)
[2025-11-01 12:58:37.441984] [writer    ]: Sent to enforcer: @119 tick();
[2025-11-01 12:58:37.443190] [reader    ]: Received from enforcer: {'ts': 118, 'proactive': True}
[2025-11-01 12:58:37.443214] [reader    ]: Matching request: @119 tick();
in readdir
[DEBUG readdir] called with path=/
[INSTRUMENT] → entering MyFS.read with args=('/ahlala', 4096, 0), kwargs={}
[DEBUG] Parent process: sudo (pid=10807)
[DEBUG] Parent process: sudo (pid=10806)
[DEBUG] Parent process: bash (pid=4317)
[DEBUG] Parent process: gnome-terminal-server (pid=4306)
[DEBUG] Parent process: systemd (pid=2939)
[DEBUG] Parent process: systemd (pid=1)
[INSTRUMENT] → events = [Use("ahlala", "marketing", "anonymous")]
[2025-11-01 12:58:38.113204] [writer    ]: Sent to enforcer: @119 Use("ahlala", "marketing", "anonymous");
[2025-11-01 12:58:38.113375] [reader    ]: Received from enforcer: {'ts': 119, 'suppress': [{'name': 'Use', 'args': ['ahlala', 'marketing', 'anonymous']}]}
[2025-11-01 12:58:38.113422] [reader    ]: Matching request: @119 Use("ahlala", "marketing", "anonymous");
Calling function MyFS.read took 0 ms
[INSTRUMENT] → invoking suppression handler for MyFS.read
read file
[DEBUG] Parent process: sudo (pid=10807)
[DEBUG] Parent process: sudo (pid=10806)
[DEBUG] Parent process: bash (pid=4317)
[DEBUG] Parent process: gnome-terminal-server (pid=4306)
[DEBUG] Parent process: systemd (pid=2939)
[DEBUG] Parent process: systemd (pid=1)
opened file for reading
size: 4096
[READ] path=/ahlala reading from /var/lib/gdprfs/upper/ahlala, 4 bytes, size=4096, offset=0, returning=b'hof\n'
in _is_temp_name
[DB] Updated mapping for ahlala (context=read)
[DB] Updated metadata for ahlala (last_action=read)
max_element({('Use',)})={'Use'}
[2025-11-01 12:58:38.441948] [timer     ]: tick(120)
[2025-11-01 12:58:38.442228] [writer    ]: Sent to enforcer: @120 tick();
[2025-11-01 12:58:38.442565] [reader    ]: Received from enforcer: {'ts': 119, 'proactive': True}
[2025-11-01 12:58:38.442592] [reader    ]: Matching request: @120 tick();
[2025-11-01 12:58:39.442126] [timer     ]: tick(121)
[2025-11-01 12:58:39.442323] [writer    ]: Sent to enforcer: @121 tick();
[2025-11-01 12:58:39.442464] [reader    ]: Received from enforcer: {'ts': 120, 'proactive': True}
[2025-11-01 12:58:39.442485] [reader    ]: Matching request: @121 tick();
[2025-11-01 12:58:40.442305] [timer     ]: tick(122)
[2025-11-01 12:58:40.442586] [writer    ]: Sent to enforcer: @122 tick();
[2025-11-01 12:58:40.443350] [reader    ]: Received from enforcer: {'ts': 121, 'proactive': True}
[2025-11-01 12:58:40.443404] [reader    ]: Matching request: @122 tick();
[2025-11-01 12:58:41.442506] [timer     ]: tick(123)
[2025-11-01 12:58:41.442759] [writer    ]: Sent to enforcer: @123 tick();
[2025-11-01 12:58:41.443180] [reader    ]: Received from enforcer: {'ts': 122, 'proactive': True}
[2025-11-01 12:58:41.443241] [reader    ]: Matching request: @123 tick();
[2025-11-01 12:58:42.442676] [timer     ]: tick(124)
[2025-11-01 12:58:42.442904] [writer    ]: Sent to enforcer: @124 tick();
[2025-11-01 12:58:42.443052] [reader    ]: Received from enforcer: {'ts': 123, 'proactive': True}
[2025-11-01 12:58:42.443075] [reader    ]: Matching request: @124 tick();
[2025-11-01 12:58:43.442966] [timer     ]: tick(125)
[2025-11-01 12:58:43.443308] [writer    ]: Sent to enforcer: @125 tick();
[2025-11-01 12:58:43.443707] [reader    ]: Received from enforcer: {'ts': 124, 'proactive': True}
[2025-11-01 12:58:43.443761] [reader    ]: Matching request: @125 tick();
[2025-11-01 12:58:44.443152] [timer     ]: tick(126)
[2025-11-01 12:58:44.443439] [writer    ]: Sent to enforcer: @126 tick();
[2025-11-01 12:58:44.443693] [reader    ]: Received from enforcer: {'ts': 125, 'proactive': True}
[2025-11-01 12:58:44.443723] [reader    ]: Matching request: @126 tick();
[2025-11-01 12:58:45.443377] [timer     ]: tick(127)
[2025-11-01 12:58:45.443666] [writer    ]: Sent to enforcer: @127 tick();
[2025-11-01 12:58:45.443966] [reader    ]: Received from enforcer: {'ts': 126, 'proactive': True}
[2025-11-01 12:58:45.443993] [reader    ]: Matching request: @127 tick();
[2025-11-01 12:58:46.443724] [timer     ]: tick(128)
[2025-11-01 12:58:46.444036] [writer    ]: Sent to enforcer: @128 tick();
[2025-11-01 12:58:46.444428] [reader    ]: Received from enforcer: {'ts': 127, 'proactive': True}
[2025-11-01 12:58:46.444494] [reader    ]: Matching request: @128 tick();
[UNLINK] path=/ahlala → removed from upper and mirror
[DB] Marked ahlala as deleted at 2025-11-01 12:58:47
[2025-11-01 12:58:47.443898] [timer     ]: tick(129)
[2025-11-01 12:58:47.444062] [writer    ]: Sent to enforcer: @129 tick();
[2025-11-01 12:58:47.444214] [reader    ]: Received from enforcer: {'ts': 128, 'proactive': True}
[2025-11-01 12:58:47.444234] [reader    ]: Matching request: @129 tick();
[2025-11-01 12:58:48.444217] [timer     ]: tick(130)
[2025-11-01 12:58:48.444537] [writer    ]: Sent to enforcer: @130 tick();
[2025-11-01 12:58:48.444942] [reader    ]: Received from enforcer: {'ts': 129, 'proactive': True}
[2025-11-01 12:58:48.444997] [reader    ]: Matching request: @130 tick();
```