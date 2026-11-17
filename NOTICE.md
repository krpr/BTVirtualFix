# Notices and acknowledgements

The [BSD 3-Clause license](LICENSE) covers this project's original code,
scripts, and documentation. It does not relicense third-party components,
Apple system binaries, or data generated from those binaries.

## Build dependencies

- **Lilu**, by vit9696 and contributors: the plugin uses Lilu's interfaces and
  compiles its `plugin_start.cpp`. Lilu's BSD 3-Clause notice is preserved in
  [licenses/Lilu.txt](licenses/Lilu.txt). Source:
  <https://github.com/acidanthera/Lilu>.
- **MacKernelSDK**, maintained by Acidanthera: the build uses its kernel headers
  and `libkmod` library. Its top-level Apple Public Source License 2.0 is
  preserved in [licenses/MacKernelSDK.txt](licenses/MacKernelSDK.txt). Individual
  files retain their own notices; the top-level license is not a declaration
  that every SDK file has identical terms. Source:
  <https://github.com/acidanthera/MacKernelSDK>.

The dependency revisions are pinned by the build tooling. Their source trees
are fetched locally and are not vendored in this repository.

## Related work

The post-validation Lilu hook mechanism was informed by **BlueToolFixup** in
Acidanthera's **BrcmPatchRAM**, including work by Dhinak G and other
contributors. BrcmPatchRAM is distributed under GPL version 2; its source and
license remain at <https://github.com/acidanthera/BrcmPatchRAM>. This repository
does not vendor BlueToolFixup or claim its license is BSD.

**OpenCore** supplies the boot configuration used in the documented deployment.
**VMHide** is an optional existing component whose `bluetoothd` process filter
must be considered when enabling the native virtual transport. Neither product
is included in this repository. The Xcode project here is generated from this
project's own minimal build description in `scripts/generate_xcode_project.py`.

## Locally generated reference data

`Sources/ReferencePage.hpp` is generated from a user-supplied, exact-build
`bluetoothd` binary. It contains two complete original code pages used for
strict runtime matching. The binary, generated reference header, and compiled
kext containing those pages are excluded from this source repository. The
project license grants no rights to redistribute Apple code.

Apple, macOS, Bluetooth, and other product names belong to their respective
owners. This is an independent experimental project and is not endorsed by
Apple, Acidanthera, or the authors of the related projects.
