Semantics, Complexity, and Compatibility
========================================

This page spells out the runtime contracts that ``MethodicalMachine``
guarantees, the cost of each operation, and the compatibility trade-offs
behind those choices.  Every guarantee listed here is pinned by the
contract tests in ``src/automat/_test/test_methodical_contracts.py``,
which drive the machine exclusively through public, bound-method input
calls.

State commitment ordering
-------------------------

A transition is committed to the instance's ``Transitioner`` **before
any output runs**.  The sequence for one input call is:

1. The input's (empty) body is invoked to validate the call signature.
2. The automaton computes the transition; ``NoTransition`` is raised
   here if none exists, leaving the current state untouched.
3. The transition tracer (if any) is called; if it raises, the state is
   *not* committed and no output runs.
4. The new state is committed.
5. Each declared output runs in declaration order, observing the
   **new** state (for example through a ``@machine.serializer()``
   method), and the per-output tracer fires before each output body.
6. Output return values are aggregated, in declaration order, by the
   transition's collector (``list`` by default).

Failure semantics
-----------------

- **Illegal input**: ``NoTransition`` commits nothing and runs no
  outputs; the machine remains usable in its previous state.
- **Output failure**: because the commit happens first, an output that
  raises leaves the machine in the *new* state.  Outputs declared
  before the failing one have run; outputs declared after it have not.
  There is no automatic rollback — this is deliberate, since outputs
  perform arbitrary side effects that Automat cannot undo.  The
  exception propagates to the caller unwrapped, as the identical object
  with its original traceback intact.
- **Tracer failure**: a transition tracer that raises prevents the
  commit (state unchanged, no outputs); a per-output tracer that raises
  happens after the commit but before that output's body.

Re-entrancy
-----------

Outputs may call input methods on the same instance.  Because the outer
transition commits first, a nested input reads the *new* generation of
state and chains legally from it; outputs of the outer transition that
run after the nested call observe whatever state the nested transition
committed.  Recursion must be bounded by the application (for example
with a guard counter) — an output that unconditionally re-triggers its
own input recurses until the stack is exhausted, exactly like ordinary
mutually recursive method calls.

Descriptors, inheritance, and instances
---------------------------------------

- The machine, its states, and its inputs are single class-level
  objects shared by the entire inheritance hierarchy; subclasses may be
  instantiated and driven without any re-declaration.
- Each *instance* lazily gets its own ``Transitioner`` on first input,
  so two instances never share runtime state, even across subclass
  boundaries.
- Binding an input descriptor to a second class attribute (an alias)
  reuses the identical input object; both names trigger the same
  transitions.
- Defining a plain method with the same name as an input in a subclass
  shadows the descriptor for that subclass only.  It does **not**
  modify the shared automaton: the base class and other subclasses keep
  their transitions, and the subclass instance's machine state is
  unaffected by calls to the shadowing method.
- The machine and its states are readable as class attributes; inputs
  are per-instance bindings and raise ``AttributeError`` when accessed
  on the class, as does the machine when accessed on an instance.

Complexity
----------

Let *T* be the number of declared transitions and *O* the number of
outputs on a single transition.

- ``state.upon(...)`` is O(*T*): duplicate detection scans the existing
  transition set.
- An input call is O(*T* + *O*): transition lookup is a linear scan of
  the transition set, then each output runs once.
- Memory is O(*T*) per machine plus O(1) per instance (one
  ``Transitioner``).

State machines are expected to be small (tens of transitions), so
Automat favors simple linear scans over index structures.

Compatibility
-------------

These semantics are stable across all supported Python versions and
platforms; the contract tests avoid implementation details such as
method reprs, object addresses, and dictionary ordering so they hold
everywhere.  The one deliberate trade-off to be aware of when
upgrading: code that *depended* on outputs observing the pre-transition
state, or on automatic rollback after an output failure, was relying on
behavior Automat never provided — commit-before-outputs with no
rollback has always been the semantics, and it is now locked by tests.
