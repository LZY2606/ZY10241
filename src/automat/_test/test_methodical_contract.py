"""
Contract tests for L{MethodicalMachine} runtime semantics.

These tests pin down behaviors that the "happy path" tests in
L{test_methodical} do not cover:

- *when* a transition commits its new state relative to the outputs that
  the transition runs (before, not after),
- what happens when an output, a tracer, or an input itself fails partway
  through a transition,
- what state a re-entrant input (an input triggered from inside an output)
  observes,
- and how the descriptors that make up a machine behave under inheritance,
  aliasing, plain-method shadowing, and class-level access.

Every scenario is driven exclusively through the public, bound interface
(calling input methods on instances); no test reaches into private
transitioner state to arrange a situation.  Assertions are made against
explicit event sequences and serialized state names, never against method
reprs, object addresses, or dictionary ordering.
"""

import traceback
from unittest import TestCase

from .. import MethodicalMachine, NoTransition


class ContractBoom(Exception):
    """
    An exception raised by outputs and tracers that are set up to fail, so
    that tests can distinguish deliberately raised failures from bugs.
    """


class ContractBase(object):
    """
    A machine used across the contract tests.

    Outputs record C{(output-name, observed-state)} pairs into
    C{self.observations}, where the observed state is read through the
    public L{MethodicalMachine.serializer} interface at the moment the
    output runs.  This makes the commit ordering of transitions directly
    observable without touching private state.
    """

    machine = MethodicalMachine()
    setTrace = machine._setTrace

    def __init__(self):
        self.observations = []
        self.ticksRemaining = 0

    @machine.state(initial=True, serialized="idle")
    def idle(self):
        "The initial state."

    @machine.state(serialized="ready")
    def ready(self):
        "Armed and ready to fire."

    @machine.state(serialized="done")
    def done(self):
        "Fired."

    @machine.input()
    def arm(self):
        "idle -> ready, recording one observation."

    @machine.input()
    def armExploding(self):
        "idle -> ready, but its only output raises."

    @machine.input()
    def armMulti(self):
        "idle -> ready; the second of three outputs raises."

    @machine.input()
    def fire(self):
        "ready -> done."

    ignite = fire
    "An alias: the very same input descriptor under a second name."

    @machine.input()
    def tick(self):
        "ready -> ready; its output may re-trigger it a bounded number of times."

    @machine.input()
    def chain(self):
        "idle -> ready; its output re-enters the machine via fire()."

    @machine.input()
    def collect(self):
        "ready -> ready, aggregating two output values with a custom collector."

    @machine.input()
    def poke(self):
        "idle -> idle; shadowed by a plain method on L{ContractChild}."

    @machine.input()
    def reset(self):
        "done -> idle, with no outputs."

    @machine.output()
    def observeArm(self):
        self.observations.append(("observeArm", self.currentState()))
        return "armed"

    @machine.output()
    def observeFire(self):
        self.observations.append(("observeFire", self.currentState()))
        return "fired"

    @machine.output()
    def observePoke(self):
        self.observations.append(("observePoke", self.currentState()))
        return "poked"

    @machine.output()
    def observeTick(self):
        self.observations.append(("observeTick", self.currentState()))
        if self.ticksRemaining > 0:
            self.ticksRemaining -= 1
            self.tick()
        return "tock"

    @machine.output()
    def chainFire(self):
        self.observations.append(("chainFire", self.currentState()))
        self.fire()
        return "chained"

    @machine.output()
    def explode(self):
        self.observations.append(("explode", self.currentState()))
        self._detonate()

    @machine.output()
    def unreachable(self):
        self.observations.append(("unreachable", self.currentState()))
        return "unreachable"

    @machine.output()
    def firstValue(self):
        return "first"

    @machine.output()
    def secondValue(self):
        return "second"

    def _detonate(self):
        raise ContractBoom("explode() was asked to fail")

    @machine.serializer()
    def currentState(self, state):
        return state

    idle.upon(arm, enter=ready, outputs=[observeArm])
    idle.upon(armExploding, enter=ready, outputs=[explode])
    idle.upon(armMulti, enter=ready, outputs=[observeArm, explode, unreachable])
    idle.upon(chain, enter=ready, outputs=[chainFire])
    idle.upon(poke, enter=idle, outputs=[observePoke])
    ready.upon(fire, enter=done, outputs=[observeFire])
    ready.upon(tick, enter=ready, outputs=[observeTick])
    ready.upon(collect, enter=ready, outputs=[firstValue, secondValue], collector=tuple)
    done.upon(reset, enter=idle, outputs=[])


