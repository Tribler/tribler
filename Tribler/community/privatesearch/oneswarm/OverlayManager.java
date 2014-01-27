package edu.washington.cs.oneswarm.f2f.network;

import java.io.ByteArrayInputStream;
import java.io.DataInputStream;
import java.io.IOException;
import java.net.InetAddress;
import java.net.Socket;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.PublicKey;
import java.security.SecureRandom;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Date;
import java.util.HashMap;
import java.util.LinkedList;
import java.util.List;
import java.util.Map;
import java.util.Timer;
import java.util.TimerTask;
import java.util.concurrent.ConcurrentHashMap;
import java.util.logging.Logger;

import org.bouncycastle.util.encoders.Base64;
import org.gudy.azureus2.core3.config.COConfigurationManager;
import org.gudy.azureus2.core3.config.ParameterListener;
import org.gudy.azureus2.core3.download.DownloadManager;
import org.gudy.azureus2.core3.global.GlobalManagerStats;
import org.gudy.azureus2.core3.torrent.TOTorrent;
import org.gudy.azureus2.core3.torrent.TOTorrentException;
import org.gudy.azureus2.core3.util.Base32;
import org.gudy.azureus2.core3.util.Debug;

import com.aelitis.azureus.core.impl.AzureusCoreImpl;
import com.aelitis.azureus.core.instancemanager.AZInstance;
import com.aelitis.azureus.core.networkmanager.ConnectionEndpoint;
import com.aelitis.azureus.core.networkmanager.NetworkConnection;
import com.aelitis.azureus.core.networkmanager.impl.tcp.TCPTransportImpl;

import edu.washington.cs.oneswarm.f2f.BigFatLock;
import edu.washington.cs.oneswarm.f2f.FileList;
import edu.washington.cs.oneswarm.f2f.FileListManager;
import edu.washington.cs.oneswarm.f2f.Friend;
import edu.washington.cs.oneswarm.f2f.FriendConnectListener;
import edu.washington.cs.oneswarm.f2f.chat.Chat;
import edu.washington.cs.oneswarm.f2f.chat.ChatDAO;
import edu.washington.cs.oneswarm.f2f.friends.FriendManager;
import edu.washington.cs.oneswarm.f2f.messaging.OSF2FHashSearch;
import edu.washington.cs.oneswarm.f2f.messaging.OSF2FHashSearchResp;
import edu.washington.cs.oneswarm.f2f.messaging.OSF2FMessage;
import edu.washington.cs.oneswarm.f2f.messaging.OSF2FMessageFactory;
import edu.washington.cs.oneswarm.f2f.messaging.OSF2FSearch;
import edu.washington.cs.oneswarm.f2f.messaging.OSF2FSearchCancel;
import edu.washington.cs.oneswarm.f2f.messaging.OSF2FSearchResp;
import edu.washington.cs.oneswarm.plugins.PluginCallback;
import edu.washington.cs.oneswarm.ui.gwt.rpc.StringTools;

public class OverlayManager {

    /**
     * make sure to not call any az functions when holding this lock
     */
    public static BigFatLock lock = BigFatLock.getInstance(false);

    // private Friend me;
    public final static Logger logger = Logger.getLogger(OverlayManager.class.getName());

    private int mMIN_DELAY_LINK_LATENCY = COConfigurationManager
            .getIntParameter("f2f_search_emulate_hops_min")
            * COConfigurationManager.getIntParameter("f2f_overlay_emulate_link_latency_max");
    private int mMAX_DELAY_LINK_LATENCY = COConfigurationManager
            .getIntParameter("f2f_search_emulate_hops_max")
            * COConfigurationManager.getIntParameter("f2f_overlay_emulate_link_latency_max");
    private int mMIN_RESPONSE_DELAY = COConfigurationManager
            .getIntParameter("f2f_search_emulate_hops_min")
            * COConfigurationManager.getIntParameter("f2f_search_forward_delay");
    private int mMAX_RESPONSE_DELAY = COConfigurationManager
            .getIntParameter("f2f_search_emulate_hops_max")
            * COConfigurationManager.getIntParameter("f2f_search_forward_delay");

    private double mForwardSearchProbability = COConfigurationManager
            .getFloatParameter("f2f_forward_search_probability");

    // this is just a way to treat requests for the local file list a bit
    // differently
    public final static int OWN_CONNECTION_ID_MAGIC_NUMBER = 0;

    private final static String RESPONSE_DELAY_SEED_SETTING_KEY = "response_delay_seed";

