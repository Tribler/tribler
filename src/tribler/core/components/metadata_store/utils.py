import random
import time

from faker import Faker
from ipv8.keyvault.crypto import default_eccrypto
from pony.orm import db_session

from tribler.core.components.database.db.layers.knowledge_data_access_layer import Operation, ResourceType
from tribler.core.components.knowledge.community.knowledge_payload import StatementOperation
from tribler.core.components.knowledge.knowledge_constants import MIN_RESOURCE_LENGTH
from tribler.core.utilities.unicode import hexlify
from tribler.core.utilities.utilities import random_infohash

# Some random keys used for generating tags.
random_key_1 = default_eccrypto.generate_key('low')
random_key_2 = default_eccrypto.generate_key('low')
random_key_3 = default_eccrypto.generate_key('low')
fake = Faker()


class RequestTimeoutException(Exception):
    pass


class NoChannelSourcesException(Exception):
    pass


def generate_title(words_count=5):
    return fake.sentence(nb_words=words_count)[:-1]


def get_random_word(min_length=0):
    word = fake.word()
    while len(word) < min_length:
        word = fake.word()
    return word


def tag_torrent(infohash, db, tags=None, suggested_tags=None):
    infohash = hexlify(infohash)
    if tags is None:
        tags_count = random.randint(2, 6)
        tags = []
        while len(tags) < tags_count:
            tag = get_random_word(min_length=MIN_RESOURCE_LENGTH)
            if tag not in tags:
                tags.append(tag)

    if suggested_tags is None:
        suggested_tags_count = random.randint(1, 3)
        suggested_tags = []
        while len(suggested_tags) < suggested_tags_count:
            tag = get_random_word(min_length=MIN_RESOURCE_LENGTH)
            if tag not in suggested_tags:
                suggested_tags.append(tag)

    def _add_operation(_obj, _op, _key, _predicate=ResourceType.TAG):
        operation = StatementOperation(subject_type=ResourceType.TORRENT, subject=infohash, predicate=_predicate,
                                       object=_obj, operation=_op, clock=0, creator_public_key=_key.pub().key_to_bin())
        operation.clock = db.knowledge.get_clock(operation) + 1
        db.knowledge.add_operation(operation, b"")

    # Give the torrent some tags
    for tag in tags:
        for key in [random_key_1, random_key_2]:  # Each tag should be proposed by two unique users
            _add_operation(tag, Operation.ADD, key)

    # Make sure we have some suggestions
    for tag in suggested_tags:
        _add_operation(tag, Operation.ADD, random_key_3)
        _add_operation(tag, Operation.REMOVE, random_key_2)

    # Give the torrent some simple attributes
    random_title = generate_title(2)
    random_year = f"{random.randint(1990, 2040)}"
    random_description = generate_title(5)
    random_lang = random.choice(["english", "russian", "dutch", "klingon", "valyerian"])
    for key in [random_key_1, random_key_2]:  # Each statement should be proposed by two unique users
        _add_operation(random_title, Operation.ADD, key, _predicate=ResourceType.TITLE)
        _add_operation(random_year, Operation.ADD, key, _predicate=ResourceType.DATE)
        _add_operation(random_description, Operation.ADD, key, _predicate=ResourceType.DESCRIPTION)
        _add_operation(random_lang, Operation.ADD, key, _predicate=ResourceType.LANGUAGE)


@db_session
def generate_torrent(metadata_store, db, parent, title=None):
    infohash = random_infohash()

    # Give each torrent some health information. For now, we assume all torrents are healthy.
    now = int(time.time())
    last_check = now - random.randint(3600, 24 * 3600)
    category = random.choice(["Video", "Audio", "Documents", "Compressed", "Books", "Science"])
    torrent_state = metadata_store.TorrentState(infohash=infohash, seeders=10, last_check=last_check)
    metadata_store.TorrentMetadata(title=title or generate_title(words_count=4), infohash=infohash,
                                   origin_id=parent.id_, health=torrent_state, tags=category)

    tag_torrent(infohash, db)
