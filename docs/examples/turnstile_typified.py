from typing import Callable, Protocol
from automat import TypeMachineBuilder


class Lock:
    "A sample I/O device."

    def engage(self) -> None:
        print("Locked.")

    def disengage(self) -> None:
        print("Unlocked.")


class Turnstile(Protocol):
    def arm_turned(self) -> None:
        "The arm was turned."

    def fare_paid(self, coin: int) -> None:
        "The fare was paid."


def buildMachine() -> Callable[[Lock], Turnstile]:
    builder = TypeMachineBuilder(Turnstile, Lock)
    locked = builder.state("Locked")
    unlocked = builder.state("Unlocked")

    @locked.upon(Turnstile.fare_paid).to(unlocked)
    def pay(self: Turnstile, lock: Lock, coin: int) -> None:
        lock.disengage()

    @locked.upon(Turnstile.arm_turned).loop()
    def block(self: Turnstile, lock: Lock) -> None:
        print("**Clunk!**  The turnstile doesn't move.")

    @unlocked.upon(Turnstile.arm_turned).to(locked)
    def turn(self: Turnstile, lock: Lock) -> None:
        lock.engage()

    return builder.build()


TurnstileImpl = buildMachine()
turner = TurnstileImpl(Lock())
print("Paying fare 1.")
turner.fare_paid(1)
print("Walking through.")
turner.arm_turned()
print("Jumping.")
turner.arm_turned()
print("Paying fare 2.")
turner.fare_paid(1)
print("Walking through 2.")
turner.arm_turned()
print("Done.")