    private static final int TIMEOUT_CHECK_PERIOD = 5 * 1000;
    private final ConcurrentHashMap<Integer, FriendConnection> connections;
    private final FileListManager filelistManager;
    private final LinkedList<FriendConnectListener> friendConnectListeners = new LinkedList<FriendConnectListener>();

    private final FriendManager friendManager;
    private long lastConnectionCheckRun = System.currentTimeMillis();

    private final AZInstance myInstance;
    private final PublicKey ownPublicKey;
    private final QueueManager queueManager = new QueueManager();
    private final RandomnessManager randomnessManager;
    private final RandomnessManager responseDelayRandomnesManager;
    private final SearchManager searchManager;

    public RotatingLogger searchTimingsLogger = new RotatingLogger("search_timing");

    private final GlobalManagerStats stats;

    private boolean stopped = false;
    private final Timer t = new Timer("FriendConnectionInitialChecker", true);

    private PacketListener packetListener;

    public OverlayManager(FriendManager _friendManager, PublicKey _ownPublicKey,
            FileListManager _fileListManager, GlobalManagerStats _stats) {
        stats = _stats;
        myInstance = AzureusCoreImpl.getSingleton().getInstanceManager().getMyInstance();

        this.randomnessManager = new RandomnessManager();
        this.friendManager = _friendManager;
        this.filelistManager = _fileListManager;
        this.ownPublicKey = _ownPublicKey;
        this.connections = new ConcurrentHashMap<Integer, FriendConnection>();
        this.searchManager = new SearchManager(this, filelistManager, randomnessManager, stats);

        byte[] seedBytes = COConfigurationManager.getByteParameter(RESPONSE_DELAY_SEED_SETTING_KEY);
        if (seedBytes != null) {
            responseDelayRandomnesManager = new RandomnessManager(seedBytes);
        } else {
            responseDelayRandomnesManager = new RandomnessManager();
            COConfigurationManager.setParameter(RESPONSE_DELAY_SEED_SETTING_KEY,
                    randomnessManager.getSecretBytes());
        }

        COConfigurationManager.addAndFireParameterListeners(new String[] {
                "f2f_overlay_emulate_link_latency_max", "f2f_search_emulate_hops_min",
                "f2f_search_emulate_hops_max", "f2f_search_forward_delay",
                "f2f_forward_search_probability" }, new ParameterListener() {
            @Override
            public void parameterChanged(String parameterName) {
                mMIN_DELAY_LINK_LATENCY = COConfigurationManager
                        .getIntParameter("f2f_search_emulate_hops_min")
                        * COConfigurationManager
                                .getIntParameter("f2f_overlay_emulate_link_latency_max");
                mMAX_DELAY_LINK_LATENCY = COConfigurationManager
                        .getIntParameter("f2f_search_emulate_hops_max")
                        * COConfigurationManager
                                .getIntParameter("f2f_overlay_emulate_link_latency_max");
                mMIN_RESPONSE_DELAY = COConfigurationManager
                        .getIntParameter("f2f_search_emulate_hops_min")
                        * COConfigurationManager.getIntParameter("f2f_search_forward_delay");
                mMAX_RESPONSE_DELAY = COConfigurationManager
                        .getIntParameter("f2f_search_emulate_hops_max")
                        * COConfigurationManager.getIntParameter("f2f_search_forward_delay");
                mForwardSearchProbability = COConfigurationManager
                        .getFloatParameter("f2f_forward_search_probability");

                if (mForwardSearchProbability <= 0
                        || Math.abs(mForwardSearchProbability - 0.95) < 0.1) {
                    COConfigurationManager.setParameter("f2f_forward_search_probability", 0.5f);
                    mForwardSearchProbability = 0.5;
                }
                System.err.println("f2f_search_fwd_p: " + mForwardSearchProbability);
            }
        });

        OSF2FMessageFactory.init();

        Timer timeoutTimer = new Timer("OS Overlay Timeout checker", true);
        timeoutTimer.schedule(new ConnectionChecker(), 0, TIMEOUT_CHECK_PERIOD);

    }

    public void closeAllConnections() {
        for (FriendConnection c : connections.values()) {
            c.close();
        }

        stopped = true;
    }

    public boolean createIncomingConnection(byte[] publicKey, NetworkConnection netConn) {

        if (isConnectionAllowed(netConn, publicKey)) {
            Friend friend = friendManager.getFriend(publicKey);
            new FriendConnection(stats, queueManager, netConn, friend, filelistManager,
                    new FriendConnectionListener());

            return true;
        } else {
            System.err.println("INCOMING CONNECTION NOT ALLOWED!!!: " + netConn);
        }
        return false;
    }

