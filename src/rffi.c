#include "include/rffi.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#if defined(_WIN32)
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <winsock2.h>
#include <ws2tcpip.h>
#else
#include <dlfcn.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <unistd.h>
#include <netdb.h>
#endif

#if defined(_WIN32)
#include <windows.h>
#endif

struct rffi_s {
#if defined(_WIN32)
    SOCKET sock;
#else
    int sock;
#endif
};

rffi_t *rffi_create(void) {
    rffi_t *rffi = (rffi_t *)malloc(sizeof(rffi_t));
    if (rffi) {
#if defined(_WIN32)
        rffi->sock = INVALID_SOCKET;
#else
        rffi->sock = -1;
#endif
    }
    return rffi;
}

void rffi_destroy(rffi_t *rffi) {
    if (rffi) {
#if defined(_WIN32)
        if (rffi->sock != INVALID_SOCKET) {
            closesocket(rffi->sock);
            WSACleanup();
        }
#else
        if (rffi->sock >= 0) {
            close(rffi->sock);
        }
#endif
        free(rffi);
    }
}

#include "cJSON.h"

/* rffi_param_s and enum now defined in rffi.h */

struct rffi_call_s {
    // Placeholder for call context
    int dummy;
};


int rffi_ep_init_target(rffi_t *rffi) {
    const char *env = getenv("REMOTE_FFI_HOST");
    if (!env) {
        fprintf(stderr, "REMOTE_FFI_HOST not set\n");
        return -1;
    }

    // Parse host:port
    char host[256];
    char port[16];
    const char *colon = strchr(env, ':');
    if (!colon || colon == env || strlen(colon+1) == 0) {
        fprintf(stderr, "REMOTE_FFI_HOST must be host:port\n");
        return -2;
    }
    size_t hostlen = colon - env;
    if (hostlen >= sizeof(host) || strlen(colon+1) >= sizeof(port)) {
        fprintf(stderr, "REMOTE_FFI_HOST value too long\n");
        return -3;
    }
    strncpy(host, env, hostlen);
    host[hostlen] = '\0';
    strncpy(port, colon+1, sizeof(port)-1);
    port[sizeof(port)-1] = '\0';

    // Next: socket connection (cross-platform)
    int sock = -1;
#if defined(_WIN32)
    WSADATA wsaData;
    if (WSAStartup(MAKEWORD(2,2), &wsaData) != 0) {
        fprintf(stderr, "WSAStartup failed\n");
        return -4;
    }
#endif

    struct addrinfo hints, *res = NULL;
    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;

    int err = getaddrinfo(host, port, &hints, &res);
    if (err != 0 || !res) {
        fprintf(stderr, "getaddrinfo failed: %s\n",
#if defined(_WIN32)
            gai_strerrorA(err)
#else
            gai_strerror(err)
#endif
        );
#if defined(_WIN32)
        WSACleanup();
#endif
        return -5;
    }

    sock = (int)socket(res->ai_family, res->ai_socktype, res->ai_protocol);
#if defined(_WIN32)
    if (sock == INVALID_SOCKET) {
        fprintf(stderr, "socket() failed\n");
        freeaddrinfo(res);
        WSACleanup();
        return -6;
    }
#else
    if (sock < 0) {
        fprintf(stderr, "socket() failed\n");
        freeaddrinfo(res);
        return -6;
    }
#endif

    if (
#if defined(_WIN32)
        connect(sock, res->ai_addr, (int)res->ai_addrlen)
#else
        connect(sock, res->ai_addr, res->ai_addrlen)
#endif
        != 0) {
        fprintf(stderr, "connect() failed\n");
#if defined(_WIN32)
        closesocket(sock);
        WSACleanup();
#else
        close(sock);
#endif
        freeaddrinfo(res);
        return -7;
    }
    freeaddrinfo(res);

    // Store sock in rffi_t struct for later use
#if defined(_WIN32)
    rffi->sock = sock;
#else
    rffi->sock = sock;
#endif

    // Length-prefixed JSON hello exchange
    // 1. Read 4 bytes (big-endian length)
    uint8_t lenbuf[4];
    ssize_t nread = 0, total = 0;
    while (total < 4) {
#if defined(_WIN32)
        nread = recv(sock, (char*)lenbuf + total, 4 - total, 0);
#else
        nread = recv(sock, lenbuf + total, 4 - total, 0);
#endif
        if (nread <= 0) {
            fprintf(stderr, "Failed to read hello length\n");
#if defined(_WIN32)
            closesocket(sock);
            WSACleanup();
#else
            close(sock);
#endif
            return -8;
        }
        total += nread;
    }
    uint32_t msglen = (lenbuf[0]<<24) | (lenbuf[1]<<16) | (lenbuf[2]<<8) | lenbuf[3];
    if (msglen == 0 || msglen > 4096) {
        fprintf(stderr, "Invalid hello message length: %u\n", msglen);
#if defined(_WIN32)
        closesocket(sock);
        WSACleanup();
#else
        close(sock);
#endif
        return -9;
    }
    char msgbuf[4097];
    total = 0;
    while (total < (ssize_t)msglen) {
#if defined(_WIN32)
        nread = recv(sock, msgbuf + total, msglen - total, 0);
#else
        nread = recv(sock, msgbuf + total, msglen - total, 0);
#endif
        if (nread <= 0) {
            fprintf(stderr, "Failed to read hello message\n");
#if defined(_WIN32)
            closesocket(sock);
            WSACleanup();
#else
            close(sock);
#endif
            return -10;
        }
        total += nread;
    }
    msgbuf[msglen] = 0;

    // Simple check for "type":"hello"
    if (strstr(msgbuf, "\"type\":\"hello\"") == NULL) {
        fprintf(stderr, "Did not receive hello message\n");
#if defined(_WIN32)
        closesocket(sock);
        WSACleanup();
#else
        close(sock);
#endif
        return -11;
    }

    // 2. Send our hello message
    const char *hello = "{\"type\":\"hello\",\"lang\":\"c\"}";
    uint32_t hlen = (uint32_t)strlen(hello);
    uint8_t hlenbuf[4] = {
        (uint8_t)((hlen >> 24) & 0xFF),
        (uint8_t)((hlen >> 16) & 0xFF),
        (uint8_t)((hlen >> 8) & 0xFF),
        (uint8_t)(hlen & 0xFF)
    };
    ssize_t nsent = 0;
#if defined(_WIN32)
    nsent = send(sock, (const char*)hlenbuf, 4, 0);
#else
    nsent = send(sock, hlenbuf, 4, 0);
#endif
    if (nsent != 4) {
        fprintf(stderr, "Failed to send hello length\n");
#if defined(_WIN32)
        closesocket(sock);
        WSACleanup();
#else
        close(sock);
#endif
        return -12;
    }
#if defined(_WIN32)
    nsent = send(sock, hello, hlen, 0);
#else
    nsent = send(sock, hello, hlen, 0);
#endif
    if (nsent != (ssize_t)hlen) {
        fprintf(stderr, "Failed to send hello message\n");
#if defined(_WIN32)
        closesocket(sock);
        WSACleanup();
#else
        close(sock);
#endif
        return -13;
    }

    // TODO: Store sock in rffi_t struct for later use
    (void)rffi;
    return 0;
}

