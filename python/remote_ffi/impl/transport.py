from __future__ import annotations
import asyncio
import json
import struct
from typing import Any, Dict, Optional, Tuple

DEFAULT_RW_TIMEOUT = 10.0

class JSONLengthPrefixedTransport:
    """Length-prefixed (LE uint32) JSON transport over asyncio streams."""

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        rw_timeout: float = DEFAULT_RW_TIMEOUT,
    ):
        self._reader = reader
        self._writer = writer
        self._rw_timeout = rw_timeout
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    async def send_obj(self, obj: Dict[str, Any]) -> None:
        data = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        hdr = struct.pack("<I", len(data))
        try:
            self._writer.write(hdr)
            self._writer.write(data)
            await asyncio.wait_for(self._writer.drain(), timeout=self._rw_timeout)
        except Exception:
            await self.aclose()
            raise

    async def recv_obj(self) -> Dict[str, Any]:
        try:
            hdr = await asyncio.wait_for(self._reader.readexactly(4), timeout=self._rw_timeout)
            (length,) = struct.unpack("<I", hdr)
            if length == 0:
                return {}
            payload = await asyncio.wait_for(self._reader.readexactly(length), timeout=self._rw_timeout)
            return json.loads(payload.decode("utf-8"))
        except Exception:
            await self.aclose()
            raise

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._writer.close()
            try:
                await asyncio.wait_for(self._writer.wait_closed(), timeout=1.0)
            except Exception:
                pass
        except Exception:
            pass

async def open_connection(host: str, port: int, rw_timeout: float = DEFAULT_RW_TIMEOUT) -> JSONLengthPrefixedTransport:
    reader, writer = await asyncio.open_connection(host=host, port=port)
    return JSONLengthPrefixedTransport(reader, writer, rw_timeout=rw_timeout)

async def start_server(
    host: str,
    port: int,
    client_connected_cb,
) -> Tuple[asyncio.AbstractServer, Tuple[str, int]]:
    """Start an asyncio server and return (server, (host, port)) bound."""
    client_ready = asyncio.get_event_loop().create_future()

    async def _on_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        await client_connected_cb(reader, writer, client_ready)

    server = await asyncio.start_server(_on_client, host=host, port=port)
    # Resolve actual bound sockname
    sockets = server.sockets or []
    bind_host, bind_port = "0.0.0.0", 0
    if sockets:
        sock = sockets[0].getsockname()
        # sock can be (host, port) or (host, port, flow, scope)
        bind_host, bind_port = sock[0], sock[1]

    return server, (bind_host, bind_port)
