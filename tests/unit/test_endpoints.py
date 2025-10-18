from __future__ import annotations
import sys
import os
from pathlib import Path
import asyncio
import pytest

from remote_ffi.impl import AsyncInitiator
from remote_ffi.impl.protocol import RemoteError

pytestmark = pytest.mark.asyncio

async def start_initiator():
    # Launch target as a Python module so it can import from src
    cmd = [sys.executable, "-m", "remote_ffi.impl.target"]
    # Ensure child can import project packages and test modules
    root = Path(__file__).resolve().parents[2]
    src = root / "src"
    child_env = os.environ.copy()
    prev = child_env.get("PYTHONPATH", "")
    child_env["PYTHONPATH"] = str(src) + ":" + str(root) + ((":" + prev) if prev else "")
    init = AsyncInitiator(cmd, env=child_env, bind_host="0.0.0.0", bind_port=0)
    await init.init_subprocess()
    return init

async def stop_initiator(init: AsyncInitiator):
    await init.aclose()

async def dlopen_sample(init: AsyncInitiator) -> int:
    # Module path relative to tests tree (conftest adds src to sys.path)
    return await init.dlopen("tests.unit.helpers.sample_module")

@pytest.mark.timeout(30)
async def test_dlopen_dlsym_call_add():
    init = await start_initiator()
    try:
        lib = await dlopen_sample(init)
        fn = await init.dlsym("add", lib)
        res = await init.call(fn, [1, 2])
        assert res == 3
    finally:
        await stop_initiator(init)

@pytest.mark.timeout(30)
async def test_call_unsupported_types_raise():
    init = await start_initiator()
    try:
        lib = await dlopen_sample(init)

        sum_list = await init.dlsym("sum_list", lib)
        with pytest.raises(Exception):
            await init.call(sum_list, [[1, 2, 3, 4]])

        nested_echo = await init.dlsym("nested_echo", lib)
        with pytest.raises(Exception):
            await init.call(nested_echo, [{"a": [1, 2, {"k": "v"}], "b": {"x": 7}}])

    finally:
        await stop_initiator(init)

@pytest.mark.timeout(30)
async def test_call_bad_handle_raises_remote_error():
    init = await start_initiator()
    try:
        with pytest.raises(RemoteError):
            await init.call(999999, [])
    finally:
        await stop_initiator(init)
