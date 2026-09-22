from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from automat import TypeMachineBuilder


@dataclass
class Beans:
    description: str


@dataclass
class Water:
    "It's Water"


@dataclass
class Carafe:
    "It's a carafe"
    full: bool = False


@dataclass
class Ready:
    beans: Beans
    water: Water
    carafe: Carafe

    def brew(self) -> Mixture:
        print(f"brewing {self.beans} with {self.water} in {self.carafe}")
        return Mixture(self.beans, self.water)


@dataclass
class Mixture:
    beans: Beans
    water: Water


class Brewer(Protocol):
    def brew_button(self) -> None:
        "The user pressed the 'brew' button."

    def wait_a_while(self) -> Mixture:
        "Allow some time to pass."

    def put_in_beans(self, beans: Beans) -> None:
        "The user put in some beans."

    def put_in_water(self, water: Water) -> None:
        "The user put in some water."

    def put_in_carafe(self, carafe: Carafe) -> None:
        "The user put the mug"


class _BrewerInternals(Brewer, Protocol):
    def _ready(self, beans: Beans, water: Water, carafe: Carafe) -> None:
        "We are ready with all of our inputs."


@dataclass
class Light:
    on: bool = False


@dataclass
class BrewCore:
    "state for the brew process"
    ready_light: Light
    brew_light: Light
    beans: Beans | None = None
    water: Water | None = None
    carafe: Carafe | None = None
    brewing: Mixture | None = None


def _coffee_machine() -> TypeMachineBuilder[_BrewerInternals, BrewCore]:
    """
    Best practice: these functions are all fed in to the builder, they don't
    need to call each other, so they don't need to be defined globally.  Use a
    function scope to avoid littering a module with states and such.
    """
    builder = TypeMachineBuilder(_BrewerInternals, BrewCore)
    # reveal_type(builder)

    not_ready = builder.state("not_ready")

    def ready_factory(
        brewer: _BrewerInternals,
        core: BrewCore,
        beans: Beans,
        water: Water,
        carafe: Carafe,
    ) -> Ready:
        return Ready(beans, water, carafe)

    def mixture_factory(brewer: _BrewerInternals, core: BrewCore) -> Mixture:
        # We already do have a 'ready' but it's State-Specific Data which makes
        # it really annoying to relay on to the *next* state without passing it
        # through the state core.  requiring the factory to take SSD inherently
        # means that it could only work with transitions away from a single
        # state, which would not be helpful, although that *is* what we want
        # here.

        assert core.beans is not None
        assert core.water is not None
        assert core.carafe is not None

        return Mixture(core.beans, core.water)

    ready = builder.state("ready", ready_factory)
    brewing = builder.state("brewing", mixture_factory)

    def ready_check(brewer: _BrewerInternals, core: BrewCore) -> None:
        if (
            core.beans is not None
            and core.water is not None
            and core.carafe is not None
            and core.carafe.full is not None
        ):
            brewer._ready(core.beans, core.water, core.carafe)

    @not_ready.upon(Brewer.put_in_beans).loop()
    def put_beans(brewer: _BrewerInternals, core: BrewCore, beans: Beans) -> None:
        core.beans = beans
        ready_check(brewer, core)

    @not_ready.upon(Brewer.put_in_water).loop()
    def put_water(brewer: _BrewerInternals, core: BrewCore, water: Water) -> None:
        core.water = water
        ready_check(brewer, core)

    @not_ready.upon(Brewer.put_in_carafe).loop()
    def put_carafe(brewer: _BrewerInternals, core: BrewCore, carafe: Carafe) -> None:
        core.carafe = carafe
        ready_check(brewer, core)

    @not_ready.upon(_BrewerInternals._ready).to(ready)
    def get_ready(
        brewer: _BrewerInternals,
        core: BrewCore,
        beans: Beans,
        water: Water,
        carafe: Carafe,
    ) -> None:
        print("ready output")

    @ready.upon(Brewer.brew_button).to(brewing)
    def brew(brewer: _BrewerInternals, core: BrewCore, ready: Ready) -> None:
        core.brew_light.on = True
        print("BREW CALLED")
        core.brewing = ready.brew()

    @brewing.upon(_BrewerInternals.wait_a_while).to(not_ready)
    def brewed(brewer: _BrewerInternals, core: BrewCore, mixture: Mixture) -> Mixture:
        core.brew_light.on = False
        return mixture

    return builder


CoffeeMachine: Callable[[BrewCore], Brewer] = _coffee_machine().build()

if __name__ == "__main__":
    machine = CoffeeMachine(core := BrewCore(Light(), Light()))
    machine.put_in_beans(Beans("light roast"))
    machine.put_in_water(Water())
    machine.put_in_carafe(Carafe())
    machine.brew_button()
    brewed = machine.wait_a_while()
    print(brewed)
