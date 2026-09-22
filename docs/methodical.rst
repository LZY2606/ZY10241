****************************************
``MethodicalMachine`` Runtime Contract
****************************************

.. note::

   This page documents the runtime semantics of the legacy
   ``automat.MethodicalMachine`` API, which remains fully supported.  New
   code may prefer ``TypeMachineBuilder`` (see the :doc:`tutorial`); the
   guarantees below are locked by the contract test suite in
   ``src/automat/_test/test_methodical_contract.py`` and apply to
   ``MethodicalMachine`` only.

Transition Commit Ordering
==========================

A transition commits its new state **before** any of its outputs run.  When
an input method is called:

1. the automaton computes the transition for the current state,
2. the transition tracer (if any) is invoked,
3. the new state is committed,
4. each output runs, in declared order, and
5. the outputs' return values are aggregated by the transition's
   ``collector`` (a ``list``, by default) and returned to the caller.

Observable consequences:

- An output that inspects the machine (for example through a
  ``@machine.serializer()`` method) sees the *new* state, not the state the
  transition is leaving.
- If an output raises, the transition is **not** rolled back.  The exception
  propagates to the caller, the machine stays in the committed state, and it
  remains usable from there.
- If one of several outputs raises, earlier outputs have already run and
  later outputs never run; the state is still the committed one.

Exceptions
==========

- An exception raised by an output propagates **unchanged**: it is the same
  exception object, with its original traceback (including the output
  method's own frames), not a wrapped or re-raised substitute.
- Calling an input that has no transition for the current state raises
  ``automat.NoTransition``.  The state is unchanged, no output runs, and the
  machine remains usable.  The exception's ``state`` and ``symbol``
  attributes identify the current state and the rejected input by identity.

Reentrancy
==========

Outputs may call input methods on the same instance.  Because the state
commits before outputs run, a re-entrant input is evaluated against the
*committed* state, so an output can legally chain into the next transition
(for example ``idle -> ready`` whose output calls the input for
``ready -> done``).  Recursion through a self-loop transition is likewise
legal, but it is ordinary Python recursion: it must be bounded by the
application (for example by a counter on the instance), or it will exhaust
the call stack like any other unbounded recursion.

Tracing
=======

``machine._setTrace`` installs a tracer per instance.

- The *transition tracer* runs before the commit (step 2 above).  If it
  raises, the transition is aborted: the state is unchanged and no output
  runs.
- The *output tracer* runs after the commit but before each output.  If it
  raises, the state has already moved on, and the output whose trace call
  failed (and all subsequent ones) never runs.

Inheritance and Descriptor Identity
===================================

Machines, states, and inputs are class-level descriptors.

- **One machine per hierarchy.**  Subclasses share the base class's machine
  and its complete transition table; they do not get a copy.  Inherited
  inputs drive subclass instances exactly as they drive base instances.
- **State is per-instance.**  Each instance lazily acquires its own current
  state on first use; two instances never share state, even when driven by
  an interleaved event sequence.
- **Shadowing is name-local.**  If a subclass defines a *plain* method with
  the same name as an inherited input, that name resolves to the plain
  method for the subclass (driving no transition), while the base class's
  automaton is completely unaffected.
- **Aliases share identity.**  Assigning an input descriptor to a second
  class attribute name (``ignite = fire``) binds the *same* descriptor
  object; both names trigger the identical transition.
- **Inputs are instance-bound.**  Accessing an input on the class itself
  raises ``AttributeError``; the machine object, however, may be accessed on
  the class (this is how visualization tools inspect it).

Complexity
==========

``MethodicalMachine`` favors simplicity over asymptotic efficiency, which is
a deliberate trade-off for machines that are built once and have modest
numbers of transitions:

- Declaring a transition (``state.upon(...)``) is O(n) in the number of
  existing transitions, so defining a whole machine is O(n²).
- Each input dispatch is O(n) in the number of transitions, plus O(k) for
  its k outputs.
- Each instance carries one lazily-created transitioner object (O(1) extra
  state per instance per machine).

Compatibility
=============

These semantics describe long-standing behavior; the contract tests were
added to pin them down, not to change them.  No public API was added,
removed, or altered, and the supported Python versions (3.9+) are
unchanged.  Code that relied on commit-before-outputs ordering, exception
propagation, or per-instance state continues to work; code that
accidentally relied on unspecified behavior in these areas is now covered
by an explicit, tested contract.
