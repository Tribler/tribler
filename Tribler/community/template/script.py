"""
Example file

python Tribler/Main/dispersy.py --script template
"""
import logging
logger = logging.getLogger(__name__)

from Tribler.dispersy.script import ScriptBase


class TestScript(ScriptBase):

    def run(self):
        self.caller(self.test)

    def test(self):
        logger.debug("testing...")
        assert True
