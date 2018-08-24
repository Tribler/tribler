from Tribler.Core.leveldbstore import get_write_batch_plyvel
from Tribler.Test.Core.test_leveldb_store import ClockedAbstractLevelDBStore, AbstractTestLevelDBStore


class ClockedPlyvelStore(ClockedAbstractLevelDBStore):
    from Tribler.Core.plyveladapter import LevelDB
    _leveldb = LevelDB
    _writebatch = get_write_batch_plyvel


class TestPlyvelStore(AbstractTestLevelDBStore):
    skip = False
    _storetype = ClockedPlyvelStore
