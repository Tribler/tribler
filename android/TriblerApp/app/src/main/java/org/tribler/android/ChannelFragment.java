package org.tribler.android;

import android.content.Intent;
import android.nfc.NdefRecord;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.Message;
import android.support.v7.app.ActionBar;
import android.support.v7.app.AppCompatActivity;
import android.support.v7.widget.SearchView;
import android.util.Log;
import android.view.Menu;
import android.view.MenuInflater;
import android.view.MenuItem;

import com.jakewharton.rxbinding.support.v7.widget.RxSearchView;
import com.jakewharton.rxbinding.support.v7.widget.SearchViewQueryTextEvent;

import org.tribler.android.restapi.EventStream;
import org.tribler.android.restapi.json.SubscribedAck;
import org.tribler.android.restapi.json.TorrentDiscoveredEvent;
import org.tribler.android.restapi.json.TorrentRemovedFromChannelEvent;
import org.tribler.android.restapi.json.TriblerTorrent;
import org.tribler.android.restapi.json.UnsubscribedAck;

import rx.Observable;
import rx.Observer;
import rx.android.schedulers.AndroidSchedulers;
import rx.schedulers.Schedulers;

public class ChannelFragment extends DefaultInteractionListFragment implements Handler.Callback {

    private MenuItem _btnFav;
    private MenuItem _btnBeam;
    private Handler _eventHandler;

    private String _dispersyCid;
    private int _channelId;
    private String _name;
    private boolean _subscribed;

    /**
     * {@inheritDoc}
     */
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setHasOptionsMenu(true);

        Intent intent = getActivity().getIntent();
        _dispersyCid = intent.getStringExtra(ChannelActivity.EXTRA_DISPERSY_CID);
        _channelId = intent.getIntExtra(ChannelActivity.EXTRA_CHANNEL_ID, -1);
        _name = intent.getStringExtra(ChannelActivity.EXTRA_NAME);
        _subscribed = intent.getBooleanExtra(ChannelActivity.EXTRA_SUBSCRIBED, false);

