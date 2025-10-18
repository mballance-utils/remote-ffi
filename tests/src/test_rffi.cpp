#include <gtest/gtest.h>
#include "rffi.h"

TEST(RffiTest, LoadLibraryAndSymbol) {
    rffi_t *ctx = rffi_create();
    ASSERT_NE(ctx, nullptr);
    ASSERT_EQ(rffi_ep_init_target(ctx), 0);

#if defined(_WIN32)
    const char *libname = "kernel32.dll";
    const char *symname = "GetCurrentProcessId";
#else
    const char *libname = "libc.so.6";
    const char *symname = "getpid";
#endif

    void *lib = rffi_ep_dlopen(ctx, libname);
    ASSERT_NE(lib, nullptr) << "Failed to open library: " << libname;

    void *sym = rffi_ep_dlsym(ctx, lib, symname);
    ASSERT_NE(sym, nullptr) << "Failed to find symbol: " << symname;

    rffi_destroy(ctx);
}

TEST(RffiTest, CallFunction) {
    rffi_t *ctx = rffi_create();
    ASSERT_NE(ctx, nullptr);
    ASSERT_EQ(rffi_ep_init_target(ctx), 0);

#if defined(_WIN32)
    const char *libname = "kernel32.dll";
    const char *symname = "GetCurrentProcessId";
#else
    const char *libname = "libc.so.6";
    const char *symname = "getpid";
#endif

    void *lib = rffi_ep_dlopen(ctx, libname);
    ASSERT_NE(lib, nullptr) << "Failed to open library: " << libname;

    void *sym = rffi_ep_dlsym(ctx, lib, symname);
    ASSERT_NE(sym, nullptr) << "Failed to find symbol: " << symname;

    rffi_param_t params[1];
    params[0].type = RFFI_PARAM_PTR;
    params[0].v.ptr = sym;

    uintptr_t result = rffi_ep_call(ctx, params, 1);
    ASSERT_NE(result, 0u) << "rffi_ep_call returned 0";

    rffi_destroy(ctx);
}
