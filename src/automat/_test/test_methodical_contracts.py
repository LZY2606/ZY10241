"""
Contract tests for L{MethodicalMachine} descriptor semantics.

These tests pin down behavior that the happy-path tests in
L{test_methodical} deliberately leave unspecified:

- *when* the L{Transitioner} commits its new state relative to output
  execution (before outputs run),
- what state the machine is left in when one of several outputs fails
  partway through a transition,
- which generation of state a re-entrant input (an input triggered from
  inside an output) observes,
- that output exceptions propagate with their original traceback,
- and that descriptor identity is stable across inheritance, aliasing,
  subclass shadowing, parallel instances, and class-attribute access.

Every scenario is driven exclusively through the public, bound-method
input path; no test writes to a C{Transitioner}'s private state to
arrange a scenario.  Assertions are made against explicit event
sequences and serialized state names, never against method reprs, object
addresses, or dictionary ordering.
"""

import traceback
from inspect import getattr_static
from unittest import TestCase

from .. import MethodicalMachine, NoTransition
from .._methodical import MethodicalInput, MethodicalState


class ContractBase(object):
    """
    A three-state machine whose outputs record the state they observe on
    entry and can optionally raise, re-enter another input, or loop.

    Instance attributes control the optional behaviors so that a single
    machine definition can serve every contract scenario:

    @ivar events: an explicit, ordered log of everything the outputs did.
    @ivar boom: an exception instance for L{maybeBoom} to raise, or None.
    @ivar reenterComplete: whether L{logBegin} should re-enter C{complete}.
    @ivar pokesLeft: guard counter keeping the C{poke} self-loop finite.
    """

    machine = MethodicalMachine()

    def __init__(self):
        self.events = []
        self.boom = None
        self.reenterComplete = False
        self.pokesLeft = 0

    @machine.state(initial=True, serialized="idle")
    def idle(self):
        "Initial state."

    @machine.state(serialized="working")
    def working(self):
        "State entered by C{begin}."

    @machine.state(serialized="done")
    def done(self):
        "Terminal state entered by C{complete}."

    @machine.input()
    def begin(self):
        "idle -> working, running three outputs in order."

    @machine.input()
    def beginJoined(self):
        "idle -> working with a joining collector."

    @machine.input()
    def complete(self):
        "working -> done."

    @machine.input()
    def poke(self):
        "working -> working, an immediate self-loop."

    # An alias: the very same input descriptor under a second name.
    kick = begin

    @machine.output()
    def logBegin(self):
        self.events.append("logBegin:" + self.save())
        if self.reenterComplete:
            self.complete()
        return "began"

    @machine.output()
    def maybeBoom(self):
        self.events.append("maybeBoom:" + self.save())
        if self.boom is not None:
            raise self.boom
        return "ok"

    @machine.output()
    def afterBoom(self):
        self.events.append("afterBoom:" + self.save())
        return "after"

    @machine.output()
    def logComplete(self):
        self.events.append("logComplete:" + self.save())
        return "completed"

    @machine.output()
    def pokeAgain(self):
        self.events.append("poke:" + self.save())
        if self.pokesLeft:
            self.pokesLeft -= 1
            self.poke()
        return "poked"

    @machine.serializer()
    def save(self, state):
        return state

    setTrace = machine._setTrace

    def describe(self):
        return "base"

    idle.upon(begin, enter=working, outputs=[logBegin, maybeBoom, afterBoom])
    idle.upon(
        beginJoined,
        enter=working,
        outputs=[logBegin, maybeBoom, afterBoom],
        collector="|".join,
    )
    working.upon(complete, enter=done, outputs=[logComplete])
    working.upon(poke, enter=working, outputs=[pokeAgain])


class MiddleMachine(ContractBase):
    """
    First subclass level: overrides a plain method and shadows the
    C{poke} input with a same-name non-input method.
    """

    def describe(self):
        return "middle:" + super().describe()

    def poke(self):
        "A plain method shadowing the inherited input descriptor."
        self.events.append("plain-poke")
        return "plain"


class LeafMachine(MiddleMachine):
    """
    Second subclass level: inherits everything unchanged.
    """


