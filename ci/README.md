# GitHub Actions template

`source-checks.yml` runs Python prerequisite/generator tests, verifies checks remain effective under `python -O`, and runs 44 ASan/UBSan page-guard assertions using synthetic references. It needs no Apple binary and does not build or publish a kext.

The template is not an active workflow at this location. To enable it, move the file to `.github/workflows/ci.yml` and commit that change using GitHub credentials authorized to modify workflows. Its default token permissions are read-only.

The equivalent checks passed locally from a clean source export. GitHub-hosted execution has not yet been verified.
