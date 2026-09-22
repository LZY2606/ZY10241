from __future__ import annotations

from dataclasses import dataclass, field
from itertools import count
from typing import Callable, List, Protocol

from automat import TypeMachineBuilder


# scaffolding; no state machines yet


@dataclass
class Request:
    id: int = field(default_factory=count(1).__next__)


@dataclass
class RequestGetter:
    cb: Callable[[Request], None] | None = None

    def startGettingRequests(self, cb: Callable[[Request], None]) -> None:
        self.cb = cb


@dataclass(repr=False)
class Task:
    performer: TaskPerformer
    request: Request
    done: Callable[[Task, bool], None]
    active: bool = True
    number: int = field(default_factory=count(1000).__next__)

    def __repr__(self) -> str:
        return f"<task={self.number} request={self.request.id}>"

    def complete(self, success: bool) -> None:
        # Also a state machine, maybe?
        print("complete", success)
        self.performer.activeTasks.remove(self)
        self.active = False
        self.done(self, success)

    def stop(self) -> None:
        self.complete(False)


@dataclass
class TaskPerformer:
    activeTasks: List[Task] = field(default_factory=list)
    taskLimit: int = 3

    def performTask(self, r: Request, done: Callable[[Task, bool], None]) -> Task:
        self.activeTasks.append(it := Task(self, r, done))
        return it


class ConnectionCoordinator(Protocol):
    def start(self) -> None:
        "kick off the whole process"

    def requestReceived(self, r: Request) -> None:
        "a task was received"

    def taskComplete(self, task: Task, success: bool) -> None:
        "task complete"

    def atCapacity(self) -> None:
        "we're at capacity stop handling requests"

    def headroom(self) -> None:
        "one of the tasks completed"

    def cleanup(self) -> None:
        "clean everything up"


@dataclass
class ConnectionState:
    getter: RequestGetter
    performer: TaskPerformer
    allDone: Callable[[Task], None]
    queue: List[Request] = field(default_factory=list)


def buildMachine() -> Callable[[ConnectionState], ConnectionCoordinator]:

    builder = TypeMachineBuilder(ConnectionCoordinator, ConnectionState)
    Initial = builder.state("Initial")
    Requested = builder.state("Requested")
    AtCapacity = builder.state("AtCapacity")
    CleaningUp = builder.state("CleaningUp")

    Requested.upon(ConnectionCoordinator.atCapacity).to(AtCapacity).returns(None)
    Requested.upon(ConnectionCoordinator.headroom).loop().returns(None)
    CleaningUp.upon(ConnectionCoordinator.headroom).loop().returns(None)
    CleaningUp.upon(ConnectionCoordinator.cleanup).loop().returns(None)

    @Initial.upon(ConnectionCoordinator.start).to(Requested)
    def startup(coord: ConnectionCoordinator, core: ConnectionState) -> None:
        core.getter.startGettingRequests(coord.requestReceived)

    @AtCapacity.upon(ConnectionCoordinator.requestReceived).loop()
    def requestReceived(
        coord: ConnectionCoordinator, core: ConnectionState, r: Request
    ) -> None:
        print("buffering request", r)
        core.queue.append(r)

    @AtCapacity.upon(ConnectionCoordinator.headroom).to(Requested)
    def headroom(coord: ConnectionCoordinator, core: ConnectionState) -> None:
        "nothing to do, just transition to Requested state"
        unhandledRequest = core.queue.pop()
        print("dequeueing", unhandledRequest)
        coord.requestReceived(unhandledRequest)

    @Requested.upon(ConnectionCoordinator.requestReceived).loop()
    def requestedRequest(
        coord: ConnectionCoordinator, core: ConnectionState, r: Request
    ) -> None:
        print("immediately handling request", r)
        core.performer.performTask(r, coord.taskComplete)
        if len(core.performer.activeTasks) >= core.performer.taskLimit:
            coord.atCapacity()


    @Initial.upon(ConnectionCoordinator.taskComplete).loop()
    @Requested.upon(ConnectionCoordinator.taskComplete).loop()
    @AtCapacity.upon(ConnectionCoordinator.taskComplete).loop()
    @CleaningUp.upon(ConnectionCoordinator.taskComplete).loop()
    def taskComplete(
        c: ConnectionCoordinator, s: ConnectionState, task: Task, success: bool
    ) -> None:
        if success:
            c.cleanup()
            s.allDone(task)
        else:
            c.headroom()

    @Requested.upon(ConnectionCoordinator.cleanup).to(CleaningUp)
    @AtCapacity.upon(ConnectionCoordinator.cleanup).to(CleaningUp)
    def cleanup(coord: ConnectionCoordinator, core: ConnectionState):
        # We *don't* want to recurse in here; stopping tasks will cause
        # taskComplete!
        while core.performer.activeTasks:
            core.performer.activeTasks[-1].stop()

    return builder.build()


ConnectionMachine = buildMachine()


def begin(
    r: RequestGetter, t: TaskPerformer, done: Callable[[Task], None]
) -> ConnectionCoordinator:
    machine = ConnectionMachine(ConnectionState(r, t, done))
    machine.start()
    return machine


def story() -> None:

    rget = RequestGetter()
    tper = TaskPerformer()

    def yay(t: Task) -> None:
        print("yay")

    m = begin(rget, tper, yay)
    cb = rget.cb
    assert cb is not None
    cb(Request())
    cb(Request())
    cb(Request())
    cb(Request())
    cb(Request())
    cb(Request())
    cb(Request())
    print([each for each in tper.activeTasks])
    sc: ConnectionState = m.__automat_core__  # type:ignore
    print(sc.queue)
    tper.activeTasks[0].complete(False)
    tper.activeTasks[0].complete(False)
    print([each for each in tper.activeTasks])
    print(sc.queue)
    tper.activeTasks[0].complete(True)
    print([each for each in tper.activeTasks])


if __name__ == "__main__":
    story()
