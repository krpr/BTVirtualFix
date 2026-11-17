#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ "$(uname -s)" != "Darwin" ]]; then
  echo 'The kernel extension requires macOS and Xcode. Synthetic guard tests also run on Linux.' >&2
  exit 1
fi
mkdir -p logs
python3 scripts/bootstrap.py --check-only
python3 prepare_reference.py "$@" > logs/reference-preflight.json
if ! xcodebuild -project BTVirtualFix.xcodeproj -target BTVirtualFix \
  -configuration Release -jobs 2 CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO \
  > logs/build-release.log 2>&1; then
  tail -n 60 logs/build-release.log >&2
  exit 1
fi
python3 scripts/test_guards.py --generated | tee logs/page-guard-tests.txt
xcrun nm -u build/Release/BTVirtualFix.kext/Contents/MacOS/BTVirtualFix \
  > logs/undefined-imports.txt
python3 make_manifest.py