class DescriptorIdentityTests(TestCase):
    """
    The machine, its states, and its inputs are single descriptor
    objects shared by the whole inheritance hierarchy.
    """

    def test_machineIsSharedAcrossHierarchy(self):
        """
        The same L{MethodicalMachine} is visible on the base class and on
        both subclass levels via class-attribute access.
        """
        self.assertIs(MiddleMachine.machine, ContractBase.machine)
        self.assertIs(LeafMachine.machine, ContractBase.machine)

    def test_stateDescriptorIdentity(self):
        """
        States are plain class attributes (not descriptors), so subclass
        access returns the identical L{MethodicalState} object.
        """
        self.assertIsInstance(ContractBase.idle, MethodicalState)
        self.assertIs(MiddleMachine.idle, ContractBase.idle)
        self.assertIs(LeafMachine.working, ContractBase.working)

    def test_inputDescriptorIdentityAndAlias(self):
        """
        Inputs are descriptors inherited by identity, and an alias name
        binds the very same L{MethodicalInput} object.
        """
        baseBegin = getattr_static(ContractBase, "begin")
        self.assertIsInstance(baseBegin, MethodicalInput)
        self.assertIs(getattr_static(MiddleMachine, "begin"), baseBegin)
        self.assertIs(getattr_static(LeafMachine, "begin"), baseBegin)
        self.assertIs(getattr_static(ContractBase, "kick"), baseBegin)
        self.assertIs(getattr_static(LeafMachine, "kick"), baseBegin)

    def test_aliasDrivesTheSameTransition(self):
        """
        Calling the aliased name performs the identical transition as the
        original input name.
        """
        m = ContractBase()
        m.kick()
        self.assertEqual(m.save(), "working")
        self.assertEqual(
            m.events,
            ["logBegin:working", "maybeBoom:working", "afterBoom:working"],
        )

    def test_classAttributeAccess(self):
        """
        The machine and its states are readable on the class; inputs are
        per-instance bindings and refuse class-level access.
        """
        self.assertIs(ContractBase.machine, LeafMachine.machine)
        self.assertIs(ContractBase.done, LeafMachine.done)
        with self.assertRaises(AttributeError):
            ContractBase.begin
        with self.assertRaises(AttributeError):
            LeafMachine.complete

    def test_machineIsPrivateOnInstances(self):
        """
        The machine itself remains an implementation detail on instances
        at every level of the hierarchy.
        """
        for instance in (ContractBase(), MiddleMachine(), LeafMachine()):
            with self.assertRaises(AttributeError):
                instance.machine