void *rffi_ep_dlopen(rffi_t *rffi, const char *lib) {
    (void)rffi;
#if defined(_WIN32)
    return (void*)LoadLibraryA(lib);
#else
    return dlopen(lib, RTLD_LAZY);
#endif
}

void *rffi_ep_dlsym(rffi_t *rffi, void *lib, const char *sym) {
    (void)rffi;
#if defined(_WIN32)
    return (void*)GetProcAddress((HMODULE)lib, sym);
#else
    return dlsym(lib, sym);
#endif
}

static cJSON *rffi_param_to_json(const rffi_param_t *p) {
    switch (p->type) {
        case RFFI_PARAM_INT: {
            // Use i32/i64 depending on value
            if (p->v.ival >= -(1LL<<31) && p->v.ival < (1LL<<31)) {
                cJSON *o = cJSON_CreateObject();
                cJSON_AddStringToObject(o, "t", "i32");
                cJSON_AddNumberToObject(o, "v", (double)p->v.ival);
                return o;
            } else {
                cJSON *o = cJSON_CreateObject();
                cJSON_AddStringToObject(o, "t", "i64");
                cJSON_AddNumberToObject(o, "v", (double)p->v.ival);
                return o;
            }
        }
        case RFFI_PARAM_UINT: {
            // Use u32/u64 depending on value
            if (p->v.uval < (1ULL<<32)) {
                cJSON *o = cJSON_CreateObject();
                cJSON_AddStringToObject(o, "t", "u32");
                cJSON_AddNumberToObject(o, "v", (double)p->v.uval);
                return o;
            } else {
                cJSON *o = cJSON_CreateObject();
                cJSON_AddStringToObject(o, "t", "u64");
                cJSON_AddNumberToObject(o, "v", (double)p->v.uval);
                return o;
            }
        }
        case RFFI_PARAM_FLOAT: {
            // Always encode as f64
            cJSON *o = cJSON_CreateObject();
            cJSON_AddStringToObject(o, "t", "f64");
            cJSON_AddNumberToObject(o, "v", p->v.fval);
            return o;
        }
        case RFFI_PARAM_PTR: {
            // Encode pointer as u64
            cJSON *o = cJSON_CreateObject();
            cJSON_AddStringToObject(o, "t", "u64");
            cJSON_AddNumberToObject(o, "v", (double)(uintptr_t)p->v.ptr);
            return o;
        }
        default:
            return NULL;
    }
}

