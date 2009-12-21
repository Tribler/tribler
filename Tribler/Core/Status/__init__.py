# Written by Njaal Borch
# see LICENSE.txt for license information

"""
Status gathering module with some simple reporting functionality

Usage example:

status = Status.get_status_holder("somename") # Get status object
reporter = MyReporter("MyReporter")           # Create the reporter
status.add_reporter(reporter)                 # Add the reporter to the status object

# Create new element
elem = status.create_status_element("ElementName",
                                    "Description",
                                    initial_value=None)
elem.set_value(somevalue)

# The element will now be reported by the reporter.

A reporter can be created easily like this:

# Print name=value when the element is changed
class MyOnChangeStatusReporter(Status.OnChangeStatusReporter):

    def report(self, element):
        print element.name,"=",element.value


# Print name=value for all elements when the periodic reporter runs
class MyPeriodicStatusReporter(Status.PeriodicStatusReporter):
    def report(self):
        for elems in self.elements[:]:
            print element.name,"=",element.value


See the StatusTest.py class for more examples

"""

from Status import *
from LivingLabReporter import LivingLabPeriodicReporter
