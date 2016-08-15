package org.tribler.android;

import android.Manifest;
import android.app.Activity;
import android.content.ContentResolver;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.net.Uri;
import android.nfc.NdefRecord;
import android.os.Bundle;
import android.provider.MediaStore;
import android.support.annotation.NonNull;
import android.support.v4.app.ActivityCompat;
import android.support.v4.content.ContextCompat;
import android.support.v7.app.ActionBar;
import android.support.v7.app.AlertDialog;
import android.support.v7.app.AppCompatActivity;
import android.support.v7.widget.SearchView;
import android.text.InputType;
import android.text.TextUtils;
import android.util.Log;
import android.view.Menu;
import android.view.MenuInflater;
import android.view.MenuItem;
import android.view.View;
import android.widget.EditText;
import android.widget.Toast;

import com.jakewharton.rxbinding.support.v7.widget.RxSearchView;
import com.jakewharton.rxbinding.support.v7.widget.SearchViewQueryTextEvent;

import org.kivy.android.AssetExtract;
import org.tribler.android.restapi.json.AddedAck;
import org.tribler.android.restapi.json.AddedUrlAck;
import org.tribler.android.restapi.json.ChannelOverview;
import org.tribler.android.restapi.json.MyChannelResponse;
import org.tribler.android.restapi.json.RemovedAck;
import org.tribler.android.restapi.json.TorrentCreatedResponse;
import org.tribler.android.restapi.json.TriblerTorrent;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;

import retrofit2.adapter.rxjava.HttpException;
import rx.Observable;
import rx.Observer;
import rx.android.schedulers.AndroidSchedulers;
import rx.schedulers.Schedulers;

public class MyChannelFragment extends DefaultInteractionListFragment {

    public static final int CREATE_CHANNEL_ACTIVITY_REQUEST_CODE = 401;
    public static final int EDIT_CHANNEL_ACTIVITY_REQUEST_CODE = 402;
    public static final int BROWSE_FILE_ACTIVITY_REQUEST_CODE = 411;

    public static final int READ_STORAGE_PERMISSION_REQUEST_CODE = 410;

    private String _dispersyCid;
    private String _name;
    private String _description;

