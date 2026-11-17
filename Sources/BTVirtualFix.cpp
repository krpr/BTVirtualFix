// Experimental, explicit opt-in, macOS 15.4.1-only Lilu plugin.
// Uses the post-validation memory-page route employed by official BlueToolFixup.
#include <Headers/plugin_start.hpp>
#include <Headers/kern_api.hpp>
#include <Headers/kern_user.hpp>
#include <Headers/kern_util.hpp>
#include "PageGuard.hpp"

// Match Lilu's declarations of version_major/version_minor without importing
// libkern/version.h, whose C-linkage block conflicts with those C++ declarations.
extern const int version_revision;

static constexpr const char *kModule = "btvirt";
static mach_vm_address_t originalValidatePage = 0;
static bool enabled = false;

static bool exactDarwin() {
    return version_major == 24 && version_minor == 4 && version_revision == 0;
}

static void validatePage(vnode_t vp, memory_object_t pager,
                         memory_object_offset_t pageOffset, const void *data,
                         int *validated, int *tainted, int *nonExecutable) {
    FunctionCast(validatePage, originalValidatePage)(vp, pager, pageOffset, data,
                                                   validated, tainted, nonExecutable);
    if (!enabled || !exactDarwin() || !data || !validated || !tainted || !nonExecutable)
        return;
    // Cheap offset gate before resolving a path; never inspect unrelated pages.
    const auto *reference = BTVirtualGuard::referenceForOffset(pageOffset);
    if (!reference)
        return;
    char path[PATH_MAX] = {};
    int pathLength = sizeof(path);
    if (vn_getpath(vp, path, &pathLength) != 0 || !BTVirtualGuard::exactPath(path))
        return;
    const auto result = BTVirtualGuard::patchPage(
        static_cast<uint8_t *>(const_cast<void *>(data)), PAGE_SIZE, pageOffset,
        path, enabled, exactDarwin(), *validated != 0, *tainted != 0, *nonExecutable != 0);
    if (result == BTVirtualGuard::Applied) {
        SYSLOG(kModule, "applied %s to bluetoothd page 0x%llX; %u bytes", reference->label,
               static_cast<unsigned long long>(pageOffset), static_cast<unsigned>(reference->changedBytes));
    } else {
        SYSLOG(kModule, "refused bluetoothd page 0x%llX: guard %u (validation %d, taint %d, nx %d)",
               static_cast<unsigned long long>(pageOffset), static_cast<unsigned>(result),
               *validated, *tainted, *nonExecutable);
    }
    // Do not modify the original code-signature validation result or SIP state.
}

static void pluginStart() {
    if (!checkKernelArgument("-btvirtfix")) {
        SYSLOG(kModule, "inactive: explicit -btvirtfix argument is absent");
        return;
    }
    if (!exactDarwin()) {
        SYSLOG(kModule, "inactive: requires Darwin 24.4.0, found %d.%d.%d",
               version_major, version_minor, version_revision);
        return;
    }
    const auto error = lilu.onPatcherLoad([](void *, KernelPatcher &patcher) {
        KernelPatcher::RouteRequest route("_cs_validate_page", validatePage, originalValidatePage);
        if (!patcher.routeMultipleLong(KernelPatcher::KernelID, &route, 1)) {
            SYSLOG(kModule, "route failed; no Bluetooth page modifications will be attempted");
            patcher.clearError();
            return;
        }
        enabled = true;
        SYSLOG(kModule, "armed for hash-reviewed bluetoothd 24E263; full-page and unique-pattern guards required");
    });
    if (error != LiluAPI::Error::NoError)
        SYSLOG(kModule, "callback registration failed: %u", static_cast<unsigned>(error));
}

static const char *bootargOff[] = { "-btvirtfixoff" };
static const char *bootargDebug[] = { "-btvirtfixdbg" };

PluginConfiguration ADDPR(config) {
    xStringify(PRODUCT_NAME), parseModuleVersion(xStringify(MODULE_VERSION)),
    LiluAPI::AllowNormal,
    bootargOff, arrsize(bootargOff), bootargDebug, arrsize(bootargDebug),
    nullptr, 0,
    KernelVersion::Sequoia, KernelVersion::Sequoia,
    pluginStart
};
