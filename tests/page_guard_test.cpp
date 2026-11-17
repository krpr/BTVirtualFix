#include <cassert>
#include <cstdio>
#include <cstring>
#include <array>
#include "../Sources/PageGuard.hpp"

using BTVirtualGuard::patchPage;
using BTVirtualReferences::PageReference;
using BTVirtualReferences::kPageSize;
static unsigned tests = 0;

static void denied(const PageReference &ref, const char *path, bool enabled, bool os,
                   bool validated, bool tainted, bool nx, uint64_t offset, size_t size) {
    std::array<uint8_t,kPageSize> page;
    std::memcpy(page.data(), ref.original, page.size());
    const auto before = page;
    assert(patchPage(page.data(),size,offset,path,enabled,os,validated,tainted,nx) != BTVirtualGuard::Applied);
    assert(page == before);
    ++tests;
}

int main() {
    constexpr const char *path = "/usr/sbin/bluetoothd";
    size_t totalChanged = 0;
    for (const auto &ref : BTVirtualReferences::kPages) {
        std::array<uint8_t,kPageSize+2> fenced;
        fenced.front()=0xA5; fenced.back()=0x5A;
        std::memcpy(fenced.data()+1,ref.original,kPageSize);
        assert(patchPage(fenced.data()+1,kPageSize,ref.fatOffset,path,true,true,true,false,false)==BTVirtualGuard::Applied);
        size_t changed=0;
        for(size_t i=0;i<kPageSize;++i) {
            uint8_t expected = ref.original[i];
            if (i>=ref.signatureOffset && i<ref.signatureOffset+ref.signatureSize)
                expected = ref.replacement[i-ref.signatureOffset];
            assert(fenced[i+1] == expected);
            changed += fenced[i+1] != ref.original[i];
        }
        assert(changed==ref.changedBytes && fenced.front()==0xA5 && fenced.back()==0x5A);
        totalChanged += changed; ++tests;
        assert(std::memcmp(fenced.data()+1+ref.signatureOffset,ref.replacement,ref.signatureSize)==0); ++tests;
        const auto already=fenced;
        assert(patchPage(fenced.data()+1,kPageSize,ref.fatOffset,path,true,true,true,false,false)==BTVirtualGuard::WrongPage);
        assert(fenced==already); ++tests;
        denied(ref,path,false,true,true,false,false,ref.fatOffset,kPageSize);
        denied(ref,path,true,false,true,false,false,ref.fatOffset,kPageSize);
        denied(ref,path,true,true,false,false,false,ref.fatOffset,kPageSize);
        denied(ref,path,true,true,true,true,false,ref.fatOffset,kPageSize);
        denied(ref,path,true,true,true,false,true,ref.fatOffset,kPageSize);
        denied(ref,nullptr,true,true,true,false,false,ref.fatOffset,kPageSize);
        denied(ref,"",true,true,true,false,false,ref.fatOffset,kPageSize);
        denied(ref,"/usr/sbin/BlueTool",true,true,true,false,false,ref.fatOffset,kPageSize);
        denied(ref,"/usr/sbin/bluetoothd.extra",true,true,true,false,false,ref.fatOffset,kPageSize);
        denied(ref,"/tmp/bluetoothd",true,true,true,false,false,ref.fatOffset,kPageSize);
        denied(ref,path,true,true,true,false,false,ref.thinOffset,kPageSize);
        denied(ref,path,true,true,true,false,false,ref.fatOffset+kPageSize,kPageSize);
        denied(ref,path,true,true,true,false,false,ref.fatOffset,kPageSize-1);
        denied(ref,path,true,true,true,false,false,ref.fatOffset,kPageSize+1);
        std::array<uint8_t,kPageSize> altered;
        std::memcpy(altered.data(),ref.original,kPageSize); altered[0]^=1;
        auto before=altered;
        assert(patchPage(altered.data(),kPageSize,ref.fatOffset,path,true,true,true,false,false)==BTVirtualGuard::WrongPage);
        assert(altered==before); ++tests;
        std::memcpy(altered.data(),ref.original,kPageSize);
        std::memcpy(altered.data(),ref.find,ref.signatureSize); before=altered;
        assert(patchPage(altered.data(),kPageSize,ref.fatOffset,path,true,true,true,false,false)==BTVirtualGuard::WrongPage);
        assert(altered==before); ++tests;
        assert(patchPage(nullptr,kPageSize,ref.fatOffset,path,true,true,true,false,false)==BTVirtualGuard::NotTarget); ++tests;
        // A valid reference page at the other reviewed page's offset must fail closed.
        for (const auto &other : BTVirtualReferences::kPages)
            if (&other != &ref)
                denied(ref,path,true,true,true,false,false,other.fatOffset,kPageSize);
    }
    assert(totalChanged == 7); ++tests;
    const auto &uhe = BTVirtualReferences::kPages[1];
    assert(uhe.fatOffset==0x148000 && uhe.thinOffset==0x144000 && uhe.signatureOffset==0x2F5);
    assert(uhe.find[10]==0x72 && uhe.replacement[10]==0x76 && uhe.find[11]==uhe.replacement[11]); ++tests;
    std::printf("PASS: %u page guard and exact-change assertions for 2 pages / 7 bytes (ASan/UBSan build)\n",tests);
}
