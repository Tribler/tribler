package org.tribler.android;

import android.content.Intent;
import android.os.Bundle;
import android.support.annotation.Nullable;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;

import org.tribler.android.restapi.json.TriblerTorrent;

import rx.Observer;
import rx.android.schedulers.AndroidSchedulers;
import rx.schedulers.Schedulers;

public class TorrentFragment extends ViewFragment {

    private String _dispersyCid;
    private String _infohash;

    /**
     * {@inheritDoc}
     */
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        Intent intent = getActivity().getIntent();
        _dispersyCid = intent.getStringExtra(ChannelActivity.EXTRA_DISPERSY_CID);
        _infohash = intent.getStringExtra(TorrentActivity.EXTRA_TORRENT_INFOHASH);

        loadTorrent();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public View onCreateView(LayoutInflater inflater, @Nullable ViewGroup container, @Nullable Bundle savedInstanceState) {
        return inflater.inflate(R.layout.fragment_torrent, container, false);
    }

    private void loadTorrent() {
        rxSubs.add(service.getTorrent(_dispersyCid, _infohash)
                .subscribeOn(Schedulers.io())
                .retryWhen(MyUtils::twoSecondsDelay)
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<TriblerTorrent>() {

                    public void onNext(TriblerTorrent torrent) {
                        //TODO
                    }

                    public void onCompleted() {

                    }

                    public void onError(Throwable e) {

                    }
                }));
    }
}
