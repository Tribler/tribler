package org.tribler.android;

import android.app.Activity;
import android.app.SearchManager;
import android.content.Context;
import android.content.Intent;
import android.support.v7.widget.SearchView;

public class SearchViewListener implements SearchView.OnQueryTextListener {

    private Activity mActivity;
    private SearchView mSearchView;

    public SearchViewListener(Activity activity) {
        mActivity = activity;
    }

    public void setSearchView(SearchView searchView) {
        mSearchView = searchView;
        mSearchView.setOnQueryTextListener(this);
        // Set searchable configuration
        SearchManager searchManager = (SearchManager) mActivity.getSystemService(Context.SEARCH_SERVICE);
        mSearchView.setSearchableInfo(searchManager.getSearchableInfo(mActivity.getComponentName()));
    }

    @Override
    public boolean onQueryTextSubmit(String query) {
        mSearchView.clearFocus();
        Intent intent = new Intent(Intent.ACTION_SEARCH, null, mActivity, Home.class);
        intent.putExtra(SearchManager.QUERY, query);
        mActivity.startActivity(intent);
        return true;
    }

    @Override
    public boolean onQueryTextChange(String newText) {
        return false;
    }

}

