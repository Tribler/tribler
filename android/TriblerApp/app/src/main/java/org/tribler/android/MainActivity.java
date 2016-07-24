package org.tribler.android;

import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Bundle;
import android.support.design.widget.NavigationView;
import android.support.v4.view.GravityCompat;
import android.support.v4.widget.DrawerLayout;
import android.support.v7.app.ActionBarDrawerToggle;
import android.support.v7.app.AppCompatDelegate;
import android.support.v7.widget.Toolbar;
import android.view.Menu;
import android.view.MenuItem;
import android.widget.Toast;

import java.io.File;

import butterknife.BindView;

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

    @BindView(R.id.toolbar)
    Toolbar toolbar;

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

        // The action bar will automatically handle clicks on the Home/Up button,
        // so long as you specify a parent activity in AndroidManifest.xml
        setSupportActionBar(toolbar);

        // Hamburger icon
        _navToggle = new ActionBarDrawerToggle(this, drawer, toolbar, R.string.navigation_drawer_open, R.string.navigation_drawer_close);
        drawer.addDrawerListener(_navToggle);
        _navToggle.syncState();

        // Registers BroadcastReceiver to track network connection changes
        //_networkReceiver = new NetworkReceiver();
        //IntentFilter filter = new IntentFilter(ConnectivityManager.CONNECTIVITY_ACTION);
        //registerReceiver(_networkReceiver, filter);

        initService();
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
                Toast.makeText(this, "Video saved to:\n" + data.getData(), Toast.LENGTH_LONG).show();
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

    public void btnSearch(MenuItem item) {
        Intent intent = new Intent(this, SearchActivity.class);
        startActivity(intent);
    }

    public void navSubscriptions(MenuItem item) {
        drawer.closeDrawer(GravityCompat.START);
        SubscribedFragment fragment = new SubscribedFragment();
        String tag = fragment.getClass().toString();
        getFragmentManager().beginTransaction().addToBackStack(tag)
                .replace(R.id.fragment_placeholder, fragment, tag)
                .commit();
        fragment.getSubscriptions();
    }

    public void navMyChannel(MenuItem item) {
        drawer.closeDrawer(GravityCompat.START);
        //TODO: my channel
    }

    public void navMyPlaylists(MenuItem item) {
        drawer.closeDrawer(GravityCompat.START);
    }

    public void navPopular(MenuItem item) {
        drawer.closeDrawer(GravityCompat.START);
        DiscoveredFragment fragment = new DiscoveredFragment();
        String tag = fragment.getClass().toString();
        getFragmentManager().beginTransaction().addToBackStack(tag)
                .replace(R.id.fragment_placeholder, fragment, tag)
                .commit();
        fragment.getDiscoveredChannels();
    }

    public void navCaptureVideo(MenuItem item) {
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

    public void navBeam(MenuItem item) {
        drawer.closeDrawer(GravityCompat.START);
        File apk = new File(this.getPackageResourcePath());
        Intent beamIntent = AppUtils.sendBeam(Uri.fromFile(apk), this);
        startActivity(beamIntent);
    }

    public void navSettings(MenuItem item) {
        drawer.closeDrawer(GravityCompat.START);
        Intent settingsIntent = new Intent(this, SettingsActivity.class);
        startActivity(settingsIntent);
    }

    public void navFeedback(MenuItem item) {
        drawer.closeDrawer(GravityCompat.START);
        CharSequence title = getText(R.string.app_feedback_url);
        Uri uri = Uri.parse(title.toString());
        Intent browserIntent = AppUtils.viewChooser(uri, title);
        startActivity(browserIntent);
    }

    public void navShutdown(MenuItem item) {
        drawer.closeDrawer(GravityCompat.START);
        Triblerd.stop(this);
        // Exit MainActivity
        finish();
    }
}