    /**
     * {@inheritDoc}
     */
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setHasOptionsMenu(true);
        loadMyChannel();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onCreateOptionsMenu(Menu menu, MenuInflater inflater) {
        super.onCreateOptionsMenu(menu, inflater);
        inflater.inflate(R.menu.fragment_my_channel_menu, menu);

        // Search button
        MenuItem btnFilter = menu.findItem(R.id.btn_filter_my_channel);
        SearchView searchView = (SearchView) btnFilter.getActionView();

        // Set search hint
        searchView.setQueryHint(getText(R.string.action_search_in_channel));

        // Filter on query text change
        rxMenuSubs.add(RxSearchView.queryTextChangeEvents(searchView)
                .subscribe(new Observer<SearchViewQueryTextEvent>() {

                    public void onNext(SearchViewQueryTextEvent event) {
                        adapter.getFilter().filter(event.queryText());
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        Log.e("onCreateOptionsMenu", "queryTextChangeEvents", e);
                    }
                }));
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onPrepareOptionsMenu(Menu menu) {
        super.onPrepareOptionsMenu(menu);
        // Hide main search button
        menu.findItem(R.id.btn_search).setShowAsActionFlags(MenuItem.SHOW_AS_ACTION_NEVER);

        // Is my channel created?
        boolean created = _dispersyCid != null;
        menu.findItem(R.id.btn_add_my_channel).setVisible(created);
        menu.findItem(R.id.btn_beam_my_channel).setVisible(created);
        menu.findItem(R.id.btn_edit_my_channel).setVisible(created);
        menu.findItem(R.id.btn_filter_my_channel).setVisible(created);

        // Set title
        if (created && context instanceof AppCompatActivity) {
            ActionBar actionBar = ((AppCompatActivity) context).getSupportActionBar();
            if (actionBar != null) {
                actionBar.setTitle(_name);
            }
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void reload() {
        super.reload();
        adapter.clear();
        loadMyChannelTorrents();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedRight(final TriblerTorrent torrent) {
        // Revert swipe
        adapter.notifyObjectChanged(torrent);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedLeft(final TriblerTorrent torrent) {
        askUserToDeleteTorrent(torrent);
    }

    private void loadMyChannel() {
        loading = service.getMyChannel()
                .subscribeOn(Schedulers.io())
                .map(MyChannelResponse::getMyChannel)
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<ChannelOverview>() {

                    public void onNext(ChannelOverview overview) {
                        _dispersyCid = overview.getIdentifier();
                        _name = overview.getName();
                        _description = overview.getDescription();
                        // Update view
                        invalidateOptionsMenu();
                        loadMyChannelTorrents();
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        if (e instanceof HttpException && ((HttpException) e).code() == 404) {
                            // My channel has not been created yet
                            createChannel();

                            // Hide loading indicator
                            progressView.setVisibility(View.GONE);
                            statusBar.setText("");
                        } else {
                            Log.e("loadMyChannel", "getMyChannel", e);
                            MyUtils.onError(e, context);
                            try {
                                Thread.sleep(1000);
                            } catch (InterruptedException ex) {
                            }
                            // Retry
                            loadMyChannel();
                        }
                    }
                });
        rxSubs.add(loading);
    }

    private void loadMyChannelTorrents() {
        loading = service.getTorrents(_dispersyCid)
                .subscribeOn(Schedulers.io())
                .flatMap(response -> Observable.from(response.getTorrents()))
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<TriblerTorrent>() {

                    public void onNext(TriblerTorrent torrent) {
                        adapter.addObject(torrent);
                    }

                    public void onCompleted() {
                        // Hide loading indicator
                        progressView.setVisibility(View.GONE);
                        statusBar.setText("");
                    }

                    public void onError(Throwable e) {
                        Log.e("loadMyChannelTorrents", "getTorrents", e);
                        MyUtils.onError(e, context);
                        try {
                            Thread.sleep(1000);
                        } catch (InterruptedException ex) {
                        }
                        // Retry
                        loadMyChannelTorrents();
                    }
                });
        rxSubs.add(loading);
    }

    private void createTorrent(final File file, final boolean delete) {
        // Workaround endpoint array parsing:
        String[] list = {"[\"" + file.getAbsolutePath() + "\"]"};
        loading = service.createTorrent(list)
                .subscribeOn(Schedulers.io())
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<TorrentCreatedResponse>() {

                    public void onNext(TorrentCreatedResponse response) {
                        Toast.makeText(context, String.format(context.getString(R.string.info_created_success), "Torrent"), Toast.LENGTH_SHORT).show();
                        // Add to my channel immediately
                        addTorrent(response.getTorrent());
                    }

                    public void onCompleted() {
                        if (delete) {
                            AssetExtract.recursiveDelete(new File(file.getParent()));
                        }
                    }

                    public void onError(Throwable e) {
                        if (e instanceof HttpException && ((HttpException) e).code() == 500) {
                            if (delete) {
                                AssetExtract.recursiveDelete(new File(file.getParent()));
                            }
                            Toast.makeText(context, String.format(context.getString(R.string.info_created_failure), "Torrent"), Toast.LENGTH_SHORT).show();
                            // Update view
                            reload();
                        } else {
                            Log.e("createTorrent", "getAbsolutePath", e);
                            MyUtils.onError(e, context);
                            try {
                                Thread.sleep(1000);
                            } catch (InterruptedException ex) {
                            }
                            // Retry
                            createTorrent(file, delete);
                        }
                    }
                });
        rxSubs.add(loading);
    }

    private void addTorrent(final String torrent_b64) {
        adapter.clear();
        // Show loading indicator
        progressView.setVisibility(View.VISIBLE);
        statusBar.setText(getText(R.string.status_adding_torrent));

        loading = service.addTorrent(_dispersyCid, torrent_b64)
                .subscribeOn(Schedulers.io())
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<AddedAck>() {

                    public void onNext(AddedAck response) {
                        Toast.makeText(context, String.format(context.getString(R.string.info_added_success), "Torrent"), Toast.LENGTH_SHORT).show();
                    }

                    public void onCompleted() {
                        // Update view
                        reload();
                    }

                    public void onError(Throwable e) {
                        if (e instanceof HttpException && ((HttpException) e).code() == 500) {
                            Toast.makeText(context, String.format(context.getString(R.string.info_added_failure), "Torrent"), Toast.LENGTH_SHORT).show();
                        } else {
                            Log.e("addTorrent", "base64", e);
                            MyUtils.onError(e, context);
                            try {
                                Thread.sleep(1000);
                            } catch (InterruptedException ex) {
                            }
                            // Retry
                            addTorrent(torrent_b64);
                        }
                    }
                });
        rxSubs.add(loading);
    }

    private void addTorrent(final Uri url) {
        adapter.clear();
        // Show loading indicator
        progressView.setVisibility(View.VISIBLE);
        statusBar.setText(getText(R.string.status_adding_torrent));

        loading = service.addTorrent(_dispersyCid, url)
                .subscribeOn(Schedulers.io())
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<AddedUrlAck>() {

                    public void onNext(AddedUrlAck response) {
                        Toast.makeText(context, String.format(context.getString(R.string.info_added_success), "Torrent"), Toast.LENGTH_SHORT).show();
                    }

                    public void onCompleted() {
                        // Update view
                        reload();
                    }

                    public void onError(Throwable e) {
                        if (e instanceof HttpException && ((HttpException) e).code() == 500) {
                            Toast.makeText(context, String.format(context.getString(R.string.info_added_already), "Torrent"), Toast.LENGTH_SHORT).show();
                        } else {
                            Log.e("addTorrent", "url", e);
                            MyUtils.onError(e, context);
                            try {
                                Thread.sleep(1000);
                            } catch (InterruptedException ex) {
                            }
                            // Retry
                            addTorrent(url);
                        }
                    }
                });
        rxSubs.add(loading);
    }

