package org.tribler.android;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.util.Log;
import android.widget.Toast;

import org.tribler.android.restapi.json.StartedAck;
import org.tribler.android.restapi.json.StartedDownloadAck;
import org.tribler.android.restapi.json.SubscribedAck;
import org.tribler.android.restapi.json.TriblerChannel;
import org.tribler.android.restapi.json.TriblerTorrent;
import org.tribler.android.restapi.json.UnsubscribedAck;
import org.tribler.android.restapi.json.VariablesResponse;

import java.io.File;
import java.util.Map;

import retrofit2.adapter.rxjava.HttpException;
import rx.Observable;
import rx.Observer;
import rx.android.schedulers.AndroidSchedulers;
import rx.schedulers.Schedulers;

public class DefaultInteractionListFragment extends ListFragment implements ListFragment.IListFragmentInteractionListener {

    public static final int CHANNEL_ACTIVITY_REQUEST_CODE = 301;

    private int videoServerPort = -1;

    /**
     * {@inheritDoc}
     */
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getVariables();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onAttach(Context context) {
        super.onAttach(context);
        setListInteractionListener(this);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onClick(final TriblerChannel channel) {
        Intent intent = MyUtils.viewChannelIntent(channel.getDispersyCid(), channel.getId(), channel.getName(), channel.isSubscribed());
        startActivityForResult(intent, CHANNEL_ACTIVITY_REQUEST_CODE);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onActivityResult(int requestCode, int resultCode, Intent data) {
        switch (requestCode) {

            case CHANNEL_ACTIVITY_REQUEST_CODE:
                switch (resultCode) {

                    case Activity.RESULT_FIRST_USER:
                        // Update the subscription status of the channel identified by dispersy_cid
                        String dispersyCid = data.getStringExtra(ChannelActivity.EXTRA_DISPERSY_CID);
                        boolean subscribed = data.getBooleanExtra(ChannelActivity.EXTRA_SUBSCRIBED, false);

                        TriblerChannel channel = adapter.findByDispersyCid(dispersyCid);
                        if (channel != null) {
                            channel.setSubscribed(subscribed);
                            // Update view
                            adapter.notifyObjectChanged(channel);
                        }
                        return;
                }
                return;
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedRight(final TriblerChannel channel) {
        adapter.removeObject(channel);
        // Is already subscribed?
        if (channel.isSubscribed()) {
            Toast.makeText(context, String.format(context.getString(R.string.info_subscribe_already), channel.getName()), Toast.LENGTH_SHORT).show();
        } else {
            subscribe(channel.getDispersyCid(), channel.getName());
        }
    }

    Observable<SubscribedAck> subscribe(final String dispersyCid, final String name) {

        Observable<SubscribedAck> observable = service.subscribe(dispersyCid)
                .subscribeOn(Schedulers.io())
                .retryWhen(MyUtils::twoSecondsDelay)
                .share();

        rxSubs.add(observable
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<SubscribedAck>() {

                    public void onNext(SubscribedAck response) {
                        // Subscribed?
                        if (response.isSubscribed()) {
                            Toast.makeText(context, String.format(context.getString(R.string.info_subscribe_success), name), Toast.LENGTH_SHORT).show();
                        } else {
                            throw new Error(String.format("Not subscribed to channel: %s \"%s\"", dispersyCid, name));
                        }
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        if (e instanceof HttpException && ((HttpException) e).code() == 409) {
                            // Already subscribed
                            Toast.makeText(context, String.format(context.getString(R.string.info_subscribe_already), name), Toast.LENGTH_SHORT).show();
                        } else {
                            MyUtils.onError(DefaultInteractionListFragment.this, "subscribe", e);
                        }
                    }
                }));

        return observable;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedLeft(final TriblerChannel channel) {
        adapter.removeObject(channel);
        // Is already un-subscribed?
        if (!channel.isSubscribed()) {
            Toast.makeText(context, String.format(context.getString(R.string.info_unsubscribe_already), channel.getName()), Toast.LENGTH_SHORT).show();
        } else {
            unsubscribe(channel.getDispersyCid(), channel.getName());
        }
    }

    Observable<UnsubscribedAck> unsubscribe(final String dispersyCid, final String name) {

        Observable<UnsubscribedAck> observable = service.unsubscribe(dispersyCid)
                .subscribeOn(Schedulers.io())
                .retryWhen(MyUtils::twoSecondsDelay)
                .share();

        rxSubs.add(observable
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<UnsubscribedAck>() {

                    public void onNext(UnsubscribedAck response) {
                        // Un-subscribed?
                        if (response.isUnsubscribed()) {
                            Toast.makeText(context, String.format(context.getString(R.string.info_unsubscribe_success), name), Toast.LENGTH_SHORT).show();
                        } else {
                            throw new Error(String.format("Not unsubscribed form channel: %s \"%s\"", dispersyCid, name));
                        }
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        if (e instanceof HttpException && ((HttpException) e).code() == 404) {
                            // Already subscribed
                            Toast.makeText(context, String.format(context.getString(R.string.info_unsubscribe_already), name), Toast.LENGTH_SHORT).show();
                        } else {
                            MyUtils.onError(DefaultInteractionListFragment.this, "unsubscribe", e);
                        }
                    }
                }));

        return observable;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onClick(final TriblerTorrent torrent) {
        File destination = new File(getContext().getExternalCacheDir(), torrent.getName());
        destination.mkdirs();

        rxSubs.add(startDownload(torrent.getInfohash(), torrent.getName(), destination)
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<StartedAck>() {

                    public void onNext(StartedAck response) {
                        if (response.isStarted()) {
                            // Notify user
                            String category = torrent.getCategory();
                            if (category == null) {
                                category = "";
                            }
                            switch (category) {
                                case "Video":
                                    Toast.makeText(context, "Watch now", Toast.LENGTH_SHORT).show();
                                    break;

                                case "Audio":
                                    Toast.makeText(context, "Listen now", Toast.LENGTH_SHORT).show();
                                    break;

                                case "Document":
                                    Toast.makeText(context, "Read now", Toast.LENGTH_SHORT).show();
                                    break;

                                case "Compressed":
                                case "xxx":
                                case "other":
                                    Toast.makeText(context, "Download now", Toast.LENGTH_SHORT).show();
                                    break;
                            }
                        }
                        Log.v("videoServerPort", " = " + videoServerPort);

                        if (videoServerPort > 0) {
                            // Play video
                            Uri uri = Uri.parse("http://127.0.0.1:" + videoServerPort + "/" + torrent.getInfohash() + "/0");
                            Intent viewIntent = MyUtils.viewVideoIntent(uri, torrent.getName());
                            startActivity(viewIntent);
                        } else {
                            //TODO: retry
                        }
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        Log.v("videoServerPort", " = " + videoServerPort);

                        // Play video
                        Uri uri = Uri.parse("http://127.0.0.1:" + videoServerPort + "/" + torrent.getInfohash() + "/0");
                        Intent viewIntent = MyUtils.viewVideoIntent(uri, torrent.getName());
                        startActivity(viewIntent);
                    }
                }));

    }

    Observable<StartedDownloadAck> startDownload(final Uri uri, final String name, final File destination) {
        Log.v("startDownload", String.format("Starting download: %s \"%s\" %s", uri.toString(), name, destination.getAbsolutePath()));

        Observable<StartedDownloadAck> observable = service.startDownload(uri, 0, 0, destination.getAbsolutePath())
                .subscribeOn(Schedulers.io())
                .retryWhen(MyUtils::twoSecondsDelay)
                .share();

        rxSubs.add(observable
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<StartedDownloadAck>() {

                    public void onNext(StartedDownloadAck response) {
                        // Started?
                        if (response.isStarted()) {
                            Log.v("startDownload", String.format("Download started: %s \"%s\"", response.getInfohash(), name));

                            Toast.makeText(context, String.format(context.getString(R.string.info_start_download_success), name), Toast.LENGTH_SHORT).show();
                        } else {
                            throw new Error(String.format("Failed to start download: %s \"%s\"", response.getInfohash(), name));
                        }
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        if (e instanceof HttpException && ((HttpException) e).code() == 500) { //FIXME: 500
                            // Already started
                            Toast.makeText(context, String.format(context.getString(R.string.info_start_download_already), name), Toast.LENGTH_SHORT).show();
                        } else if (e instanceof HttpException && ((HttpException) e).code() == 400) {
                            Log.e("startDownload", "error", e);
                            // Failed to start
                            Toast.makeText(context, String.format(context.getString(R.string.info_start_download_failure), name), Toast.LENGTH_SHORT).show();
                        } else {
                            MyUtils.onError(DefaultInteractionListFragment.this, "startDownload", e);
                        }
                    }
                }));

        return observable;
    }

    Observable<StartedAck> startDownload(final String infohash, final String name, final File destination) {
        Log.v("startDownload", String.format("Starting download: %s \"%s\" %s", infohash, name, destination.getAbsolutePath()));

        Observable<StartedAck> observable = service.startDownload(infohash, 0, 0, destination.getAbsolutePath())
                .subscribeOn(Schedulers.io())
                .retryWhen(MyUtils::twoSecondsDelay)
                .share();

        rxSubs.add(observable
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<StartedAck>() {

                    public void onNext(StartedAck response) {
                        // Started?
                        if (response.isStarted()) {
                            Log.v("startDownload", String.format("Download started: %s \"%s\"", infohash, name));

                            Toast.makeText(context, String.format(context.getString(R.string.info_start_download_success), name), Toast.LENGTH_SHORT).show();
                        } else {
                            throw new Error(String.format("Failed to start download: %s \"%s\"", infohash, name));
                        }
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        if (e instanceof HttpException && ((HttpException) e).code() == 409) {
                            // Already started
                            Toast.makeText(context, String.format(context.getString(R.string.info_start_download_already), name), Toast.LENGTH_SHORT).show();
                        } else if (e instanceof HttpException && ((HttpException) e).code() == 400) {
                            Log.e("startDownload", "error", e);
                            // Failed to start
                            Toast.makeText(context, String.format(context.getString(R.string.info_start_download_failure), name), Toast.LENGTH_SHORT).show();
                        } else {
                            MyUtils.onError(DefaultInteractionListFragment.this, "startDownload", e);
                        }
                    }
                }));

        return observable;
    }

    Observable<VariablesResponse> getVariables() {

        Observable<VariablesResponse> observable = service.getVariables()
                .subscribeOn(Schedulers.io())
                .retryWhen(MyUtils::twoSecondsDelay)
                .share();

        rxSubs.add(observable
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<VariablesResponse>() {

                    public void onNext(VariablesResponse response) {
                        Log.v("getVariables", response.getVariables().toString());

                        // Get video server port
                        Map<String, Map<String, Object>> settings = response.getVariables();
                        if (settings.containsKey("ports")) {
                            Map<String, Object> ports = settings.get("ports");
                            if (ports.containsKey("video~port")) {
                                Object port = ports.get("video~port");
                                if (port instanceof Integer) {
                                    videoServerPort = (int) port;
                                } else if (port instanceof String) {
                                    videoServerPort = Integer.valueOf((String) port);
                                } else if (port instanceof Double) {
                                    videoServerPort = ((Double) port).intValue();
                                }
                                Log.v("getVariables", "video server port = " + videoServerPort);
                            }
                        }
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        MyUtils.onError(DefaultInteractionListFragment.this, "getVariables", e);
                    }
                }));

        return observable;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedRight(final TriblerTorrent torrent) {
        adapter.removeObject(torrent);

        // watch later?
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedLeft(final TriblerTorrent torrent) {
        adapter.removeObject(torrent);

        // not interested, never see again?
    }

}
