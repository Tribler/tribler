package org.tribler.android;

import android.content.Context;
import android.content.DialogInterface;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.nfc.NfcAdapter;
import android.nfc.NfcEvent;
import android.nfc.NfcManager;
import android.os.Bundle;
import android.provider.Settings;
import android.support.design.widget.FloatingActionButton;
import android.support.design.widget.NavigationView;
import android.support.design.widget.Snackbar;
import android.support.v4.view.GravityCompat;
import android.support.v4.widget.DrawerLayout;
import android.support.v7.app.ActionBarDrawerToggle;
import android.support.v7.app.AlertDialog;
import android.support.v7.app.AppCompatActivity;
import android.support.v7.app.AppCompatDelegate;
import android.support.v7.widget.SearchView;
import android.support.v7.widget.Toolbar;
import android.view.Menu;
import android.view.MenuInflater;
import android.view.MenuItem;
import android.view.View;
import android.widget.ImageView;
import android.widget.Toast;

import java.io.File;

public class MainActivity extends AppCompatActivity
        implements NavigationView.OnNavigationItemSelectedListener {

    public static final int CAPTURE_VIDEO_ACTIVITY_REQUEST_CODE = 200;

    static {
        AppCompatDelegate.setCompatVectorFromResourcesEnabled(true);
    }

    private SearchViewListener mSearchViewListener;
    private CaptureVideoListener mCaptureVideoListener;

    /**
     * {@inheritDoc}
     */
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        //ServiceTriblerd.start(this, "");

        initCaptureVideo();
        initSearch();
        initGui();
    }

    /**
     * {@inheritDoc}
     */
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

    /**
     * {@inheritDoc}
     */
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
            case R.id.nav_beam:
                File apk = new File(this.getPackageResourcePath());
                startBeam(Uri.fromFile(apk));
                return true;
            case R.id.nav_settings:
                this.startActivity(new Intent(this, SettingsActivity.class));
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
            /**
             * {@inheritDoc}
             */
            @Override
            public void onClick(View view) {
                Snackbar.make(view, "Replace with your own action", Snackbar.LENGTH_LONG)
                        .setAction("Action", null).show();
            }
        });
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

    private void startBeam(Uri uri) {
        // Check if device has nfc
        if (!getPackageManager().hasSystemFeature(PackageManager.FEATURE_NFC)) {
            NfcManager nfcManager = (NfcManager) getSystemService(Context.NFC_SERVICE);
            NfcAdapter nfcAdapter = nfcManager.getDefaultAdapter();
            assert nfcAdapter != null;

            // Check if android beam is enabled
            if (!nfcAdapter.isEnabled()) {
                Toast.makeText(MainActivity.this, R.string.action_beam_nfc_enable, Toast.LENGTH_LONG).show();
                startActivity(new Intent(Settings.ACTION_NFC_SETTINGS));
            } else if (!nfcAdapter.isNdefPushEnabled()) {
                Toast.makeText(MainActivity.this, R.string.action_beam_enable, Toast.LENGTH_LONG).show();
                startActivity(new Intent(Settings.ACTION_NFCSHARING_SETTINGS));
            }

            nfcAdapter.setBeamPushUris(new Uri[]{uri}, this);

            // Show instructions
            AlertDialog.Builder builder = new AlertDialog.Builder(this);
            ImageView image = new ImageView(this);
            image.setImageResource(R.drawable.beam);
            builder.setView(image);
            AlertDialog dialog = builder.create();
            dialog.show();

        } else {
            // Use bluetooth
            Intent shareIntent = new Intent();
            shareIntent.setAction(Intent.ACTION_SEND);
            shareIntent.putExtra(Intent.EXTRA_STREAM, uri);
            shareIntent.setType(MyUtils.getMimeType(uri));
            startActivity(Intent.createChooser(shareIntent, getText(R.string.action_beam_app_chooser)));
        }
    }

}