class ContractChild(ContractBase):
    """
    Inherits the whole machine, but shadows the C{poke} input with a plain
    method.  This must not disturb the base class's automaton in any way.
    """

    def poke(self):
        return "plain-poke"


class ContractGrandchild(ContractChild):
    """
    A second level of inheritance; drives the machine entirely through
    descriptors inherited from L{ContractBase}.
    """


class CommitTimingTests(TestCase):
    """
    A transition commits its new state *before* any of its outputs run.
    """

    def test_stateCommitsBeforeOutputsRun(self):
        """
        The output attached to C{arm} observes, through the public
        serializer, the state the transition is entering ("ready"), not the
        state it is leaving ("idle").
        """
        m = ContractBase()
        self.assertEqual(m.currentState(), "idle")
        self.assertEqual(m.arm(), ["armed"])
        self.assertEqual(m.observations, [("observeArm", "ready")])
        self.assertEqual(m.currentState(), "ready")

    def test_outputExceptionLeavesCommittedState(self):
        """
        If an output raises, the exception propagates, but the transition is
        not rolled back: the machine stays in the state it committed to, and
        remains usable from there.
        """
        m = ContractBase()
        with self.assertRaises(ContractBoom):
            m.armExploding()
        self.assertEqual(m.currentState(), "ready")
        self.assertEqual(m.observations, [("explode", "ready")])
        # The machine is not wedged; the committed state drives what is legal.
        self.assertEqual(m.fire(), ["fired"])
        self.assertEqual(m.currentState(), "done")

    def test_multipleOutputsStopAtFirstFailure(self):
        """
        Outputs run in declared order.  When one of several outputs raises,
        the earlier outputs have already run, the later ones never run, and
        the state remains the committed post-transition state.
        """
        m = ContractBase()
        with self.assertRaises(ContractBoom):
            m.armMulti()
        self.assertEqual(m.currentState(), "ready")
        self.assertEqual(
            m.observations,
            [("observeArm", "ready"), ("explode", "ready")],
        )

    def test_outputExceptionTracebackIsPreserved(self):
        """
        An exception raised inside an output propagates unchanged: it is the
        same failure, with its original traceback (including the frames of
        the output method and its helper), not a re-raised wrapper.
        """
        m = ContractBase()
        caught = None
        frameNames = []
        try:
            m.armExploding()
        except ContractBoom as e:
            # Extract the frames here, inside the except block: the traceback
            # is only guaranteed to be intact while the exception is handled.
            caught = e
            frameNames = [frame.name for frame in traceback.extract_tb(e.__traceback__)]
        self.assertIsNotNone(caught)
        self.assertEqual(str(caught), "explode() was asked to fail")
        # The original exception, not a chained or re-raised wrapper.
        self.assertIsNone(caught.__context__)
        self.assertIsNone(caught.__cause__)
        self.assertIn("explode", frameNames)
        self.assertIn("_detonate", frameNames)
        self.assertLess(frameNames.index("explode"), frameNames.index("_detonate"))


