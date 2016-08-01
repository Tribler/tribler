package org.tribler.android;

import android.content.Intent;
import android.os.Bundle;
import android.support.annotation.LayoutRes;
import android.support.v7.app.AppCompatActivity;
import android.support.v7.widget.Toolbar;
import android.util.Log;

import butterknife.BindView;
import butterknife.ButterKnife;
import rx.subscriptions.CompositeSubscription;

/**
 * Use ButterKnife to automatically bind fields.
 * <p>
 * Use RxJava CompositeSubscription to automatically un-subscribe onDestroy.
 */
public abstract class BaseActivity extends AppCompatActivity {

    @BindView(R.id.toolbar)
    Toolbar toolbar;

    protected CompositeSubscription rxSubs;

    /**
     * {@inheritDoc}
     */
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Log.v(this.getClass().getSimpleName(), "onCreate");

        rxSubs = new CompositeSubscription();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected void onDestroy() {
        super.onDestroy();
        Log.v(this.getClass().getSimpleName(), "onDestroy");

        // Memory leak detection
        MyUtils.getRefWatcher(this).watch(this);

        rxSubs.unsubscribe();
        rxSubs = null;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void setContentView(@LayoutRes int layoutResID) {
        super.setContentView(layoutResID);
        ButterKnife.bind(this);

        setSupportActionBar(toolbar);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        Log.v(this.getClass().getSimpleName(), String.format("onNewIntent: %s", intent.getAction()));

        setIntent(intent);
        handleIntent(intent);
    }

    protected abstract void handleIntent(Intent intent);
}
