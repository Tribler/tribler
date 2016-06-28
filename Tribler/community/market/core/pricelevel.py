from tick import Quantity
from tickentry import TickEntry


class PriceLevel(object):
    """Class to represents a list of ticks at a specific price level"""

    def __init__(self):
        self._head_tick = None  # First tick of the double linked list
        self._tail_tick = None  # Last tick of the double linked list
        self._length = 0  # The number of ticks in the price level
        self._depth = Quantity(0)  # Total amount of quantity contained in this price level
        self._last = None  # The current tick of the iterator

    @property
    def first_tick(self):
        """
        :rtype: TickEntry
        """
        return self._head_tick

    @property
    def length(self):
        """
        Return the length of the amount of ticks contained in the price level
        :rtype: integer
        """
        return self._length

    @property
    def depth(self):
        """
        The depth is equal to the total amount of volume contained in this price level
        :rtype: Quantity
        """
        return self._depth

    @depth.setter
    def depth(self, new_depth):
        """
        :param new_depth: The new depth
        :type new_depth: Quantity
        """
        assert isinstance(new_depth, Quantity), type(new_depth)

        self._depth = new_depth

    def __len__(self):
        """
        Return the length of the amount of ticks contained in the price level
        """
        return self.length

    def __iter__(self):
        self._last = self._head_tick
        return self

    def next(self):
        """
        Return the next tick in the price level for the iterator
        """
        if self._last is None:
            raise StopIteration
        else:
            return_value = self._last
            self._last = self._last.next_tick()
            return return_value

    def append_tick(self, tick):
        """
        :type tick: TickEntry
        """
        assert isinstance(tick, TickEntry), type(tick)

        if self._length == 0:  # Add the first tick
            tick._prev_tick = None
            tick._next_tick = None
            self._head_tick = tick
            self._tail_tick = tick
        else:  # Add to the end of the existing ticks
            tick._prev_tick = self._tail_tick
            tick._next_tick = None
            self._tail_tick._next_tick = tick
            self._tail_tick = tick

        # Update the counters
        self._length += 1
        self._depth += tick.quantity

    def remove_tick(self, tick):
        """
        :type tick: TickEntry
        """
        assert isinstance(tick, TickEntry), type(tick)

        # Update the counters
        self._depth -= tick.quantity
        self._length -= 1

        if self._length == 0:  # Was the only tick in this price level
            return

        prev_tick = tick.prev_tick()
        next_tick = tick.next_tick()
        if prev_tick is not None and next_tick is not None:  # TickEntry in between to other ticks
            prev_tick._next_tick = next_tick
            next_tick._prev_tick = prev_tick
        elif next_tick is not None:  # First tick
            next_tick._prev_tick = None
            self._head_tick = next_tick
        elif prev_tick is not None:  # Last tick
            prev_tick._next_tick = None
            self._tail_tick = prev_tick

    def __str__(self):
        from cStringIO import StringIO

        temp_file = StringIO()
        for tick in self:
            temp_file.write("%s\n" % str(tick))
        return temp_file.getvalue()
