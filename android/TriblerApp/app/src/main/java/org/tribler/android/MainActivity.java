package org.tribler.android;

import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.support.design.widget.FloatingActionButton;
import android.support.design.widget.NavigationView;
import android.support.design.widget.Snackbar;
import android.support.v4.app.NavUtils;
import android.support.v4.app.TaskStackBuilder;
import android.support.v4.view.GravityCompat;
import android.support.v4.widget.DrawerLayout;
import android.support.v7.app.ActionBarDrawerToggle;
import android.support.v7.app.AppCompatActivity;
import android.support.v7.app.AppCompatDelegate;
import android.support.v7.widget.SearchView;
import android.support.v7.widget.Toolbar;
import android.view.Menu;
import android.view.MenuInflater;
import android.view.MenuItem;
import android.view.View;

import java.io.File;

public class MainActivity extends AppCompatActivity
        implements NavigationView.OnNavigationItemSelectedListener {

    public static final int CAPTURE_VIDEO_ACTIVITY_REQUEST_CODE = 200;

    static {
        AppCompatDelegate.setCompatVectorFromResourcesEnabled(true);
    }

    private SearchViewListener mSearchViewListener;
    private CaptureVideoListener mCaptureVideoListener;
    private NfcBeamListener mNfcBeamListener;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        //ServiceTriblerd.start(this, "");

        initCaptureVideo();
        initSearch();
        initBeam();
        initGui();

        handleIntent(getIntent());
    }

    @Override
    protected void onNewIntent(Intent intent) {
        setIntent(intent);
        handleIntent(intent);
    }

    private void handleIntent(Intent intent) {
        if (Intent.ACTION_MAIN.equals(intent.getAction())) {
            //TODO: show home content
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode == CAPTURE_VIDEO_ACTIVITY_REQUEST_CODE) {
            mCaptureVideoListener.onActivityResult(resultCode, data);
        }
    }

    private void initGui() {
        setContentView(R.layout.activity_main);
        Toolbar toolbar = (Toolbar) findViewById(R.id.toolbar);
        assert toolbar != null;
        setSupportActionBar(toolbar);

        initFloatingActionButton();

        DrawerLayout drawer = (DrawerLayout) findViewById(R.id.drawer_layout);
        assert drawer != null;
        ActionBarDrawerToggle toggle = new ActionBarDrawerToggle(
                this, drawer, toolbar, R.string.navigation_drawer_open, R.string.navigation_drawer_close);

        drawer.addDrawerListener(toggle);
        toggle.syncState();

        NavigationView navigationView = (NavigationView) findViewById(R.id.nav_view);
        assert navigationView != null;
        navigationView.setNavigationItemSelectedListener(this);
    }

    @Override
    public void onBackPressed() {
        DrawerLayout drawer = (DrawerLayout) findViewById(R.id.drawer_layout);
        if (drawer != null && drawer.isDrawerOpen(GravityCompat.START)) {
            drawer.closeDrawer(GravityCompat.START);
        } else {
            super.onBackPressed();
        }
    }

    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        // Add items to the action bar if it is present
        MenuInflater inflater = getMenuInflater();
        inflater.inflate(R.menu.action_menu, menu);

        // Search button
        final MenuItem btnSearch = (MenuItem) menu.findItem(R.id.btn_search);
        assert btnSearch != null;
        SearchView searchView = (SearchView) btnSearch.getActionView();
        mSearchViewListener.setSearchView(searchView);

        return true;
    }

    @Override
    public boolean onOptionsItemSelected(MenuItem item) {
        // Handle action bar item clicks here. The action bar will
        // automatically handle clicks on the Home/Up button, so long
        // as you specify a parent activity in AndroidManifest.xml.
        switch (item.getItemId()) {
            // Respond to the action bar's Up/Home button
            case android.R.id.home:
                Intent upIntent = NavUtils.getParentActivityIntent(this);
                if (NavUtils.shouldUpRecreateTask(this, upIntent)) {
                    // This activity is NOT part of this app's task, so create a new task
                    // when navigating up, with a synthesized back stack.
                    TaskStackBuilder.create(this)
                            // Add all of this activity's parents to the back stack
                            .addNextIntentWithParentStack(upIntent)
                            // Navigate up to the closest parent
                            .startActivities();
                } else {
                    // This activity is part of this app's task, so simply
                    // navigate up to the logical parent activity.
                    NavUtils.navigateUpTo(this, upIntent);
                }
                return true;
        }
        return super.onOptionsItemSelected(item);
    }

    @Override
    public boolean onNavigationItemSelected(MenuItem item) {
        DrawerLayout drawer = (DrawerLayout) findViewById(R.id.drawer_layout);
        assert drawer != null;
        drawer.closeDrawer(GravityCompat.START);

        // Handle navigation view item clicks here
        switch (item.getItemId()) {
            case R.id.nav_capture_video:

                return true;
            case R.id.nav_my_channel:

                return true;
            case R.id.nav_my_playlists:

                return true;
            case R.id.nav_settings:

                return true;
            case R.id.nav_shutdown:

                return true;
        }
        return true;
    }

    private void initFloatingActionButton() {
        FloatingActionButton fab = (FloatingActionButton) findViewById(R.id.fab);
        assert fab != null;

        fab.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View view) {
                Snackbar.make(view, "Replace with your own action", Snackbar.LENGTH_LONG)
                        .setAction("Action", null).show();
            }
        });
    }

    private void initBeam() {
        // Check if device has nfc
        if (getPackageManager().hasSystemFeature(PackageManager.FEATURE_NFC)) {
            mNfcBeamListener = new NfcBeamListener(this);
            // Send app apk with Android Beam from this activity
            File apk = new File(this.getPackageResourcePath());
            mNfcBeamListener.addFile(apk);
        }
    }

    private void initCaptureVideo() {
        // Check if device has camera
        if (getPackageManager().hasSystemFeature(PackageManager.FEATURE_CAMERA)) {
            mCaptureVideoListener = new CaptureVideoListener(this);
        }
    }

    private void initSearch() {
        mSearchViewListener = new SearchViewListener(this);
    }


}