    public void createOutgoingConnection(ConnectionEndpoint remoteFriendAddr, Friend friend) {
        for (FriendConnection connection : connections.values()) {
            if (connection.getRemoteFriend().equals(friend)) {
                String address = remoteFriendAddr.getNotionalAddress().getAddress()
                        .getHostAddress();
                if (connection.getRemoteIp().getHostAddress().equals(address)) {
                    logger.fine("Skipping friend connection, already connected to target address");
                    return;
                }
            }
        }
        final FriendConnection fc = new FriendConnection(stats, queueManager, remoteFriendAddr,
                friend, filelistManager, new FriendConnectionListener());
        /*
         * create a check for this connection to verify that we actually get
         * connected within a reasonable time frame
         */
        t.schedule(new TimerTask() {
            @Override
            public void run() {
                if (fc.isTimedOut()) {
                    fc.close();
                }
            }
        }, FriendConnection.INITIAL_HANDSHAKE_TIMEOUT + 10 * 1000);
    }

    private boolean deregisterConnection(FriendConnection connection) {
        lock.lock();
        try {
            logger.finer("deregistered connection: " + connection.toString() + " "
                    + connections.containsKey(connection.hashCode()) + " ");
            boolean res = null != connections.remove(connection.hashCode());
            Friend remoteFriend = connection.getRemoteFriend();

            /*
             * check if there are any active connections to the friend, if not,
             * mark as disconnected
             * 
             * this check is needed if there are 2 concurrent connections to the
             * same friend , and one is denied to register because of the other
             * one already connected
             */

            FriendConnection connectedConn = null;
            for (FriendConnection c : connections.values()) {
                if (c.getRemoteFriend().equals(remoteFriend)) {
                    connectedConn = c;
                }
            }
            /*
             * if the connection id != null, verify that the friend actually
             * think it is connected to the right connection id
             */
            if (connectedConn != null && connectedConn.isHandshakeReceived()) {
                int friendConnId = remoteFriend.getConnectionId();
                if (connectedConn.hashCode() != friendConnId) {
                    // fix it...
                    boolean fileListReceived = connectedConn.isFileListReceived();
                    if (!fileListReceived) {
                        logger.finer("connection closed, existing connection found, set to handshaking: "
                                + remoteFriend.getNick());
                        remoteFriend.setStatus(Friend.STATUS_HANDSHAKING);
                        remoteFriend.setConnectionId(Friend.NOT_CONNECTED_CONNECTION_ID);
                    } else {
                        logger.finer("connection closed, existing connection found, set to connected: "
                                + remoteFriend.getNick());
                        remoteFriend.setConnectionId(connectedConn.hashCode());
                        remoteFriend.setStatus(Friend.STATUS_ONLINE);
                    }
                }
            } else {
                // ok, no existing connections, mark as disconnected.
                remoteFriend.disconnected(connection.hashCode());
            }

            return res;
        } finally {
            lock.unlock();
        }
    }

    public void disconnectFriend(Friend f) {
        for (FriendConnection conn : connections.values()) {
            if (conn.getRemoteFriend().equals(f)) {
                conn.close();
            }
        }
    }

    void forwardSearchOrCancel(FriendConnection ignoreConn, OSF2FSearch msg) {
        for (FriendConnection conn : connections.values()) {
            if (ignoreConn.hashCode() == conn.hashCode()) {
                logger.finer("not forwarding search/cancel to: " + conn + " (source friend)");
                continue;
            }
            logger.finer("forwarding search/cancel to: " + conn);
            if (shouldForwardSearch(msg, ignoreConn)) {
                conn.sendSearch(msg.clone(), false);
            }
        }
    }

    public int getConnectCount() {
        return connections.size();
    }

