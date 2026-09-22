import dataclasses
import typing

from automat import TypeMachineBuilder


class Inputs(typing.Protocol):
    def compute(self) -> int: ...
    def behavior(self) -> None: ...
class Nothing: ...


builder = TypeMachineBuilder(Inputs, Nothing)
start = builder.state("start")


@start.upon(Inputs.compute).loop()
def three(inputs: Inputs, core: Nothing) -> int:
    return 3


# begin computations
computations = []


@start.upon(Inputs.behavior).loop()
def behave(inputs: Inputs, core: Nothing) -> None:
    computations.append(inputs.compute)


machineFactory = builder.build()
machineFactory(Nothing()).behavior()
print(computations[0]())
# end computations
