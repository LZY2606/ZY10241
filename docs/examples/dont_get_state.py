from dataclasses import dataclass
from typing import Protocol

from automat import TypeMachineBuilder


class Transport:
    def send(self, arg: bytes) -> None:
        print(f"sent: {arg!r}")


# begin salient
class Connector(Protocol):
    def sendMessage(self) -> None:
        "send a message"


@dataclass
class Core:
    _transport: Transport


builder = TypeMachineBuilder(Connector, Core)
disconnected = builder.state("disconnected")
connected = builder.state("connector")


@connected.upon(Connector.sendMessage).loop()
def actuallySend(connector: Connector, core: Core) -> None:
    core._transport.send(b"message")


@disconnected.upon(Connector.sendMessage).loop()
def failSend(connector: Connector, core: Core):
    print("not connected")
    # end salient


machineFactory = builder.build()
machine = machineFactory(Core(Transport()))
machine.sendMessage()