        // Start listening to events on the main thread so the gui can be updated
        _eventHandler = new Handler(Looper.getMainLooper(), this);
        EventStream.addHandler(_eventHandler);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onDestroy() {
        EventStream.removeHandler(_eventHandler);
        super.onDestroy();
        _eventHandler = null;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onCreateOptionsMenu(Menu menu, MenuInflater inflater) {
        super.onCreateOptionsMenu(menu, inflater);
        // Add items to the action bar (if it is present)
        inflater.inflate(R.menu.fragment_channel_menu, menu);

        // Search button
        MenuItem btnFilter = menu.findItem(R.id.btn_filter_channel);
        SearchView searchView = (SearchView) btnFilter.getActionView();

        // Set search hint
        searchView.setQueryHint(getText(R.string.action_search_in_channel));

        // Filter on query text change
        rxMenuSubs.add(RxSearchView.queryTextChangeEvents(searchView)
                .subscribe(new Observer<SearchViewQueryTextEvent>() {

                    public void onNext(SearchViewQueryTextEvent event) {
                        adapter.getFilter().filter(event.queryText());
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        Log.e("onCreateOptionsMenu", "queryTextChangeEvents", e);
                    }
                }));
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onPrepareOptionsMenu(Menu menu) {
        super.onPrepareOptionsMenu(menu);

        // Toggle subscribed icon
        _btnFav = menu.findItem(R.id.btn_channel_toggle_subscribed);
        _btnFav.setActionView(null);
        Intent toggleIntent = new Intent();
        if (_subscribed) {
            _btnFav.setIcon(R.drawable.ic_action_star);
            _btnFav.setTitle(R.string.action_unsubscribe);
            toggleIntent.setAction(ChannelActivity.ACTION_UNSUBSCRIBE);
        } else {
            _btnFav.setIcon(R.drawable.ic_action_star_outline);
            _btnFav.setTitle(R.string.action_subscribe);
            toggleIntent.setAction(ChannelActivity.ACTION_SUBSCRIBE);
        }
        toggleIntent.putExtra(ChannelActivity.EXTRA_DISPERSY_CID, _dispersyCid);
        _btnFav.setIntent(toggleIntent);

        // Beam button
        _btnBeam = menu.findItem(R.id.btn_beam_channel);
        NdefRecord record = NdefRecord.createMime("text/plain", _dispersyCid.getBytes());
        Intent beamIntent = MyUtils.beamIntent(record);
        _btnBeam.setIntent(beamIntent);

        // Set title
        if (context instanceof AppCompatActivity) {
            ActionBar actionBar = ((AppCompatActivity) context).getSupportActionBar();
            if (actionBar != null) {
                if (_subscribed) {
                    actionBar.setTitle(_name);
                } else {
                    actionBar.setTitle(String.format("%s: %s", getString(R.string.title_channel_preview), _name));
                }
            }
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean handleMessage(Message message) {
        if (message.obj instanceof TorrentDiscoveredEvent) {
            TorrentDiscoveredEvent event = (TorrentDiscoveredEvent) message.obj;

            // Check if torrent belongs to this channel
            if (_dispersyCid != null && _dispersyCid.equals(event.getDispersyCid())) {
                Log.v("AddedToChannel", String.format("%s dispersy_cid: %s (%s)", event.getName(), event.getDispersyCid(), event.getInfohash()));

                if (event.getInfohash() != null) {
                    adapter.addObject(new TriblerTorrent(event));
                }
            }
        } else if (message.obj instanceof TorrentRemovedFromChannelEvent) {
            TorrentRemovedFromChannelEvent event = (TorrentRemovedFromChannelEvent) message.obj;

            // Check if torrent belongs to this channel
            if (_channelId != -1 && _channelId == event.getChannelId()) {
                Log.v("RemovedFromChannel", String.format("channel_id: %s (%s)", event.getChannelId(), event.getInfohash()));

                if (event.getInfohash() != null) {
                    adapter.removeObject(new TriblerTorrent(event));
                }
            }
        }
        return true;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected void reload() {
        super.reload();
        loadTorrents();
    }

    void loadTorrents() {
        showLoading(true);

        rxSubs.add(service.getTorrents(_dispersyCid, 1)
                .subscribeOn(Schedulers.io())
                .retryWhen(MyUtils::twoSecondsDelay)
                .flatMap(response -> Observable.from(response.getTorrents()))
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<TriblerTorrent>() {

                    public void onNext(TriblerTorrent torrent) {
                        if (torrent.getInfohash() != null && torrent.getSize() > 0) {
                            adapter.addObject(torrent);
                        } else {
                            Log.v("ChannelTorrent", String.format("%s size: %d (%s)", torrent.getName(), torrent.getSize(), torrent.getInfohash()));
                        }
                    }

                    public void onCompleted() {
                        showLoading(false);
                    }

                    public void onError(Throwable e) {
                        MyUtils.onError(ChannelFragment.this, "loadTorrents", e);
                    }
                }));
    }

    Observable<SubscribedAck> subscribe() {
        // null if original intent of ChannelActivity was to subscribe only
        if (_btnFav != null) {
            _btnFav.setActionView(R.layout.action_view_loading);
        } else {
            showLoading(R.string.status_subscribing);
        }
        return super.subscribe(_dispersyCid, _name).doOnCompleted(() -> _subscribed = true);
    }

    Observable<UnsubscribedAck> unsubscribe() {
        // null if original intent of ChannelActivity was to un-subscribe only
        if (_btnFav != null) {
            _btnFav.setActionView(R.layout.action_view_loading);
        } else {
            showLoading(R.string.status_unsubscribing);
        }
        return super.unsubscribe(_dispersyCid, _name).doOnCompleted(() -> _subscribed = false);
    }
}