    public Map<Integer, Friend> getConnectedFriends() {
        // sanity checks
        for (int connectionId : connections.keySet()) {
            FriendConnection c = connections.get(connectionId);
            // check status just to make sure
            final Friend remoteFriend = c.getRemoteFriend();
            int status = remoteFriend.getStatus();
            if (status == Friend.STATUS_OFFLINE && c.isHandshakeReceived()) {
                // fix it...
                boolean handshakeCompletedFully = c.isFileListReceived();
                if (!handshakeCompletedFully) {
                    Debug.out("getConnectedFriends, existing connection found, settings to handshaking: "
                            + remoteFriend.getNick());
                    remoteFriend.setStatus(Friend.STATUS_HANDSHAKING);
                } else {
                    Debug.out("getConnectedFriends, existing connection found, settings to connected: "
                            + remoteFriend.getNick());
                    remoteFriend.setConnectionId(c.hashCode());
                    remoteFriend.setStatus(Friend.STATUS_ONLINE);
                }
            }
        }

        Map<Integer, Friend> l = new HashMap<Integer, Friend>(connections.size());
        /*
         * we don't show me in friends list anymore
         */
        // l.put(me.getConnectionIds().get(0), me);
        Friend[] friends = friendManager.getFriends();
        for (Friend friend : friends) {
            if (friend.getStatus() == Friend.STATUS_ONLINE) {
                // System.out.println("online: " + friend.getNick());
                l.put(friend.getConnectionId(), friend);
            }
        }

        return l;
    }

    public int getSearchDelayForInfohash(Friend destination, byte[] infohash) {
        if (destination.isCanSeeFileList()) {
            return 0;
        } else {
            int searchDelay = responseDelayRandomnesManager.getDeterministicNextInt(infohash,
                    mMIN_RESPONSE_DELAY, mMAX_RESPONSE_DELAY);
            int latencyDelay = getLatencyDelayForInfohash(destination, infohash);
            return searchDelay + latencyDelay;
        }
    }

    public int getLatencyDelayForInfohash(Friend destination, byte[] infohash) {
        if (destination.isCanSeeFileList()) {
            return 0;
        } else {
            return responseDelayRandomnesManager.getDeterministicNextInt(infohash,
                    mMIN_DELAY_LINK_LATENCY, mMAX_DELAY_LINK_LATENCY);
        }
    }

    public List<Friend> getDisconnectedFriends() {
        List<Friend> l = new ArrayList<Friend>();
        Friend[] friends = friendManager.getFriends();
        for (Friend friend : friends) {
            if (friend.getStatus() != Friend.STATUS_ONLINE) {
                l.add(friend);
            }
        }
        return l;
    }

    public FileListManager getFilelistManager() {
        return filelistManager;
    }

    public List<FriendConnection> getFriendConnections() {
        return new ArrayList<FriendConnection>(connections.values());
    }

    public long getLastConnectionCheckRun() {
        return lastConnectionCheckRun;
    }

    public PublicKey getOwnPublicKey() {
        return ownPublicKey;
    }

    public QueueManager getQueueManager() {
        return queueManager;
    }

    public SearchManager getSearchManager() {
        return searchManager;
    }

    public double getTransportDownloadKBps() {
        long totalDownloadSpeed = 0;

        LinkedList<FriendConnection> conns = new LinkedList<FriendConnection>();
        conns.addAll(connections.values());

        for (FriendConnection fc : conns) {
            final Map<Integer, EndpointInterface> ot = fc.getOverlayTransports();

            for (EndpointInterface o : ot.values()) {
                totalDownloadSpeed += o.getDownloadRate();
            }
        }

        return totalDownloadSpeed / 1024.0;
    }

    public long getTransportSendRate(boolean includeLan) {
        long totalUploadSpeed = 0;

        LinkedList<FriendConnection> conns = new LinkedList<FriendConnection>();
        conns.addAll(connections.values());

        for (FriendConnection fc : conns) {
            final Map<Integer, EndpointInterface> ot = fc.getOverlayTransports();

            for (EndpointInterface o : ot.values()) {
                if (!includeLan && o.isLANLocal()) {
                    // not including lan local peers
                } else {
                    totalUploadSpeed += o.getUploadRate();
                }
            }
        }

        return totalUploadSpeed;
    }

