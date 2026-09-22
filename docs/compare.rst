What makes Automat different?
=============================
There are `dozens of libraries on PyPI implementing state machines
<https://pypi.org/search/?q=finite+state+machine>`_.
So it behooves me to say why yet another one would be a good idea.

Automat is designed around the following principle:
while organizing your code around state machines is a good idea,
your callers don't, and shouldn't have to, care that you've done so.

In Python, the "input" to a stateful system is a method call;
the "output" may be a method call, if you need to invoke a side effect,
or a return value, if you are just performing a computation in memory.
Most other state-machine libraries require you to explicitly create an input object,
provide that object to a generic "input" method, and then receive results,
sometimes in terms of that library's interfaces and sometimes in terms of
classes you define yourself.

Therefore, from the outside, an Automat state machine looks like a Plain Old
Python Object (POPO).  It has methods, and the methods have type annotations,
and you can call them and get their documented return values.
