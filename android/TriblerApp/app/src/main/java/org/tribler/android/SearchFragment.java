package org.tribler.android;

public class SearchFragment extends DefaultInteractionListFragment {

    private String _query;

    public void startSearch(String query) {
        if (query == _query) {
            // Do not restart search
            return;
        }
        _query = query;

        adapter.clear();

        service.startSearch(query);
    }
}
