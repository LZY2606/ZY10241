from dataclasses import dataclass, field
from typing import Protocol

from automat import TypeMachineBuilder


@dataclass
class PaymentBackend:
    accounts: dict[str, int] = field(default_factory=dict)

    def checkBalance(self, accountID: str) -> int:
        "how many AutoBux™ do you have"
        return self.accounts[accountID]

    def deduct(self, accountID: str, amount: int) -> None:
        "deduct some amount of money from the given account"
        balance = self.accounts[accountID]
        newBalance = balance - amount
        if newBalance < 0:
            raise ValueError("not enough money")
        self.accounts[accountID] = newBalance


@dataclass
class Food:
    name: str
    price: int
    doorNumber: int


class Doors:
    def openDoor(self, number: int) -> None:
        print(f"opening door {number}")


class Automat(Protocol):
    def swipeCard(self, accountID: str) -> None:
        "Swipe a payment card with the given account ID."

    def selectFood(self, doorNumber: int) -> None:
        "Select a food."

    def _dispenseFood(self, doorNumber: int) -> None:
        "Open a door and dispense the food."


@dataclass
class AutomatCore:
    payments: PaymentBackend
    foods: dict[int, Food]  # mapping door-number to food
    doors: Doors


@dataclass
class PaymentDetails:
    accountID: str


def rememberAccount(
    inputs: Automat, core: AutomatCore, accountID: str
) -> PaymentDetails:
    print(f"remembering {accountID=}")
    return PaymentDetails(accountID)


# define machine
builder = TypeMachineBuilder(Automat, AutomatCore)

idle = builder.state("idle")
choosing = builder.state("choosing", rememberAccount)

idle.upon(Automat.swipeCard).to(choosing).returns(None)
# end define


@choosing.upon(Automat.selectFood).loop()
def selected(
    inputs: Automat, core: AutomatCore, details: PaymentDetails, doorNumber: int
) -> None:
    food = core.foods[doorNumber]
    try:
        core.payments.deduct(details.accountID, core.foods[doorNumber].price)
    except ValueError as ve:
        print(ve)
    else:
        inputs._dispenseFood(doorNumber)


@choosing.upon(Automat._dispenseFood).to(idle)
def doOpen(
    inputs: Automat, core: AutomatCore, details: PaymentDetails, doorNumber: int
) -> None:
    core.doors.openDoor(doorNumber)


machineFactory = builder.build()

if __name__ == "__main__":
    machine = machineFactory(
        AutomatCore(
            PaymentBackend({"alice": 100}),
            {
                1: Food("burger", 5, 1),
                2: Food("fries", 3, 2),
                3: Food("pheasant under glass", 200, 3),
            },
            Doors(),
        )
    )
    machine.swipeCard("alice")
    print("too expensive")
    machine.selectFood(3)
    print("just right")
    machine.selectFood(1)
    print("oops")
    machine.selectFood(2)
