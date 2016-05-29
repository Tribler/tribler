package org.tribler.android;

import android.app.SearchManager;
import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.os.Message;
import android.support.v7.app.AppCompatActivity;
import android.support.v7.widget.LinearLayoutManager;
import android.support.v7.widget.RecyclerView;
import android.support.v7.widget.SearchView;
import android.support.v7.widget.helper.ItemTouchHelper;
import android.view.Menu;
import android.view.MenuInflater;
import android.view.MenuItem;

import com.google.gson.Gson;
import com.google.gson.stream.JsonReader;
import com.loopj.android.http.AsyncHttpResponseHandler;

import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.UnsupportedEncodingException;

import cz.msebera.android.httpclient.Header;
import cz.msebera.android.httpclient.HttpEntity;
import cz.msebera.android.httpclient.HttpResponse;

public class SearchActivity extends AppCompatActivity {

    private TriblerViewAdapter mAdapter;

    /**
     * {@inheritDoc}
     */
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        initGui();
        handleIntent(getIntent());
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        handleIntent(intent);
    }

    private void handleIntent(Intent intent) {
        if (Intent.ACTION_SEARCH.equals(intent.getAction())) {
            String query = intent.getStringExtra(SearchManager.QUERY);
            doMySearch(query);
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        super.onCreateOptionsMenu(menu);
        // Add items to the action bar if it is present
        MenuInflater inflater = getMenuInflater();
        inflater.inflate(R.menu.activity_search_action_bar, menu);

        // Search button
        MenuItem btnSearch = (MenuItem) menu.findItem(R.id.btn_search);
        assert btnSearch != null;
        final SearchView searchView = (SearchView) btnSearch.getActionView();
        searchView.setIconifiedByDefault(false);
        searchView.requestFocus();

        SearchManager searchManager = (SearchManager) getSystemService(Context.SEARCH_SERVICE);
        searchView.setSearchableInfo(searchManager.getSearchableInfo(getComponentName()));

        searchView.setOnQueryTextListener(new SearchView.OnQueryTextListener() {
            /**
             * {@inheritDoc}
             */
            @Override
            public boolean onQueryTextSubmit(String query) {
                searchView.clearFocus();
                Intent intent = new Intent(SearchActivity.this, SearchActivity.class);
                intent.setAction(Intent.ACTION_SEARCH);
                intent.putExtra(SearchManager.QUERY, query);
                onNewIntent(intent);
                return true;
            }

            /**
             * {@inheritDoc}
             */
            @Override
            public boolean onQueryTextChange(String newText) {
                return false;
            }
        });

        return true;
    }

    private void initGui() {
        setContentView(R.layout.activity_search);

        // Set list layout
        RecyclerView recyclerView = (RecyclerView) findViewById(R.id.search_results_list);
        recyclerView.setHasFixedSize(true);
        RecyclerView.LayoutManager layoutManager = new LinearLayoutManager(this);
        recyclerView.setLayoutManager(layoutManager);

        // Set list adapter
        mAdapter = new TriblerViewAdapter();
        recyclerView.setAdapter(mAdapter);

        // Click list item
        TriblerViewClickListener.OnItemClickListener onClick = new HomeClickListener(mAdapter);
        RecyclerView.SimpleOnItemTouchListener touchListener = new TriblerViewClickListener(this, onClick);
        recyclerView.addOnItemTouchListener(touchListener);

        // Swipe list item
        ItemTouchHelper.SimpleCallback onSwipe = new HomeSwipeListener(mAdapter);
        ItemTouchHelper touchHelper = new ItemTouchHelper(onSwipe);
        touchHelper.attachToRecyclerView(recyclerView);
    }


    private void doMySearch(String query) {
        //TODO
        Triblerd.restApi.get(this, Triblerd.BASE_URL + "/channels/discovered", new AsyncHttpResponseHandler() {

            protected static final int MY_MESSAGE = -1;

            public Gson gson = new Gson();

            /**
             * {@inheritDoc}
             */
            @Override
            public void sendResponseMessage(HttpResponse response) throws IOException {
                // do not process if request has been cancelled
                if (!Thread.currentThread().isInterrupted()) {
                    HttpEntity entity = response.getEntity();
                    if (entity != null) {
                        InputStream inputStream = entity.getContent();
                        if (inputStream != null) {
                            readJsonStream(inputStream);
                        }
                    }
                }
            }

            /**
             * This code reads a JSON document containing an array of messages.
             * It steps through array elements as a stream to avoid loading the complete document into memory.
             * It is concise because it uses Gson’s object-model to parse the individual messages:
             *
             * @param in
             * @return
             * @throws IOException
             */
            public void readJsonStream(InputStream in) throws IOException {
                JsonReader reader = new JsonReader(new InputStreamReader(in, getCharset()));
                reader.beginObject();
                reader.nextName(); // "channels":
                reader.beginArray();
                while (reader.hasNext()) {
                    TriblerChannel channel = gson.fromJson(reader, TriblerChannel.class);
                    sendMyMessage(channel);
                }
                reader.endArray();
                reader.endObject();
                reader.close();
            }

            final public void sendMyMessage(TriblerChannel channel) {
                sendMessage(obtainMessage(MY_MESSAGE, channel));
            }

            @Override
            protected void handleMessage(Message message) {
                if (MY_MESSAGE == message.what) {
                    onMy((TriblerChannel) message.obj);
                } else {
                    super.handleMessage(message);
                }
            }

            public void onMy(TriblerChannel channel) {
                mAdapter.addItem(channel);
            }

            /**
             * {@inheritDoc}
             */
            @Override
            public void onSuccess(int statusCode, Header[] headers, byte[] responseBody) {
                System.out.println(statusCode);
                try {
                    System.out.println(new String(responseBody, getCharset()));
                } catch (UnsupportedEncodingException ex) {

                }
            }

            /**
             * {@inheritDoc}
             */
            @Override
            public void onFailure(int statusCode, Header[] headers, byte[] responseBody, Throwable error) {
                System.err.println(statusCode);
                try {
                    System.err.println(new String(responseBody, getCharset()));
                } catch (UnsupportedEncodingException ex) {

                }
            }
        });
    }

}