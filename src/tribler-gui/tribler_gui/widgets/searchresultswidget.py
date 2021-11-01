import logging
import time
import uuid
from dataclasses import dataclass, field

from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal

from tribler_common.sentry_reporter.sentry_mixin import AddBreadcrumbOnShowMixin
from tribler_common.utilities import to_fts_query

from tribler_core.components.metadata_store.db.serialization import CHANNEL_TORRENT, COLLECTION_NODE, REGULAR_TORRENT

from tribler_gui.tribler_request_manager import TriblerNetworkRequest
from tribler_gui.utilities import connect, get_ui_file_path, tr
from tribler_gui.widgets.tablecontentmodel import SearchResultsModel

widget_form, widget_class = uic.loadUiType(get_ui_file_path('search_results.ui'))


def format_search_loading_label(search_request):
    data = {
        "total_peers": len(search_request.peers),
        "num_complete_peers": len(search_request.peers_complete),
        "num_remote_results": len(search_request.remote_results),
    }

    return (
        tr(
            "Remote responses: %(num_complete_peers)i / %(total_peers)i"
            "\nNew remote results received: %(num_remote_results)i"
        )
        % data
    )


@dataclass
class SearchRequest:
    uuid: uuid
    query: str
    peers: set
    peers_complete: set = field(default_factory=set)
    remote_results: list = field(default_factory=list)

    @property
    def complete(self):
        return self.peers == self.peers_complete


class SearchResultsWidget(AddBreadcrumbOnShowMixin, widget_form, widget_class):
    received_remote_results = pyqtSignal(object)

    def __init__(self, parent=None):
        widget_class.__init__(self, parent=parent)

        try:
            self.setupUi(self)
        except SystemError:
            pass

        self.last_search_time = None
        self.last_search_query = None
        self.hide_xxx = None
        self.search_request = None

    def initialize(self, hide_xxx=False):
        self.hide_xxx = hide_xxx
        self.results_page.initialize_content_page(hide_xxx=hide_xxx)
        self.results_page.channel_torrents_filter_input.setHidden(True)
        connect(self.received_remote_results, self.update_loading_page)
        connect(self.timeout_progress_bar.timeout, self.show_results)
        connect(self.show_results_button.clicked, self.show_results)

    @property
    def has_results(self):
        return self.last_search_query is not None

    def show_results(self, *_):
        if self.search_request is None:
            # Fixes a race condition where the user clicks the show_results button before the search request
            # has been registered by the Core
            return
        self.timeout_progress_bar.stop()
        query = self.search_request.query
        self.results_page.initialize_root_model(
            SearchResultsModel(
                channel_info={"name": (tr("Search results for %s") % query) if len(query) < 50 else f"{query[:50]}..."},
                endpoint_url="search",
                hide_xxx=self.results_page.hide_xxx,
                text_filter=to_fts_query(query),
                type_filter=[REGULAR_TORRENT, CHANNEL_TORRENT, COLLECTION_NODE],
            )
        )
        self.setCurrentWidget(self.results_page)

    def check_can_show(self, query):
        if (
            self.last_search_query == query
            and self.last_search_time is not None
            and time.time() - self.last_search_time < 1
        ):
            logging.info("Same search query already sent within 500ms so dropping this one")
            return False
        return True

    def search(self, query):
        if not self.check_can_show(query):
            return

        self.last_search_query = query
        self.last_search_time = time.time()

        # Trigger remote search
        def register_request(response):
            self.search_request = SearchRequest(response["request_uuid"], query, set(response["peers"]))
            self.state_label.setText(format_search_loading_label(self.search_request))
            self.timeout_progress_bar.start()
            self.setCurrentWidget(self.loading_page)

        params = {'txt_filter': to_fts_query(query), 'hide_xxx': self.hide_xxx}

        TriblerNetworkRequest('remote_query', register_request, method="PUT", url_params=params)

    def reset(self):
        if self.currentWidget() == self.results_page:
            self.results_page.go_back_to_level(0)

    def update_loading_page(self, remote_results):
        if not self.search_request or remote_results.get("uuid") != self.search_request.uuid:
            return
        peer = remote_results["peer"]
        self.search_request.peers_complete.add(peer)
        self.search_request.remote_results.append(remote_results.get("results", []))
        self.state_label.setText(format_search_loading_label(self.search_request))
        if self.search_request.complete:
            self.show_results()
