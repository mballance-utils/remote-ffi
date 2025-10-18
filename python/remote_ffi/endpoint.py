
from __future__ import annotations
import abc
import ctypes
from typing import List, Optional, Protocol

class ParamVal(object):
    pass

class SymbolResolver(Protocol):

    @abc.abstractmethod
    def dlopen(self, name) -> Optional[ctypes.c_void_p]:
        ...

    @abc.abstractmethod
    def dlsym(self, lib : Optional[ctypes.c_void_p], name : str) -> Optional[ctypes.c_void_p]:
        ...

class Endpoint(Protocol):

    @abc.abstractmethod
    def setSymbolResolver(self, resolver : SymbolResolver) -> None:
        ...

    @abc.abstractmethod
    async def dlsym(self, name : str, lib : Optional[ctypes.c_void_p]=None): 
        ...

    @abc.abstractmethod
    async def dlopen(self, path : str) -> Optional[ctypes.c_void_p]:
        ...

    @abc.abstractmethod
    async def call(self, fn : ctypes.c_void_p, args : List[ParamVal]) -> ParamVal:
        ...


class EndpointInitiator(Endpoint):

    def __new__(cls, *args, **kwargs):
        pass

    @abc.abstractmethod
    async def init_subprocess(self):
        """Initialize the endpoint by starting and connecting 
        to a subprocess"""
        pass


    pass

class EndpointTarget(Endpoint):

    def __new__(cls, *args, **kwargs):
        pass

    @abc.abstractmethod
    async def init_port(self):
        """Initializes the endpoint by connecting to a port. 
        The implementation of the endpoint will determine 
        how communication proceeds.
        - initiator publishes capabilities
        - target responds with capabilities
        -> Intersection of capabilities determines how communication proceeds
        """
        pass

    pass