class ReentrancyTests(TestCase):
    """
    Outputs may call input methods; such re-entrant inputs observe the
    already-committed state.
    """

    def test_reentrantInputObservesCommittedState(self):
        """
        C{chain} moves idle -> ready and its output calls C{fire}.  The
        re-entrant input is evaluated against the committed "ready" state
        (not the stale "idle"), forming a finite, legal chain that ends in
        "done".
        """
        m = ContractBase()
        self.assertEqual(m.chain(), ["chained"])
        self.assertEqual(
            m.observations,
            [("chainFire", "ready"), ("observeFire", "done")],
        )
        self.assertEqual(m.currentState(), "done")

    def test_immediateSelfLoop(self):
        """
        A transition whose C{enter} state is its start state loops back
        immediately; each explicit input event runs the outputs once and
        leaves the machine in the same state.
        """
        m = ContractBase()
        m.arm()
        self.assertEqual(m.tick(), ["tock"])
        self.assertEqual(m.tick(), ["tock"])
        self.assertEqual(m.currentState(), "ready")
        self.assertEqual(
            m.observations,
            [
                ("observeArm", "ready"),
                ("observeTick", "ready"),
                ("observeTick", "ready"),
            ],
        )

    def test_boundedRecursiveSelfLoop(self):
        """
        An output of a self-loop transition may re-trigger the same input;
        because the state commits before outputs run, each recursion level
        sees a legal transition.  The recursion is bounded by ordinary
        instance data, and each level runs exactly once.
        """
        m = ContractBase()
        m.arm()
        m.ticksRemaining = 2
        m.tick()
        self.assertEqual(
            m.observations,
            [("observeArm", "ready")] + [("observeTick", "ready")] * 3,
        )
        self.assertEqual(m.currentState(), "ready")


class IllegalInputTests(TestCase):
    """
    Inputs with no transition for the current state fail cleanly.
    """

    def test_illegalInputRaisesAndLeavesStateUntouched(self):
        """
        L{NoTransition} is raised, the machine's state is unchanged, no
        output runs, and the machine remains fully usable afterwards.
        """
        m = ContractBase()
        with self.assertRaises(NoTransition) as cm:
            m.fire()
        self.assertEqual(m.currentState(), "idle")
        self.assertEqual(m.observations, [])
        # The exception identifies the failing transition by identity:
        # the very state and input descriptors declared on the class.
        self.assertIs(cm.exception.state, vars(ContractBase)["idle"])
        self.assertIs(cm.exception.symbol, vars(ContractBase)["fire"])
        # A failed input does not corrupt the machine.
        self.assertEqual(m.arm(), ["armed"])
        self.assertEqual(m.fire(), ["fired"])
        self.assertEqual(m.currentState(), "done")

    def test_illegalInputFromSubclassInstance(self):
        """
        The same contract holds when the input descriptor is invoked through
        an inherited binding on a grandchild instance.
        """
        g = ContractGrandchild()
        with self.assertRaises(NoTransition):
            g.fire()
        self.assertEqual(g.currentState(), "idle")
        self.assertEqual(g.arm(), ["armed"])
        self.assertEqual(g.currentState(), "ready")


class OutputCollectionTests(TestCase):
    """
    Input methods return the aggregated return values of their outputs.
    """

    def test_defaultCollectorAggregatesInOrder(self):
        """
        By default, output return values are collected into a list, in the
        order the outputs were declared on the transition.
        """
        m = ContractBase()
        self.assertEqual(m.arm(), ["armed"])
        self.assertEqual(m.fire(), ["fired"])
        self.assertEqual(m.reset(), [])

    def test_customCollector(self):
        """
        The C{collector} argument to C{upon} receives the sequence of output
        return values and its own return value becomes the input's result.
        """
        m = ContractBase()
        m.arm()
        self.assertEqual(m.collect(), ("first", "second"))


class TracerContractTests(TestCase):
    """
    Tracer callbacks participate in commit ordering too.
    """

    def test_transitionTracerExceptionAbortsCommit(self):
        """
        The transition tracer runs *before* the new state is committed, so
        if it raises, the transition never happens: the state is unchanged
        and no output runs.
        """
        m = ContractBase()

        def tracer(oldState, inputName, newState):
            raise ContractBoom("transition tracer failed")

        m.setTrace(tracer)
        with self.assertRaises(ContractBoom):
            m.arm()
        self.assertEqual(m.currentState(), "idle")
        self.assertEqual(m.observations, [])

    def test_outputTracerExceptionHappensAfterCommit(self):
        """
        The output tracer runs *after* the commit but *before* each output,
        so if it raises, the state has already moved on while no output has
        run yet.
        """
        m = ContractBase()

        def tracer(oldState, inputName, newState):
            def outputTracer(outputName):
                raise ContractBoom("output tracer failed")

            return outputTracer

        m.setTrace(tracer)
        with self.assertRaises(ContractBoom):
            m.arm()
        self.assertEqual(m.currentState(), "ready")
        self.assertEqual(m.observations, [])


