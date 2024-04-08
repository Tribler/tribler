from typing import Dict, List

from tribler.core.components.database.db.serialization import SNIPPET
from tribler.core.components.knowledge.rules.content_bundling import calculate_diversity, group_content_by_number
from tribler.gui.widgets.tablecontentmodel import ChannelContentModel, get_item_uid


class SearchResultsModel(ChannelContentModel):
    def __init__(self, original_query, **kwargs):
        self.original_query = original_query
        self.remote_results = {}
        title = self.format_title()
        super().__init__(channel_info={"name": title}, **kwargs)
        self.remote_results_received = False
        self.postponed_remote_results = []
        self.highlight_remote_results = True
        self.group_by_name = True
        self.sort_by_rank = True
        self.original_search_results = []

    def format_title(self):
        q = self.original_query
        q = q if len(q) < 50 else q[:50] + '...'
        return f'Search results for {q}'

    def perform_initial_query(self):
        return self.perform_query(first=1, last=200)

    def on_query_results(self, response, remote=False, on_top=False):
        super().on_query_results(response, remote=remote, on_top=on_top)
        self.add_remote_results([])  # to trigger adding postponed results
        self.show_remote_results()

    @property
    def all_local_entries_loaded(self):
        return self.loaded

    def add_remote_results(self, results):
        if not self.all_local_entries_loaded:
            self.postponed_remote_results.extend(results)
            return []

        results = self.postponed_remote_results + results
        self.postponed_remote_results = []
        new_items = []
        for item in results:
            uid = get_item_uid(item)
            if uid not in self.item_uid_map and uid not in self.remote_results:
                self.remote_results_received = True
                new_items.append(item)
                self.remote_results[uid] = item
        return new_items

    def show_remote_results(self):
        if not self.all_local_entries_loaded:
            return

        remote_items = list(self.remote_results.values())
        self.remote_results.clear()
        self.remote_results_received = False
        if remote_items:
            self.add_items(remote_items, remote=True)

    def create_bundles(self, content_list: List[Dict], filter_zero_seeders=True, min_bundle_size=3) -> List[Dict]:
        """
        Create bundles from the content list. Each bundle contains at least min_bundle_size items.
        Args:
            content_list: list of content items
            filter_zero_seeders: if True, items with zero seeders are filtered out
            min_bundle_size: minimum number of items in a bundle

        Returns:
            list: list of content items and bundles
        """
        diversity = calculate_diversity(content_list)
        self._logger.info(f'Diversity: {diversity}')
        if diversity > 6:  # 6 is a threshold found empirically
            self._logger.info('Diversity is higher than 6. Bundling is disabled.')
            return content_list
        groups = group_content_by_number(content_list, min_bundle_size)

        result = []
        torrents_in_bundles = set()
        for name, group in groups.items():
            if filter_zero_seeders:
                group = [item for item in group if item.get('num_seeders', 0) > 0]
            if len(group) < min_bundle_size:
                continue

            bundle = {
                'category': '',
                'infohash': name,
                'name': name,
                'torrents': len(group),
                'torrents_in_snippet': group,
                'type': SNIPPET,
            }
            result.append(bundle)
            torrents_in_bundles.update(t.get('infohash') for t in group)

        content_not_in_bundles = (item for item in content_list if item.get('infohash') not in torrents_in_bundles)
        result.extend(content_not_in_bundles)
        return result

    def add_items(self, new_items, on_top=False, remote=False):
        """
        Adds new items to the table model. All items are mapped to their unique ids to avoid the duplicates.
        New items are prepended to the end of the model.
        Note that item_uid_map tracks items twice: once by public_key+id and once by infohash. This is necessary to
        support status updates from TorrentChecker based on infohash only.
        :param new_items: list(item)
        :param on_top: True if new_items should be added on top of the table
        :param remote: True if new_items are from a remote peer. Default: False
        :return: None
        """
        if not new_items:
            return
        unique_new_items, _ = self.extract_unique_new_items(new_items, on_top, remote)
        if remote:
            self.original_search_results = self.original_search_results + unique_new_items
            if self.sort_by_rank:
                self.original_search_results.sort(key=lambda item: item['rank'], reverse=True)
            items = self.create_bundles(self.original_search_results)
        else:
            self.original_search_results = unique_new_items
            items = self.create_bundles(unique_new_items)

        self.beginResetModel()
        self.data_items = items
        self.item_uid_map = self.create_uid_map(items)
        self.endResetModel()
