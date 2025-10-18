from __future__ import annotations
import base64
import ctypes
import sys
from typing import Any, Dict, Optional

# Protocol versioning and feature advertisement
VERSION = "0.1"
FEATURES = ["dlopen", "dlsym", "call"]


def pointer_size() -> int:
    return ctypes.sizeof(ctypes.c_void_p)


def endianness() -> str:
    return "little" if sys.byteorder == "little" else "big"


def make_hello() -> Dict[str, Any]:
    return {
        "type": "hello",
        "version": VERSION,
        "endianness": endianness(),
        "ptr_size": pointer_size(),
        "features": FEATURES,
    }


class RemoteFFIError(Exception):
    pass


class ProtocolError(RemoteFFIError):
    pass


class RemoteError(RemoteFFIError):
    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(f"Remote error {code}: {message}")
        self.code = code
        self.data = data


# ParamVal encoding helpers (JSON-friendly)
# Supported:
# - i8, u8, i16, u16, i32, u32, i64, u64
# - f32, f64
# - ptr (u64)
# - bytes (base64, with explicit length)
def encode_param(v: Any) -> Any:
    # Only allow supported types: int, float, bytes, pointer
    if isinstance(v, int):
        # Signed/unsigned 8/16/32/64-bit detection
        if -(1 << 7) <= v < (1 << 7):
            return {"t": "i8", "v": v}
        if 0 <= v < (1 << 8):
            return {"t": "u8", "v": v}
        if -(1 << 15) <= v < (1 << 15):
            return {"t": "i16", "v": v}
        if 0 <= v < (1 << 16):
            return {"t": "u16", "v": v}
        if -(1 << 31) <= v < (1 << 31):
            return {"t": "i32", "v": v}
        if 0 <= v < (1 << 32):
            return {"t": "u32", "v": v}
        if -(1 << 63) <= v < (1 << 63):
            return {"t": "i64", "v": v}
        if 0 <= v < (1 << 64):
            return {"t": "u64", "v": v}
        raise ProtocolError("int out of supported range")
    if isinstance(v, float):
        # Use f32 if possible, else f64
        import struct
        f32 = struct.unpack("f", struct.pack("f", v))[0]
        if f32 == v:
            return {"t": "f32", "v": v}
        return {"t": "f64", "v": v}
    if isinstance(v, (bytes, bytearray, memoryview)):
        b = bytes(v)
        return {"t": "bytes", "v": base64.b64encode(b).decode("ascii"), "len": len(b)}
    # Pointer-by-address can be represented as integer elsewhere; keep simple here
    raise ProtocolError(f"unsupported param type: {type(v).__name__}")
    if isinstance(v, int):
        if v >= (1 << 63) or v < -(1 << 63):
            raise ProtocolError("int out of i64 range")
        return {"t": "i64", "v": int(v)}
    if isinstance(v, float):
        return {"t": "f64", "v": float(v)}
    if isinstance(v, str):
        return {"t": "str", "v": v}
    if isinstance(v, (bytes, bytearray, memoryview)):
        b = bytes(v)
        return {"t": "bytes", "v": base64.b64encode(b).decode("ascii")}
    if isinstance(v, list):
        return {"t": "list", "v": [encode_param(e) for e in v]}
    if isinstance(v, dict):
        return {"t": "dict", "v": {str(k): encode_param(val) for k, val in v.items()}}
    # Pointer-by-address can be represented as integer elsewhere; keep simple here
    raise ProtocolError(f"unsupported param type: {type(v).__name__}")


def decode_param(o: Any) -> Any:
    if not isinstance(o, dict) or "t" not in o:
        raise ProtocolError("invalid param encoding")
    t = o.get("t")
    v = o.get("v")
    if t in ("i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64", "ptr"):
        if v is None:
            raise ProtocolError(f"missing value for type {t}")
        return int(v)
    if t in ("f32", "f64"):
        if v is None:
            raise ProtocolError(f"missing value for type {t}")
        return float(v)
    if t == "bytes":
        return base64.b64decode(v) if v is not None else b""
    raise ProtocolError(f"unknown param type: {t}")
