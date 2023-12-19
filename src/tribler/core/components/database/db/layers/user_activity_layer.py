from __future__ import annotations

import random
import typing
from dataclasses import dataclass

from pony import orm
from pony.orm import db_session

from tribler.core.components.user_activity.types import InfoHash
from tribler.core.utilities.pony_utils import TrackedDatabase

if typing.TYPE_CHECKING:
    @dataclass
    class InfohashPreference:
        infohash: bytes
        preference: float
        parent_query: Query

    @dataclass
    class Query:
        query: str
        infohashes: typing.Set[InfohashPreference]


class UserActivityLayer:

    def __init__(self, database: TrackedDatabase, update_weight: float = 0.8, e: float = 0.01) -> None:
        """
        Create a new User Activity scheme for a particular database.

        :param database: The database to bind to.
        :param update_weight: The weight of new updates.
        :param e: A small value to decide near-zero preference.
        """
        self.database = database

        self.e = e
        self.update_weight_new = update_weight
        self.update_weight_old = 1 - self.update_weight_new

        class Query(database.Entity):
            query = orm.PrimaryKey(str)
            infohashes = orm.Set("InfohashPreference")

        class InfohashPreference(database.Entity):
            infohash = orm.Required(bytes)
            preference = orm.Required(float)
            parent_query = orm.Required(Query)
            orm.PrimaryKey(infohash, parent_query)

        self.Query = Query
        self.InfohashPreference = InfohashPreference

    def store(self, query: str, infohash: InfoHash, losing_infohashes: typing.Set[InfoHash]) -> None:
        """
        Store a query, its selected infohash, and the infohashes that were not downloaded.

        :param query: The text that the user searched for.
        :param infohash: The infohash that the user downloaded.
        :param losing_infohashes: The infohashes that the user saw but ignored.
        """
        # Convert "win" or "loss" to "1.0" or "0.0".
        weights = {ih: 0.0 for ih in losing_infohashes}
        weights[infohash] = 1.0

        # Update or create a new database entry
        with db_session:
            existing = self.Query.get(query=query)
            if existing is not None:
                for old_infohash_preference in existing.infohashes:
                    if old_infohash_preference.infohash in weights:
                        new_weight = (old_infohash_preference.preference * self.update_weight_old
                                      + weights.pop(old_infohash_preference.infohash, 0.0) * self.update_weight_new)
                        old_infohash_preference.preference = new_weight
                    else:
                        # This infohash did not pop up, candidate for deletion
                        new_weight = old_infohash_preference.preference * self.update_weight_old
                        if new_weight < self.e:
                            old_infohash_preference.delete()
                        else:
                            old_infohash_preference.preference = new_weight
                if infohash in weights:
                    weights[infohash] = self.update_weight_new
            else:
                existing = self.Query(query=query, infohashes=set())

            for new_infohash, weight in weights.items():
                existing.infohashes.add(self.InfohashPreference(infohash=new_infohash, preference=weight,
                                                                parent_query=existing))

    @db_session
    def _select_superior(self, infohash_preference: InfohashPreference) -> InfoHash:
        """
        For a given InfohashPreference, get the preferable infohash from the parent query.
        """
        all_hashes_for_query = list(infohash_preference.parent_query.infohashes)
        all_hashes_for_query.sort(key=lambda x: x.preference, reverse=True)
        return typing.cast(InfoHash, all_hashes_for_query[0].infohash)

    def get_preferable(self, infohash: InfoHash) -> InfoHash:
        """
        Given an infohash, see if we know of more preferable infohashes.

        :param infohash: The infohash to find better alternatives for.
        """
        with db_session:
            existing = self.InfohashPreference.select(infohash=infohash)[:]

            if not existing:
                return infohash

            return self._select_superior(random.SystemRandom().choice(existing))

    def get_preferable_to_random(self, limit: int = 1) -> set[InfoHash]:
        """
        Retrieve (a) random infohash(es) and then return the preferred infohash for each infohash.

        This method selects up to the limit of random infohashes and then outputs the set of preferable infohashes.
        This means that you may start with ``limit`` number of infohashes and worst-case, if they all share the same,
        preferable infohash, end up with only one infohash as the output.

        :param limit: The number of infohashes to randomly get the preferred infohash for (the output set may be less).
        :returns: A set of infohashes of size 0 up to ``limit``.
        """
        with db_session:
            random_selection = self.InfohashPreference.select_random(limit=limit)
            return {self._select_superior(ih) for ih in random_selection}