    private void deleteTorrent(final String infohash, final String name) {
        rxSubs.add(service.deleteTorrent(_dispersyCid, infohash)
                .subscribeOn(Schedulers.io())
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<RemovedAck>() {

                    public void onNext(RemovedAck response) {
                        Toast.makeText(context, String.format(context.getString(R.string.info_removed_success), name), Toast.LENGTH_SHORT).show();
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        if (e instanceof HttpException && ((HttpException) e).code() == 404) {
                            Toast.makeText(context, String.format(context.getString(R.string.info_removed_already), name), Toast.LENGTH_SHORT).show();
                        } else {
                            Log.e("onSwipedLeft", "deleteTorrent", e);
                            MyUtils.onError(e, context);
                            try {
                                Thread.sleep(1000);
                            } catch (InterruptedException ex) {
                            }
                            // Retry
                            deleteTorrent(infohash, name);
                        }
                    }
                }));
    }

    private void askUserToCreateMyChannel() {
        AlertDialog.Builder builder = new AlertDialog.Builder(context);
        builder.setMessage(getText(R.string.dialog_create_my_channel));
        builder.setPositiveButton(getText(R.string.action_create), (dialog, which) -> {
            createChannel();
        });
        builder.setNegativeButton(getText(R.string.action_cancel), (dialog, which) -> {
            // Do nothing
        });
        AlertDialog dialog = builder.create();
        dialog.show();
    }

    void askUserToAddTorrent() {
        AlertDialog.Builder builder = new AlertDialog.Builder(context);
        builder.setMessage(getText(R.string.dialog_add_torrent));

        EditText input = new EditText(context);
        input.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        input.setHint(getText(R.string.hint_add_torrent));
        builder.setView(input);

        builder.setPositiveButton(getText(R.string.action_add), (dialog, which) -> {
            CharSequence text = input.getText();
            if (!TextUtils.isEmpty(text)) {
                Uri uri = Uri.parse(text.toString());
                addTorrent(uri);
            }
        });
        builder.setNeutralButton(getText(R.string.action_browse), (dialog, which) -> {
            // Browse file to create torrent
            askUserToSelectFile();
        });
        builder.setNegativeButton(getText(R.string.action_cancel), (dialog, which) -> {
            // Do nothing
        });
        AlertDialog dialog = builder.create();
        dialog.show();
    }

    private void askUserToDeleteTorrent(TriblerTorrent torrent) {
        AlertDialog.Builder builder = new AlertDialog.Builder(context);
        builder.setMessage(String.format(getString(R.string.dialog_delete_torrent), torrent.getName()));
        builder.setPositiveButton(getText(R.string.action_delete), (dialog, which) -> {
            adapter.removeObject(torrent);
            deleteTorrent(torrent.getInfohash(), torrent.getName());
        });
        builder.setNegativeButton(getText(R.string.action_cancel), (dialog, which) -> {
            // Revert swipe
            adapter.notifyObjectChanged(torrent);
        });
        AlertDialog dialog = builder.create();
        dialog.show();
    }

    void askUserToBeamChannelId() {
        NdefRecord record = NdefRecord.createMime("text/plain", _dispersyCid.getBytes());
        Intent beamIntent = MyUtils.beamIntent(record);
        startActivity(beamIntent);
    }

    private void askUserToSelectFile() {
        if (ContextCompat.checkSelfPermission(getActivity(), Manifest.permission.READ_EXTERNAL_STORAGE) != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(getActivity(), new String[]{Manifest.permission.READ_EXTERNAL_STORAGE}, READ_STORAGE_PERMISSION_REQUEST_CODE);
        } else {
            Intent browseIntent = MyUtils.browseFileIntent();
            Intent chooserIntent = Intent.createChooser(browseIntent, getText(R.string.dialog_create_torrent));
            startActivityForResult(chooserIntent, BROWSE_FILE_ACTIVITY_REQUEST_CODE);
        }
    }

    private void createChannel() {
        Intent createIntent = MyUtils.createChannelIntent();
        startActivityForResult(createIntent, CREATE_CHANNEL_ACTIVITY_REQUEST_CODE);
    }

    void editChannel() {
        Intent createIntent = MyUtils.editChannelIntent(_dispersyCid, _name, _description);
        startActivityForResult(createIntent, EDIT_CHANNEL_ACTIVITY_REQUEST_CODE);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onRequestPermissionsResult(int requestCode, @NonNull String[] permissions, @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        switch (requestCode) {

            case READ_STORAGE_PERMISSION_REQUEST_CODE:
                // If request is cancelled, the result arrays are empty
                if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                    askUserToSelectFile();
                }
                return;
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onActivityResult(int requestCode, int resultCode, Intent data) {
        switch (requestCode) {

            case CREATE_CHANNEL_ACTIVITY_REQUEST_CODE:
                switch (resultCode) {

                    case Activity.RESULT_OK:
                        loadMyChannel();
                        return;

                    case Activity.RESULT_CANCELED:
                        askUserToCreateMyChannel();
                        return;
                }
                return;

            case EDIT_CHANNEL_ACTIVITY_REQUEST_CODE:
                switch (resultCode) {

                    case Activity.RESULT_OK:
                        _name = data.getStringExtra(ChannelActivity.EXTRA_NAME);
                        _description = data.getStringExtra(ChannelActivity.EXTRA_DESCRIPTION);
                        // Update view
                        if (isAdded()) {
                            getActivity().invalidateOptionsMenu();
                        }
                        return;

                    case Activity.RESULT_CANCELED:
                        // Do nothing
                        return;
                }
                return;

            case BROWSE_FILE_ACTIVITY_REQUEST_CODE:
                switch (resultCode) {

                    case Activity.RESULT_OK:
                        adapter.clear();
                        // Show loading indicator
                        progressView.setVisibility(View.VISIBLE);
                        statusBar.setText(getText(R.string.status_creating_torrent));

                        rxSubs.add(Observable.fromCallable(() -> resolveUri(data.getData()))
                                .subscribeOn(Schedulers.io())
                                .observeOn(AndroidSchedulers.mainThread())
                                .subscribe(new Observer<File>() {

                                    public void onNext(File file) {
                                        createTorrent(file, true);
                                    }

                                    public void onCompleted() {
                                    }

                                    public void onError(Throwable e) {
                                        Log.e("askUserToSelectFile", "resolveUri", e);
                                        // Retry
                                        askUserToSelectFile();
                                    }
                                }));
                        return;

                    case Activity.RESULT_CANCELED:
                        // Do nothing
                        return;
                }
                return;
        }
    }

    private File resolveUri(Uri uri) throws IOException {
        ContentResolver resolver = context.getContentResolver();
        String filename = uri.getLastPathSegment();

        // Get meta-data
        Cursor cursor = resolver.query(uri, null, null, null, null);
        if (cursor != null && cursor.moveToFirst()) {
            for (int i = 0, j = cursor.getColumnCount(); i < j; i++) {
                Log.v(cursor.getColumnName(i), cursor.getString(i)); //DEBUG
            }
            try {
                int i = cursor.getColumnIndexOrThrow(MediaStore.MediaColumns.DISPLAY_NAME);
                filename = cursor.getString(i);
            } catch (IllegalArgumentException ex) {
            }
            cursor.close();
        }

        // Make file accessible to service by copying to cache dir
        InputStream input = resolver.openInputStream(uri);

        // The name of the dir the file is in becomes the name of the .torrent file
        File dir = new File(context.getCacheDir(), filename);
        File file = new File(dir, filename);
        dir.mkdirs();
        OutputStream output = new FileOutputStream(file, false);

        MyUtils.copy(input, output);
        return file;
    }

}
