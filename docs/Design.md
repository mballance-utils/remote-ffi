
A remote-ffi connection consists of two connected endpoints. The Initiator 
endpoint creates the connection -- typically by creating a new sub-process
that will connect back to the initiator. The Target endpoint connects back
to the initiator -- typically by reading the socket hostname and port on
which the initiator is listening. AFter connecting, the initiator and
target coordinate to determine the capabilities of each.

Each endpoint has a symbol resolver. These methods are invoked to load
libraries (and/or Python modules) in response to requests from the peer
endpoint, and search for symbols within those libraries. 

Each endpoint handle provides asynchronous methods for communicating with
the functionality present on the peer.

An endpoint calls a method within the peer by:
- Finding its name by looking up the symbol in the peer (dlsym)
- Forming an argument list 
- Invoking the 'call' method and waiting for it to complete

