package org.tribler.android;

import android.content.Intent;
import android.os.Bundle;
import android.text.TextUtils;
import android.view.MenuItem;

import org.tribler.android.restapi.json.SubscribedAck;
import org.tribler.android.restapi.json.UnsubscribedAck;

import rx.Observer;
import rx.android.schedulers.AndroidSchedulers;

public class ChannelActivity extends BaseActivity {

    public static final String ACTION_SUBSCRIBE = "org.tribler.android.channel.SUBSCRIBE";
    public static final String ACTION_UNSUBSCRIBE = "org.tribler.android.channel.UNSUBSCRIBE";

    public static final String EXTRA_DISPERSY_CID = "org.tribler.android.channel.dispersy.CID";
    public static final String EXTRA_CHANNEL_ID = "org.tribler.android.channel.ID";
    public static final String EXTRA_NAME = "org.tribler.android.channel.NAME";
    public static final String EXTRA_DESCRIPTION = "org.tribler.android.channel.DESCRIPTION";
    public static final String EXTRA_SUBSCRIBED = "org.tribler.android.channel.SUBSCRIBED";

    private ChannelFragment _fragment;

    /**
     * {@inheritDoc}
     */
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_channel);

        _fragment = (ChannelFragment) getSupportFragmentManager().findFragmentById(R.id.fragment_channel);
        _fragment.setRetainInstance(true);

        handleIntent(getIntent());
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected void onDestroy() {
        super.onDestroy();
        _fragment = null;
    }

    protected void handleIntent(Intent intent) {
        String action = intent.getAction();
        if (TextUtils.isEmpty(action)) {
            return;
        }
        final String dispersyCid = intent.getStringExtra(EXTRA_DISPERSY_CID);

        switch (action) {

            case Intent.ACTION_GET_CONTENT:
                _fragment.loadTorrents();
                return;

            case ACTION_SUBSCRIBE:
                rxSubs.add(_fragment.subscribe()
                        .observeOn(AndroidSchedulers.mainThread())
                        .subscribe(new Observer<SubscribedAck>() {

                            public void onNext(SubscribedAck subscribedAck) {
                                /** @see DefaultInteractionListFragment
                                 */
                            }

                            public void onCompleted() {
                                Intent result = new Intent();
                                result.putExtra(EXTRA_DISPERSY_CID, dispersyCid);
                                result.putExtra(EXTRA_SUBSCRIBED, true);

                                // Flag modification
                                setResult(RESULT_FIRST_USER, result);

                                // Original intent was to subscribe only?
                                if (ACTION_SUBSCRIBE.equals(getIntent().getAction())) {
                                    finish();
                                } else {
                                    // Update view
                                    invalidateOptionsMenu();
                                }
                            }

                            public void onError(Throwable e) {
                            }
                        }));
                return;

            case ACTION_UNSUBSCRIBE:
                rxSubs.add(_fragment.unsubscribe()
                        .observeOn(AndroidSchedulers.mainThread())
                        .subscribe(new Observer<UnsubscribedAck>() {

                            public void onNext(UnsubscribedAck unsubscribedAck) {
                                /** @see DefaultInteractionListFragment
                                 */
                            }

                            public void onCompleted() {
                                Intent result = new Intent();
                                result.putExtra(EXTRA_DISPERSY_CID, dispersyCid);
                                result.putExtra(EXTRA_SUBSCRIBED, false);

                                // Flag modification
                                setResult(RESULT_FIRST_USER, result);

                                // Original intent was to un-subscribe only?
                                if (ACTION_UNSUBSCRIBE.equals(getIntent().getAction())) {
                                    finish();
                                } else {
                                    // Update view
                                    invalidateOptionsMenu();
                                }
                            }

                            public void onError(Throwable e) {
                            }
                        }));
                return;
        }
    }

    public void btnFavoriteClicked(MenuItem item) {
        handleIntent(item.getIntent());
    }

}
