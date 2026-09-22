from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, Self

from automat import TypeMachineBuilder


@dataclass
class Core:
    value: int


@dataclass
class DataObj:
    datum: str

    @classmethod
    def create(cls, inputs: Inputs, core: Core, datum: str) -> Self:
        return cls(datum)


# begin salient
class Inputs(Protocol):
    def serialize(self) -> tuple[int, str | None]: ...
    def next(self) -> None: ...
    def data(self, datum: str) -> None: ...


builder = TypeMachineBuilder(Inputs, Core)
start = builder.state("start")
nodata = builder.state("nodata")
data = builder.state("data", DataObj.create)
nodata.upon(Inputs.data).to(data).returns(None)
start.upon(Inputs.next).to(nodata).returns(None)


@nodata.upon(Inputs.serialize).loop()
def serialize(inputs: Inputs, core: Core) -> tuple[int, None]:
    return (core.value, None)


@data.upon(Inputs.serialize).loop()
def serializeData(inputs: Inputs, core: Core, data: DataObj) -> tuple[int, str]:
    return (core.value, data.datum)
    # end salient


# build and serialize
machineFactory = builder.build()
machine = machineFactory(Core(3))
machine.next()
print(machine.serialize())
machine.data("hi")
print(machine.serialize())
# end build


def deserializeWithoutData(serialization: tuple[int, DataObj | None]) -> Inputs:
    coreValue, dataValue = serialization
    assert dataValue is None, "not handling data yet"
    return machineFactory(Core(coreValue), nodata)


print(deserializeWithoutData((3, None)))


def deserialize(serialization: tuple[int, str | None]) -> Inputs:
    coreValue, dataValue = serialization
    if dataValue is None:
        return machineFactory(Core(coreValue), nodata)
    else:
        return machineFactory(
            Core(coreValue),
            data,
            lambda inputs, core: DataObj(dataValue),
        )


print(deserialize((3, None)).serialize())
print(deserialize((4, "hello")).serialize())
