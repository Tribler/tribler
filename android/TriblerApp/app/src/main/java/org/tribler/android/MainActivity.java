package org.tribler.android;

import android.Manifest;
import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.net.ConnectivityManager;
import android.net.Uri;
import android.net.wifi.WifiManager;
import android.net.wifi.p2p.WifiP2pManager;
import android.nfc.NdefMessage;
import android.nfc.NdefRecord;
import android.nfc.NfcAdapter;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.Message;
import android.os.Parcelable;
import android.os.Process;
import android.support.annotation.NonNull;
import android.support.annotation.Nullable;
import android.support.annotation.StringRes;
import android.support.design.widget.NavigationView;
import android.support.design.widget.Snackbar;
import android.support.v4.app.ActivityCompat;
import android.support.v4.app.Fragment;
import android.support.v4.app.FragmentManager;
import android.support.v4.content.ContextCompat;
import android.support.v4.view.GravityCompat;
import android.support.v4.widget.DrawerLayout;
import android.support.v7.app.ActionBarDrawerToggle;
import android.support.v7.app.AlertDialog;
import android.support.v7.app.AppCompatDelegate;
import android.text.TextUtils;
import android.util.Log;
import android.view.Menu;
import android.view.MenuItem;
import android.view.View;
import android.widget.TextView;
import android.widget.Toast;

import com.cantrowitz.rxbroadcast.RxBroadcast;
import com.facebook.stetho.Stetho;

import org.tribler.android.restapi.EventStream;
import org.tribler.android.restapi.IRestApi;
import org.tribler.android.restapi.TriblerService;
import org.tribler.android.restapi.json.EventsStartEvent;
import org.tribler.android.restapi.json.ShutdownAck;
import org.tribler.android.service.TriblerdService;

import java.io.File;
import java.io.IOException;

import butterknife.BindView;
import rx.Observable;
import rx.Observer;
import rx.android.schedulers.AndroidSchedulers;
import rx.schedulers.Schedulers;

public class MainActivity extends BaseActivity implements Handler.Callback {

    public static final int CAPTURE_VIDEO_ACTIVITY_REQUEST_CODE = 101;
    public static final int SEARCH_ACTIVITY_REQUEST_CODE = 102;
    public static final int SUBSCRIBE_TO_CHANNEL_ACTIVITY_REQUEST_CODE = 103;
    public static final int INSTALL_VLC_REQUEST_CODE = 104;

    public static final int WRITE_STORAGE_PERMISSION_REQUEST_CODE = 110;

    static {
        // Backwards compatibility for vector graphics
        AppCompatDelegate.setCompatVectorFromResourcesEnabled(true);
    }

    @BindView(R.id.drawer_layout)
    DrawerLayout drawer;

    @BindView(R.id.nav_view)
    NavigationView navigationView;

    @BindView(R.id.main_progress)
    View progressView;

    @BindView(R.id.main_progress_status)
    TextView statusBar;

    private ActionBarDrawerToggle _navToggle;
    private ConnectivityManager _connectivityManager;
    private Handler _eventHandler;
    private IRestApi _service;

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

        Stetho.initializeWithDefaults(getApplicationContext()); //DEBUG

        // VLC installed?
        if (!MyUtils.isPackageInstalled(getString(R.string.vlc_package_name), this)) {
            askUserToInstallVlc();
        }

        initConnectivityManager();

        // Start listening to events on the main thread so the gui can be updated
        _eventHandler = new Handler(Looper.getMainLooper(), this);
        EventStream.addHandler(_eventHandler);

        if (!EventStream.isReady()) {
            showLoading(R.string.status_opening_eventstream);
            EventStream.openEventStream();
        }