    public boolean isConnectionAllowed(NetworkConnection connection, byte[] remotePubKey) {
        InetAddress remoteIP = connection.getEndpoint().getNotionalAddress().getAddress();
        Friend friend = friendManager.getFriend(remotePubKey);
        if (stopped) {
            logger.finer("connection denied: (f2f transfers disabled)");
            return false;
        }
        // check if we should allow this public key to connect
        if (Arrays.equals(remotePubKey, ownPublicKey.getEncoded())
                && remoteIP.equals(myInstance.getExternalAddress())) {
            logger.info("connection from self not allowed (if same ip)");
            return false;
        } else if (friend == null) {
            logger.fine(" access denied (not friend): " + remoteIP);
            return false;
        } else if (friend.isBlocked()) {
            logger.fine(" access denied (friend blocked): " + remoteIP);
            return false;
        } else if (friend.getFriendBannedUntil() > System.currentTimeMillis()) {
            double minutesLeft = friend.getFriendBannedUntil() - System.currentTimeMillis()
                    / (60 * 1000.0);
            friend.updateConnectionLog(true, "incoming connection denied, friend blocked for "
                    + minutesLeft + " more minutes because of: " + friend.getBannedReason());
            logger.fine(" access denied (friend blocked for " + minutesLeft + " more minutes): "
                    + remoteIP);
            return false;
        }

        FriendConnection toDisconnect = null;
        for (FriendConnection c : connections.values()) {
            // If we have 2 concurrent connections (and both have not yet
            // completed the handshake). Disconnect the one with the lowest sum
            // of port numbers.

            if (c.getRemoteFriend().equals(friend)) {
                int existingConnectionPortSum = getPortSum(c.getNetworkConnection());
                int newConnectionPortSum = getPortSum(connection);
                if (existingConnectionPortSum < newConnectionPortSum) {
                    toDisconnect = c;
                    break;
                } else {
                    // the new connection is "worse", keep the old one.
                    logger.info("new connection concurrent with a better one.");
                    return false;
                }
            }
        }
        if (toDisconnect != null) {
            toDisconnect.close();
        }
        logger.fine("friend connection ok: " + remoteIP + " :: " + friend);
        return true;
    }

    /**
     * make sure to synchronize before calling this function
     */
    private void notifyConnectionListeners(Friend f, boolean connected) {
        lock.lock();
        try {
            for (FriendConnectListener cb : friendConnectListeners) {
                if (connected) {
                    cb.friendConnected(f);
                } else {
                    cb.friendDisconnected(f);
                }
            }
        } finally {
            lock.unlock();
        }
    }

    private static int getPortSum(NetworkConnection conn) {
        TCPTransportImpl transport = (TCPTransportImpl) conn.getTransport();
        Socket s = transport.getSocketChannel().socket();
        return s.getLocalPort() + s.getPort();
    }

    private boolean registerConnection(FriendConnection connection) {
        lock.lock();
        try {
            if (isConnectionAllowed(connection.getNetworkConnection(),
                    connection.getRemotePublicKey())) {
                connections.put(connection.hashCode(), connection);
                connection.setPacketListener(packetListener);
                /*
                 * don't mark remote friend as connected until after the
                 * oneswarm handshake message is received
                 */
                // connection.getRemoteFriend().connected(connection.hashCode());
                logger.finer("registered connection: " + connection);
                return true;
            } else {
                return false;
            }
        } finally {
            lock.unlock();
        }
    }

    public void registerForConnectNotifications(FriendConnectListener callback) {
        lock.lock();
        try {
            friendConnectListeners.add(callback);
        } finally {
            lock.unlock();
        }
    }

    public void restartAllConnections() {
        stopped = false;
    }

    public void setPacketListener(PacketListener listener) {
        this.packetListener = listener;
        for (FriendConnection conn : connections.values()) {
            conn.setPacketListener(listener);
        }
    }

    public PacketListener getPacketListener() {
        return this.packetListener;
    }

    public void sendChatMessage(int connectionId, String inPlaintextMessage) {
        FriendConnection conn = connections.get(connectionId);
        conn.sendChat(inPlaintextMessage);
    }

    void sendDirectedSearch(FriendConnection target, OSF2FHashSearch search) {
        logger.finer("sending search to " + target);
        target.sendSearch(search, true);
    }

    public boolean sendFileListRequest(int connectionId, long maxCacheAge,
            PluginCallback<FileList> callback) {

        // just check if the request is for the local list
        if (connectionId == OWN_CONNECTION_ID_MAGIC_NUMBER) {
            callback.requestCompleted(filelistManager.getOwnFileList());
        }

        FriendConnection conn = connections.get(connectionId);

        if (conn != null) {

            FileList oldList = filelistManager.getFriendsList(conn.getRemoteFriend());
            if (oldList != null
                    && (System.currentTimeMillis() - oldList.getCreated()) < maxCacheAge) {
                callback.requestCompleted(oldList);
            }

            logger.finer("sending filelist request to " + conn);
            conn.sendFileListRequest(OSF2FMessage.FILE_LIST_TYPE_COMPLETE, callback);
            return true;
        } else {
            System.err
                    .println("tried to get filelist for unknown connection id (friend just went offline?)!, stack trace is:");
            new RuntimeException().printStackTrace();
        }
        return false;
    }

    // public void startDownload(byte type, byte[] metainfo,
    // boolean createIfNotExist) {
    // if (type == OSF2FMessage.METAINFO_TYPE_BITTORRENT) {
    //

