
#ifndef INCLUDED_RFFI_H
#define INCLUDED_RFFI_H
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct rffi_s rffi_t;
typedef enum {
    RFFI_PARAM_INT,
    RFFI_PARAM_UINT,
    RFFI_PARAM_FLOAT,
    RFFI_PARAM_PTR
} rffi_param_type_e;

typedef struct rffi_param_s {
    rffi_param_type_e type;
    union {
        int64_t ival;
        uint64_t uval;
        double fval;
        void *ptr;
    } v;
} rffi_param_t;
typedef struct rffi_call_s rffi_call_t;


rffi_t *rffi_create(void);
void rffi_destroy(rffi_t *rffi);

int rffi_ep_init_target(rffi_t *rffi);

void *rffi_ep_dlsym(rffi_t *rffi, void *lib, const char *sym);

void *rffi_ep_dlopen(rffi_t *rffi, const char *lib);

uintptr_t rffi_ep_call(rffi_t *rffi, rffi_param_t *params, int32_t nparams);



#ifdef __cplusplus
}
#endif
#endif /* INCLUDED_RFFI_H */
