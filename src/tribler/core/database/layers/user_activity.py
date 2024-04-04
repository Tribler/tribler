from __future__ import annotations

import logging
import random
import typing

from pony import orm
from pony.orm import Database, db_session

from tribler.core.user_activity.types import InfoHash

if typing.TYPE_CHECKING:
    from dataclasses import dataclass


    @dataclass
    class InfohashPreference:
        """
        Typing for infohash preference database entries.
        """

        infohash: bytes
        preference: float
        parent_query: Query


    @dataclass
    class Query:
        """
        Typing for query database entries.
        """

        query: str
        forwarding_pk: bytes | None
        infohashes: typing.Set[InfohashPreference]

logger = logging.getLogger(__name__)


class UserActivityLayer:
    """
    A database layer to store queries and corresponding preference.
    """

    def __init__(self, database: Database, update_weight: float = 0.8, e: float = 0.01) -> None:
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
            query = orm.Required(str)
            forwarding_pk = orm.Required(bytes)
            infohashes = orm.Set("InfohashPreference")
            orm.PrimaryKey(query, forwarding_pk)

        class InfohashPreference(database.Entity):
            infohash = orm.Required(bytes)
            preference = orm.Required(float)
            parent_query = orm.Required(Query)
            orm.PrimaryKey(infohash, parent_query)

        self.Query = Query
        self.InfohashPreference = InfohashPreference

    def store_external(self, query: str, infohashes: list[bytes], weights: list[float], public_key: bytes) -> None:
        """
        Store externally shared info.
        """
        if len(infohashes) != len(weights):
            logger.warning("Refusing to store query for %s: infohashes and weights lists do not match!",
                           repr(public_key))
            return

        with db_session:
            existing = self.Query.get(query=query, forwarding_pk=public_key)
            existing_entries = {}
            if existing is None:
                existing = self.Query(query=query, forwarding_pk=public_key, infohashes=set())
            else:
                for infohash in existing.infohashes:
                    if infohash.infohash not in infohashes:
                        infohash.delete()
                    else:
                        existing_entries[infohash.infohash] = infohash
            for i in range(len(infohashes)):
                if infohashes[i] in existing_entries:
                    existing_entries[infohashes[i]].preference = weights[i]
                else:
                    existing.infohashes.add(self.InfohashPreference(infohash=InfoHash(infohashes[i]),
                                                                    preference=weights[i],
                                                                    parent_query=existing))

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
                existing = self.Query(query=query, infohashes=set(), forwarding_pk=b"")

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

    def get_random_query_aggregate(self, neighbors: int,
                                   limit: int = 20) -> tuple[str, list[InfoHash], list[float]] | None:
        """
        Select a random query string and aggregate the scores from different peers.

        :param neighbors: The number of connected neighbors.
        :param limit: The number of infohashes to randomly get weights for.
        :returns: a randomly-selected query and up to ``limit`` associated infohashes, or None.
        """
        with db_session:
            random_queries = self.Query.select_random(limit=1)
            if not random_queries:
                return None
            random_selection, = random_queries
            infohashes = []
            weights = []
            # Option 1: give my knowledge with a chance weighted according to the number of connected neighbors
            existing = self.Query.select(query=random_selection.query, forwarding_pk=b"")[:]
            if existing and (neighbors == 0 or random.random() < 1.0 - 1/neighbors):
                items = list(existing[0].infohashes)
                random.shuffle(items)
                for infohash_preference in items[:limit]:
                    infohashes.append(InfoHash(infohash_preference.infohash))
                    weights.append(infohash_preference.preference)
                return random_selection.query, infohashes, weights
            # Option 2: aggregate
            results = self.Query.select(lambda q: q.query == random_selection.query)[:]
            num_results_div = 1/len(results)
            preferences = {}
            for query in results:
                for infohash_preference in query.infohashes:
                    preferences[infohash_preference.infohash] = (preferences.get(infohash_preference.infohash, 0.0)
                                                                 + infohash_preference.preference * num_results_div)
            if not preferences:
                return None
            items = list(preferences.items())
            random.shuffle(items)
            for aggregated in items[:limit]:
                infohash, preference = aggregated
                infohashes.append(InfoHash(infohash))
                weights.append(preference)
            return random_selection.query, infohashes, weights
