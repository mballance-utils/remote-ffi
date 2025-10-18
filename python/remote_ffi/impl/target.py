from __future__ import annotations
import asyncio
import importlib
import os
from typing import Any, Dict, Optional, Tuple

from .protocol import make_hello, ProtocolError, encode_param, decode_param
from .transport import open_connection, JSONLengthPrefixedTransport

class PythonModuleResolver:
    """Simple resolver for tests: uses importlib to load modules and getattr to resolve symbols."""
    def dlopen(self, name: str) -> Any:
        return importlib.import_module(name)

    def dlsym(self, lib: Any, name: str) -> Any:
        return getattr(lib, name)

class AsyncTarget:
    """Target endpoint: connects back to initiator, performs handshake, and services requests."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        *,
        env_key: str = "REMOTE_FFI_HOST",
        rw_timeout: float = 10.0,
    ):
        self._host = host
        self._port = port
        self._env_key = env_key
        self._rw_timeout = rw_timeout

        self._transport: Optional[JSONLengthPrefixedTransport] = None
        self._closed = False

        self._resolver: Optional[Any] = None

        # Handle registry
        self._next_handle: int = 1
        self._handle_to_obj: Dict[int, Any] = {}
        self._objid_to_handle: Dict[int, int] = {}

    def setSymbolResolver(self, resolver: Any) -> None:
        self._resolver = resolver

    def _alloc_handle_for(self, obj: Any) -> int:
        oid = id(obj)
        h = self._objid_to_handle.get(oid)
        if h is not None:
            return h
        h = self._next_handle
        self._next_handle += 1
        self._objid_to_handle[oid] = h
        self._handle_to_obj[h] = obj
        return h

    def _get_obj(self, handle: Optional[int]) -> Any:
        if handle is None:
            raise ProtocolError("handle is required")
        if handle not in self._handle_to_obj:
            raise ProtocolError(f"invalid handle: {handle}")
        return self._handle_to_obj[handle]

    async def init_port(self) -> None:
        """Connect to the initiator using provided host/port or env, exchange hello, and serve requests."""
        if self._transport is not None:
            return

        host = self._host
        port = self._port
        if host is None or port is None:
            hk = self._env_key
            hostport = os.environ.get(hk)
            if hostport is None:
                raise ProtocolError("Missing connection info (host:port)")
            try:
                host, port_str = hostport.rsplit(":", 1)
                port = int(port_str)
            except Exception as e:
                raise ProtocolError(f"Invalid REMOTE_FFI_HOST format: {hostport}") from e

        assert host is not None and port is not None
        self._transport = await open_connection(host, port, rw_timeout=self._rw_timeout)

        # Handshake: expect hello, then reply
        peer_hello = await self._transport.recv_obj()
        if peer_hello.get("type") != "hello":
            raise ProtocolError("Expected hello from peer (initiator)")
        await self._transport.send_obj(make_hello())

        # Serve loop
        await self._serve_loop()

    async def _serve_loop(self) -> None:
        assert self._transport is not None
        try:
            while True:
                msg = await self._transport.recv_obj()
                mtype = msg.get("type")
                if mtype != "req":
                    # Ignore unknown messages
                    continue
                msg_id = msg.get("id")
                method = msg.get("method")
                params = msg.get("params") or {}
                try:
                    if method == "dlopen":
                        result = await self._op_dlopen(params)
                    elif method == "dlsym":
                        result = await self._op_dlsym(params)
                    elif method == "call":
                        result = await self._op_call(params)
                    else:
                        raise ProtocolError(f"Unknown method: {method}")
                    await self._transport.send_obj({"type": "res", "id": msg_id, "result": result, "error": None})
                except Exception as e:
                    await self._transport.send_obj({
                        "type": "res",
                        "id": msg_id,
                        "error": {"code": -32000, "message": str(e)}
                    })
        except Exception:
            # Connection closed or error; exit serve loop
            pass
        finally:
            await self.aclose()

    async def _op_dlopen(self, params: Dict[str, Any]) -> Dict[str, Any]:
        name = params.get("name")
        if not isinstance(name, str):
            raise ProtocolError("dlopen requires string 'name'")
        if self._resolver is None:
            lib_obj = importlib.import_module(name)
        else:
            lib_obj = self._resolver.dlopen(name)
        handle = self._alloc_handle_for(lib_obj)
        return {"handle": handle}

    async def _op_dlsym(self, params: Dict[str, Any]) -> Dict[str, Any]:
        name = params.get("name")
        lib = params.get("lib")
        if not isinstance(name, str):
            raise ProtocolError("dlsym requires string 'name'")
        lib_obj = self._get_obj(lib)
        if self._resolver is None:
            sym_obj = getattr(lib_obj, name)
        else:
            sym_obj = self._resolver.dlsym(lib_obj, name)
        handle = self._alloc_handle_for(sym_obj)
        return {"handle": handle}

    async def _op_call(self, params: Dict[str, Any]) -> Any:
        fn_handle = params.get("fn")
        args_enc = params.get("args") or []
        fn_obj = self._get_obj(fn_handle)
        if not callable(fn_obj):
            raise ProtocolError("call target is not callable")
        # Decode args
        args = [decode_param(a) if isinstance(a, dict) and "t" in a else a for a in args_enc]
        result = fn_obj(*args)
        # Only allow supported result types
        if not (
            isinstance(result, int)
            or isinstance(result, float)
            or isinstance(result, (bytes, bytearray, memoryview))
        ):
            raise ProtocolError(
                f"Function result type {type(result).__name__} is not supported by the protocol"
            )
        # Encode result
        return encode_param(result)

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._transport is not None:
            try:
                await self._transport.aclose()
            except Exception:
                pass
            self._transport = None

# Entry point for running as a module: python -m remote_ffi.impl.target
async def _main_async() -> None:
    tgt = AsyncTarget()
    tgt.setSymbolResolver(PythonModuleResolver())
    await tgt.init_port()

def main() -> None:
    asyncio.run(_main_async())

if __name__ == "__main__":
    main()