    public boolean sendMetaInfoRequest(int connectionId, int channelId, byte[] infohash,
            int lengthHint, PluginCallback<byte[]> callback) {
        FriendConnection conn = connections.get(connectionId);
        logger.finer("sending metainfo request to " + conn);
        if (conn != null) {
            conn.sendMetaInfoRequest(OSF2FMessage.METAINFO_TYPE_BITTORRENT, channelId, infohash,
                    lengthHint, callback);
            return true;
        }
        return false;

    }

    void sendSearchOrCancel(OSF2FSearch search, boolean skipQueue, boolean forceSend) {
        logger.finer("sending search/cancel to " + connections.size());
        int numSent = 0;
        for (FriendConnection conn : connections.values()) {

            boolean shouldSend = true;
            if (!forceSend) {
                shouldSend = shouldForwardSearch(search, conn);
            }
            if (shouldSend) {
                logger.finer("About to send a search to " + conn.getRemoteFriend().getNick());
                conn.sendSearch(search.clone(), skipQueue);
                numSent++;
                logger.finer("Sent a search to " + conn.getRemoteFriend().getNick());
            }
            if (search instanceof OSF2FHashSearch) {
                OSF2FHashSearch hs = (OSF2FHashSearch) search;
                searchTimingsLogger.log(System.currentTimeMillis() + ", send_search, "
                        + conn.getRemoteFriend().getNick() + ", " + hs.getSearchID() + ", "
                        + hs.getInfohashhash());
            }
        }
        /*
         * for searches sent by us, if we didn't send it to anyone try again but
         * without the randomness linitng who we are sending to
         */
        if (numSent == 0 && !forceSend) {
            sendSearchOrCancel(search, skipQueue, true);
        }
    }

    /**
     * to protect against colluding friends we are only forwarding searches with
     * 95% probability
     * 
     * if forcesend = true the search will be forwarded anyway even if the
     * randomness says that friend shouldn't be forwarded
     */
    private boolean shouldForwardSearch(OSF2FSearch search, FriendConnection conn) {
        boolean shouldSend = true;
        if (search instanceof OSF2FHashSearch) {
            shouldSend = shouldForwardSearch(((OSF2FHashSearch) search).getInfohashhash(), conn);
        } else if (search instanceof OSF2FSearchCancel) {
            long infohash = searchManager.getInfoHashHashFromSearchId(search.getSearchID());
            if (infohash != -1) {
                shouldSend = shouldForwardSearch(infohash, conn);
            } else {
                shouldSend = false;
            }
        }
        return shouldSend;
    }

    private boolean shouldForwardSearch(long infohashhash, FriendConnection conn) {
        if (conn.getRemoteFriend().isCanSeeFileList()) {
            return true;
        }
        byte[] infohashbytes = RandomnessManager.getBytes(infohashhash);
        byte[] friendHash = RandomnessManager.getBytes(conn.getRemotePublicKeyHash());
        byte[] all = new byte[infohashbytes.length + friendHash.length];
        System.arraycopy(infohashbytes, 0, all, 0, infohashbytes.length);
        System.arraycopy(friendHash, 0, all, infohashbytes.length, friendHash.length);

        int randomVal = randomnessManager.getDeterministicRandomInt(all);
        if (randomVal < 0) {
            randomVal = -randomVal;
        }
        if (randomVal < Integer.MAX_VALUE * mForwardSearchProbability) {
            return true;
        } else {
            return false;
        }
    }

    public void triggerFileListUpdates() {
        List<FriendConnection> conns = new LinkedList<FriendConnection>();
        lock.lock();
        try {
            conns.addAll(connections.values());
        } finally {
            lock.unlock();
        }
        for (FriendConnection conn : connections.values()) {
            conn.triggerFileListSend();
        }
    }

    private class ConnectionChecker extends TimerTask {

