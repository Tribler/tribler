package org.tribler.android;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.net.ConnectivityManager;
import android.net.Uri;
import android.net.wifi.WifiManager;
import android.os.Bundle;
import android.support.annotation.Nullable;
import android.support.design.widget.NavigationView;
import android.support.v4.app.Fragment;
import android.support.v4.app.FragmentManager;
import android.support.v4.view.GravityCompat;
import android.support.v4.widget.DrawerLayout;
import android.support.v7.app.ActionBarDrawerToggle;
import android.support.v7.app.AppCompatDelegate;
import android.text.TextUtils;
import android.util.Log;
import android.view.Menu;
import android.view.MenuItem;
import android.view.View;
import android.widget.ProgressBar;
import android.widget.Toast;

import com.cantrowitz.rxbroadcast.RxBroadcast;

import org.tribler.android.restapi.EventStream;
import org.tribler.android.restapi.IEventListener;
import org.tribler.android.restapi.IRestApi;
import org.tribler.android.restapi.TriblerService;
import org.tribler.android.restapi.json.EventsStartEvent;
import org.tribler.android.restapi.json.ShutdownAck;
import org.tribler.android.service.Triblerd;

import java.io.File;
import java.io.IOException;

import butterknife.BindView;
import rx.Observer;
import rx.android.schedulers.AndroidSchedulers;
import rx.schedulers.Schedulers;

public class MainActivity extends BaseActivity implements IEventListener {

    public static final int CAPTURE_VIDEO_ACTIVITY_REQUEST_CODE = 200;

    static {
        AppCompatDelegate.setCompatVectorFromResourcesEnabled(true);
    }

    @BindView(R.id.drawer_layout)
    DrawerLayout drawer;

    @BindView(R.id.nav_view)
    NavigationView navigationView;

    @BindView(R.id.progress_bar)
    ProgressBar progressBar;

    private ActionBarDrawerToggle _navToggle;
    private ConnectivityManager _connectivityManager;
    private IRestApi _service;

    private void initService() {
        // Check network connection before starting service
        if (MyUtils.isNetworkConnected(_connectivityManager)) {

            Triblerd.start(this); // Run normally
            //Twistd.start(this); // Run profiler
            //NoseTestService.start(this); // Run tests
            //ExperimentService.start(this); // Run experiment

        } else {
            Toast.makeText(this, R.string.info_no_connection, Toast.LENGTH_LONG).show();
        }
    }

