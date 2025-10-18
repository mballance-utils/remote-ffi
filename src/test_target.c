#include <stdio.h>

#ifdef __cplusplus
extern "C" {
#endif

int test_add(int a, int b) {
    return a + b;
}

#ifdef __cplusplus
}
#endif

int main(int argc, char **argv) {
    printf("test_target ready\\n");
    fflush(stdout);
    while (1) {
        // Keep process alive for remote FFI
        sleep(1);
    }
    return 0;
}
