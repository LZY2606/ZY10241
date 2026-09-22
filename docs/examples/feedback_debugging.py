import dataclasses
import typing

from automat import TypeMachineBuilder


class Inputs(typing.Protocol):
    def behavior1(self) -> None: ...
    def behavior2(self) -> None: ...
class Nothing: ...


builder = TypeMachineBuilder(Inputs, Nothing)
start = builder.state("start")


@start.upon(Inputs.behavior1).loop()
def one(inputs: Inputs, core: Nothing) -> None:
    print("starting behavior 1")
    inputs.behavior2()
    print("ending behavior 1")


@start.upon(Inputs.behavior2).loop()
def two(inputs: Inputs, core: Nothing) -> None:
    print("behavior 2")


machineFactory = builder.build()
machineFactory(Nothing()).behavior1()
