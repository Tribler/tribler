"""
Tribler is a privacy enhanced BitTorrent client with P2P content discovery.
"""
from tribler.core.utilities.asyncio_fixes.wait_for import patch_wait_for

# The patch is applied at the top level of tribler.core, ensuring it precedes other imports within this subpackage.
# Consequently, submodules importing wait_for from asyncio will use the patched asyncio.tasks.wait_for
# during both runtime and testing.

patch_wait_for()
