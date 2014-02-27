"""Generci Module
"""

class GenericModule(object):

    """
    A generic module interface that needs to be initialized and
    finalized (or shutdown).
    """

    def __init__(self):
        super(GenericModule, self).__init__()

    def initialize(self):
        """Initializes this module.
        """
        pass

    def finalize(self):
        """Finalizes this module.
        """
        pass
