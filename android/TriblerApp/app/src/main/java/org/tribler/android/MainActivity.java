package org.tribler.android;

import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Bundle;
import android.support.annotation.Nullable;
import android.support.design.widget.NavigationView;
import android.support.v4.app.Fragment;
import android.support.v4.app.FragmentManager;
import android.support.v4.view.GravityCompat;
import android.support.v4.widget.DrawerLayout;
import android.support.v7.app.ActionBarDrawerToggle;
import android.support.v7.app.AppCompatDelegate;
import android.view.Menu;
import android.view.MenuItem;
import android.widget.Toast;

import org.tribler.android.restapi.IRestApi;
import org.tribler.android.restapi.TriblerService;
import org.tribler.android.service.Triblerd;

import java.io.File;

import butterknife.BindView;
import rx.Observer;
import rx.android.schedulers.AndroidSchedulers;
import rx.schedulers.Schedulers;

public class MainActivity extends BaseActivity {

    public static final int CAPTURE_VIDEO_ACTIVITY_REQUEST_CODE = 200;

    static {
        AppCompatDelegate.setCompatVectorFromResourcesEnabled(true);
    }

    private void initService() {
        // Check network connection before starting service
        //if (NetworkReceiver.isNetworkConnected(this)) {

        Triblerd.start(this); // Run normally
        //Twistd.start(this); // Run profiler
        //NoseTestService.start(this); // Run tests
        //ExperimentService.start(this); // Run experiment

        //} else {
        //    Toast.makeText(this, R.string.info_no_connection, Toast.LENGTH_LONG).show();
        //}
    }

    @BindView(R.id.drawer_layout)
    DrawerLayout drawer;

    @BindView(R.id.nav_view)
    NavigationView navigationView;

    private ActionBarDrawerToggle _navToggle;
    //private NetworkReceiver _networkReceiver;

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

        //Stetho.initializeWithDefaults(this); //DEBUG

        // Registers BroadcastReceiver to track network connection changes
        //_networkReceiver = new NetworkReceiver();
        //IntentFilter filter = new IntentFilter(ConnectivityManager.CONNECTIVITY_ACTION);
        //registerReceiver(_networkReceiver, filter);

        initService();
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
        //unregisterReceiver(_networkReceiver);
        //_networkReceiver = null;
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
        // Startup action
        if (Intent.ACTION_MAIN.equals(intent.getAction())) {
            //TODO: show loading screen until rest api connected
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

    public void btnSearch(@Nullable MenuItem item) {
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
            }
            fragmentManager
                    .beginTransaction()
                    .addToBackStack(tag)
                    .replace(R.id.fragment_main, fragment, tag)
                    .commit();
        }
    }

    public void navSubscriptions(@Nullable MenuItem item) throws InstantiationException, IllegalAccessException {
        drawer.closeDrawer(GravityCompat.START);
        switchFragment(SubscribedFragment.class);
    }

    public void navMyChannel(@Nullable MenuItem item) {
        drawer.closeDrawer(GravityCompat.START);
        //TODO: my channel
    }

    public void navMyPlaylists(@Nullable MenuItem item) {
        drawer.closeDrawer(GravityCompat.START);
    }

    public void navPopular(@Nullable MenuItem item) throws InstantiationException, IllegalAccessException {
        drawer.closeDrawer(GravityCompat.START);
        switchFragment(DiscoveredFragment.class);
    }

    public void navCaptureVideo(@Nullable MenuItem item) {
        drawer.closeDrawer(GravityCompat.START);
        // Check if device has camera
        if (getPackageManager().hasSystemFeature(PackageManager.FEATURE_CAMERA)) {
            // Obtain output file
            File output = AppUtils.getOutputVideoFile(this);
            if (output == null) {
                Toast.makeText(this, R.string.error_output_file, Toast.LENGTH_LONG).show();
            }
            Intent captureIntent = AppUtils.captureVideo(Uri.fromFile(output));
            startActivityForResult(captureIntent, CAPTURE_VIDEO_ACTIVITY_REQUEST_CODE);
        }
    }

    public void navBeam(@Nullable MenuItem item) {
        drawer.closeDrawer(GravityCompat.START);
        File apk = new File(this.getPackageResourcePath());
        Intent beamIntent = AppUtils.sendBeam(Uri.fromFile(apk), this);
        startActivity(beamIntent);
    }

    public void navSettings(@Nullable MenuItem item) {
        drawer.closeDrawer(GravityCompat.START);
        Intent settingsIntent = new Intent(this, SettingsActivity.class);
        startActivity(settingsIntent);
    }

    public void navFeedback(@Nullable MenuItem item) {
        drawer.closeDrawer(GravityCompat.START);
        CharSequence title = getText(R.string.app_feedback_url);
        Uri uri = Uri.parse(title.toString());
        Intent browserIntent = AppUtils.viewChooser(uri, title);
        startActivity(browserIntent);
    }

    public void navShutdown(@Nullable MenuItem item) {
        drawer.closeDrawer(GravityCompat.START);
        // Shutdown service
        String baseUrl = getString(R.string.service_url) + ":" + getString(R.string.service_port_number);
        String authToken = getString(R.string.service_auth_token);
        IRestApi service = TriblerService.createService(baseUrl, authToken);
        service.shutdown()
                .subscribeOn(Schedulers.io())
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<Object>() {

                    public void onNext(Object response) {
                    }

                    public void onCompleted() {
                        // Service shuts down without properly closing the stream, resulting in
                        // java.io.IOException: unexpected end of stream
                    }

                    public void onError(Throwable e) {
                        // Stop MainActivity
                        finish();
                    }
                });
    }
}
