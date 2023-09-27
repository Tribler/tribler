from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from cryptography.exceptions import InvalidSignature
from ipv8.keyvault.private.libnaclkey import LibNaCLSK
from pony.orm import db_session

from tribler.core.components.knowledge.community.knowledge_payload import StatementOperation
from tribler.core.upgrade.tags_to_knowledge.previous_dbs.knowledge_db import KnowledgeDatabase
from tribler.core.upgrade.tags_to_knowledge.migration import MigrationTagsToKnowledge
from tribler.core.upgrade.tags_to_knowledge.previous_dbs.tags_db import TagDatabase
from tribler.core.utilities.simpledefs import STATEDIR_DB_DIR


# pylint: disable=redefined-outer-name
@pytest.fixture
def migration(tmp_path: Path):
    db_dir = tmp_path / STATEDIR_DB_DIR
    db_dir.mkdir()
    migration = MigrationTagsToKnowledge(tmp_path, LibNaCLSK())
    return migration


def test_no_tags_db(migration: MigrationTagsToKnowledge):
    # test that in the case of missed `tags.db`, migration.run() returns False
    assert not migration.run()
    assert not migration.tag_db_path.exists()
    assert not migration.knowledge_db_path.exists()


def test_remove_tags_db(migration: MigrationTagsToKnowledge):
    # Test that the migration removes the `tags.db` after successful migration procedure.

    # create DB file
    tags_db = TagDatabase(str(migration.tag_db_path))
    tags_db.shutdown()

    assert migration.tag_db_path.exists()

    # run migration
    assert migration.run()
    assert not migration.tag_db_path.exists()


def test_remove_tags_db_with_exception(migration: MigrationTagsToKnowledge):
    # Test that the migration doesn't remove the `tags.db` after unsuccessful migration procedure.

    # create DB file
    tags_db = TagDatabase(str(migration.tag_db_path))
    tags_db.shutdown()

    assert migration.tag_db_path.exists()

    # run migration
    with pytest.raises(FileNotFoundError):
        with patch.object(KnowledgeDatabase, '__init__', Mock(side_effect=FileNotFoundError)):
            migration.run()

    assert migration.tag_db_path.exists()


def test_migration(migration: MigrationTagsToKnowledge):
    @db_session
    def fill_db(key: LibNaCLSK):
        _clock = 0

        def clock() -> int:
            nonlocal _clock
            _clock += 1
            return _clock

        add = 1
        remove = 2

        # add 3 local operations
        local_pub_key = key.pub().key_to_bin()
        tag_db.add_tag_operation(b'1' * 20, 'tag1', b'', add, clock(), local_pub_key, is_local_peer=True)
        tag_db.add_tag_operation(b'2' * 20, 'tag2', b'', add, clock(), local_pub_key, is_local_peer=True)
        tag_db.add_tag_operation(b'3' * 20, 'tag3', b'', remove, clock(), local_pub_key, is_local_peer=True)

        # add 3 remote operations
        tag_db.add_tag_operation(b'4' * 20, 'tag4', b'', add, clock(), b'peer1', is_local_peer=False)
        tag_db.add_tag_operation(b'5' * 20, 'tag5', b'', add, clock(), b'peer2', is_local_peer=False)
        tag_db.add_tag_operation(b'6' * 20, 'tag6', b'', remove, clock(), b'peer3', is_local_peer=False)

        assert len(tag_db.instance.Peer.select()) == 4
        assert len(tag_db.instance.Tag.select()) == 6
        assert len(tag_db.instance.Torrent.select()) == 6

    def verify_signature(o: StatementOperation, signature: bytes):
        packed = migration.serializer.pack_serializable(o)
        if not migration.crypto.is_valid_signature(migration.key, packed, signature):
            raise InvalidSignature(f'Invalid signature for {o}')

    ###############################
    tag_db = TagDatabase(str(migration.tag_db_path))
    fill_db(migration.key)
    tag_db.shutdown()

    assert migration.run()

    knowledge_db = KnowledgeDatabase(str(migration.knowledge_db_path))

    with db_session:
        # assert only local peer is here
        peer = knowledge_db.instance.Peer.get()
        assert peer.public_key == migration.key.pub().key_to_bin()

        # assert only local operations were added
        operations = set(knowledge_db.instance.StatementOp.select())
        assert len(operations) == 3
        assert all(s.local_operation for s in knowledge_db.instance.Statement.select())

        # assert resources are correct
        resources = {r.name for r in knowledge_db.instance.Resource.select()}
        assert resources == {'3333333333333333333333333333333333333333',
                             '3232323232323232323232323232323232323232',
                             '3131313131313131313131313131313131313131',
                             'tag1', 'tag2', 'tag3'}

        # assert signatures are valid
        for operation in operations:
            signature = operation.signature
            operation = StatementOperation(
                subject_type=operation.statement.subject.type,
                subject=operation.statement.subject.name,
                predicate=operation.statement.object.type,
                object=operation.statement.object.name,
                operation=operation.operation,
                clock=operation.clock,
                creator_public_key=operation.peer.public_key
            )
            verify_signature(operation, signature)
