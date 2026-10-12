"""The key that signs Jobwatch updates.

Only releases signed with the matching private key (the JOBWATCH_UPDATE_KEY
secret in CI, never in this repository) are installed. Test builds replace
this file (tools/build_windows.py --update-key-file) and may also point the
updater at a local feed; release builds never can.
"""

PUBLIC_KEY = "O6di/XnhDaW7z7RW5ZnpmtNS3dJNT5bcUTS78fkfHqQ="
ALLOW_FEED_OVERRIDE = False