uintptr_t rffi_ep_call(rffi_t *rffi, rffi_param_t *params, int32_t nparams) {
    // 1. Build args array
    cJSON *args = cJSON_CreateArray();
    for (int i = 0; i < nparams; i++) {
        cJSON *arg = rffi_param_to_json(&params[i]);
        if (!arg) {
            cJSON_Delete(args);
            return 0;
        }
        cJSON_AddItemToArray(args, arg);
    }
    // 2. Build params object
    cJSON *params_obj = cJSON_CreateObject();
    // fn: first param is function pointer
    if (nparams < 1 || params[0].type != RFFI_PARAM_PTR) {
        cJSON_Delete(args);
        cJSON_Delete(params_obj);
        return 0;
    }
    cJSON_AddNumberToObject(params_obj, "fn", (double)(uintptr_t)params[0].v.ptr);
    // args: remaining params
    cJSON_AddItemToObject(params_obj, "args", args);

    // 3. Build request object
    static int req_id = 1;
    cJSON *req = cJSON_CreateObject();
    cJSON_AddStringToObject(req, "type", "req");
    cJSON_AddNumberToObject(req, "id", req_id);
    cJSON_AddStringToObject(req, "method", "call");
    cJSON_AddItemToObject(req, "params", params_obj);

    // 4. Serialize to string
    char *req_str = cJSON_PrintUnformatted(req);
    cJSON_Delete(req);

    // 5. Send length-prefixed message
    uint32_t len = (uint32_t)strlen(req_str);
    uint8_t lenbuf[4] = {
        (uint8_t)((len >> 24) & 0xFF),
        (uint8_t)((len >> 16) & 0xFF),
        (uint8_t)((len >> 8) & 0xFF),
        (uint8_t)(len & 0xFF)
    };
#if defined(_WIN32)
    send(rffi->sock, (const char*)lenbuf, 4, 0);
    send(rffi->sock, req_str, len, 0);
#else
    write(rffi->sock, lenbuf, 4);
    write(rffi->sock, req_str, len);
#endif
    free(req_str);

    // 6. Receive response (length-prefixed)
    uint8_t rlenbuf[4];
    ssize_t nread = 0, total = 0;
    while (total < 4) {
#if defined(_WIN32)
        nread = recv(rffi->sock, (char*)rlenbuf + total, 4 - total, 0);
#else
        nread = read(rffi->sock, rlenbuf + total, 4 - total);
#endif
        if (nread <= 0) return 0;
        total += nread;
    }
    uint32_t rlen = (rlenbuf[0]<<24) | (rlenbuf[1]<<16) | (rlenbuf[2]<<8) | rlenbuf[3];
    if (rlen == 0 || rlen > 4096) return 0;
    char rbuf[4097];
    total = 0;
    while (total < (ssize_t)rlen) {
#if defined(_WIN32)
        nread = recv(rffi->sock, rbuf + total, rlen - total, 0);
#else
        nread = read(rffi->sock, rbuf + total, rlen - total);
#endif
        if (nread <= 0) return 0;
        total += nread;
    }
    rbuf[rlen] = 0;

    // 7. Parse response
    cJSON *resp = cJSON_Parse(rbuf);
    if (!resp) return 0;
    cJSON *resp_id = cJSON_GetObjectItem(resp, "id");
    if (!resp_id || resp_id->valueint != req_id) {
        cJSON_Delete(resp);
        return 0;
    }
    req_id++; // increment for next call

    cJSON *error = cJSON_GetObjectItem(resp, "error");
    if (error && error->type != cJSON_NULL) {
        cJSON_Delete(resp);
        return 0;
    }
    cJSON *result = cJSON_GetObjectItem(resp, "result");
    uintptr_t ret = 0;
    if (result && cJSON_IsObject(result)) {
        // Only handle integer/ptr return for now
        cJSON *t = cJSON_GetObjectItem(result, "t");
        cJSON *v = cJSON_GetObjectItem(result, "v");
        if (t && v && (strcmp(t->valuestring, "i32") == 0 || strcmp(t->valuestring, "i64") == 0 ||
                       strcmp(t->valuestring, "u32") == 0 || strcmp(t->valuestring, "u64") == 0 ||
                       strcmp(t->valuestring, "ptr") == 0)) {
            ret = (uintptr_t)v->valuedouble;
        }
    }
    cJSON_Delete(resp);
    return ret;
}