        @Override
        public void run() {

            try {
                // first, check if we have any overlays that are timed out
                for (FriendConnection connection : connections.values()) {
                    connection.clearTimedOutForwards();
                    connection.clearTimedOutTransports();
                    connection.clearTimedOutSearchRecords();
                    connection.clearOldMetainfoRequests();
                }
            } catch (Throwable t) {
                Debug.out("F2F Connection Checker: got error when clearing transports/forwards", t);
            }
            try {
                // then, check if we need to send any keepalives
                for (FriendConnection connection : connections.values()) {
                    connection.doKeepAliveCheck();
                }
            } catch (Throwable t) {
                Debug.out("F2F Connection Checker: got error when sending keep alives", t);
            }

            try {
                // check if we have any timed out connections
                List<FriendConnection> timedOut = new ArrayList<FriendConnection>();
                for (FriendConnection connection : connections.values()) {
                    if (connection.isTimedOut()) {
                        timedOut.add(connection);
                    }
                }
                // and close them
                for (FriendConnection friendConnection : timedOut) {
                    friendConnection.close();
                }
            } catch (Throwable t) {
                Debug.out("F2F Connection Checker: got error when clearing friend connections", t);
            }

            try {
                // then, recycle the search IDs
                searchManager.clearTimedOutSearches();
            } catch (Throwable t) {
                Debug.out("F2F Connection Checker: got error when clearing timed out searches", t);
            }
            lastConnectionCheckRun = System.currentTimeMillis();
        }
    }

    class FriendConnectionListener {
        public boolean connectSuccess(FriendConnection friendConnection) {
            if (!registerConnection(friendConnection)) {
                logger.finer("Unable to register connection, "
                        + "connect count to high, closing connection");
                friendConnection.close();
                return false;
            }
            return true;
        }

        public void disconnected(FriendConnection friendConnection) {
            if (friendConnection.isFileListReceived()) {
                notifyConnectionListeners(friendConnection.getRemoteFriend(), false);
            }
            deregisterConnection(friendConnection);
        }

        public void gotSearchCancel(FriendConnection friendConnection, OSF2FSearchCancel msg) {
            searchManager.handleIncomingSearchCancel(friendConnection, msg);
        }

        public void gotSearchMessage(FriendConnection friendConnection, OSF2FSearch msg) {
            if (msg instanceof OSF2FHashSearch) {
                OSF2FHashSearch hs = (OSF2FHashSearch) msg;
                searchTimingsLogger.log(System.currentTimeMillis() + ", search, "
                        + friendConnection.getRemoteFriend().getNick() + ", " + hs.getSearchID()
                        + ", " + hs.getInfohashhash() + ", "
                        + friendConnection.getRemoteIp().getHostAddress());
            }
            searchManager.handleIncomingSearch(friendConnection, msg);
        }

        public void gotSearchResponse(FriendConnection friendConnection, OSF2FSearchResp msg) {
            if (msg instanceof OSF2FHashSearchResp) {
                OSF2FHashSearchResp hsr = (OSF2FHashSearchResp) msg;
                searchTimingsLogger.log(System.currentTimeMillis() + ", response, "
                        + friendConnection.getRemoteFriend().getNick() + ", " + hsr.getSearchID()
                        + ", " + hsr.getChannelID() + ", "
                        + friendConnection.getRemoteIp().getHostAddress() + ", " + hsr.getPathID());
            }
            searchManager.handleIncomingSearchResponse(friendConnection, msg);
        }

        @SuppressWarnings("unchecked")
        public void handshakeCompletedFully(final FriendConnection friendConnection) {

            notifyConnectionListeners(friendConnection.getRemoteFriend(), true);

            /*
             * check if we have any running downloads that this friend has
             */
            logger.finer("New friend connected, checking if friend has anything we want");
            List<byte[]> runningDownloadHashes = new LinkedList<byte[]>();
            List<DownloadManager> dms = AzureusCoreImpl.getSingleton().getGlobalManager()
                    .getDownloadManagers();
            for (DownloadManager dm : dms) {
                if (dm.getState() == DownloadManager.STATE_DOWNLOADING) {
                    try {
                        TOTorrent torrent = dm.getTorrent();
                        if (torrent != null) {
                            runningDownloadHashes.add(torrent.getHash());
                        }
                    } catch (TOTorrentException e) {
                        e.printStackTrace();
                    }
                }
            }
            logger.finer("found " + runningDownloadHashes.size() + " running downloads");
            FileList remoteFileList = filelistManager.getFriendsList(friendConnection
                    .getRemoteFriend());
            for (byte[] hash : runningDownloadHashes) {
                if (remoteFileList.contains(hash)) {
                    logger.finer("sending search for '" + Base32.encode(hash) + "' to "
                            + friendConnection.getRemoteFriend());
                    searchManager.sendDirectedHashSearch(friendConnection, hash);
                }
            }

            /**
             * Check if we need to send any pending chat messages to this user.
             * (5/sec)
             */
            Thread queryThread = new Thread("Queued chat SQL query for: "
                    + friendConnection.getRemoteFriend().getNick()) {
                @Override
                public void run() {

                    try {
                        Thread.sleep(3 * 1000);
                    } catch (InterruptedException e) {
                    }

                    String base64Key = new String(Base64.encode(friendConnection
                            .getRemotePublicKey()));
                    ChatDAO dao = ChatDAO.get();
                    List<Chat> out = dao.getQueuedMessagesForUser(base64Key);
                    for (Chat c : out) {
                        if (friendConnection.isTimedOut() || friendConnection.isClosing()) {
                            return;
                        }

                        friendConnection.sendChat(c.getMessage() + " (sent "
                                + StringTools.formatDateAppleLike(new Date(c.getTimestamp()), true)
                                + ")");
                        dao.markSent(c.getUID());

                        try {
                            Thread.sleep(200);
                        } catch (InterruptedException e) {
                        }
                    }
                }
            };
            queryThread.setDaemon(true);
            queryThread.start();
        }
    }
}

