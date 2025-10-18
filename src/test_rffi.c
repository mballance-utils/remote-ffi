#include "include/rffi.h"
#include <stdio.h>

int main() {
    rffi_t ctx;
    if (rffi_ep_init_target(&ctx) != 0) {
        printf("Failed to initialize rffi context\n");
        return 1;
    }

    // Example: open the current process as a library (platform-specific)
#if defined(_WIN32)
    const char *libname = "kernel32.dll";
    const char *symname = "GetCurrentProcessId";
#else
    const char *libname = "libc.so.6";
    const char *symname = "getpid";
#endif

    void *lib = rffi_ep_dlopen(&ctx, libname);
    if (!lib) {
        printf("Failed to open library: %s\n", libname);
        return 2;
    }

    void *sym = rffi_ep_dlsym(&ctx, lib, symname);
    if (!sym) {
        printf("Failed to find symbol: %s\n", symname);
        return 3;
    }

    printf("Successfully loaded symbol %s from %s\n", symname, libname);
    return 0;
}
