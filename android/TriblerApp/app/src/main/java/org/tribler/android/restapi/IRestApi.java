package org.tribler.android.restapi;

import org.tribler.android.restapi.json.QueriedAck;
import org.tribler.android.restapi.json.SubscribedAck;
import org.tribler.android.restapi.json.TriblerChannel;
import org.tribler.android.restapi.json.TriblerEvent;
import org.tribler.android.restapi.json.TriblerTorrent;
import org.tribler.android.restapi.json.UnsubscribedAck;

import java.util.List;

import retrofit2.http.DELETE;
import retrofit2.http.GET;
import retrofit2.http.PUT;
import retrofit2.http.Path;
import rx.Observable;

public interface IRestApi {

    @GET("/events")
    Observable<List<TriblerEvent>> getEventStream();

    @GET("/search?q={query}")
    Observable<QueriedAck> startSearch(
            @Path("query") String query
    );

    @GET("/channels/discovered")
    Observable<List<TriblerChannel>> getDiscoveredChannels();

    @GET("/channels/discovered/{dispersy_cid}/torrents")
    Observable<List<TriblerTorrent>> getTorrents(
            @Path("dispersy_cid") String dispersyCid
    );

    @GET("/channels/subscribed")
    Observable<List<TriblerChannel>> getFavoriteChannels();

    @PUT("/channels/subscribed/{dispersy_cid}")
    Observable<SubscribedAck> subscribe(
            @Path("dispersy_cid") String dispersyCid
    );

    @DELETE("/channels/subscribed/{dispersy_cid}")
    Observable<UnsubscribedAck> unsubscribe(
            @Path("dispersy_cid") String dispersyCid
    );
}