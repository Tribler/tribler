package org.tribler.android;

import java.util.List;

import retrofit2.http.DELETE;
import retrofit2.http.GET;
import retrofit2.http.PUT;
import retrofit2.http.Path;
import rx.Observable;

public interface IRestApi {

    @GET("/events")
    Observable<List<TriblerEvent>> getEventStream();

    @GET("/search?q={url_encoded_query}")
    Observable<QueriedAck> startSearch(
            @Path("url_encoded_query") String url_encoded_query
    );

    @GET("/channels/discovered")
    Observable<List<TriblerChannel>> getDiscoveredChannels();

    @GET("/channels/discovered/{dispersy_cid}/torrents")
    Observable<List<TriblerTorrent>> getTorrents(
            @Path("dispersy_cid") String dispersy_cid
    );

    @GET("/channels/subscribed")
    Observable<List<TriblerChannel>> getFavoriteChannels();

    @PUT("/channels/subscribed/{dispersy_cid}")
    Observable<SubscribedAck> subscribe(
            @Path("dispersy_cid") String dispersy_cid
    );

    @DELETE("/channels/subscribed/{dispersy_cid}")
    Observable<UnsubscribedAck> unsubscribe(
            @Path("dispersy_cid") String dispersy_cid
    );
}