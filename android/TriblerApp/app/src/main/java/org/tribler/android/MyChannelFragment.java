package org.tribler.android;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.support.v7.app.ActionBar;
import android.support.v7.widget.SearchView;
import android.util.Log;
import android.view.Menu;
import android.view.MenuInflater;
import android.view.MenuItem;
import android.view.View;

import com.jakewharton.rxbinding.support.v7.widget.RxSearchView;
import com.jakewharton.rxbinding.support.v7.widget.SearchViewQueryTextEvent;

import org.tribler.android.restapi.json.ChannelOverview;
import org.tribler.android.restapi.json.MyChannelResponse;
import org.tribler.android.restapi.json.TriblerTorrent;

import retrofit2.adapter.rxjava.HttpException;
import rx.Observable;
import rx.Observer;
import rx.android.schedulers.AndroidSchedulers;
import rx.schedulers.Schedulers;

public class MyChannelFragment extends DefaultInteractionListFragment {

    public static final int CREATE_CHANNEL_ACTIVITY_REQUEST_CODE = 401;
    public static final int EDIT_CHANNEL_ACTIVITY_REQUEST_CODE = 402;

    private ChannelOverview _myChannel;

    /**
     * {@inheritDoc}
     */
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setHasOptionsMenu(true);
        loadMyChannel();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onCreateOptionsMenu(Menu menu, MenuInflater inflater) {
        super.onCreateOptionsMenu(menu, inflater);
        inflater.inflate(R.menu.fragment_my_channel_menu, menu);

        // Search button
        MenuItem btnFilter = menu.findItem(R.id.btn_filter_my_channel);
        SearchView searchView = (SearchView) btnFilter.getActionView();

        // Set search hint
        searchView.setQueryHint(getText(R.string.action_search_in_channel));

        // Filter on query text change
        rxSubs.add(RxSearchView.queryTextChangeEvents(searchView)
                .subscribe(new Observer<SearchViewQueryTextEvent>() {

                    public void onNext(SearchViewQueryTextEvent event) {
                        adapter.getFilter().filter(event.queryText());
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        Log.e("onCreateOptionsMenu", "SearchViewQueryTextEvent", e);
                    }
                }));
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onPrepareOptionsMenu(Menu menu) {
        super.onPrepareOptionsMenu(menu);
        // Hide main search button
        menu.findItem(R.id.btn_search).setShowAsActionFlags(MenuItem.SHOW_AS_ACTION_NEVER);

        // Is my channel created?
        boolean created = _myChannel != null;
        menu.findItem(R.id.btn_add_my_channel).setEnabled(created);
        menu.findItem(R.id.btn_filter_my_channel).setEnabled(created);

        // Set title
        if (created) {
            ActionBar actionBar = ((BaseActivity) getActivity()).getSupportActionBar();
            if (actionBar != null) {
                actionBar.setTitle(_myChannel.getName());
            }
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedRight(final TriblerTorrent torrent) {
        // Revert swipe
        adapter.notifyObjectChanged(torrent);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedLeft(final TriblerTorrent torrent) {
        adapter.removeObject(torrent);

        //TODO: remove from my channel
    }

    public void addToChannel() {
        //TODO: add to my channel
    }

    public void editChannel() {
        Intent createIntent = MyUtils.editChannelIntent(_myChannel.getIdentifier(), _myChannel.getName(), _myChannel.getDescription());
        startActivityForResult(createIntent, EDIT_CHANNEL_ACTIVITY_REQUEST_CODE);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void reload() {
        super.reload();
        adapter.clear();
        loadMyChannel();
    }

    private void loadMyChannel() {
        loading = service.getMyChannel()
                .subscribeOn(Schedulers.io())
                .map(MyChannelResponse::getMyChannel)
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<ChannelOverview>() {

                    public void onNext(ChannelOverview overview) {
                        _myChannel = overview;
                        if (isAdded()) {
                            getActivity().invalidateOptionsMenu();
                        }
                    }

                    public void onCompleted() {
                        loadMyChannelTorrents();
                    }

                    public void onError(Throwable e) {
                        if (e instanceof HttpException && ((HttpException) e).code() == 404) {
                            // My channel has not been created yet
                            Intent createIntent = MyUtils.createChannelIntent();
                            startActivityForResult(createIntent, CREATE_CHANNEL_ACTIVITY_REQUEST_CODE);
                        } else {
                            Log.e("loadMyChannel", "getMyChannel", e);
                            MyUtils.onError(e, context);
                            try {
                                Thread.sleep(1000);
                            } catch (InterruptedException ex) {
                            }
                            // Retry
                            reload();
                        }
                    }
                });
        rxSubs.add(loading);
    }

    private void loadMyChannelTorrents() {
        loading = service.getTorrents(_myChannel.getIdentifier())
                .subscribeOn(Schedulers.io())
                .flatMap(response -> Observable.from(response.getTorrents()))
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<TriblerTorrent>() {

                    public void onNext(TriblerTorrent torrent) {
                        adapter.addObject(torrent);
                    }

                    public void onCompleted() {
                        // Hide loading indicator
                        progressView.setVisibility(View.GONE);
                    }

                    public void onError(Throwable e) {
                        Log.e("loadMyChannelTorrents", "getTorrents", e);
                        MyUtils.onError(e, context);
                        try {
                            Thread.sleep(1000);
                        } catch (InterruptedException ex) {
                        }
                        // Retry
                        loadMyChannelTorrents();
                    }
                });
        rxSubs.add(loading);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onActivityResult(int requestCode, int resultCode, Intent data) {
        switch (requestCode) {

            case CREATE_CHANNEL_ACTIVITY_REQUEST_CODE:
                switch (resultCode) {

                    case Activity.RESULT_OK:
                        loadMyChannel();
                        return;

                    case Activity.RESULT_CANCELED:
                        // Hide loading indicator
                        progressView.setVisibility(View.GONE);

                        //TODO: show error message
                        return;
                }
                return;

            case EDIT_CHANNEL_ACTIVITY_REQUEST_CODE:
                switch (resultCode) {

                    case Activity.RESULT_FIRST_USER:
                        String name = data.getStringExtra(ChannelActivity.EXTRA_NAME);

                        // Update title
                        ActionBar actionBar = ((BaseActivity) getActivity()).getSupportActionBar();
                        if (actionBar != null) {
                            actionBar.setTitle(name);
                        }
                        return;
                }
                return;
        }
    }

}
