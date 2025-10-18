import os
import subprocess
import time
import socket
import pytest

from remote_ffi.impl.initiator import AsyncInitiator

def find_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    addr, port = s.getsockname()
    s.close()
    return port

@pytest.mark.integration
def test_rffi_ep_call_add():
    # Find a free port for the target to listen on
    port = find_free_port()
    host = f"127.0.0.1:{port}"

    # Launch the target process
    target_exe = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../build/src/test_target"))
    env = os.environ.copy()
    env["REMOTE_FFI_HOST"] = host

    # Start the target process
    target_proc = subprocess.Popen([target_exe], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        # Wait for the target to be ready
        time.sleep(1)

        import asyncio

        async def run_test():
            # Start the initiator and connect to the target
            initiator = AsyncInitiator([target_exe])
            await initiator.init_subprocess()

            # Lookup the test_add symbol
            fn_ptr = await initiator.dlsym("test_add")
            assert fn_ptr is not None

            # Prepare parameters for test_add(2, 3)
            from remote_ffi.impl.protocol import RFFI_PARAM_INT, RFFI_PARAM_PTR, RffiParam
            params = [
                RffiParam(RFFI_PARAM_PTR, fn_ptr),
                RffiParam(RFFI_PARAM_INT, 2),
                RffiParam(RFFI_PARAM_INT, 3)
            ]

            # Call the function
            result = await initiator.call(fn_ptr, params[1:])
            assert result == 5

        asyncio.run(run_test())
    finally:
        target_proc.terminate()
        target_proc.wait(timeout=5)