class RandomnessManager {
    private byte[] secretBytes = new byte[20];

    public RandomnessManager() {
        SecureRandom random;
        try {
            random = SecureRandom.getInstance("SHA1PRNG");
            random.nextBytes(secretBytes);
        } catch (NoSuchAlgorithmException e) {
            // TODO Auto-generated catch block
            e.printStackTrace();
            secretBytes = null;
        }
    }

    public RandomnessManager(byte[] secretBytes) {
        this.secretBytes = secretBytes;
    }

    /**
     * returns a random int between 0 (inclusive) and n (exclusive) seeded by
     * seedBytes
     */

    public int getDeterministicNextInt(byte[] seedBytes, int minValue, int maxValue) {
        int randomInt = getDeterministicRandomInt(seedBytes);
        if (randomInt < 0) {
            randomInt = -randomInt;
        }
        return minValue + (randomInt % (maxValue - minValue));
    }

    public int getDeterministicNextInt(int seed, int minValue, int maxValue) {
        byte[] seedBytes = getBytes(seed);
        return getDeterministicNextInt(seedBytes, minValue, maxValue);
    }

    public int getDeterministicNextInt(long seed, int minValue, int maxValue) {
        byte[] seedBytes = getBytes(seed);
        return getDeterministicNextInt(seedBytes, minValue, maxValue);
    }

    public int getDeterministicRandomInt(byte[] seedBytes) {
        if (secretBytes != null) {
            byte[] sha1input = new byte[secretBytes.length + seedBytes.length];
            System.arraycopy(secretBytes, 0, sha1input, 0, secretBytes.length);
            System.arraycopy(seedBytes, 0, sha1input, secretBytes.length, seedBytes.length);
            MessageDigest md;
            try {
                md = MessageDigest.getInstance("SHA-1");
                md.update(sha1input);
                byte[] sha1 = md.digest();
                ByteArrayInputStream bis = new ByteArrayInputStream(sha1);
                DataInputStream in = new DataInputStream(bis);
                return in.readInt();
            } catch (NoSuchAlgorithmException e) {
                // TODO Auto-generated catch block
                e.printStackTrace();
            } catch (IOException e) {
                // TODO Auto-generated catch block
                e.printStackTrace();
            }
        }

        throw new RuntimeException("unable to generate deterministic random int");
    }

    /**
     * Returns a random int seeded with the secret appended to the seed. For a
     * given seed the returned value will always be the same for a given
     * instance of the RandomnessManager
     * 
     * @param seed
     * @return
     * @throws NoSuchAlgorithmException
     * @throws IOException
     */
    public int getDeterministicRandomInt(int seed) {
        byte[] seedBytes = getBytes(seed);
        return getDeterministicRandomInt(seedBytes);
    }

    public int getDeterministicRandomInt(long seed) {
        byte[] seedBytes = getBytes(seed);
        return getDeterministicRandomInt(seedBytes);
    }

    public byte[] getSecretBytes() {
        return secretBytes;
    }

    static byte[] getBytes(int val) {
        byte[] b = new byte[4];
        b[3] = (byte) (val >>> 0);
        b[2] = (byte) (val >>> 8);
        b[1] = (byte) (val >>> 16);
        b[0] = (byte) (val >>> 24);
        return b;
    }

    static byte[] getBytes(long val) {
        byte[] b = new byte[8];
        b[7] = (byte) (val >>> 0);
        b[6] = (byte) (val >>> 8);
        b[5] = (byte) (val >>> 16);
        b[4] = (byte) (val >>> 24);
        b[3] = (byte) (val >>> 32);
        b[2] = (byte) (val >>> 40);
        b[1] = (byte) (val >>> 48);
        b[0] = (byte) (val >>> 56);
        return b;
    }

}