class InheritanceBehaviorTests(TestCase):
    """
    Inherited inputs drive subclass instances; same-name plain methods
    in subclasses neither rewrite the shared automaton nor break normal
    method overriding.
    """

    def test_inheritedInputsDriveSubclassInstances(self):
        """
        A two-level subclass instance transitions through the inherited
        machine exactly like a base instance.
        """
        leaf = LeafMachine()
        leaf.begin()
        self.assertEqual(leaf.save(), "working")
        leaf.complete()
        self.assertEqual(leaf.save(), "done")
        self.assertEqual(
            leaf.events,
            [
                "logBegin:working",
                "maybeBoom:working",
                "afterBoom:working",
                "logComplete:done",
            ],
        )

    def test_overriddenPlainMethodCoexistsWithMachine(self):
        """
        Overriding a same-name ordinary method follows normal Python
        inheritance and does not disturb the automaton.
        """
        self.assertEqual(ContractBase().describe(), "base")
        self.assertEqual(MiddleMachine().describe(), "middle:base")
        self.assertEqual(LeafMachine().describe(), "middle:base")
        leaf = LeafMachine()
        leaf.begin()
        self.assertEqual(leaf.save(), "working")

    def test_shadowingInputWithPlainMethodLeavesAutomatonAlone(self):
        """
        Defining a non-input method with the same name as an input in a
        subclass shadows the descriptor for that subclass only: the
        subclass instance runs the plain method (no transition, no
        outputs), while the base class automaton is untouched.
        """
        self.assertIsInstance(getattr_static(ContractBase, "poke"), MethodicalInput)
        self.assertFalse(
            isinstance(getattr_static(MiddleMachine, "poke"), MethodicalInput)
        )

        base = ContractBase()
        middle = MiddleMachine()
        base.begin()
        middle.begin()
        baseEventsBefore = list(base.events)
        middleEventsBefore = list(middle.events)

        # The subclass runs its plain method; no output, no transition.
        self.assertEqual(middle.poke(), "plain")
        self.assertEqual(middle.events, middleEventsBefore + ["plain-poke"])
        self.assertEqual(middle.save(), "working")

        # The base class still runs the state-machine self-loop.
        self.assertEqual(base.poke(), ["poked"])
        self.assertEqual(base.events, baseEventsBefore + ["poke:working"])
        self.assertEqual(base.save(), "working")

        # The subclass instance is still a working machine afterwards.
        middle.complete()
        self.assertEqual(middle.save(), "done")

    def test_parallelInstancesNeverShareState(self):
        """
        Interleaved inputs on base-class and subclass instances advance
        independent L{Transitioner}s, even though all instances share one
        automaton definition.
        """
        first = ContractBase()
        second = ContractBase()
        leaf = LeafMachine()

        first.begin()
        second.kick()
        leaf.begin()
        first.complete()

        self.assertEqual(first.save(), "done")
        self.assertEqual(second.save(), "working")
        self.assertEqual(leaf.save(), "working")

        second.complete()
        self.assertEqual(second.save(), "done")
        self.assertEqual(leaf.save(), "working")

        leaf.complete()
        self.assertEqual(leaf.save(), "done")

        # Each instance's event log reflects only its own transitions.
        beginEvents = [
            "logBegin:working",
            "maybeBoom:working",
            "afterBoom:working",
        ]
        self.assertEqual(first.events, beginEvents + ["logComplete:done"])
        self.assertEqual(second.events, beginEvents + ["logComplete:done"])
        self.assertEqual(leaf.events, beginEvents + ["logComplete:done"])


class CommitTimingTests(TestCase):
    """
    The transition is committed to the L{Transitioner} before any output
    runs; outputs therefore observe the new state, and failures leave
    the new state committed.
    """

    def test_stateCommitsBeforeOutputsRun(self):
        """
        Every output of a transition observes the state being entered,
        not the state being left: the commit happens first.
        """
        m = ContractBase()
        self.assertEqual(m.save(), "idle")
        m.begin()
        self.assertEqual(
            m.events,
            ["logBegin:working", "maybeBoom:working", "afterBoom:working"],
        )
        self.assertEqual(m.save(), "working")

    def test_midwayOutputFailureLeavesNewStateCommitted(self):
        """
        When the middle of several outputs raises, earlier outputs have
        run, later outputs have not, and the machine remains in the
        committed new state: subsequent inputs follow from that state.
        """
        m = ContractBase()
        m.boom = RuntimeError("boom")
        with self.assertRaises(RuntimeError) as cm:
            m.begin()
        self.assertIs(cm.exception, m.boom)
        self.assertEqual(m.events, ["logBegin:working", "maybeBoom:working"])
        self.assertEqual(m.save(), "working")

        # The failed transition is not rolled back and not stuck: the
        # machine continues from the committed state.
        m.boom = None
        m.complete()
        self.assertEqual(m.save(), "done")
        self.assertEqual(
            m.events,
            [
                "logBegin:working",
                "maybeBoom:working",
                "logComplete:done",
            ],
        )

    def test_illegalInputDoesNotCommit(self):
        """
        An input with no transition for the current state raises
        L{NoTransition}, runs no outputs, and leaves the state untouched.
        """
        m = ContractBase()
        with self.assertRaises(NoTransition) as cm:
            m.complete()
        self.assertIs(cm.exception.state, ContractBase.idle)
        self.assertIs(cm.exception.symbol, getattr_static(ContractBase, "complete"))
        self.assertEqual(m.save(), "idle")
        self.assertEqual(m.events, [])

        # The machine is still usable afterwards.
        m.begin()
        self.assertEqual(m.save(), "working")

        # A terminal state rejects every input the same way.
        m.complete()
        with self.assertRaises(NoTransition):
            m.poke()
        self.assertEqual(m.save(), "done")

    def test_reentrantInputReadsCommittedState(self):
        """
        An output that re-enters another input observes the state
        committed by the outer transition (the new generation), so the
        nested input forms a finite legal chain; outputs of the outer
        transition that run after the nested call observe the nested
        transition's state.
        """
        m = ContractBase()
        m.reenterComplete = True
        m.begin()
        self.assertEqual(
            m.events,
            [
                "logBegin:working",  # outer commit is visible
                "logComplete:done",  # nested input chained from it
                "maybeBoom:done",  # outer outputs resume after nesting
                "afterBoom:done",
            ],
        )
        self.assertEqual(m.save(), "done")

    def test_immediateSelfLoopIsFiniteAndOrdered(self):
        """
        An output may immediately re-trigger the same self-looping input;
        with a guard the recursion is finite, each nesting level observes
        the same committed state, and only the outermost call's outputs
        contribute to the caller's return value.
        """
        m = ContractBase()
        m.begin()
        m.events.clear()
        m.pokesLeft = 2
        self.assertEqual(m.poke(), ["poked"])
        self.assertEqual(
            m.events,
            ["poke:working", "poke:working", "poke:working"],
        )
        self.assertEqual(m.save(), "working")
        self.assertEqual(m.pokesLeft, 0)

    def test_outputExceptionPreservesOriginalTraceback(self):
        """
        An exception raised by an output propagates to the caller
        unwrapped: it is the identical object and its traceback still
        contains the output method's own frame.
        """
        m = ContractBase()
        m.boom = ValueError("original failure")
        try:
            m.begin()
        except ValueError as caught:
            # Extract inside the handler: unittest's assertRaises and the
            # interpreter both clear tracebacks of stored exceptions.
            propagated = caught
            frameNames = [
                frame.name for frame in traceback.extract_tb(caught.__traceback__)
            ]
        else:
            self.fail("the output's exception did not propagate")
        self.assertIs(propagated, m.boom)
        self.assertIn("maybeBoom", frameNames)

    def test_outputValuesAggregateInOrder(self):
        """
        The default collector aggregates output return values into a
        list in declared output order; a custom collector receives the
        same ordered sequence.
        """
        m = ContractBase()
        self.assertEqual(m.begin(), ["began", "ok", "after"])

        joined = ContractBase()
        self.assertEqual(joined.beginJoined(), "began|ok|after")
        self.assertEqual(joined.save(), "working")


