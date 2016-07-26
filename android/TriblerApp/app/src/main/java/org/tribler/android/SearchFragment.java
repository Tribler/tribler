package org.tribler.android;

public class SearchFragment extends DefaultInteractionListFragment {

    public void startSearch(String query) {
        adapter.clear();

        service.startSearch(query);
    }
}
