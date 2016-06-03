package org.tribler.android;

import android.app.Activity;
import android.app.FragmentManager;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Bundle;
import android.support.design.widget.NavigationView;
import android.support.v4.view.GravityCompat;
import android.support.v4.widget.DrawerLayout;
import android.support.v7.app.ActionBarDrawerToggle;
import android.support.v7.app.AppCompatActivity;
import android.support.v7.app.AppCompatDelegate;
import android.support.v7.widget.LinearLayoutManager;
import android.support.v7.widget.RecyclerView;
import android.support.v7.widget.Toolbar;
import android.util.Log;
import android.view.Menu;
import android.view.MenuInflater;
import android.view.MenuItem;

import java.io.File;

import xyz.danoz.recyclerviewfastscroller.vertical.VerticalRecyclerViewFastScroller;

public class MainActivity extends AppCompatActivity
        implements NavigationView.OnNavigationItemSelectedListener {

    public static final int CAPTURE_VIDEO_ACTIVITY_REQUEST_CODE = 200;

    static {
        AppCompatDelegate.setCompatVectorFromResourcesEnabled(true);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Triblerd.start(this);
        initGui();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        super.onCreateOptionsMenu(menu);
        // Add items to the action bar if it is present
        MenuInflater inflater = getMenuInflater();
        inflater.inflate(R.menu.activity_main_action_bar, menu);

        // Search button
        MenuItem btnSearch = (MenuItem) menu.findItem(R.id.btn_search);
        assert btnSearch != null;
        btnSearch.setOnMenuItemClickListener(new MenuItem.OnMenuItemClickListener() {
            @Override
            public boolean onMenuItemClick(MenuItem menuItem) {
                Intent intent = new Intent(MainActivity.this, SearchActivity.class);
                startActivity(intent);
                return true;
            }
        });

        return true;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);

        if (requestCode == CAPTURE_VIDEO_ACTIVITY_REQUEST_CODE) {

            if (resultCode == Activity.RESULT_OK) {
                Log.d("Tribler", "Video saved to:\n" + data.getData());
                //TODO: advise user
            } else if (resultCode == Activity.RESULT_CANCELED) {
                Log.d("Tribler", "User cancelled the video capture");
            } else {
                Log.e("Tribler", "failed to capture video");
                //TODO: advise user
            }
        }
    }

    private void initGui() {
        setContentView(R.layout.activity_main);

        // Set action toolbar
        Toolbar toolbar = (Toolbar) findViewById(R.id.activity_main_toolbar);
        assert toolbar != null;
        setSupportActionBar(toolbar);

        // Set collapsible menu
        DrawerLayout drawer = (DrawerLayout) findViewById(R.id.drawer_layout);
        assert drawer != null;
        ActionBarDrawerToggle toggle = new ActionBarDrawerToggle(
                this, drawer, toolbar, R.string.navigation_drawer_open, R.string.navigation_drawer_close);
        drawer.addDrawerListener(toggle);
        toggle.syncState();

        // Set main menu
        NavigationView navigationView = (NavigationView) findViewById(R.id.nav_view);
        assert navigationView != null;
        navigationView.setNavigationItemSelectedListener(this);

        // Set list view
        RecyclerView recyclerView = (RecyclerView) findViewById(R.id.list_recycler_view);
        assert recyclerView != null;
        // Improve performance
        recyclerView.setHasFixedSize(true);

        // Set fast scroller
        VerticalRecyclerViewFastScroller fastScroller = (VerticalRecyclerViewFastScroller) findViewById(R.id.list_fast_scroller);
        assert fastScroller != null;
        // Connect the recycler to the scroller (to let the scroller scroll the list)
        fastScroller.setRecyclerView(recyclerView);
        // Connect the scroller to the recycler (to let the recycler scroll the scroller's handle)
        recyclerView.addOnScrollListener(fastScroller.getOnScrollListener());
        // Scroll to the current position of the layout manager
        setRecyclerViewLayoutManager(recyclerView);
    }

    /**
     * @param recyclerView Set the LayoutManager of this RecycleView
     */
    private void setRecyclerViewLayoutManager(RecyclerView recyclerView) {
        int scrollPosition = 0;
        LinearLayoutManager linearLayoutManager = (LinearLayoutManager) recyclerView.getLayoutManager();
        // If a layout manager has already been set, get current scroll position.
        if (linearLayoutManager != null) {
            scrollPosition = linearLayoutManager.findFirstCompletelyVisibleItemPosition();
        } else {
            linearLayoutManager = new LinearLayoutManager(this);
            recyclerView.setLayoutManager(linearLayoutManager);
        }
        recyclerView.scrollToPosition(scrollPosition);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onBackPressed() {
        DrawerLayout drawer = (DrawerLayout) findViewById(R.id.drawer_layout);
        if (drawer != null && drawer.isDrawerOpen(GravityCompat.START)) {
            drawer.closeDrawer(GravityCompat.START);
        } else {
            super.onBackPressed();
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean onNavigationItemSelected(MenuItem item) {
        DrawerLayout drawer = (DrawerLayout) findViewById(R.id.drawer_layout);
        assert drawer != null;
        drawer.closeDrawer(GravityCompat.START);

        FragmentManager fm = getFragmentManager();

        // Handle navigation view item clicks here
        switch (item.getItemId()) {

            case R.id.nav_subscribtions:
                // Check to see if we have retained the worker fragment
                SubscribedFragment fragment = (SubscribedFragment) fm.findFragmentByTag("subscribed");
                // If not retained (or first time running), we need to create it
                if (fragment == null) {
                    fragment = new SubscribedFragment();
                    // Tell the framework to try to keep this fragment around during a configuration change
                    fragment.setRetainInstance(true);
                    fm.beginTransaction().add(fragment, "subscribed").commit();

                    fragment.getSubscriptions();
                }
                return true;

            case R.id.nav_my_channel:

                return true;

            case R.id.nav_my_playlists:

                return true;

            case R.id.nav_capture_video:
                // Check if device has camera
                if (getPackageManager().hasSystemFeature(PackageManager.FEATURE_CAMERA)) {
                    // Obtain output file
                    File output = MyUtils.getOutputVideoFile(this);
                    if (output == null) {
                        Log.e(getClass().getName(), "failed to obtain output file");
                        //TODO: advise user
                    }
                    Intent captureIntent = MyUtils.captureVideo(Uri.fromFile(output));
                    startActivityForResult(captureIntent, CAPTURE_VIDEO_ACTIVITY_REQUEST_CODE);
                }
                return true;

            case R.id.nav_beam:
                File apk = new File(this.getPackageResourcePath());
                Intent beamIntent = MyUtils.sendBeam(Uri.fromFile(apk), this);
                startActivity(beamIntent);
                return true;

            case R.id.nav_settings:
                Intent settingsIntent = new Intent(this, SettingsActivity.class);
                startActivity(settingsIntent);
                return true;

            case R.id.nav_shutdown:
                Triblerd.stop(this);
                // Exit MainActivity
                finish();
                return true;
        }
        return true;
    }

}