class InheritanceContractTests(TestCase):
    """
    Machines are class-level descriptors; behavior is shared by the class
    hierarchy while state remains per-instance.
    """

    def test_inheritedInputsDriveSubclassInstances(self):
        """
        A grandchild instance is driven entirely through inherited input,
        output, state, and serializer descriptors.
        """
        g = ContractGrandchild()
        self.assertEqual(g.currentState(), "idle")
        self.assertEqual(g.arm(), ["armed"])
        self.assertEqual(g.fire(), ["fired"])
        self.assertEqual(g.currentState(), "done")
        self.assertEqual(
            g.observations,
            [("observeArm", "ready"), ("observeFire", "done")],
        )

    def test_instancesNeverShareState(self):
        """
        Two instances of the same subclass, driven by an interleaved
        explicit event sequence, each keep their own current state and
        their own observation log.
        """
        first = ContractGrandchild()
        second = ContractGrandchild()
        first.arm()
        self.assertEqual(first.currentState(), "ready")
        self.assertEqual(second.currentState(), "idle")
        second.arm()
        first.fire()
        self.assertEqual(first.currentState(), "done")
        self.assertEqual(second.currentState(), "ready")
        second.tick()
        self.assertEqual(second.currentState(), "ready")
        self.assertEqual(first.currentState(), "done")
        self.assertEqual(
            first.observations,
            [("observeArm", "ready"), ("observeFire", "done")],
        )
        self.assertEqual(
            second.observations,
            [("observeArm", "ready"), ("observeTick", "ready")],
        )

    def test_plainMethodOverrideDoesNotDisturbBaseAutomaton(self):
        """
        A subclass that defines a plain method with the same name as an
        inherited input shadows that name for itself only: the shadowed
        method drives no transition, and the base class's automaton keeps
        working exactly as declared.
        """
        base = ContractBase()
        child = ContractChild()
        grandchild = ContractGrandchild()
        # The plain method shadows the input descriptor on both subclasses.
        self.assertEqual(child.poke(), "plain-poke")
        self.assertEqual(grandchild.poke(), "plain-poke")
        # Shadowing drove no transition and recorded no observation.
        self.assertEqual(child.currentState(), "idle")
        self.assertEqual(child.observations, [])
        self.assertEqual(grandchild.currentState(), "idle")
        # The base class automaton is untouched by the subclass definition.
        self.assertEqual(base.poke(), ["poked"])
        self.assertEqual(base.observations, [("observePoke", "idle")])
        self.assertEqual(base.currentState(), "idle")
        # And the rest of the inherited machine still works on the child.
        self.assertEqual(child.arm(), ["armed"])
        self.assertEqual(child.currentState(), "ready")

    def test_aliasDescriptorSharesIdentityAndBehavior(self):
        """
        An alias binds the very same input descriptor object under a second
        class attribute name, so invoking it triggers the identical
        transition.
        """
        self.assertIs(vars(ContractBase)["ignite"], vars(ContractBase)["fire"])
        m = ContractBase()
        m.arm()
        self.assertEqual(m.ignite(), ["fired"])
        self.assertEqual(m.currentState(), "done")
        self.assertEqual(
            m.observations,
            [("observeArm", "ready"), ("observeFire", "done")],
        )

    def test_machineDescriptorSharedAcrossHierarchy(self):
        """
        The machine itself is one descriptor object, shared by the whole
        inheritance family; subclasses do not get a copy.
        """
        self.assertIs(ContractBase.machine, ContractChild.machine)
        self.assertIs(ContractChild.machine, ContractGrandchild.machine)

    def test_classAttributeAccessToInputRaises(self):
        """
        Input descriptors are bound to instances; accessing one on the
        class itself (at any level of the hierarchy) raises
        L{AttributeError} rather than returning a callable that would have
        no instance state to work with.
        """
        for cls in (ContractBase, ContractChild, ContractGrandchild):
            with self.assertRaises(AttributeError, msg="{}.fire".format(cls.__name__)):
                cls.fire
