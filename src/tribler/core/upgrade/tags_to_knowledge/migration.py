import logging
from typing import Iterable, List

from ipv8.keyvault.crypto import default_eccrypto
from ipv8.keyvault.private.libnaclkey import LibNaCLSK
from ipv8.messaging.serialization import Serializer
from pony.orm import db_session, select

from tribler.core.components.knowledge.community.knowledge_payload import StatementOperation
from tribler.core.upgrade.tags_to_knowledge.previous_dbs.knowledge_db import KnowledgeDatabase, ResourceType
from tribler.core.upgrade.tags_to_knowledge.previous_dbs.tags_db import TagDatabase
from tribler.core.utilities.path_util import Path
from tribler.core.utilities.simpledefs import STATEDIR_DB_DIR
from tribler.core.utilities.unicode import hexlify


class MigrationTagsToKnowledge:
    def __init__(self, state_dir: Path, key: LibNaCLSK):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.state_dir = state_dir
        self.key = key

        self.tag_db_path = self.state_dir / STATEDIR_DB_DIR / 'tags.db'
        self.knowledge_db_path = self.state_dir / STATEDIR_DB_DIR / 'knowledge.db'

        self.serializer = Serializer()
        self.crypto = default_eccrypto

        self.logger.info(f'Tags DB path: {self.tag_db_path}')
        self.logger.info(f'Knowledge DB path: {self.knowledge_db_path}')

    def run(self) -> bool:
        self.logger.info('Starting upgrade procedure for tags DB')

        if not self.tag_db_path.exists():
            self.logger.info("Tags DB doesn't exist. Stop procedure.")
            return False

        tag_db = None
        knowledge_db = None

        try:
            tag_db = TagDatabase(str(self.tag_db_path))
            knowledge_db = KnowledgeDatabase(str(self.knowledge_db_path))
            self.logger.info("Migrating the tags.db into the knowledge.db")

            public_key = self.key.pub().key_to_bin()

            operations = list(self._read(tag_db, public_key))
            self._write(knowledge_db, operations)
        finally:
            self.logger.info(f"Closing DB")

            if tag_db:
                tag_db.shutdown()
            if knowledge_db:
                knowledge_db.shutdown()

        self.logger.info("Removing Tags DB")
        self.tag_db_path.unlink(missing_ok=True)
        self.logger.info("Tags DB has been removed")
        return True

    @db_session
    def _read(self, tag_db: TagDatabase, public_key: bytes) -> Iterable[StatementOperation]:
        tags = select(tt for tt in tag_db.instance.TorrentTag if tt.local_operation)
        i = 0
        for i, tag in enumerate(tags):
            operation = StatementOperation(
                subject_type=ResourceType.TORRENT,
                subject=hexlify(tag.torrent.infohash),
                predicate=ResourceType.TAG,
                object=tag.tag.name,
                operation=tag.local_operation,
                clock=0,
                creator_public_key=public_key
            )
            yield operation
            if i % 10 == 0:
                self.logger.info(f'Read: {i}')
        self.logger.info(f'Read: {i}')

    @db_session
    def _write(self, knowledge_db: KnowledgeDatabase, operations: List[StatementOperation]):
        i = 0
        for i, operation in enumerate(operations):
            operation.clock = knowledge_db.get_clock(operation)
            signature = self._sign(operation)
            operation.clock = knowledge_db.get_clock(operation)
            knowledge_db.add_operation(
                operation=operation,
                signature=signature,
                is_local_peer=True,
                is_auto_generated=False
            )
            if i % 10 == 0:
                self.logger.info(f'Write: {i}')
        self.logger.info(f'Finished: {i}')

    def _sign(self, operation) -> bytes:
        packed = self.serializer.pack_serializable(operation)
        return self.crypto.create_signature(self.key, packed)