class TracerContractTests(TestCase):
    """
    Tracer callbacks participate in the commit protocol: a failing
    transition tracer prevents the commit, while a failing output tracer
    runs after the commit but before the output body.
    """

    def test_transitionTracerFailurePreventsCommit(self):
        """
        If the transition tracer raises, the state is not committed, no
        output runs, and the machine keeps working once the tracer is
        removed.
        """
        m = ContractBase()

        def badTracer(oldState, inputName, newState):
            raise RuntimeError("tracer failure")

        m.setTrace(badTracer)
        with self.assertRaises(RuntimeError) as cm:
            m.begin()
        self.assertEqual(str(cm.exception), "tracer failure")
        self.assertEqual(m.save(), "idle")
        self.assertEqual(m.events, [])

        m.setTrace(None)
        m.begin()
        self.assertEqual(m.save(), "working")

    def test_outputTracerFailureHappensAfterCommit(self):
        """
        If the per-output tracer raises, the state has already been
        committed but the output body has not yet run.
        """
        m = ContractBase()

        def tracer(oldState, inputName, newState):
            def outputTracer(outputName):
                raise RuntimeError("output tracer failure")

            return outputTracer

        m.setTrace(tracer)
        with self.assertRaises(RuntimeError) as cm:
            m.begin()
        self.assertEqual(str(cm.exception), "output tracer failure")
        self.assertEqual(m.save(), "working")
        self.assertEqual(m.events, [])

    def test_tracerObservesCommittedTransitionOrder(self):
        """
        A non-failing tracer sees each transition exactly once, in input
        order, with the state names before and after each commit.
        """
        m = ContractBase()
        seen = []
        m.setTrace(
            lambda old, inputName, new: seen.append((old, inputName, new)) or None
        )
        m.begin()
        m.complete()
        self.assertEqual(
            seen,
            [("idle", "begin", "working"), ("working", "complete", "done")],
        )
