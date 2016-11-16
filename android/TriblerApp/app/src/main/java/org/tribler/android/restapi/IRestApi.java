package org.tribler.android.restapi;

import android.net.Uri;

import org.tribler.android.restapi.json.AddedAck;
import org.tribler.android.restapi.json.AddedChannelAck;
import org.tribler.android.restapi.json.AddedUrlAck;
import org.tribler.android.restapi.json.ChannelsResponse;
import org.tribler.android.restapi.json.DownloadsResponse;
import org.tribler.android.restapi.json.ModifiedAck;
import org.tribler.android.restapi.json.MyChannelResponse;
import org.tribler.android.restapi.json.QueriedAck;
import org.tribler.android.restapi.json.RemovedAck;
import org.tribler.android.restapi.json.ShutdownAck;
import org.tribler.android.restapi.json.StartedAck;
import org.tribler.android.restapi.json.SubscribedAck;
import org.tribler.android.restapi.json.SubscribedChannelsResponse;
import org.tribler.android.restapi.json.TorrentCreatedResponse;
import org.tribler.android.restapi.json.TorrentsResponse;
import org.tribler.android.restapi.json.TriblerTorrent;
import org.tribler.android.restapi.json.UnsubscribedAck;

import java.io.Serializable;

import retrofit2.http.DELETE;
import retrofit2.http.Field;
import retrofit2.http.FormUrlEncoded;
import retrofit2.http.GET;
import retrofit2.http.PATCH;
import retrofit2.http.POST;
import retrofit2.http.PUT;
import retrofit2.http.Path;
import retrofit2.http.Query;
import retrofit2.http.Streaming;
import rx.Observable;

public interface IRestApi {

    @GET("/events")
    @Streaming
    Observable<Serializable> events();

    @PUT("/shutdown")
    Observable<ShutdownAck> shutdown();

    @GET("/search")
    Observable<QueriedAck> search(
            @Query("q") String query
    );

    @GET("/channels/popular")
    Observable<ChannelsResponse> getPopularChannels(
            @Query("limit") int limit
    );

    @GET("/channels/subscribed")
    Observable<SubscribedChannelsResponse> getSubscribedChannels();

    @PUT("/channels/subscribed/{dispersy_cid}")
    Observable<SubscribedAck> subscribe(
            @Path("dispersy_cid") String dispersyCid
    );

    @DELETE("/channels/subscribed/{dispersy_cid}")
    Observable<UnsubscribedAck> unsubscribe(
            @Path("dispersy_cid") String dispersyCid
    );

    @GET("/mychannel")
    Observable<MyChannelResponse> getMyChannel();

    @POST("/mychannel")
    @FormUrlEncoded
    Observable<ModifiedAck> editMyChannel(
            @Field("name") String name,
            @Field("description") String description
    );

    @PUT("/channels/discovered")
    @FormUrlEncoded
    Observable<AddedChannelAck> createChannel(
            @Field("name") String name,
            @Field("description") String description
    );

    @PUT("/channels/discovered")
    @FormUrlEncoded
    Observable<AddedChannelAck> createChannel(
            @Field("name") String name,
            @Field("description") String description,
            @Field("mode") String mode
    );

    @POST("/createtorrent")
    @FormUrlEncoded
    Observable<TorrentCreatedResponse> createTorrent(
            @Field("files[]") String[] files
    );

    @POST("/createtorrent")
    @FormUrlEncoded
    Observable<TorrentCreatedResponse> createTorrent(
            @Field("files[]") String[] files,
            @Field("description") String description
    );

    @POST("/createtorrent")
    @FormUrlEncoded
    Observable<TorrentCreatedResponse> createTorrent(
            @Field("files[]") String[] files,
            @Field("trackers[]") String[] trackers
    );

    @POST("/createtorrent")
    @FormUrlEncoded
    Observable<TorrentCreatedResponse> createTorrent(
            @Field("files[]") String[] files,
            @Field("description") String description,
            @Field("trackers[]") String[] trackers
    );

    @GET("/channels/discovered/{dispersy_cid}/torrents")
    Observable<TorrentsResponse> getTorrents(
            @Path("dispersy_cid") String dispersyCid
    );

    @GET("/channels/discovered/{dispersy_cid}/torrents")
    Observable<TorrentsResponse> getTorrents(
            @Path("dispersy_cid") String dispersyCid,
            @Query("disable_filter") int disableFilter
    );

    @PUT("/channels/discovered/{dispersy_cid}/torrents")
    @FormUrlEncoded
    Observable<AddedAck> addTorrent(
            @Path("dispersy_cid") String dispersyCid,
            @Field("torrent") String torrent_b64
    );

    @PUT("/channels/discovered/{dispersy_cid}/torrents")
    @FormUrlEncoded
    Observable<AddedAck> addTorrent(
            @Path("dispersy_cid") String dispersyCid,
            @Field("torrent") String torrent_b64,
            @Field("description") String description
    );

    @PUT("/channels/discovered/{dispersy_cid}/torrents/{url}")
    Observable<AddedUrlAck> addTorrent(
            @Path("dispersy_cid") String dispersyCid,
            @Path("url") Uri url
    );

    @PUT("/channels/discovered/{dispersy_cid}/torrents/{url}")
    @FormUrlEncoded
    Observable<AddedUrlAck> addTorrent(
            @Path("dispersy_cid") String dispersyCid,
            @Path("url") Uri url,
            @Field("description") String description
    );

    @GET("/channels/discovered/{dispersy_cid}/torrents/{infohash}")
    Observable<TriblerTorrent> getTorrent(
            @Path("dispersy_cid") String dispersyCid,
            @Path("infohash") String infohash
    );

    @DELETE("/channels/discovered/{dispersy_cid}/torrents/{infohash}")
    Observable<RemovedAck> deleteTorrent(
            @Path("dispersy_cid") String dispersyCid,
            @Path("infohash") String infohash
    );

    @GET("/downloads")
    Observable<DownloadsResponse> getDownloads();

    @PUT("/downloads/{infohash}")
    Observable<StartedAck> startDownload(
            @Path("infohash") String infohash,
            @Field("anon_hops") int anonHops,
            @Field("safe_seeding") boolean safeSeeding,
            @Field("destination") String destination
    );

    @PATCH("/downloads/{infohash}")
    Observable<StartedAck> modifyDownload(
            @Path("infohash") String infohash,
            @Field("state") String state
    );

    @DELETE("/downloads/{infohash}")
    Observable<StartedAck> removeDownload(
            @Path("infohash") String infohash,
            @Field("remove_data") boolean removeData
    );

}