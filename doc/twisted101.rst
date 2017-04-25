Twisted in Tribler
==================

Once you have a basic understanding of Python, you will need to understand two more advanced concepts before you can start working on Tribler: generator functions and scheduling in Twisted.
This document will teach you about both in the context of Tribler.

Generator functions
-------------------
When browsing the Tribler source code you will find a lot of ``yield`` statements.
This makes this function a *generator* and as a result you will not find any ``return`` statements in this function (which would be syntactically invalid).
The special thing about these *generators* is that they can return intermittent values, without releasing their local context.
This is an advantage when the caller of this *generator* does not necessarily need all of the outputs the *generator* could produce.
Instead, the caller can decide to stop iterating over the outputs of the *generator* at any given time.

Take for example an identifier generator:

.. code-block:: python

    def get_id():
        i = 0
        while True:
            yield i
            i = i + 1

One could then call this ``get_id()`` function as follows:

.. code-block:: python

    print get_id().next()
    
Yielding Deferreds
------------------
Now that you know about generators we can discuss Twisted's ``Deferred`` objects.
Essentially, the only thing a ``Deferred`` does, is call a specified callback function if ``Deferred.callback()`` has been called.
For more information you can reference the official documentation at https://twistedmatrix.com/documents/16.5.0/core/howto/defer.html.

To show how these Deferreds can be used in conjunction with generators, we will give an example.
In Tribler you will find a lot of the following types of code:

.. code-block:: python

    @inlineCallbacks
    def some_function():
        # Wait for some_deferred_object to be called
        yield some_deferred_object
        # The some_deferred_object event has happened now
    
This block of code does two things.

1. [``yield some_deferred_object``] Yield a ``Deferred`` object
2. [``@inlineCallbacks``] Call all values of the generator, call the ``next()`` value of this generator every time the previously yielded Deferred has been fired.

Practically speaking, this pauses the control flow through this function until the ``some_deferred_object`` has been called.
This is useful when dealing with asynchronous events, which otherwise might not be guaranteed to have happened at a certain point in time.
What makes the ``Deferred`` structure even more useful, is that it will return with a value once it has been called.
This means that we can use the return value of the yield within our generator function.
In our example:

.. code-block:: python

    @inlineCallbacks
    def some_function():
        # Wait for some_deferred_object to produce a value
        value = yield some_deferred_object
        # Now we can continue our control flow
        print value

Caveats
-------
**Return values -** As previously mentioned, Python generators do not allow return values.
To do this in a Deferred generator, one can use the ``returnValue()`` function.
In our example:

.. code-block:: python

    @inlineCallbacks
    def some_function():
        value = yield some_deferred_object
        returnValue(value)

**The main thread -** Python has some issues when it comes to function reentrancy.
To this end you might have to tell the Twisted framework that it cannot schedule other functions in between yields of your generator.
Like so:


.. code-block:: python

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def some_function():
        yield some_deferred_object
        # No other function can be called on this thread while the yield is waiting
        
Do note that your ``some_deferred_object`` cannot be called from the main thread now!
Some other thread will have to wake the Deferred for the function to continue execution.

Further reading
---------------
| Functional programming in Python: https://docs.python.org/2.7/howto/functional.html
| Deferred reference: https://twistedmatrix.com/documents/16.5.0/core/howto/defer.html
| Threading in Twisted: http://twistedmatrix.com/documents/current/core/howto/threading.html
