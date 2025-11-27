#!/bin/bash
# run_all.sh
# Purpose: launch external consent platform, internal purpose platform, and FUSE daemon.

set -e

# --- Define base paths ---
BASE=~/MA3/Building_a_GDPR-compliant_file_system/instrlib
VENV=~/gdprfs-venv

# --- Step 1: External Consent Platform (port 5000) ---
gnome-terminal -- bash -c "
cd $BASE/external_consent_platform;
source $VENV/bin/activate;
python app.py;
exec bash
"

# --- Step 2: Internal Purpose Platform (port 8000) ---
gnome-terminal -- bash -c "
cd $BASE/internal_purpose_platform;
source $VENV/bin/activate;
python app.py;
exec bash
"

# --- Step 3: LLM Analyzer (port 5005) ---
gnome-terminal -- bash -c "
cd $BASE/LLManalyzer;
source $VENV/bin/activate;
python api.py;
exec bash
"

# --- Step 4: FUSE daemon (requires root privileges) ---
gnome-terminal -- bash -c "
cd $BASE;
source $VENV/bin/activate;
./reset_myfs_sudo.sh;
exec bash
"