        // Write permissions on sdcard?
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.WRITE_EXTERNAL_STORAGE) != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, new String[]{Manifest.permission.WRITE_EXTERNAL_STORAGE}, WRITE_STORAGE_PERMISSION_REQUEST_CODE);
        } else {
            startService();
        }

        // Create API client
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
        EventStream.removeHandler(_eventHandler);
        super.onDestroy();
        _navToggle = null;
        _connectivityManager = null;
        _eventHandler = null;
        _service = null;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean handleMessage(Message message) {
        if (message.obj instanceof EventsStartEvent) {
            showLoading(false);

            // Stop listening to event stream
            EventStream.removeHandler(_eventHandler);
        }
        return true;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected void handleIntent(Intent intent) {
        String action = intent.getAction();
        // Handle intent only once
        if (!TextUtils.isEmpty(action)) {
            intent.setAction(null);
        } else {
            return;
        }
        switch (action) {

            case Intent.ACTION_MAIN:
                drawer.openDrawer(GravityCompat.START);
                return;

            case ConnectivityManager.CONNECTIVITY_ACTION:
            case WifiManager.NETWORK_STATE_CHANGED_ACTION:
            case WifiManager.WIFI_STATE_CHANGED_ACTION:
            case WifiP2pManager.WIFI_P2P_STATE_CHANGED_ACTION:
            case WifiP2pManager.WIFI_P2P_DISCOVERY_CHANGED_ACTION:
            case WifiP2pManager.WIFI_P2P_PEERS_CHANGED_ACTION:
            case WifiP2pManager.WIFI_P2P_CONNECTION_CHANGED_ACTION:
            case WifiP2pManager.WIFI_P2P_THIS_DEVICE_CHANGED_ACTION:

                // Warn user if connection is lost
                if (!MyUtils.isNetworkConnected(_connectivityManager)) {
                    Toast.makeText(MainActivity.this, R.string.warning_lost_connection, Toast.LENGTH_SHORT).show();
                }
                return;

            case NfcAdapter.ACTION_NDEF_DISCOVERED:
                Log.v("ACTION_NDEF_DISCOVERED", String.format("%b", intent.hasExtra(NfcAdapter.EXTRA_NDEF_MESSAGES)));

                Parcelable[] rawMsgs = intent.getParcelableArrayExtra(NfcAdapter.EXTRA_NDEF_MESSAGES);
                if (rawMsgs != null && rawMsgs.length > 0) {
                    for (Parcelable rawMsg : rawMsgs) {
                        // Decode message
                        NdefRecord[] records = ((NdefMessage) rawMsg).getRecords();
                        String dispersyCid = new String(records[0].getPayload());

                        askUserToSubscribe(dispersyCid, getString(R.string.info_received_channel));
                    }
                }
                return;

            case Intent.ACTION_SHUTDOWN:
                shutdown();
                return;
        }
    }

    private void askUserToSubscribe(String dispersyCid, String name) {
        AlertDialog.Builder builder = new AlertDialog.Builder(this);
        builder.setMessage(R.string.dialog_received_channel);
        builder.setPositiveButton(R.string.action_subscribe, (dialog, which) -> {
            Intent intent = MyUtils.viewChannelIntent(dispersyCid, -1, name, false);
            intent.setAction(ChannelActivity.ACTION_SUBSCRIBE);
            startActivityForResult(intent, SUBSCRIBE_TO_CHANNEL_ACTIVITY_REQUEST_CODE);
        });
        builder.setNegativeButton(R.string.action_cancel, (dialog, which) -> {
            // Do nothing
        });
        AlertDialog dialog = builder.create();
        dialog.show();
    }

    private void askUserToInstallVlc() {
        Snackbar.make(findViewById(R.id.activity_main_view), R.string.dialog_install_vlc, Snackbar.LENGTH_INDEFINITE)
                .setAction(R.string.action_INSTALL, v ->
                        rxSubs.add(Observable.fromCallable(() -> MyUtils.resolveAsset(getString(R.string.vlc_asset), this))
                                .subscribeOn(Schedulers.io())
                                .observeOn(AndroidSchedulers.mainThread())
                                .subscribe(new Observer<File>() {

                                    public void onNext(File file) {
                                        Intent intent = MyUtils.viewFileIntent(Uri.fromFile(file));
                                        startActivityForResult(intent, INSTALL_VLC_REQUEST_CODE);
                                        file.deleteOnExit();
                                    }

                                    public void onCompleted() {
                                    }

                                    public void onError(Throwable e) {
                                        Log.e("askUserToInstallVlc", "failed to resolve asset", e);
                                        // Retry
                                        askUserToInstallVlc();
                                    }
                                })))
                .setActionTextColor(ContextCompat.getColor(this, R.color.yellow))
                .show();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        switch (requestCode) {

            case CAPTURE_VIDEO_ACTIVITY_REQUEST_CODE:
                switch (resultCode) {

                    case Activity.RESULT_OK:
                        Toast.makeText(this, String.format("Video saved to: %s", data.getData()), Toast.LENGTH_LONG).show();
                        //TODO: create torrent file and add to own channel
                        return;

                    case Activity.RESULT_CANCELED:
                        Toast.makeText(this, R.string.info_cancel_capture_video, Toast.LENGTH_SHORT).show();
                        return;
                }

            case SEARCH_ACTIVITY_REQUEST_CODE:
                // Update view
                Fragment fragment = getCurrentFragment();
                if (fragment instanceof ListFragment) {
                    ((ListFragment) fragment).reload();
                }
                return;

            case SUBSCRIBE_TO_CHANNEL_ACTIVITY_REQUEST_CODE:
                switch (resultCode) {

                    case Activity.RESULT_OK:
                        // TODO: inform user
                        return;

                    case Activity.RESULT_CANCELED:
                        // TODO: inform user
                        return;
                }
                return;

            case INSTALL_VLC_REQUEST_CODE:
                // Do nothing
                return;
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onRequestPermissionsResult(int requestCode, @NonNull String[] permissions, @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        switch (requestCode) {

            case WRITE_STORAGE_PERMISSION_REQUEST_CODE:
                // If request is cancelled, the result arrays are empty
                if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                    startService();
                } else {
                    finish();
                }
                return;
        }
        // Propagate results
        Fragment fragment = getCurrentFragment();
        if (fragment != null) {
            fragment.onRequestPermissionsResult(requestCode, permissions, grantResults);
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        super.onCreateOptionsMenu(menu);
        // Add items to the action bar (if it is present)
        getMenuInflater().inflate(R.menu.activity_main_menu, menu);
        return true;
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

    protected void showLoading(@Nullable CharSequence text) {
        if (text == null) {
            progressView.setVisibility(View.GONE);
        } else {
            statusBar.setText(text);
            progressView.setVisibility(View.VISIBLE);
        }
    }

    protected void showLoading(boolean show) {
        showLoading(show ? "" : null);
    }

    protected void showLoading(@StringRes int resId) {
        showLoading(getText(resId));
    }

    private void initConnectivityManager() {
        _connectivityManager =
                (ConnectivityManager) getApplicationContext().getSystemService(Context.CONNECTIVITY_SERVICE);

        Observer observer = new Observer<Intent>() {

            public void onNext(Intent intent) {
                handleIntent(intent);
            }

            public void onCompleted() {
            }

            public void onError(Throwable e) {
                Log.v("connectivityMgr", e.getMessage(), e);
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

        // Listen for Wi-Fi direct state changes
        rxSubs.add(RxBroadcast.fromBroadcast(this, new IntentFilter(WifiP2pManager.WIFI_P2P_STATE_CHANGED_ACTION))
                .subscribe(observer));

        // Listen for Wi-Fi direct discovery changes
        rxSubs.add(RxBroadcast.fromBroadcast(this, new IntentFilter(WifiP2pManager.WIFI_P2P_DISCOVERY_CHANGED_ACTION))
                .subscribe(observer));

        // Listen for Wi-Fi direct peer changes
        rxSubs.add(RxBroadcast.fromBroadcast(this, new IntentFilter(WifiP2pManager.WIFI_P2P_PEERS_CHANGED_ACTION))
                .subscribe(observer));

        // Listen for Wi-Fi direct connection changes
        rxSubs.add(RxBroadcast.fromBroadcast(this, new IntentFilter(WifiP2pManager.WIFI_P2P_CONNECTION_CHANGED_ACTION))
                .subscribe(observer));

        // Listen for Wi-Fi direct device changes
        rxSubs.add(RxBroadcast.fromBroadcast(this, new IntentFilter(WifiP2pManager.WIFI_P2P_THIS_DEVICE_CHANGED_ACTION))
                .subscribe(observer));
    }

    @Nullable
    private Fragment getCurrentFragment() {
        return getSupportFragmentManager().findFragmentById(R.id.fragment_main);
    }

    /**
     * @param newFragmentClass The desired fragment class
     * @return True if fragment is switched, false otherwise
     */
    private boolean switchFragment(Class newFragmentClass) {
        // Check if current fragment is desired fragment
        if (!newFragmentClass.isInstance(getCurrentFragment())) {
            FragmentManager fragmentManager = getSupportFragmentManager();

            // Check if desired fragment is already instantiated
            String className = newFragmentClass.getName();
            Fragment fragment = fragmentManager.findFragmentByTag(className);
            if (fragment == null) {
                try {
                    fragment = (Fragment) newFragmentClass.newInstance();
                    fragment.setRetainInstance(true);
                } catch (InstantiationException ex) {
                    Log.e("switchFragment", className, ex);
                } catch (IllegalAccessException ex) {
                    Log.e("switchFragment", className, ex);
                }
            }
            fragmentManager
                    .beginTransaction()
                    .replace(R.id.fragment_main, fragment, className)
                    .commit();
            return true;
        }
        return false;
    }

    /**
     * @return Fragment that was removed, if any
     */
    @Nullable
    private Fragment removeFragment() {
        Fragment fragment = getCurrentFragment();
        if (fragment != null) {
            getSupportFragmentManager()
                    .beginTransaction()
                    .remove(fragment)
                    .commit();
        }
        return fragment;
    }

    public void btnSearchClicked(MenuItem item) {
        Intent intent = new Intent(this, SearchActivity.class);
        startActivityForResult(intent, SEARCH_ACTIVITY_REQUEST_CODE);
    }

    public void navSubscriptionsClicked(MenuItem item) {
        drawer.closeDrawer(GravityCompat.START);
        switchFragment(SubscribedFragment.class);
    }

    public void navMyChannelClicked(MenuItem item) {
        drawer.closeDrawer(GravityCompat.START);
        switchFragment(MyChannelFragment.class);
    }

    public void navMyPlaylistsClicked(MenuItem item) {
    }

    public void navPopularClicked(MenuItem item) {
        drawer.closeDrawer(GravityCompat.START);
        switchFragment(PopularFragment.class);
    }

    public void navCaptureVideoClicked(MenuItem item) {
        drawer.closeDrawer(GravityCompat.START);
        // Check if device has camera
        if (getPackageManager().hasSystemFeature(PackageManager.FEATURE_CAMERA)) {
            // Obtain output file
            try {
                File output = MyUtils.getOutputVideoFile(this);
                Intent captureIntent = MyUtils.videoCaptureIntent(Uri.fromFile(output));
                startActivityForResult(captureIntent, CAPTURE_VIDEO_ACTIVITY_REQUEST_CODE);
            } catch (IOException ex) {
                Log.e("getOutputVideoFile", getString(R.string.error_output_file), ex);
                Toast.makeText(this, R.string.error_output_file, Toast.LENGTH_LONG).show();
            }
        }
    }

    public void navBeamClicked(MenuItem item) {
        drawer.closeDrawer(GravityCompat.START);
        File apk = new File(getPackageResourcePath());
        Intent beamIntent = MyUtils.beamIntent(Uri.fromFile(apk));
        startActivity(beamIntent);
    }

    public void navSettingsClicked(MenuItem item) {
    }

    public void navFeedbackClicked(MenuItem item) {
        drawer.closeDrawer(GravityCompat.START);
        String url = getString(R.string.app_feedback_url);
        Intent browse = MyUtils.viewUriIntent(Uri.parse(url));
        // Ask user to open url
        AlertDialog.Builder builder = new AlertDialog.Builder(this);
        builder.setMessage(url);
        builder.setPositiveButton(R.string.action_go, (dialog, which) -> {
            startActivity(browse);
        });
        builder.setNegativeButton(R.string.action_cancel, (dialog, which) -> {
            // Do nothing
        });
        AlertDialog dialog = builder.create();
        dialog.show();
    }

    public void navShutdownClicked(MenuItem item) {
        drawer.closeDrawer(GravityCompat.START);
        Intent shutdown = new Intent(Intent.ACTION_SHUTDOWN);
        // Ask user to confirm shutdown
        AlertDialog.Builder builder = new AlertDialog.Builder(this);
        builder.setMessage(R.string.dialog_shutdown);
        builder.setPositiveButton(R.string.action_shutdown_short, (dialog, which) -> {
            onNewIntent(shutdown);
        });
        builder.setNegativeButton(R.string.action_cancel, (dialog, which) -> {
            // Do nothing
        });
        AlertDialog dialog = builder.create();
        dialog.show();
    }

    public void btnMyChannelAddClicked(MenuItem item) {
        Fragment fragment = getCurrentFragment();
        if (fragment instanceof MyChannelFragment) {
            MyChannelFragment mychannel = (MyChannelFragment) fragment;
            mychannel.askUserToAddTorrent();
        }
    }

    public void btnMyChannelBeamClicked(MenuItem item) {
        Fragment fragment = getCurrentFragment();
        if (fragment instanceof MyChannelFragment) {
            MyChannelFragment mychannel = (MyChannelFragment) fragment;
            mychannel.askUserToBeamChannelId();
        }
    }

    public void btnMyChannelEditClicked(MenuItem item) {
        Fragment fragment = getCurrentFragment();
        if (fragment instanceof MyChannelFragment) {
            MyChannelFragment mychannel = (MyChannelFragment) fragment;
            mychannel.editChannel();
        }
    }

    private void shutdown() {
        // Clear view
        removeFragment();

        showLoading(R.string.status_shutting_down);

        EventStream.closeEventStream();

        rxSubs.add(_service.shutdown()
                .subscribeOn(Schedulers.io())
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<ShutdownAck>() {

                    public void onNext(ShutdownAck response) {
                        Log.v("shutdown", "grace_time = " + response.getGracetime());
                    }

                    public void onCompleted() {
                        // Stop MainActivity
                        finish();
                        Process.killProcess(Process.myPid());
                    }

                    public void onError(Throwable e) {
                        Log.v("shutdown", e.getMessage(), e);

                        // Kill process
                        killService();

                        // Stop MainActivity
                        finish();
                        Process.killProcess(Process.myPid());
                    }
                }));
    }

    protected void startService() {
        TriblerdService.start(this); // Run normally
    }

    protected void killService() {
        TriblerdService.stop(this);
    }

}
