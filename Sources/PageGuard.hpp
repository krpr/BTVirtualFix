#pragma once
#include <stdint.h>
#include <stddef.h>
#include "ReferencePage.hpp"

// Shared by the kernel wrapper and the offline guard tests.
namespace BTVirtualGuard {
enum Result { NotTarget, InvalidSignatureState, WrongPage, NotUnique, Applied };

static const BTVirtualReferences::PageReference *referenceForOffset(uint64_t fileOffset) {
    for (const auto &reference : BTVirtualReferences::kPages)
        if (fileOffset == reference.fatOffset) return &reference;
    return nullptr;
}

static bool bytesEqual(const uint8_t *a, const uint8_t *b, size_t n) {
    for (size_t i = 0; i < n; ++i)
        if (a[i] != b[i]) return false;
    return true;
}

static bool exactPath(const char *path) {
    static const char expected[] = "/usr/sbin/bluetoothd";
    if (!path) return false;
    for (size_t i = 0; i < sizeof(expected); ++i) {
        if (path[i] != expected[i]) return false;
        if (expected[i] == '\0') return true;
    }
    return false;
}

static Result patchPage(uint8_t *page, size_t size, uint64_t fileOffset,
                        const char *path, bool enabled, bool exactDarwin,
                        bool validated, bool tainted, bool nonExecutable) {
    const auto *reference = referenceForOffset(fileOffset);
    if (!enabled || !exactDarwin || !page || size != BTVirtualReferences::kPageSize ||
        !exactPath(path) || !reference)
        return NotTarget;
    if (!validated || tainted || nonExecutable) return InvalidSignatureState;
    if (!bytesEqual(page, reference->original, size)) return WrongPage;
    size_t matches = 0;
    size_t found = 0;
    for (size_t i = 0; i + reference->signatureSize <= size; ++i) {
        if (bytesEqual(page+i, reference->find, reference->signatureSize)) {
            ++matches;
            found = i;
        }
    }
    if (matches != 1 || found != reference->signatureOffset) return NotUnique;
    // Touch only the reviewed differing bytes, preserving all surrounding code.
    for (size_t i = 0; i < reference->signatureSize; ++i)
        if (reference->find[i] != reference->replacement[i])
            page[found+i] = reference->replacement[i];
    return Applied;
}
}
