from __future__ import annotations
import asyncio
import os
from typing import Any, Dict, Optional

from .protocol import make_hello, ProtocolError, RemoteError, decode_param, encode_param
from .transport import JSONLengthPrefixedTransport

class AsyncInitiator:
    """Initiator endpoint: listens, launches arbitrary executable, accepts connection, performs handshake, issues requests."""

    def __init__(
        self,
        cmd: list[str],
        *,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
        bind_host: str = "0.0.0.0",  # expose to other hosts as requested
        bind_port: int = 0,
        connect_timeout: float = 15.0,
        rw_timeout: float = 10.0,
    ):
        if not cmd:
            raise ValueError("cmd must be a non-empty list of strings")
        self._cmd = cmd
        self._env = dict(env) if env is not None else None
        self._cwd = cwd
        self._bind_host = bind_host
        self._bind_port = bind_port
        self._connect_timeout = connect_timeout
        self._rw_timeout = rw_timeout

        self._server: Optional[asyncio.AbstractServer] = None
        self._listen_addr: Optional[tuple[str, int]] = None
        self._client_connected: Optional[asyncio.Future] = None

        self._transport: Optional[JSONLengthPrefixedTransport] = None
        self._reader_task: Optional[asyncio.Task] = None
        self._proc: Optional[asyncio.subprocess.Process] = None

        self._pending: Dict[int, asyncio.Future] = {}
        self._next_id: int = 1
        self._closed: bool = False

    async def _on_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        # Accept the first client only
        if self._transport is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            return
        self._transport = JSONLengthPrefixedTransport(reader, writer, rw_timeout=self._rw_timeout)
        # Signal that client is connected
        if self._client_connected and not self._client_connected.done():
            self._client_connected.set_result(True)

    async def init_subprocess(self) -> None:
        """Start server, launch child executable, accept connection, and complete handshake."""
        if self._server is not None:
            return

        self._client_connected = asyncio.get_event_loop().create_future()
        self._server = await asyncio.start_server(self._on_client, host=self._bind_host, port=self._bind_port)
        # Determine bound address
        sockets = self._server.sockets or []
        if sockets:
            sockname = sockets[0].getsockname()
            self._listen_addr = (sockname[0], sockname[1])
        else:
            raise ProtocolError("Failed to bind server socket")

        host, port = self._listen_addr

        # Launch the arbitrary executable, providing host/port via environment
        child_env = os.environ.copy()
        if self._env:
            child_env.update(self._env)
        child_env.setdefault("REMOTE_FFI_HOST", f"{host}:{port}")
        self._proc = await asyncio.create_subprocess_exec(*self._cmd, env=child_env, cwd=self._cwd)

        # Wait for client connection with timeout
        await asyncio.wait_for(self._client_connected, timeout=self._connect_timeout)
        if not self._transport:
            raise ProtocolError("Client connected but transport not initialized")

        # Handshake: exchange hello
        await self._transport.send_obj(make_hello())
        hello_peer = await self._transport.recv_obj()
        if hello_peer.get("type") != "hello":
            raise ProtocolError("Expected hello from peer")
        # Could validate version/endianness/ptr_size/features intersection if needed

        # Start reader loop
        self._reader_task = asyncio.create_task(self._reader_loop())

    async def _reader_loop(self):
        assert self._transport is not None
        try:
            while True:
                msg = await self._transport.recv_obj()
                mtype = msg.get("type")
                if mtype != "res":
                    # Ignore unknown/unsolicited messages for now
                    continue
                msg_id = msg.get("id")
                fut = self._pending.pop(int(msg_id), None)
                if fut is None:
                    continue
                if msg.get("error") is not None:
                    err = msg["error"]
                    fut.set_exception(RemoteError(int(err.get("code", -1)), str(err.get("message", "error")), err.get("data")))
                else:
                    fut.set_result(msg.get("result"))
        except asyncio.CancelledError:
            # Task cancelled during shutdown
            pass
        except Exception as e:
            # Close all pending with exception
            exc = e
            for fut in list(self._pending.values()):
                if not fut.done():
                    fut.set_exception(exc)
            self._pending.clear()
        finally:
            await self._cleanup_transport()

    async def _send_request(self, method: str, params: Dict[str, Any]) -> Any:
        if self._closed or self._transport is None:
            raise ProtocolError("Transport not available")
        msg_id = self._next_id
        self._next_id += 1
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[msg_id] = fut
        await self._transport.send_obj({"type": "req", "id": msg_id, "method": method, "params": params})
        return await fut

    async def dlopen(self, path: str) -> int:
        res = await self._send_request("dlopen", {"name": path})
        if not isinstance(res, dict):
            raise ProtocolError("Invalid dlopen response")
        handle_val = res.get("handle")
        if handle_val is None:
            raise ProtocolError("Invalid dlopen response: missing handle")
        return int(handle_val)

    async def dlsym(self, name: str, lib: Optional[int] = None) -> int:
        res = await self._send_request("dlsym", {"name": name, "lib": lib})
        if not isinstance(res, dict):
            raise ProtocolError("Invalid dlsym response")
        handle_val = res.get("handle")
        if handle_val is None:
            raise ProtocolError("Invalid dlsym response: missing handle")
        return int(handle_val)

    async def call(self, fn: int, args: list[Any]) -> Any:
        for a in args:
            if not (
                isinstance(a, int)
                or isinstance(a, float)
                or isinstance(a, (bytes, bytearray, memoryview))
            ):
                raise ProtocolError(
                    f"Argument type {type(a).__name__} is not supported by the protocol"
                )
        enc_args = [encode_param(a) for a in args]
        res = await self._send_request("call", {"fn": int(fn), "args": enc_args})
        # Result can be any ParamVal-encoded payload or dict with {"t":...}
        return decode_param(res) if isinstance(res, dict) and "t" in res else res

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        # Stop reader loop
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except BaseException:
                # Swallow CancelledError and any shutdown-time exceptions
                pass
        await self._cleanup_transport()
        # Close server
        if self._server is not None:
            self._server.close()
            try:
                await self._server.wait_closed()
            except Exception:
                pass
            self._server = None
        # Terminate child process if still running
        if self._proc is not None:
            try:
                if self._proc.returncode is None:
                    self._proc.terminate()
                    try:
                        await asyncio.wait_for(self._proc.wait(), timeout=3.0)
                    except asyncio.TimeoutError:
                        self._proc.kill()
                        await self._proc.wait()
            except Exception:
                pass
            self._proc = None

    async def _cleanup_transport(self) -> None:
        if self._transport is not None:
            try:
                await self._transport.aclose()
            except Exception:
                pass
            self._transport = None
