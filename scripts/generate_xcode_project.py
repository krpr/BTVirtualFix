#!/usr/bin/env python3
"""Generate this project's minimal Xcode kext target from its build inputs."""
from __future__ import annotations

import hashlib
import plistlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def object_id(label: str) -> str:
    # Identifiers are deterministic names, not security or content checksums.
    return hashlib.sha256(("BTVirtualFix/project/" + label).encode()).hexdigest()[:24].upper()


def project() -> dict:
    objects = {}

    def add(label: str, kind: str, **fields) -> str:
        key = object_id(label)
        objects[key] = {"isa": kind, **fields}
        return key

    cpp = add("plugin-source", "PBXFileReference", path="Sources/BTVirtualFix.cpp",
              lastKnownFileType="sourcecode.cpp.cpp", sourceTree="<group>")
    guard = add("page-guard", "PBXFileReference", path="Sources/PageGuard.hpp",
                lastKnownFileType="sourcecode.cpp.h", sourceTree="<group>")
    info = add("bundle-info", "PBXFileReference", path="Sources/Info.plist",
               lastKnownFileType="text.plist.xml", sourceTree="<group>")
    startup = add("lilu-startup", "PBXFileReference",
                  path="deps/Lilu/Lilu/Library/plugin_start.cpp",
                  lastKnownFileType="sourcecode.cpp.cpp", sourceTree="<group>")
    kmod = add("kernel-module-library", "PBXFileReference",
               path="deps/MacKernelSDK/Library/x86_64/libkmod.a",
               lastKnownFileType="archive.ar", sourceTree="<group>")
    product = add("kext-product", "PBXFileReference", path="BTVirtualFix.kext",
                  explicitFileType="wrapper.cfbundle", includeInIndex=0,
                  sourceTree="BUILT_PRODUCTS_DIR")
    source_files = [add("compile-plugin", "PBXBuildFile", fileRef=cpp),
                    add("compile-lilu-startup", "PBXBuildFile", fileRef=startup)]
    library_files = [add("link-kmod", "PBXBuildFile", fileRef=kmod)]
    sources = add("compile-phase", "PBXSourcesBuildPhase", buildActionMask=2147483647,
                  files=source_files, runOnlyForDeploymentPostprocessing=0)
    libraries = add("link-phase", "PBXFrameworksBuildPhase", buildActionMask=2147483647,
                    files=library_files, runOnlyForDeploymentPostprocessing=0)
    products = add("product-group", "PBXGroup", name="Products", children=[product],
                   sourceTree="<group>")
    main = add("main-group", "PBXGroup", children=[cpp, guard, info, startup, kmod, products],
               sourceTree="<group>")

    version = plistlib.loads((ROOT / "Sources/Info.plist").read_bytes())["CFBundleVersion"]
    project_configs = []
    target_configs = []
    for name in ("Debug", "Release"):
        project_configs.append(add("project-" + name, "XCBuildConfiguration", name=name,
                                   buildSettings={"SDKROOT": "macosx"}))
        settings = {
            "ARCHS": "x86_64",
            "ONLY_ACTIVE_ARCH": "NO",
            "MACOSX_DEPLOYMENT_TARGET": "15.4",
            "CLANG_CXX_LANGUAGE_STANDARD": "c++14",
            "CLANG_ENABLE_MODULES": "NO",
            "GCC_ENABLE_CPP_EXCEPTIONS": "NO",
            "GCC_ENABLE_CPP_RTTI": "NO",
            "GCC_C_LANGUAGE_STANDARD": "gnu11",
            "GCC_OPTIMIZATION_LEVEL": "0" if name == "Debug" else "s",
            "GCC_PREPROCESSOR_DEFINITIONS": ["PRODUCT_NAME=BTVirtualFix", "MODULE_VERSION=" + version],
            "HEADER_SEARCH_PATHS": ["$(PROJECT_DIR)/deps/Lilu/Lilu"],
            "KERNEL_EXTENSION_HEADER_SEARCH_PATHS": "$(PROJECT_DIR)/deps/MacKernelSDK/Headers",
            "KERNEL_FRAMEWORK_HEADERS": "$(PROJECT_DIR)/deps/MacKernelSDK/Headers",
            "LIBRARY_SEARCH_PATHS": ["$(PROJECT_DIR)/deps/MacKernelSDK/Library/x86_64"],
            "PRODUCT_NAME": "BTVirtualFix",
            "PRODUCT_BUNDLE_IDENTIFIER": "org.lotten.BTVirtualFix",
            "MODULE_NAME": "org.lotten.BTVirtualFix",
            "MODULE_VERSION": version,
            "MODULE_START": "BTVirtualFix_kern_start",
            "MODULE_STOP": "BTVirtualFix_kern_stop",
            "CURRENT_PROJECT_VERSION": version,
            "MARKETING_VERSION": version,
            "INFOPLIST_FILE": "Sources/Info.plist",
            "WRAPPER_EXTENSION": "kext",
            "CODE_SIGNING_ALLOWED": "NO",
            "CODE_SIGNING_REQUIRED": "NO",
            "CODE_SIGN_IDENTITY": "",
            "COPY_PHASE_STRIP": "NO",
            "DEBUG_INFORMATION_FORMAT": "dwarf" if name == "Debug" else "dwarf-with-dsym",
        }
        if name == "Debug":
            settings["GCC_PREPROCESSOR_DEFINITIONS"].append("DEBUG=1")
        target_configs.append(add("target-" + name, "XCBuildConfiguration", name=name,
                                  buildSettings=settings))
    project_config_list = add("project-configurations", "XCConfigurationList",
                              buildConfigurations=project_configs,
                              defaultConfigurationIsVisible=0, defaultConfigurationName="Release")
    target_config_list = add("target-configurations", "XCConfigurationList",
                             buildConfigurations=target_configs,
                             defaultConfigurationIsVisible=0, defaultConfigurationName="Release")
    target = add("kext-target", "PBXNativeTarget", name="BTVirtualFix",
                 productName="BTVirtualFix", productType="com.apple.product-type.kernel-extension",
                 productReference=product, buildConfigurationList=target_config_list,
                 buildPhases=[sources, libraries], buildRules=[], dependencies=[])
    root = add("project", "PBXProject", compatibilityVersion="Xcode 9.3",
               buildConfigurationList=project_config_list, developmentRegion="en",
               knownRegions=["en"], mainGroup=main, productRefGroup=products,
               projectDirPath="", projectRoot="", targets=[target])
    document = {"archiveVersion": 1, "classes": {}, "objectVersion": 50,
                "objects": objects, "rootObject": root}

    def xcode_scalars(value):
        # The pbxproj property-list dialect represents its numeric fields as
        # strings, even when written in XML rather than OpenStep syntax.
        if isinstance(value, dict):
            return {key: xcode_scalars(item) for key, item in value.items()}
        if isinstance(value, list):
            return [xcode_scalars(item) for item in value]
        return str(value) if isinstance(value, int) else value

    return xcode_scalars(document)


if __name__ == "__main__":
    destination = ROOT / "BTVirtualFix.xcodeproj/project.pbxproj"
    destination.parent.mkdir(exist_ok=True)
    destination.write_bytes(plistlib.dumps(project(), sort_keys=False))
    print("Generated BTVirtualFix.xcodeproj/project.pbxproj")