    private void killService() {
        Triblerd.stop(this);
        //Twistd.stop(this);
        //NoseTestService.stop(this);
        //ExperimentService.stop(this);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        // Hamburger icon
        _navToggle = new ActionBarDrawerToggle(this, drawer, toolbar, R.string.navigation_drawer_open, R.string.navigation_drawer_close);
        drawer.addDrawerListener(_navToggle);
        _navToggle.syncState();

        //Stetho.initializeWithDefaults(getApplicationContext()); //DEBUG

        initConnectionManager();
        initService();

        EventStream.addListener(this);
        EventStream.openEventStream();

        String baseUrl = getString(R.string.service_url) + ":" + getString(R.string.service_port_number);
        String authToken = getString(R.string.service_auth_token);
        _service = TriblerService.createService(baseUrl, authToken);

        handleIntent(getIntent());
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected void onDestroy() {
        drawer.removeDrawerListener(_navToggle);
        super.onDestroy();
        _navToggle = null;
        _connectivityManager = null;
        _service = null;
    }

    public void onEvent(Object event) {
        Log.w("onEvent", " " + event);

        if (event instanceof EventsStartEvent) {
            runOnUiThread(() -> {
                // Hide loading bar
                progressBar.setVisibility(View.GONE);
            });
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onBackPressed() {
        if (drawer.isDrawerOpen(GravityCompat.START)) {
            drawer.closeDrawer(GravityCompat.START);
        } else {
            super.onBackPressed();
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected void handleIntent(Intent intent) {
        String action = intent.getAction();
        if (TextUtils.isEmpty(action)) {
            return;
        }
        switch (action) {
            case Intent.ACTION_MAIN:
                // Startup action
                //TODO: show loading screen until rest api connected
                return;

            case ConnectivityManager.CONNECTIVITY_ACTION:
            case WifiManager.NETWORK_STATE_CHANGED_ACTION:
            case WifiManager.WIFI_STATE_CHANGED_ACTION:

                // Warn user if connection is lost
                if (!MyUtils.isNetworkConnected(_connectivityManager)) {
                    Toast.makeText(MainActivity.this, R.string.warning_lost_connection, Toast.LENGTH_LONG).show();
                }
                return;
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        // Result of capture video
        if (requestCode == CAPTURE_VIDEO_ACTIVITY_REQUEST_CODE) {
            if (resultCode == Activity.RESULT_OK) {
                Toast.makeText(this, "Video saved to: " + data.getData(), Toast.LENGTH_LONG).show();
                //TODO: create torrent file and add to own channel
            } else if (resultCode == Activity.RESULT_CANCELED) {

            } else {
                Toast.makeText(this, R.string.error_capture_video, Toast.LENGTH_LONG).show();
            }
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        super.onCreateOptionsMenu(menu);
        // Add items to the action bar (if it is present)
        getMenuInflater().inflate(R.menu.menu_main, menu);
        return true;
    }

    public void btnSearchClicked(@Nullable MenuItem item) {
        Intent intent = new Intent(this, SearchActivity.class);
        startActivity(intent);
    }

    /**
     * @param newFragmentClass The desired fragment class
     */
    private void switchFragment(Class newFragmentClass) throws IllegalAccessException, InstantiationException {
        FragmentManager fragmentManager = getSupportFragmentManager();
        // Check if current fragment is desired fragment
        Fragment current = fragmentManager.findFragmentById(R.id.fragment_main);
        if (!newFragmentClass.isInstance(current)) {
            String tag = newFragmentClass.getSimpleName();
            // Check if desired fragment is already instantiated
            Fragment fragment = fragmentManager.findFragmentByTag(tag);
            if (fragment == null) {
                fragment = (Fragment) newFragmentClass.newInstance();
                fragment.setRetainInstance(true);
            }
            fragmentManager
                    .beginTransaction()
                    .replace(R.id.fragment_main, fragment, tag)
                    .commit();
        }
    }

    public void navSubscriptionsClicked(@Nullable MenuItem item) throws InstantiationException, IllegalAccessException {
        drawer.closeDrawer(GravityCompat.START);
        switchFragment(SubscribedFragment.class);
    }

    public void navMyChannelClicked(@Nullable MenuItem item) {
        drawer.closeDrawer(GravityCompat.START);
        //TODO: my channel
    }

    public void navMyPlaylistsClicked(@Nullable MenuItem item) {
        drawer.closeDrawer(GravityCompat.START);
    }

    public void navPopularClicked(@Nullable MenuItem item) throws InstantiationException, IllegalAccessException {
        drawer.closeDrawer(GravityCompat.START);
        switchFragment(DiscoveredFragment.class);
    }

    public void navCaptureVideoClicked(@Nullable MenuItem item) {
        drawer.closeDrawer(GravityCompat.START);
        // Check if device has camera
        if (getPackageManager().hasSystemFeature(PackageManager.FEATURE_CAMERA)) {
            // Obtain output file
            try {
                File output = MyUtils.getOutputVideoFile(this);
                Intent captureIntent = MyUtils.captureVideo(Uri.fromFile(output));
                startActivityForResult(captureIntent, CAPTURE_VIDEO_ACTIVITY_REQUEST_CODE);
            } catch (IOException ex) {
                Log.e("getOutputVideoFile", getString(R.string.error_output_file), ex);
                Toast.makeText(this, R.string.error_output_file, Toast.LENGTH_LONG).show();
            }
        }
    }

    public void navBeamClicked(@Nullable MenuItem item) {
        drawer.closeDrawer(GravityCompat.START);
        File apk = new File(this.getPackageResourcePath());
        Intent beamIntent = MyUtils.sendBeam(Uri.fromFile(apk), this);
        startActivity(beamIntent);
    }

    public void navSettingsClicked(@Nullable MenuItem item) {
        drawer.closeDrawer(GravityCompat.START);
    }

    public void navFeedbackClicked(@Nullable MenuItem item) {
        drawer.closeDrawer(GravityCompat.START);
        CharSequence title = getText(R.string.app_feedback_url);
        Uri uri = Uri.parse(title.toString());
        Intent browserIntent = MyUtils.viewChooser(uri, title);
        startActivity(browserIntent);
    }

    public void navShutdownClicked(@Nullable MenuItem item) {
        drawer.closeDrawer(GravityCompat.START);
        rxSubs.add(_service.shutdown()
                .subscribeOn(Schedulers.io())
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<ShutdownAck>() {

                    public void onNext(ShutdownAck response) {
                        Log.v("navShutdownClicked", response.toString());
                    }

                    public void onCompleted() {
                        // Stop MainActivity
                        finish();
                    }

                    public void onError(Throwable e) {
                        // Kill process
                        killService();

                        // Stop MainActivity
                        finish();
                    }
                }));
    }

    private void initConnectionManager() {
        _connectivityManager =
                (ConnectivityManager) getApplicationContext().getSystemService(Context.CONNECTIVITY_SERVICE);

        Observer observer = new Observer<Intent>() {

            public void onNext(Intent intent) {
                onNewIntent(intent);
            }

            public void onCompleted() {
            }

            public void onError(Throwable e) {
            }
        };

        // Listen for connectivity changes
        rxSubs.add(RxBroadcast.fromBroadcast(this, new IntentFilter(ConnectivityManager.CONNECTIVITY_ACTION))
                .subscribe(observer));

        // Listen for network state changes
        rxSubs.add(RxBroadcast.fromBroadcast(this, new IntentFilter(WifiManager.NETWORK_STATE_CHANGED_ACTION))
                .subscribe(observer));

        // Listen for Wi-Fi state changes
        rxSubs.add(RxBroadcast.fromBroadcast(this, new IntentFilter(WifiManager.WIFI_STATE_CHANGED_ACTION))
                .subscribe(observer));
    }
}
