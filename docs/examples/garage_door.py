import dataclasses
import typing
from enum import Enum, auto

from automat import NoTransition, TypeMachineBuilder


class Direction(Enum):
    up = auto()
    stopped = auto()
    down = auto()


@dataclasses.dataclass
class Motor:
    direction: Direction = Direction.stopped

    def up(self) -> None:
        assert self.direction is Direction.stopped
        self.direction = Direction.up
        print("motor running up")

    def stop(self) -> None:
        self.direction = Direction.stopped
        print("motor stopped")

    def down(self) -> None:
        assert self.direction is Direction.stopped
        self.direction = Direction.down
        print("motor running down")


@dataclasses.dataclass
class Alarm:
    def beep(self) -> None:
        "Sound an alarm so that the user can hear."
        print("beep beep beep")


# protocol definition
class GarageController(typing.Protocol):
    def pushButton(self) -> None:
        "Push the button to open or close the door"

    def openSensor(self) -> None:
        "The 'open' sensor activated; the door is fully open."

    def closeSensor(self) -> None:
        "The 'close' sensor activated; the door is fully closed."


# end protocol definition
# core definition
@dataclasses.dataclass
class DoorDevices:
    motor: Motor
    alarm: Alarm


"end core definition"

# end core definition

# start building
builder = TypeMachineBuilder(GarageController, DoorDevices)
# build states
closed = builder.state("closed")
opening = builder.state("opening")
opened = builder.state("opened")
closing = builder.state("closing")
# end states


# build methods
@closed.upon(GarageController.pushButton).to(opening)
def startOpening(controller: GarageController, devices: DoorDevices) -> None:
    devices.motor.up()


@opening.upon(GarageController.openSensor).to(opened)
def finishedOpening(controller: GarageController, devices: DoorDevices):
    devices.motor.stop()


@opened.upon(GarageController.pushButton).to(closing)
def startClosing(controller: GarageController, devices: DoorDevices) -> None:
    devices.alarm.beep()
    devices.motor.down()


@closing.upon(GarageController.closeSensor).to(closed)
def finishedClosing(controller: GarageController, devices: DoorDevices):
    devices.motor.stop()
    # end methods


# do build
machineFactory = builder.build()
# end building
# story
if __name__ == "__main__":
    # do instantiate
    machine = machineFactory(DoorDevices(Motor(), Alarm()))
    # end instantiate
    print("pushing button...")
    # do open
    machine.pushButton()
    # end open
    print("pushedW")
    try:
        machine.pushButton()
    except NoTransition:
        print("this is not implemented yet")
    print("triggering open sensor, pushing button again")
    # sensor and close
    machine.openSensor()
    machine.pushButton()
    # end close
    print("pushed")
    machine.closeSensor()

# end story
