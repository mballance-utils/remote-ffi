# Remote FFI

**Platform Support:**  
remote-ffi supports Linux, Windows, and macOS.  
On macOS, the build system automatically links against libffi.dylib.

The `remote-ffi` library provides a lightweight multi-transport mechanism 
for remote procedure call between two processes. 

The library is modeled on two core concepts:
- dynamic symbol resolution (eg dlopen, dlsym, etc)
- libffi

The use model is, conceptually, very simple:
- Create an EndpointInitiator
- Optionally, define symbols for the target process to find
- Create a subprocess, via the endpoint, that is expected to connect back
- Interact with the endpoint APIs to:
  - look-up symbols in the target process
  - load dynamic libraries in the target process
  - invoke functions in the target process

A core assumption of the library is that each endpoint knows the signature 
of the functions. In other words, the library provides no real mechanism to
publish and/or introspect the signature of functions.
