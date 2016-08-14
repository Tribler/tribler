package org.tribler.android;

import android.content.Intent;
import android.os.Bundle;
import android.support.annotation.LayoutRes;
import android.support.v4.app.NavUtils;
import android.support.v7.app.ActionBar;
import android.support.v7.app.AppCompatActivity;
import android.support.v7.widget.Toolbar;
import android.util.Log;
import android.view.MenuItem;

import butterknife.BindView;
import butterknife.ButterKnife;
import rx.subscriptions.CompositeSubscription;

/**
 * Use ButterKnife to automatically bind fields.
 * <p>
 * Use RxJava CompositeSubscription to automatically un-subscribe onDestroy and invalidateOptionsMenu.
 */
public abstract class BaseActivity extends AppCompatActivity {

    @BindView(R.id.toolbar)
    Toolbar toolbar;

    protected CompositeSubscription rxSubs;
    protected CompositeSubscription rxMenuSubs;

    /**
     * {@inheritDoc}
     */
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Log.v(this.getClass().getSimpleName(), "onCreate");

        rxSubs = new CompositeSubscription();
        rxMenuSubs = new CompositeSubscription();
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

        rxMenuSubs.unsubscribe();
        rxMenuSubs = null;
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

        // The action bar will automatically handle clicks on the Home/Up button,
        // so long as you specify a parent activity in AndroidManifest.xml
        setSupportActionBar(toolbar);
        ActionBar actionbar = getSupportActionBar();
        if (actionbar != null && layoutResID != R.layout.activity_main) {
            actionbar.setDisplayHomeAsUpEnabled(true);
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void invalidateOptionsMenu() {
        super.invalidateOptionsMenu();
        rxMenuSubs.unsubscribe();
        rxMenuSubs.clear();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean onOptionsItemSelected(MenuItem item) {
        // Respond to the action bar's Up/Home button
        if (android.R.id.home == item.getItemId() && NavUtils.getParentActivityName(this) == null) {
            // Redirect SupportActionBar back button to regular back button
            onBackPressed();
            return true;
        }
        return super.onOptionsItemSelected(item);
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
