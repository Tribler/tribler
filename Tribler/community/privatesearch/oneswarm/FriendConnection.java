package edu.washington.cs.oneswarm.f2f.network;

import java.io.IOException;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.net.InetAddress;
import java.nio.ByteBuffer;
import java.text.DecimalFormat;
import java.text.NumberFormat;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Iterator;
import java.util.LinkedList;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.Set;
import java.util.TimerTask;
import java.util.concurrent.ConcurrentHashMap;
import java.util.logging.Level;
import java.util.logging.Logger;

import org.gudy.azureus2.core3.config.COConfigurationManager;
import org.gudy.azureus2.core3.global.GlobalManagerStats;
import org.gudy.azureus2.core3.util.Average;
import org.gudy.azureus2.core3.util.Base32;
import org.gudy.azureus2.core3.util.ByteFormatter;
import org.gudy.azureus2.core3.util.Debug;

import com.aelitis.azureus.core.networkmanager.ConnectionEndpoint;
import com.aelitis.azureus.core.networkmanager.IncomingMessageQueue.MessageQueueListener;
import com.aelitis.azureus.core.networkmanager.NetworkConnection;
import com.aelitis.azureus.core.networkmanager.NetworkConnection.ConnectionListener;
import com.aelitis.azureus.core.networkmanager.NetworkManager;
import com.aelitis.azureus.core.networkmanager.OutgoingMessageQueue;
import com.aelitis.azureus.core.networkmanager.impl.NetworkConnectionImpl;
import com.aelitis.azureus.core.networkmanager.impl.osssl.OneSwarmSslTools;
import com.aelitis.azureus.core.networkmanager.impl.osssl.OneSwarmSslTransportHelperFilterStream;
import com.aelitis.azureus.core.networkmanager.impl.tcp.ProtocolEndpointTCP;
import com.aelitis.azureus.core.peermanager.messaging.Message;
import com.aelitis.azureus.core.peermanager.messaging.MessageException;
import com.aelitis.azureus.core.peermanager.messaging.bittorrent.BTKeepAlive;
import com.sun.org.apache.xerces.internal.impl.dv.util.Base64;

import edu.washington.cs.oneswarm.f2f.BigFatLock;
import edu.washington.cs.oneswarm.f2f.FileList;
import edu.washington.cs.oneswarm.f2f.FileListManager;
import edu.washington.cs.oneswarm.f2f.Friend;
import edu.washington.cs.oneswarm.f2f.OSF2FMain;
import edu.washington.cs.oneswarm.f2f.chat.ChatDAO;
import edu.washington.cs.oneswarm.f2f.datagram.DatagramConnection;
import edu.washington.cs.oneswarm.f2f.datagram.DatagramConnectionManagerImpl;
import edu.washington.cs.oneswarm.f2f.datagram.DatagramListener;
import edu.washington.cs.oneswarm.f2f.messaging.OSF2FChannelDataMsg;
import edu.washington.cs.oneswarm.f2f.messaging.OSF2FChannelMsg;
import edu.washington.cs.oneswarm.f2f.messaging.OSF2FChannelReset;
import edu.washington.cs.oneswarm.f2f.messaging.OSF2FChat;
import edu.washington.cs.oneswarm.f2f.messaging.OSF2FDatagramInit;
import edu.washington.cs.oneswarm.f2f.messaging.OSF2FDatagramOk;
import edu.washington.cs.oneswarm.f2f.messaging.OSF2FDhtLocation;
import edu.washington.cs.oneswarm.f2f.messaging.OSF2FHandshake;
import edu.washington.cs.oneswarm.f2f.messaging.OSF2FHashSearch;
import edu.washington.cs.oneswarm.f2f.messaging.OSF2FHashSearchResp;
import edu.washington.cs.oneswarm.f2f.messaging.OSF2FMessage;
import edu.washington.cs.oneswarm.f2f.messaging.OSF2FMessageDecoder;
import edu.washington.cs.oneswarm.f2f.messaging.OSF2FMessageEncoder;
import edu.washington.cs.oneswarm.f2f.messaging.OSF2FMetaInfoReq;
import edu.washington.cs.oneswarm.f2f.messaging.OSF2FMetaInfoResp;
import edu.washington.cs.oneswarm.f2f.messaging.OSF2FSearch;
import edu.washington.cs.oneswarm.f2f.messaging.OSF2FSearchCancel;
import edu.washington.cs.oneswarm.f2f.messaging.OSF2FSearchResp;
import edu.washington.cs.oneswarm.f2f.messaging.OSF2FTextSearch;
import edu.washington.cs.oneswarm.f2f.messaging.OSF2FTextSearchResp;
import edu.washington.cs.oneswarm.f2f.network.DelayedExecutorService.DelayedExecutor;
import edu.washington.cs.oneswarm.f2f.network.OverlayManager.FriendConnectionListener;
import edu.washington.cs.oneswarm.f2f.network.OverlayTransport.WriteQueueWaiter;
import edu.washington.cs.oneswarm.f2f.network.QueueManager.QueueBuckets;
import edu.washington.cs.oneswarm.f2f.servicesharing.OSF2FServiceDataMsg;
import edu.washington.cs.oneswarm.plugins.PluginCallback;

public class FriendConnection implements DatagramListener {

    private static BigFatLock lock = OverlayManager.lock;

    public final static Logger logger = Logger.getLogger(FriendConnection.class.getName());

    /*
     * the max search rate, average over 10 s
     */
    public final static double MAX_OUTGOING_SEARCH_RATE = 300;

    // This is set to 1000 for legacy clients who had a MAX_OUTGOING_SEARCH_RATE
    // of 1000.
    // We don't want to ban these people just yet.
    private final static double MAX_INCOMING_SEARCH_RATE = 1000 * 1.5;

    private final Average incomingSearchRate = Average.getInstance(1000, 10);
    private final Average outgoingSearchRate = Average.getInstance(1000, 10);

    // we are a bit more aggressive with the keep alives
    // a keepalive has to be sent every 15 s
    // if nothing has been received in 60 s we disconnect
    public static final int KEEP_ALIVE_FREQ = 15 * 1000;

    public static final int KEEP_ALIVE_TIMEOUT = 65 * 1000;

    private static final int TIMOUT_FILELIST = 2 * 60 * 1000;

    static final int INITIAL_HANDSHAKE_TIMEOUT = 60 * 1000;

    // max age of an overlay, 5 minutes should be enough
    // less conserves resource, more allows searches to expire later
    public static final int OVERLAY_FORWARD_TIMEOUT = 5 * 60 * 1000;

    private static final long RECENTLY_CLOSED_TIME = 90 * 1000;

    final double FORWARD_SEARCH_PROBABILITY = COConfigurationManager.getFloatParameter(
            "f2f_forward_search_probability", 0.50f);

    private int activeOverlays = 0;

    private final LinkedList<OSF2FMessage> bufferedMessages = new LinkedList<OSF2FMessage>();
    private final NetworkConnection connection;

    // private boolean connectionRegistered = false;

    private final long connectionTime;

    private long dataBytesDownloaded = 0;

    Random random = new Random();

    private final FileListManager filelistManager;
    private final FileListRequestHandler fileListRequestHandler = new FileListRequestHandler();
    private final FriendConnectionQueue friendConnectionQueue;

    private boolean filelistReceived = false;
    private volatile boolean handShakeReceived = false;

    private int lastFileListSentToFriend = Integer.MAX_VALUE;

    private long lastByteRecvTime = System.currentTimeMillis();
    // private final Queue<WriteQueueWaiter> writeWaiters = new
    // ConcurrentLinkedQueue<WriteQueueWaiter>();
    //
    // private volatile int queueLengthBytes = 0;
    //
    // private volatile long queueLengthMs = 0;
    // private ConcurrentHashMap<Integer, Long> messageQueueTimes = new
    // ConcurrentHashMap<Integer, Long>();

    private final FriendConnectionListener listener;

    private final MetaInfoRequestHandler metaInfoRequestHandler;

    private final boolean outgoing;

    /*
     * even though we are using concurrent hash maps, calls to add or remove
     * should be synchronized to avoid problems with duplicate keys
     */
    private final ConcurrentHashMap<Integer, OverlayForward> overlayForwards = new ConcurrentHashMap<Integer, OverlayForward>();

    private final ConcurrentHashMap<Integer, Boolean> overlayTransportPathsId = new ConcurrentHashMap<Integer, Boolean>();

    private final ConcurrentHashMap<Integer, EndpointInterface> overlayTransports = new ConcurrentHashMap<Integer, EndpointInterface>();

    /*
     * map to keep track of received searches to avoid sending the search back
     * to people we got the search from
     */
    private final ConcurrentHashMap<Integer, Long> receivedSearches = new ConcurrentHashMap<Integer, Long>();

    private long protocolBytesDownloaded = 0;

    private final QueueManager queueManager;
    private final RandomnessManager randomnessManager = new RandomnessManager();

    private byte[] remoteFlags;

    private final Friend remoteFriend;
    private int remoteFriendKeyHash = -1;

    private final GlobalManagerStats stats;

    private final DebugMessageLog debugMessageLog;

    private IncomingQueueListener incomingListener;
    private OutgoingQueueListener outgoingQueueListener;

    private final ConcurrentHashMap<Integer, Long> recentlyClosedChannels = new ConcurrentHashMap<Integer, Long>();

    private boolean mClosing;

    private PacketListener setupPacketListener;

    DatagramConnectionManagerImpl udpManager = DatagramConnectionManagerImpl.get();
    DatagramConnection udpConnection;

    /**
     * outgoing
     * 
     * @param _manager
     * @param remoteFriendAddr
     * @param _remoteFriend
     */
    public FriendConnection(GlobalManagerStats stats, QueueManager _queueManager,
            ConnectionEndpoint remoteFriendAddr, Friend _remoteFriend,
            FileListManager _filelistManager, FriendConnectionListener _listener) {
        remoteFriendAddr
                .addProtocol(new ProtocolEndpointTCP(remoteFriendAddr.getNotionalAddress()));
        if (COConfigurationManager.getBooleanParameter("oneswarm.beta.updates")) {
            debugMessageLog = new DebugMessageLog();
        } else {
            debugMessageLog = null;
        }
        this.queueManager = _queueManager;
        this.outgoing = true;
        this.filelistManager = _filelistManager;
        this.remoteFriend = _remoteFriend;
        this.listener = _listener;
        this.stats = stats;
        this.metaInfoRequestHandler = new MetaInfoRequestHandler();

        byte[][] sharedSecret = new byte[2][0];
        sharedSecret[0] = OneSwarmSslTransportHelperFilterStream.SHARED_SECRET_FOR_SSL_STRING
                .getBytes();
        sharedSecret[1] = getRemotePublicKey();
        this.connectionTime = System.currentTimeMillis();
        logger.finer(getDescription() + ": making outgoing connection to:\n"
                + new String(Base64.encode(getRemotePublicKey())));
        this.connection = NetworkManager.getSingleton().createConnection(remoteFriendAddr,
                new OSF2FMessageEncoder(), new OSF2FMessageDecoder(), true, false, sharedSecret);
        this.friendConnectionQueue = queueManager
                .registerConnectionForQueueHandling(FriendConnection.this);

        // this.hash = getHashOf(remoteFriend.getPublicKey(),
        // this.getRemoteIp(), this.getRemotePort());
        this.connection.connect(null, false, new ConnectionListener() {

            @Override
            public void connectFailure(Throwable failure_msg) {
                logger.fine(getDescription() + ": " + connection + " : connect error: "
                        + failure_msg.getMessage());
                updateFriendConnectionLog(true,
                        "connect attempt failed: " + failure_msg.getMessage());
                close();
            }

            @Override
            public void connectStarted() {
            }

            @Override
            public void connectSuccess(ByteBuffer remaining_initial_data) {
                if (!connection.getTransport().getEncryption()
                        .startsWith(OneSwarmSslTransportHelperFilterStream.SSL_NAME)) {
                    Debug.out("closing outgoing f2f connection without SSL: " + connection + " ("
                            + connection.getTransport().getEncryption() + ")");
                    close();
                    return;
                }
                updateFriendConnectionLog(true, "Connected to: " + getRemoteIp().getHostAddress()
                        + ":" + getRemotePort());

                boolean registered = listener.connectSuccess(FriendConnection.this);
                if (!registered || !connection.isConnected()) {
                    updateFriendConnectionLog(true, "Parallel connection closed");
                    return;
                }
                addQueueListener();
                updateFriendConnectionLog(true, "Added queue listener");

                if (debugMessageLog != null) {
                    connection.getOutgoingMessageQueue().registerQueueListener(
                            new OutgoingQueueListener());
                }
                NetworkManager.getSingleton().startTransferProcessing(connection);
                enableFastMessageProcessing(true);

                sendHandshake();
                updateFriendConnectionLog(true, "Sent handshake...");
            }

            @Override
            public void exceptionThrown(Throwable error) {
                connectionException(error);
            }

            @Override
            public String getDescription() {
                return "connection listener: OSF2F session, outgoing";
            }
        });
    }

    public void setPacketListener(PacketListener listener) {
        this.setupPacketListener = listener;
        friendConnectionQueue.setPacketListener(listener);
    }

    private void addQueueListener() {
        if (incomingListener == null) {
            incomingListener = new IncomingQueueListener();
            connection.getIncomingMessageQueue().registerQueueListener(incomingListener);
        } else {
            Debug.out("tried to register incoming listener multiple times");
        }

        if (debugMessageLog != null) {
            if (outgoingQueueListener == null) {
                outgoingQueueListener = new OutgoingQueueListener();
                connection.getOutgoingMessageQueue().registerQueueListener(outgoingQueueListener);
            } else {
                Debug.out("tried to register outgoing listener multiple times");
            }
        }
    }

    /**
     * Used in ClientServiceConnection and ServerServiceConnection unit tests.
     * Creates a minimal FriendConnection marked as having received a handshake
     * so it thinks it's been started and will try to send data.
     */
    public static FriendConnection createStubForTests(QueueManager _queueManager,
            NetworkConnection _conn, Friend _remoteFriend) {
        return new FriendConnection(_queueManager, _conn, _remoteFriend);
    }

    private FriendConnection(QueueManager _queueManager, NetworkConnection _conn,
            Friend _remoteFriend) {
        // Setting handShakeReceived = true tells AbstractServiceChannelEndpoint
        // that this connection has been started
        this.handShakeReceived = true;
        this.remoteFriend = _remoteFriend;
        this.queueManager = _queueManager;
        this.connection = _conn;
        this.friendConnectionQueue = queueManager
                .registerConnectionForQueueHandling(FriendConnection.this);
        this.outgoing = false;
        this.metaInfoRequestHandler = null;
        this.listener = null;
        this.filelistManager = null;
        this.debugMessageLog = null;
        this.connectionTime = 0;
        this.stats = null;
    }

    /**
     * creates a new incoming connection
     * 
     * @param _connection
     * @param _remoteFriend
     * @param _filelistManager
     */
    public FriendConnection(GlobalManagerStats stats, QueueManager _queueManager,
            NetworkConnection _connection, Friend _remoteFriend, FileListManager _filelistManager,
            FriendConnectionListener _listener) {
        this.queueManager = _queueManager;
        this.outgoing = false;
        this.connection = _connection;
        this.remoteFriend = _remoteFriend;
        this.listener = _listener;
        this.filelistManager = _filelistManager;
        this.connectionTime = System.currentTimeMillis();
        this.stats = stats;
        this.metaInfoRequestHandler = new MetaInfoRequestHandler();
        if (COConfigurationManager.getBooleanParameter("oneswarm.beta.updates")) {
            debugMessageLog = new DebugMessageLog();
        } else {
            debugMessageLog = null;
        }

        friendConnectionQueue = queueManager.registerConnectionForQueueHandling(this);

        // this.hash = getHashOf(remoteFriend.getPublicKey(),
        // this.getRemoteIp(), this.getRemotePort());

        // register our connection listener
        addQueueListener();
        connection.connect(true, new ConnectionListener() {
            @Override
            public void connectFailure(Throwable failure_msg) {
                logger.fine(getDescription() + ": " + connection + " : connect error: "
                        + failure_msg.getMessage());
                close();
            }

            @Override
            public void connectStarted() {
                // nop
            }

            @Override
            public void connectSuccess(ByteBuffer remaining_initial_data) {
                updateFriendConnectionLog(false, "incoming connection from: "
                        + getRemoteIp().getHostAddress());

                boolean registered = listener.connectSuccess(FriendConnection.this);
                if (!registered || !connection.isConnected()) {
                    updateFriendConnectionLog(true, "parallel connection closed");
                    return;
                }

            }

            @Override
            public void exceptionThrown(Throwable error) {
                // ok, something strange happened,
                // notify connection and manager
                connectionException(error);
            }

            @Override
            public String getDescription() {
                return "connection listener: OSF2F session, incoming";
            }
        });
        NetworkManager.getSingleton().startTransferProcessing(connection);
        enableFastMessageProcessing(true);

        this.sendHandshake();

    }

    public void clearTimedOutForwards() {

        List<Integer> timedOutIds = new LinkedList<Integer>();

        for (Integer key : overlayForwards.keySet()) {
            if (overlayForwards.get(key).isTimedOut()) {
                timedOutIds.add(key);
            }
        }
        for (Integer key : timedOutIds) {
            OverlayForward f = overlayForwards.remove(key);

            if (overlayPathLogger.isEnabled()) {
                try {
                    if (f != null) {
                        overlayPathLogger.log(System.currentTimeMillis() + ", timeout_forward, "
                                + f.getChannelId() + ", " + f.getBytesForwarded() + ", "
                                + f.getAge() + ", " + f.getRemoteFriend().getNick() + ", "
                                + f.getRemoteIpPort());
                    }
                } catch (Exception e) {
                    e.printStackTrace();
                }
            }
        }

        /*
         * and clear the recently closed channels maps
         */
        for (Iterator<Integer> iterator = recentlyClosedChannels.keySet().iterator(); iterator
                .hasNext();) {
            Integer channel = iterator.next();
            if (System.currentTimeMillis() - recentlyClosedChannels.get(channel) > RECENTLY_CLOSED_TIME) {
                iterator.remove();
            }
        }

    }

    public void clearTimedOutTransports() {

        List<Integer> timedOutIds = new LinkedList<Integer>();
        for (Integer key : overlayTransports.keySet()) {
            if (overlayTransports.get(key).isTimedOut()) {
                timedOutIds.add(key);
            }
        }

        for (Integer key : timedOutIds) {
            overlayTransports.get(key).closeConnectionClosed(this, "channel timed out");
        }
    }

    public void clearTimedOutSearchRecords() {
        long currTime = System.currentTimeMillis();
        for (Iterator<Long> iterator = receivedSearches.values().iterator(); iterator.hasNext();) {
            Long searchTime = iterator.next();
            long age = currTime - searchTime;
            // delete old ones but keep a slighly longer history to make sure
            // that we don't let any messages through that were in the queue
            if (age > SearchManager.MAX_SEARCH_AGE + 15 * 1000) {
                iterator.remove();
            }
        }
    }

    public void close() {

        mClosing = true;

        if (connection != null) {
            try {
                /*
                 * watch out on this one, it will get the AEMonitor lock which
                 * can dead lock us!
                 */
                if (!((NetworkConnectionImpl) connection).isClosed()) {
                    connection.close();
                }
            } catch (Exception e) {
                logger.warning("got exception when closing network connection: " + e.getMessage());
            }
        }

        // we need to terminate all overlay transports
        List<EndpointInterface> transports = new LinkedList<EndpointInterface>(
                overlayTransports.values());
        for (EndpointInterface overlayTransport : transports) {
            overlayTransport.closeConnectionClosed(this, "friend closed connection");
        }

        // and all forwards
        List<OverlayForward> forwards = new LinkedList<OverlayForward>(overlayForwards.values());
        for (OverlayForward overlayForward : forwards) {
            deregisterOverlayForward(overlayForward.getChannelId(), true);
        }

        // and deregister from the queue manager
        queueManager.deregisterForQueueHandling(this);

        listener.disconnected(FriendConnection.this);

        fileListRequestHandler.close();
        if (udpConnection != null) {
            udpConnection.close();
            udpConnection = null;
        }
        // updateFriendConnectionLog(true, "network connection closed");

    }

    private void connectionException(Throwable error) {
        logger.warning(getDescription() + ": got exception in " + "OSF2F session (" + connection
                + "/" + remoteFriend.getNick() + ") disconnecting: " + error.getMessage()
                + " (from: " + error.toString() + ")");
        String friendLogMessage = error.getMessage();
        boolean expectedError = false;
        if (friendLogMessage == null) {
            expectedError = false;
        } else if (friendLogMessage.startsWith("transport closed")) {
            expectedError = true;
        } else if (friendLogMessage.startsWith("Connection reset by peer")) {
            expectedError = true;
        } else if (friendLogMessage
                .startsWith("An existing connection was forcibly closed by the remote host")) {
            expectedError = true;
        }

        if (!expectedError) {
            StringWriter st = new StringWriter();
            error.printStackTrace(new PrintWriter(st));
            String stackTrace = st.toString();
            friendLogMessage += "\n" + stackTrace;
        }
        this.updateFriendConnectionLog(true, "got exception: " + friendLogMessage);
        close();
    }

    private void updateFriendConnectionLog(boolean append, String message) {
        updateFriendConnectionLog(append, message, Level.FINE);
    }

    private void updateFriendConnectionLog(boolean append, String message, Level level) {
        remoteFriend.updateConnectionLog(append, this.hashCode(), message);
        logger.log(level, remoteFriend.getNick() + ": " + message);
    }

    static RotatingLogger overlayPathLogger = new RotatingLogger("overlay_connections");

    private void deregisterOverlayForward(int channelId, boolean sendReset) {

        OverlayForward f = null;
        lock.lock();
        try {
            f = overlayForwards.remove(channelId);
            recentlyClosedChannels.put(channelId, System.currentTimeMillis());
            activeOverlays--;
        } finally {
            lock.unlock();
        }

        if (f != null && sendReset) {
            f.sendReset();
        }

        if (overlayPathLogger.isEnabled()) {
            try {
                if (f != null) {
                    overlayPathLogger.log(System.currentTimeMillis() + ", deregistered_forward, "
                            + f.getChannelId() + ", " + f.getBytesForwarded() + ", " + f.getAge()
                            + ", " + f.getRemoteFriend().getNick() + ", " + f.getRemoteIpPort());
                }
            } catch (Exception e) {
                e.printStackTrace();
            }
        }

        friendConnectionQueue.clearForwardChannel(channelId);

    }

    void deregisterOverlayTransport(EndpointInterface transport) {
        lock.lock();
        try {
            for (int pathID : transport.getPathID()) {
                overlayTransportPathsId.remove(pathID);
                if (overlayPathLogger.isEnabled()) {
                    overlayPathLogger.log(System.currentTimeMillis() + ", deregistered_path, "
                            + pathID);
                }
            }
            int channelId = transport.getChannelId();
            EndpointInterface exists = overlayTransports.remove(channelId);
            recentlyClosedChannels.put(channelId, System.currentTimeMillis());
            if (exists != null) {
                activeOverlays--;
            }
            if (overlayPathLogger.isEnabled()) {
                overlayPathLogger
                        .log(System.currentTimeMillis() + ", deregistered_transport, "
                                + exists.getChannelId() + ", " + exists.getBytesIn() + ", "
                                + exists.getBytesOut() + ", " + exists.getAge() + ", "
                                + exists.getPathID());
            }
        } finally {
            lock.unlock();
        }
    }

    public void doKeepAliveCheck() {
        if (friendConnectionQueue.getLastMessageSentTime() > KEEP_ALIVE_FREQ) {
            connection.getOutgoingMessageQueue().addMessage(
                    new BTKeepAlive(OSF2FMessage.CURRENT_VERSION), false);
        }
        if (udpConnection != null && udpConnection.getLastMessageSentTime() > KEEP_ALIVE_FREQ) {
            udpConnection.sendUdpOK();
        }
    }

    public void enableFastMessageProcessing(boolean enable) {
        logger.finer(getDescription() + ": setting fast message processing=" + enable);
        if (enable) {
            NetworkManager.getSingleton().upgradeTransferProcessing(connection, null);
            connection.getOutgoingMessageQueue().registerQueueListener(
                    new LowLatencyMessageWriter(this.connection));
        } else {

            // always enable this
            // NetworkManager.getSingleton().upgradeTransferProcessing(connection
            // );
        }
    }

    /**
     * don't override, used in overlaymanager.handleSearch
     */
    @Override
    public boolean equals(Object obj) {
        return super.equals(obj);
    }

    public long getConnectionAge() {
        return System.currentTimeMillis() - connectionTime;
    }

    public int getCurrentUploadSpeed() {
        return friendConnectionQueue.getCurrentUploadSpeedInBps();
    }

    public long getDataBytesDownloaded() {
        return dataBytesDownloaded;
    }

    public long getDataBytesUploaded() {
        return friendConnectionQueue.getDataBytesUploaded();
    }

    public int getForwardQueueLengthBytes() {
        return friendConnectionQueue.getForwardQueueBytes();
    }

    public long getLastMessageRecvTime() {
        return System.currentTimeMillis() - lastByteRecvTime;
    }

    public long getLastMessageSentTime() {
        return friendConnectionQueue.getLastMessageSentTime();
    }

    // Used for unit testing of ClientServiceConnection and
    // ServerServiceConnection
    public OSF2FMessage getLastMessageQueued() {
        return friendConnectionQueue.getLastMessageQueued();
    }

    NetworkConnection getNetworkConnection() {
        return connection;
    }

    public Map<Integer, OverlayForward> getOverlayForwards() {
        return overlayForwards;
    }

    public Map<Integer, EndpointInterface> getOverlayTransports() {
        return overlayTransports;
    }

    public long getProtocolBytesDownloaded() {
        return protocolBytesDownloaded;
    }

    public long getProtocolBytesUploaded() {
        return friendConnectionQueue.getProtocolBytesUploaded();
    }

    public Friend getRemoteFriend() {
        return remoteFriend;
    }

    @Override
    public InetAddress getRemoteIp() {
        return connection.getEndpoint().getNotionalAddress().getAddress();
    }

    public int getRemotePort() {
        return connection.getEndpoint().getNotionalAddress().getPort();
    }

    public byte[] getRemotePublicKey() {
        return remoteFriend.getPublicKey();
    }

    public int getRemotePublicKeyHash() {
        if (remoteFriendKeyHash == -1) {
            remoteFriendKeyHash = Arrays.hashCode(remoteFriend.getPublicKey());
        }
        return remoteFriendKeyHash;
    }

    public int getSendQueueCurrentCapacity(int channelId) {
        if (udpConnection != null && udpConnection.isSendingActive()) {
            return udpConnection.getCapacityForChannel(channelId);
        } else if (this.overlayTransports.size() > 0) {
            return (FriendConnectionQueue.MAX_FRIEND_QUEUE_LENGTH - friendConnectionQueue
                    .getForwardQueueBytes()) / this.overlayTransports.size();
        } else {
            return 0;
        }
    }

    public int getSendQueuePotentialCapacity(int channelId) {
        if (udpConnection != null && udpConnection.isSendingActive()) {
            return udpConnection.getPotentialCapacityForChannel(channelId);
        } else if (this.overlayTransports.size() > 0) {
            return (FriendConnectionQueue.MAX_FRIEND_QUEUE_LENGTH) / this.overlayTransports.size();
        } else {
            return 0;
        }
    }

    private void handleChannelMsg(Message message) {
        if (message instanceof OSF2FChannelDataMsg) {
            OSF2FChannelDataMsg msg = (OSF2FChannelDataMsg) message;
            int channelId = msg.getChannelId();

            if (overlayTransports.containsKey(channelId)) {
                // ok, this is a msg to us
                EndpointInterface t = overlayTransports.get(channelId);
                msg.setForward(false);
                // this might we the first message we get in this channel
                // means that the other side responded to our channel setup
                // we need to start the peer transport above the overlay
                if (!t.isStarted()) {
                    t.start();
                }
                // and tell it that we got a message
                t.incomingOverlayMsg(msg);
            } else if (overlayForwards.containsKey(channelId)) {
                // this is a message we should forward
                OverlayForward f = overlayForwards.get(channelId);
                msg.setForward(true);
                f.forwardMessage(msg);
            } else {
                if (!recentlyClosedChannels.containsKey(msg.getChannelId())) {
                    logger.warning(getDescription()
                            + ": got channel message for unregistered channel id "
                            + msg.getChannelId() + " / " + msg.getCreatedTime());
                }
            }

        } else {
            logger.warning(getDescription() + ": handleChannelMsg "
                    + "got non OSF2FChannelMsg message: " + message.getDescription());
        }
    }

    private void handleChannelReset(Message message) {

        if (message instanceof OSF2FChannelReset) {
            OSF2FChannelReset msg = (OSF2FChannelReset) message;
            if (overlayTransports.containsKey(msg.getChannelId())) {
                overlayTransports.get(msg.getChannelId()).closeChannelReset();

            } else if (overlayForwards.containsKey(msg.getChannelId())) {
                final OverlayForward overlayForward = overlayForwards.get(msg.getChannelId());
                // if we get a channel reset it means that the source of the
                // reset doesn't want to get any more messages with that channel
                // id, figure out where we get them from and close the forward +
                // flush the queue
                overlayForward.gotChannelReset();
            } else {
                if (!recentlyClosedChannels.containsKey(msg.getChannelId())) {
                    logger.warning(getDescription()
                            + ": got channel reset for unregistered channel id "
                            + msg.getChannelId());
                }
            }
        } else {
            Debug.out(remoteFriend.getNick() + ": handleChannelReset "
                    + "got non OSF2FChannelReset message: " + message.getDescription());
        }

    }

    private void handleChannelSetup(Message message) {
        if (message instanceof OSF2FHashSearchResp) {
            OSF2FHashSearchResp msg = (OSF2FHashSearchResp) message;
            listener.gotSearchResponse(this, msg);
        } else {
            Debug.out(remoteFriend.getNick() + ": handleChannelSetup "
                    + "got non channelSetup message: " + message.getDescription());
        }
    }

    private final static int MAX_FILE_LIST_REQUESTS = 10;

    private int numFileListRequestsReceived = 0;

    private void handleFileListRequest(OSF2FTextSearch message) {
        try {
            if (numFileListRequestsReceived > 0) {
                updateFriendConnectionLog(true,
                        "strange, remote friend is sending more than 1 file list request");
                logger.warning(getDescription() + ": more than 1 file list request received");
            } else if (numFileListRequestsReceived > MAX_FILE_LIST_REQUESTS) {
                String warnMsg = "banning friend for 10 minutes, sent more than "
                        + MAX_FILE_LIST_REQUESTS + " file list requests (DOS?)";
                updateFriendConnectionLog(true, warnMsg);
                remoteFriend.setFriendBannedUntil("file list request spam",
                        System.currentTimeMillis() + 10 * 60 * 1000);
                logger.warning(warnMsg);
                close();
                return;
            }
            numFileListRequestsReceived++;
            int prevId = Integer.parseInt(message.getSearchString());
            this.sendFileListResponse(message.getRequestType(), message.getSearchID(), prevId, true);

        } catch (NumberFormatException e) {
            Debug.out("error when parsing file list request, '" + message.getSearchString()
                    + "' is not a number");
        }

    }

    private void handleHandshake(Message message) {

        if (message instanceof OSF2FHandshake) {
            OSF2FHandshake hs = (OSF2FHandshake) message;
            handShakeReceived = true;
            updateFriend();
            remoteFlags = hs.getFlags();

            String extras = "";
            if (this.hasChatSupport()) {
                // System.out.println(this + " has chat");
                extras += "(Chat)";
            }
            if (this.hasExtendedFileListsSupport()) {
                // System.out.println(this + " has extended file lists");
                extras += "(Extended file lists)";
            }
            if (this.hasExtendedDHTKeyNegotiationSupport()) {
                extras += "(dht loc)";
            }
            if (this.hasUdpSupport()) {
                extras += "(udp)";
            }

            /*
             * check that we still are connected, if we are mark friends
             * connected
             */
            if (!connection.isConnected()) {
                Debug.out("got handshake message but connection is already closed: "
                        + remoteFriend.getNick());
                updateFriendConnectionLog(true,
                        "got handshake message but connection is already closed");
                close();
                return;
            }
            remoteFriend.connected();

            updateFriendConnectionLog(true, "received remote handshake, " + extras);
            // check if we need to sync up on the dht publish location
            if (outgoing && this.hasExtendedDHTKeyNegotiationSupport()
                    && remoteFriend.isDhtLocationConfirmed() == false) {
                // if we are outgoing, send the dht location
                updateFriendConnectionLog(true, "proposing dht location");
                sendDhtLocation();
            }

            // If the remote side supports UDP, send over the keys
            if (this.hasUdpSupport()) {
                try {
                    udpConnection = udpManager.createConnection(this);
                    initDatagramConnection();
                } catch (Exception e) {
                    logger.warning("Unable to create udp connection");
                    e.printStackTrace();
                }
            }

            if (remoteFriend.isRequestFileList()) {
                sendFileListRequest(OSF2FMessage.FILE_LIST_TYPE_COMPLETE, null);
                // handshake is considered complete once the friend send the
                // filelist
                updateFriendConnectionLog(true, "filelist requested");
            } else {
                // else, just spoof a new file list
                FileList fileList = new FileList();
                filelistManager.receivedFriendFileList(remoteFriend,
                        OSF2FMessage.FILE_LIST_TYPE_COMPLETE, fileList);
                fileListRequestHandler.notifyListenerComplete(fileList);
            }

            while (bufferedMessages.size() != 0) {
                sendMessage(bufferedMessages.remove(), true);
            }
        } else {
            Debug.out("handleHandshake got non " + "handshake message: " + message.getDescription());
        }
    }

    @Override
    public void initDatagramConnection() {
        if (udpConnection != null) {
            updateFriendConnectionLog(true, "sending over udp crypto key");
            sendMessage(udpConnection.createInitMessage(), true);
        }
    }

    private void sendDhtLocation() {
        /*
         * protocol:
         * 
         * if( no address is confirmed) the user connecting (u1) generate 2
         * addresses, start to publish and read from both the special locations
         * and the public key based locations
         * 
         * u1 sends the addresses
         * 
         * the user responding (u2) will save the addresses, set the dht
         * location status to confirmed and then send back a new message with
         * the addresses
         * 
         * u1 receives the addresses, sets dht location status to confirmed and
         * stops updating the public key based addresses
         */

        byte[] proposedDhtReadLocation = new byte[20];
        byte[] proposedDhtWriteLocation = new byte[20];
        Random r = new Random();
        r.nextBytes(proposedDhtReadLocation);
        r.nextBytes(proposedDhtWriteLocation);
        remoteFriend.setDhtReadLocation(proposedDhtReadLocation);
        remoteFriend.setDhtWriteLocation(proposedDhtWriteLocation);
        OSF2FMain.getSingelton().getFriendManager().flushToDisk(true, true, false);
        updateFriendConnectionLog(true, "dht locations flushed to disk");
        /*
         * the read and write locations in hte message are from the point of the
         * receiver, which means that they are swapped compared to what we have
         * stored locally
         * 
         * the location we write to is the location the other user should read
         * from, and similarly for the read location
         */
        sendMessage(new OSF2FDhtLocation(OSF2FMessage.CURRENT_VERSION,
                remoteFriend.getDhtWriteLocation(), remoteFriend.getDhtReadLocation()));
    }

    public boolean hasChatSupport() {
        if (remoteFlags == null) {
            return false;
        }

        return (remoteFlags[0] & OSF2FHandshake.SUPPORTS_CHAT) == OSF2FHandshake.SUPPORTS_CHAT;
    }

    public boolean hasExtendedFileListsSupport() {
        if (remoteFlags == null) {
            return false;
        }

        return (remoteFlags[0] & OSF2FHandshake.SUPPORTS_EXTENDED_FILE_LISTS) == OSF2FHandshake.SUPPORTS_EXTENDED_FILE_LISTS;
    }

    public boolean hasExtendedDHTKeyNegotiationSupport() {
        if (remoteFlags == null) {
            return false;
        }

        return (remoteFlags[0] & OSF2FHandshake.SUPPORTS_DHT_LOCATION_HS) == OSF2FHandshake.SUPPORTS_DHT_LOCATION_HS;
    }

    public boolean hasUdpSupport() {
        if (remoteFlags == null) {
            return false;
        }

        return (remoteFlags[0] & OSF2FHandshake.SUPPORTS_UDP) == OSF2FHandshake.SUPPORTS_UDP;
    }

    public int getImageMetaInfoQueueSize() {
        return metaInfoRequestHandler.imageRequests.size();
    }

    public void clearOldMetainfoRequests() {
        metaInfoRequestHandler.clearOldRequests();
    }

    public int getTorrentMetaInfoQueueSize() {
        return metaInfoRequestHandler.torrentRequests.size();
    }

    private void handleMetainfoRequest(Message message) {
        if (message instanceof OSF2FMetaInfoReq) {
            OSF2FMetaInfoReq req = (OSF2FMetaInfoReq) message;
            int channelId = req.getChannelId();

            // first, check if we can handle it...
            if (metaInfoRequestHandler.canRespond(req)) {
                metaInfoRequestHandler.handleMetaInfoRequest(req);
            } else if (overlayForwards.containsKey(channelId)) {
                // we have this path registered, sent it to the other end
                overlayForwards.get(channelId).forwardMessage(req);
            } else {
                Debug.out("got meta info request message " + "with unknown channel Id: "
                        + req.getDescription());
            }
        } else {
            Debug.out("handleMetainfoRequest got non " + "metainfoRequest message: "
                    + message.getDescription());
        }
    }

    private void handleMetainfoResponse(Message message) {
        if (message instanceof OSF2FMetaInfoResp) {
            OSF2FMetaInfoResp resp = (OSF2FMetaInfoResp) message;
            int channelId = resp.getChannelId();
            // channel id 0 means that we shouldn't forward, this is just
            // between friends
            if (channelId == 0) {
                metaInfoRequestHandler.handleMetaInfoResponse(resp);
            } else if (metaInfoRequestHandler.handleMetaInfoResponse(resp)) {
                // we sent this, all is good.
            } else if (overlayForwards.containsKey(channelId)) {
                overlayForwards.get(channelId).forwardMessage(resp);
            } else {
                Debug.out("got meta info resp message " + "with unknown channel Id: "
                        + resp.getDescription());
            }

        } else {
            Debug.out("handleMetaInfoResponse got non " + "metaInfoResponse message: "
                    + message.getDescription());
        }
    }

    private void handleChat(Message message) {
        if (message instanceof OSF2FChat) {
            OSF2FChat chat = (OSF2FChat) message;

            if (remoteFriend.isAllowChat() == false) {
                logger.warning(getDescription() + "Received chat from " + this
                        + " even though not allowed, dropping.");
                return;
            }

            logger.finer(getDescription() + "received chat: " + chat.getPlainText() + " from "
                    + this.getRemoteFriend().getNick());
            ChatDAO.get().queuePlaintextMessageForProcessing(chat.getPlainText(),
                    this.getRemoteFriend());
        } else {
            Debug.out(getDescription() + "handleChat got non " + "chat message: "
                    + message.getDescription());
        }
    }

    private void handleSearch(Message message) {

        boolean possiblePrune = true;

        // Update the stats based on the _raw_ volume of searches we observe.
        if (message instanceof OSF2FTextSearch) {
            OSF2FTextSearch cast = (OSF2FTextSearch) message;
            if (cast.getSearchString().startsWith("sha1;")) {
                stats.sha1PrefixSearchReceived();
            } else if (cast.getSearchString().startsWith("ed2k;")) {
                stats.ed2kPrefixSearchReceived();
            } else if (cast.getSearchString().startsWith("id;")) {
                stats.idPrefixSearchReceived();
            } else {
                stats.textSearchReceived();
            }

        } else if (message instanceof OSF2FHashSearch) {
            stats.hashSearchReceived();
        }

        if (message instanceof OSF2FTextSearch) {
            OSF2FTextSearch asSearch = (OSF2FTextSearch) message;
            if (asSearch.getSearchString().startsWith("sha1;") == false
                    && asSearch.getSearchString().startsWith("ed2k;") == false) {
                possiblePrune = false;
            } else {
                // Just always skip sha1;, ed2k; searches for now.
                // No search drop in 0.7.5
                // return;
            }
        } else {
            // For now, just disable early drops
            possiblePrune = false;
        }

        if (possiblePrune) {
            // Early drop if we have it in the bloom filter
            SearchManager searchManager = OSF2FMain.getSingelton().getOverlayManager()
                    .getSearchManager();
            if (message instanceof OSF2FSearch) {
                OSF2FSearch asSearch = (OSF2FSearch) message;
                if (searchManager.isSearchInBloomFilter(asSearch)) {
                    logger.fine("Early drop of search in BF: " + asSearch.getDescription());
                    return;
                }
            }

            // Start probablistically dropping
            double dropProb = searchManager.getFriendSearchDropProbability(this.getRemoteFriend());
            if (random.nextDouble() < dropProb) {
                logger.fine("SearchQueuePressure drop: " + dropProb + " "
                        + getRemoteFriend().getNick());
                return;
            }
        }

        incomingSearchRate.addValue(1);

        long average = incomingSearchRate.getAverage();

        if (average > MAX_INCOMING_SEARCH_RATE) {
            remoteFriend.updateConnectionLog(true,
                    "Search spam detected, closing connection, friend banned for 10 min");
            remoteFriend.setFriendBannedUntil("search spam",
                    System.currentTimeMillis() + 10 * 60 * 1000);
            this.updateFriendConnectionLog(true, "Search spam detected");
            close();
            return;
        }
        if (logger.isLoggable(Level.FINEST)) {
            logger.finest("Incoming search. desc: " + getDescription() + " , rate=" + average);
        }
        if (message instanceof OSF2FSearch) {
            OSF2FSearch msg = (OSF2FSearch) message;
            // check special case, search ID = 0 means no forward
            if (msg.getSearchID() == 0) {
                if (message instanceof OSF2FTextSearch) {
                    handleFileListRequest((OSF2FTextSearch) message);
                } else {
                    Debug.out(getDescription() + "handleSearch got search with id=0, "
                            + "but it wasn't an TextSearch!");
                }
            } else {
                receivedSearches.put(msg.getSearchID(), System.currentTimeMillis());
                listener.gotSearchMessage(this, msg);
            }
        } else {
            Debug.out(getDescription() + "handleSearch got non " + "OSF2FSearch message: "
                    + message.getDescription());
        }

    }

    private void handleTextSearchReponse(Message message) {
        if (message instanceof OSF2FTextSearchResp) {
            OSF2FTextSearchResp resp = (OSF2FTextSearchResp) message;
            if (resp.getFileListType() == OSF2FMessage.FILE_LIST_TYPE_COMPLETE) {
                fileListRequestHandler.handleFileListResponse(resp);
            } else if (resp.getFileListType() == OSF2FMessage.FILE_LIST_TYPE_PARTIAL) {
                listener.gotSearchResponse(this, resp);
            } else {
                Debug.out(getDescription() + "File list type: " + resp.getFileListType()
                        + " not implemented");
            }
        } else {
            Debug.out(getDescription() + "handleFileListResponse "
                    + "got non fileListResponse message: " + message.getDescription());
        }
    }

    private void handleDhtLocationMessage(OSF2FDhtLocation message) {
        // if we are outgoing we already sent the message, check if it matches
        // and if it does confirm the location
        if (outgoing) {
            byte[] readLocation = message.getReadLocation();
            byte[] storedReadLocation = remoteFriend.getDhtReadLocation();

            if (!Arrays.equals(readLocation, storedReadLocation)) {
                updateFriendConnectionLog(true,
                        "got inconsistent dht read location data, not confirming dht location");
                return;
            }

            byte[] writeLocation = message.getWriteLocation();
            byte[] storedWriteLocation = remoteFriend.getDhtWriteLocation();
            if (!Arrays.equals(writeLocation, storedWriteLocation)) {
                updateFriendConnectionLog(true,
                        "got inconsistent dht write location data, not confirming dht location");
                return;
            }
            /*
             * ok, the other side replied with the right locations, confirm the
             * location and stop updating the dht redundantly
             */
            OSF2FMain.getSingelton().getFriendManager().flushToDisk(true, true, false);
            updateFriendConnectionLog(true, "dht location confirmed");
            remoteFriend.setDhtLocationConfirmed(true);
        } else {
            // incoming
            byte[] readLocation = message.getReadLocation();
            remoteFriend.setDhtReadLocation(readLocation);
            byte[] writeLocation = message.getWriteLocation();
            remoteFriend.setDhtWriteLocation(writeLocation);
            remoteFriend.setDhtLocationConfirmed(true);
            OSF2FMain.getSingelton().getFriendManager().flushToDisk(true, true, false);
            /*
             * again, the read and write locations in the message are from the
             * standpoint of the receiver which means that they are swapped from
             * our standpoint
             */
            sendMessage(new OSF2FDhtLocation(OSF2FMessage.CURRENT_VERSION,
                    remoteFriend.getDhtWriteLocation(), remoteFriend.getDhtReadLocation()));
            updateFriendConnectionLog(true,
                    "stored dht location, sending dht location confirmation");
        }
    }

    @Override
    public int hashCode() {
        // don't override, return hash;
        return super.hashCode();
    }

    public boolean hasRegisteredPath(int pathID) {
        return overlayTransportPathsId.containsKey(pathID);
    }

    public boolean isHandshakeReceived() {
        return handShakeReceived;
    }

    public boolean isFileListReceived() {
        return filelistReceived;
    }

    @Override
    public boolean isLanLocal() {
        return connection.isLANLocal();
    }

    public boolean isReadyForWrite(WriteQueueWaiter writeQueueWaiter) {
        return friendConnectionQueue.isReadyForTransportWrite(writeQueueWaiter);
    }

    public boolean isTimedOut() {
        if (!handShakeReceived
                && System.currentTimeMillis() - connectionTime > INITIAL_HANDSHAKE_TIMEOUT) {
            // if the handshake hasn't completed in 60s it will never
            // complete...
            logger.fine(getDescription() + "handshake timeout, closing: " + this);
            updateFriendConnectionLog(true, "handshake timeout, closing");
            return true;
        }
        long timeSinceLastMsg = System.currentTimeMillis() - lastByteRecvTime;

        if (!isFileListReceived() && System.currentTimeMillis() - connectionTime > TIMOUT_FILELIST) {
            logger.finer(getDescription() + "closing friend connection: " + this
                    + " (filelist timed out)");
            Debug.out("closing friend connection: " + this
                    + " (filelist timed out), timeSinceLastMsg=" + timeSinceLastMsg
                    + " bytes sent=" + (getProtocolBytesUploaded() + getDataBytesUploaded())
                    + " recv=" + (getProtocolBytesDownloaded() + getDataBytesDownloaded())
                    + " friend status: " + remoteFriend.getStatus());
            updateFriendConnectionLog(true, "closing friend connection (filelist timed out)");
            return true;
        }
        if (lastByteRecvTime != 0 && timeSinceLastMsg > KEEP_ALIVE_TIMEOUT) {
            logger.finer(getDescription() + "closing friend connection: " + this + " (timed out,"
                    + timeSinceLastMsg + ")");
            updateFriendConnectionLog(true, "closing friend connection (timed out)");
            return true;
        }
        return false;
    }

    void registerOverlayForward(OSF2FSearchResp currentSetupMsg, FriendConnection conn,
            OSF2FSearch search, boolean searcherSide)
            throws FriendConnection.OverlayRegistrationError {
        lock.lock();
        try {
            if (overlayForwards.containsKey(currentSetupMsg.getChannelID())) {
                OverlayForward existing = overlayForwards.get(currentSetupMsg.getChannelID());

                final String existingNick = existing.getRemoteFriend().getNick();
                final String currentNick = conn.getRemoteFriend().getNick();

                String existingType = existing.getSetupMessage().getID();
                String currentType = currentSetupMsg.getID();

                if (existingNick.equals(currentNick)) {
                    throw new OverlayRegistrationError(getRemoteFriend().getNick(),
                            currentSetupMsg.getChannelID(), "existing channel id: exid="
                                    + Integer.toHexString(existing.getChannelId()) + " exbytes="
                                    + existing.getBytesForwarded() + " exage=" + existing.getAge()
                                    + " extarget=" + existingNick + " cutarget=" + currentNick
                                    + " exside=" + existing.isSearcherSide() + " cuside="
                                    + searcherSide + " registered=" + overlayForwards.size()
                                    + " ctype=" + currentType + " extype=" + existingType);
                } else {
                    throw new OverlayRegistrationError("collision", currentSetupMsg.getChannelID(),
                            "colliding channel id: exid="
                                    + Integer.toHexString(existing.getChannelId()) + " exbytes="
                                    + existing.getBytesForwarded() + " exage=" + existing.getAge()
                                    + " extarget=" + existingNick + " cutarget=" + currentNick
                                    + " exside=" + existing.isSearcherSide() + " cuside="
                                    + searcherSide + " registered=" + overlayForwards.size()
                                    + " ctype=" + currentType + " extype=" + existingType);
                }
            }
            overlayForwards.put(currentSetupMsg.getChannelID(),
                    new OverlayForward(currentSetupMsg.getChannelID(), conn, search,
                            currentSetupMsg, searcherSide));

            activeOverlays++;

        } finally {
            lock.unlock();
        }
    }

    public void registerOverlayTransport(EndpointInterface transport)
            throws OverlayRegistrationError {
        lock.lock();
        try {
            int channelId = transport.getChannelId();
            if (overlayTransports.containsKey(channelId)) {
                Debug.out(getDescription() + "tried to register existing channel id, "
                        + "this should _never_ happen " + this);
                throw new FriendConnection.OverlayRegistrationError(getRemoteFriend().getNick(),
                        channelId, "existing channel id");

            }
            overlayTransports.put(channelId, transport);
            for (int pathID : transport.getPathID()) {
                if (overlayTransportPathsId.containsKey(pathID)) {
                    Debug.out(getDescription() + "tried to register existing path id, "
                            + "this should _never_ happen " + this);
                    // TODO(willscott): determine appropriate channelID here.
                    throw new FriendConnection.OverlayRegistrationError(
                            getRemoteFriend().getNick(), 0, "existing path id");
                }
                overlayTransportPathsId.put(pathID, true);
            }
            activeOverlays++;

        } finally {
            lock.unlock();
        }
    }

    void sendChannelMsg(OSF2FChannelMsg message, boolean transport) {
        if (udpConnection != null && message.isDatagram() && udpConnection.isSendingActive()
                && message instanceof OSF2FServiceDataMsg) {
            sendUdpPacket((OSF2FServiceDataMsg) message);
            return;
        }
        if (debugMessageLog != null) {
            debugMessageLog.messageQueuedChannel(message.getDescription());
        }
        if (transport) {
            friendConnectionQueue.queuePacketForceQueue(QueueBuckets.TRANSPORT, message);
        } else {
            friendConnectionQueue.queuePacketForceQueue(QueueBuckets.FORWARD, message);
        }
    }

    void sendChannelRst(OSF2FChannelReset message) {
        friendConnectionQueue.queuePacket(QueueBuckets.FORWARD, message, false);
    }

    void sendChannelSetup(OSF2FHashSearchResp message, boolean forwarded) {
        // we need to add some deterministic randomness to this.
        // The goal is to be able to uniquely identify a path
        // without leaking the connections link id
        // (new RuntimeException()).printStackTrace();
        message.updatePathID(randomnessManager.getDeterministicRandomInt(message.getPathID()));
        if (forwarded) {
            friendConnectionQueue.queuePacketForceQueue(QueueBuckets.FORWARD, message);
        } else {
            friendConnectionQueue.queuePacketForceQueue(QueueBuckets.TRANSPORT, message);
        }
    }

    public void sendFileListRequest(byte type, PluginCallback<FileList> callback) {
        if (type == OSF2FMessage.FILE_LIST_TYPE_COMPLETE) {
            fileListRequestHandler.sendFileListRequest(callback);
        } else {
            throw new RuntimeException("File list type: " + type + " not implemented");
        }
    }

    private void sendFileListResponse(byte type, int searchId, int lastId,
            boolean sendResponseOnNoChange) {
        long t = System.currentTimeMillis();
        FileList fileListToSendToFriend = filelistManager.getFileListToSendToFriend(remoteFriend);
        byte[] bytesToSend;
        if (lastFileListSentToFriend == fileListToSendToFriend.getListId()) {
            // if there is no change in the file list, skip the response unless
            // it is specifically asked for
            logger.finer(getDescription() + "file list for " + this.getRemoteFriend().getNick()
                    + " unchanged, skipping file list send");

            if (!sendResponseOnNoChange) {
                return;
            }
            bytesToSend = new byte[0];
        } else {

            logger.finer(getDescription() + "file list for " + this.getRemoteFriend().getNick()
                    + " changed, sending new list");

            lastFileListSentToFriend = fileListToSendToFriend.getListId();
            if (this.hasExtendedFileListsSupport() == false) {
                logger.finer(getDescription() + "sending basic flist: "
                        + this.getRemoteFriend().getNick());
                bytesToSend = FileListManager.encode_basic(fileListToSendToFriend, true);
            } else {
                logger.finer(getDescription() + "sending extended flist"
                        + this.getRemoteFriend().getNick());
                bytesToSend = FileListManager.encode_extended(fileListToSendToFriend, true);
                logger.finest(getDescription() + " the bytes of extended: "
                        + ByteFormatter.encodeString(bytesToSend));
            }
        }
        logger.finer(getDescription() + "sending custom list to friend, bytes="
                + bytesToSend.length + " took " + (System.currentTimeMillis() - t)
                + "ms to generate");
        int channelId = 0;
        OSF2FTextSearchResp msg = new OSF2FTextSearchResp(OSF2FMessage.CURRENT_VERSION,
                OSF2FMessage.FILE_LIST_TYPE_COMPLETE, searchId, channelId, bytesToSend);
        sendMessage(msg, QueueBuckets.CONTROL, true);
    }

    public void sendChat(String plaintextMessage) {
        if (logger.isLoggable(Level.FINE)) {
            logger.fine("[" + this.getRemoteFriend().getNick() + "]: Sending chat message: "
                    + plaintextMessage);
        }

        connection.getOutgoingMessageQueue().addMessage(new OSF2FChat((byte) 1, plaintextMessage),
                false);
    }

    private void sendHandshake() {
        if (remoteFriend.isAllowChat()) {
            connection.getOutgoingMessageQueue().addMessage(
                    new OSF2FHandshake((byte) 1, OSF2FHandshake.OS_FLAGS), false);
        } else {
            /**
             * Pretend not to support chat.
             */
            byte[] my_flags = new byte[OSF2FHandshake.OS_FLAGS.length];
            System.arraycopy(OSF2FHandshake.OS_FLAGS, 0, my_flags, 0, my_flags.length);
            my_flags[0] ^= OSF2FHandshake.SUPPORTS_CHAT;
            connection.getOutgoingMessageQueue().addMessage(new OSF2FHandshake((byte) 1, my_flags),
                    false);
        }
    }

    private void sendMessage(OSF2FMessage msg) {
        sendMessage(msg, false);
    }

    private void sendMessage(OSF2FMessage msg, boolean skipQueue) {
        sendMessage(msg, QueueBuckets.CONTROL, skipQueue);
    }

    private void sendMessage(OSF2FMessage msg, QueueBuckets queueBuckets, boolean skipQueue) {
        if (!handShakeReceived) {
            bufferedMessages.add(msg);
            logger.finer(getDescription() + "waiting for handshake to complete, queue size: "
                    + bufferedMessages.size());
        } else {
            friendConnectionQueue.queuePacket(QueueBuckets.CONTROL, msg, skipQueue);
        }
    }

    public void sendMetaInfoRequest(byte type, int channelId, byte[] infoHash, int lengthHint,
            PluginCallback<byte[]> callback) {
        if (type == OSF2FMessage.METAINFO_TYPE_BITTORRENT
                || type == OSF2FMessage.METAINFO_TYPE_THUMBNAIL) {
            metaInfoRequestHandler.sendMetaInfoRequest(type, channelId, infoHash, lengthHint,
                    callback);
        } else {
            throw new RuntimeException("Meta info type: " + type + " not implemented");
        }
    }

    public GlobalManagerStats getStats() {
        return stats;
    }

    void sendSearch(OSF2FSearch search, boolean skipQueue) {
        if (receivedSearches.containsKey(search.getSearchID())) {
            logger.finer("not sending search, this search id is already received from this friend");
            return;
        }
        long average = outgoingSearchRate.getAverage();
        if (average > MAX_OUTGOING_SEARCH_RATE) {
            logger.warning(getDescription() + "Dropping search, sending too fast");
            return;
        }
        outgoingSearchRate.addValue(1);

        if (search instanceof OSF2FTextSearch) {
            stats.textSearchSent();
        } else if (search instanceof OSF2FHashSearch) {
            stats.hashSearchSent();
        } else if (search instanceof OSF2FSearchCancel) {
            stats.searchCancelSent();
        }

        if (logger.isLoggable(Level.FINE) && search instanceof OSF2FTextSearch) {
            logger.finer("Forwarding text search: " + ((OSF2FTextSearch) search).getSearchString());
        }

        logger.finest(getDescription() + "forwarding search, rate=" + average);
        sendMessage(search, skipQueue);
    }

    void sendTextSearchResp(OSF2FTextSearchResp message, boolean forwarded) {
        if (forwarded) {
            sendMessage(message, QueueBuckets.FORWARD, false);
        } else {
            sendMessage(message, QueueBuckets.TRANSPORT, false);
        }

    }

    private String desc = null;

    @Override
    public String toString() {
        if (desc == null) {
            desc = connection + " :: " + remoteFriend + " id=" + hashCode();
        }
        return desc;
    }

    // private class OutgoingQueueListener implements
    // OutgoingMessageQueue.MessageQueueListener {
    //
    // private long packetNum = 0;
    //
    // public void dataBytesSent(int byte_count) {
    // dataBytesUploaded += byte_count;
    // remoteFriend.updateUploaded(byte_count);
    // }
    //
    // public boolean messageAdded(Message message) {
    //
    // queueLengthBytes = connection.getOutgoingMessageQueue().getTotalSize();
    // // System.out.println(" added: " + message + " , queue: "
    // // + queueLengthBytes + " bytes ");
    // messageQueueTimes.put(message.hashCode(), System.currentTimeMillis());
    // return (true);
    // }
    //
    // public void messageQueued(Message message) {
    // // System.out.println(" queued: " + message);
    // }
    //
    // public void messageRemoved(Message message) {
    // // System.out.println(" removed: " + message);
    // messageQueueTimes.remove(message.hashCode());
    // queueLengthBytes = connection.getOutgoingMessageQueue().getTotalSize();
    // message.destroy();
    // }
    //
    // public void messageSent(Message message) {
    // lastMessageSentTime = System.currentTimeMillis();
    // packetNum++;
    // int len = 0;
    // DirectByteBuffer[] b = message.getData();
    // for (int i = 0; i < b.length; i++) {
    // len += b[i].position(DirectByteBuffer.SS_NET);
    // }
    // queueLengthBytes = connection.getOutgoingMessageQueue().getTotalSize();
    // Long queued = messageQueueTimes.remove(message.hashCode());
    //
    // if (queued != null) {
    // queueLengthMs = System.currentTimeMillis() - queued;
    // }
    // if (!message.getID().equals(OSF2FMessage.ID_OS_CHANNEL_MSG) || packetNum
    // % 100 == 0) {
    // logger.fine(" sent: " + message.getDescription() + " " + len +
    // " bytes, queue: " + queueLengthBytes + " (" + queueLengthMs + "ms) \t::"
    // + FriendConnection.this);
    // // printRatelimitInfo();
    // }
    //
    // readyForWrite();
    // }
    //
    // public void protocolBytesSent(int byte_count) {
    // protocolBytesUploaded += byte_count;
    // remoteFriend.updateUploaded(byte_count);
    // }
    //
    // public void flush() {
    // }
    // }

    public void triggerFileListSend() {
        this.sendFileListResponse(OSF2FMessage.FILE_LIST_TYPE_COMPLETE, 0, -1, false);
        // if (remoteFriend.isRequestFileList()) {
        // sendFileListRequest(OSF2FMessage.FILE_LIST_TYPE_COMPLETE, null);
        // }
    }

    public String getDebugMessageLog() {
        if (debugMessageLog == null) {
            return "debug messages only available in beta mode, if you just enabled beta mode messages are available after reconnect";
        }
        return debugMessageLog.getLog();
    }

    public String getQueueDebug() {
        return friendConnectionQueue.getDebug() + "\nrecent search size=" + receivedSearches.size();
    }

    public int getTotalOutgoingQueueLengthBytes() {
        return friendConnectionQueue.getTotalOutgoingQueueLengthBytes();
    }

    private void updateFriend() {
        remoteFriend.setLastConnectIP(getRemoteIp());
        remoteFriend.updateConnectedDate();
        if (outgoing) {
            remoteFriend
                    .setLastConnectPort(connection.getEndpoint().getNotionalAddress().getPort());
        }
        logger.fine(getDescription() + "updating friend: out=" + outgoing + " friend="
                + remoteFriend);
    }

    private String getDescription() {
        return remoteFriend.getNick() + ": ";
    }

    public static int getHashOf(byte[] publicKey, InetAddress addr, int port) {
        return Arrays.hashCode(publicKey)
                ^ (int) OneSwarmSslTools.unsignedIntToLong(addr.getAddress()) ^ port;
    }

    private class DebugMessageLog {
        private final NumberFormat formatter = new DecimalFormat("0,000.000");
        private final NumberFormat numFormatter = new DecimalFormat("000");

        private final static int LOG_LENGTH = 30;
        LinkedList<MessageLogEntry> log = new LinkedList<MessageLogEntry>();
        private long bytesRecv = 0;

        private int sentNum = 0;
        private int queuedNum = 0;
        private int recvNum = 0;

        public synchronized void bytesReceived(long num) {
            bytesRecv += num;
        }

        private long bytesSent = 0;

        public synchronized void bytesSent(long num) {
            bytesSent += num;
        }

        public synchronized void messageReceived(String msg) {
            recvNum++;
            if (log.size() > LOG_LENGTH) {
                log.removeLast();
            }
            bytesRecv = 0;
            log.addFirst(new MessageLogEntry("recv ", msg, recvNum));
        }

        public synchronized void messageSent(String msg) {
            sentNum++;
            if (log.size() > LOG_LENGTH) {
                log.removeLast();
            }
            bytesSent = 0;
            log.addFirst(new MessageLogEntry("sent ", msg, sentNum));
        }

        public synchronized void messageQueuedListener(String msg) {
            queuedNum++;
            if (log.size() > LOG_LENGTH) {
                log.removeLast();
            }
            log.addFirst(new MessageLogEntry("que2 ", msg, queuedNum));
        }

        public synchronized void messageQueuedChannel(String msg) {
            queuedNum++;
            if (log.size() > LOG_LENGTH) {
                log.removeLast();
            }
            log.addFirst(new MessageLogEntry("que1 ", msg, queuedNum));
        }

        public synchronized String getLog() {
            StringBuilder b = new StringBuilder();
            b.append("in transit: in=" + bytesRecv + " out=" + bytesSent + "\n");
            b.append("log:\n");
            for (MessageLogEntry e : log) {
                b.append(e + "\n");
            }
            return b.toString();
        }

        class MessageLogEntry {
            public MessageLogEntry(String action, String msg, int num) {
                this.time = System.currentTimeMillis() - connectionTime;
                this.message = msg;
                this.action = action;
                this.num = num;
            }

            final String action;
            final String message;
            final long time;
            final int num;

            @Override
            public String toString() {
                return formatter.format(time / 1000.0) + "\t" + action + ":"
                        + numFormatter.format(num) + "\t" + message;
            }
        }
    }

    private class FileListRequestHandler {

        private final List<PluginCallback<FileList>> listeners = new ArrayList<PluginCallback<FileList>>();

        private final byte type = OSF2FMessage.FILE_LIST_TYPE_COMPLETE;

        public FileListRequestHandler() {
        }

        public void close() {
            synchronized (listeners) {
                for (PluginCallback<FileList> callback : listeners) {
                    callback.errorOccured("Connection closed");
                }
            }
        }

        public void handleFileListResponse(OSF2FTextSearchResp resp) {

            if (!remoteFriend.isRequestFileList()) {
                return;
            }
            // byte type = resp.getFileListType();
            byte[] fileList = resp.getFileList();

            notifyListenersProgress(100);

            try {
                List<byte[]> newInfoHashes = filelistManager.receivedFriendFileList(remoteFriend,
                        type, fileList, FriendConnection.this.hasExtendedFileListsSupport());
                // valid list
                notifyListenerComplete(filelistManager.getFriendsList(remoteFriend));

                // now, try so sync up all the thumbnails

                final List<byte[]> neededThumbnails = filelistManager.getMetaInfoManager()
                        .getTorrentThumbnailNeeded(newInfoHashes);

                sendNextImageRequest(neededThumbnails);

            } catch (IOException e) {
                logger.warning(getDescription() + ": got decode error when "
                        + "processing file list: " + this + ": " + e.getMessage());
            }
        }

        public void notifyListenerComplete(FileList fileList) {
            synchronized (listeners) {
                if (fileList != null) {
                    for (PluginCallback<FileList> callback : listeners) {
                        callback.requestCompleted(fileList);
                    }
                } else {
                    for (PluginCallback<FileList> callback : listeners) {
                        callback.errorOccured("file list is null");
                    }
                }
                listeners.clear();
            }
            if (connection.isConnected()) {
                if (fileList.getFileNum() > 0) {
                    updateFriendConnectionLog(true, "file list received");
                }
                if (!filelistReceived) {
                    remoteFriend.handShakeCompleted(FriendConnection.this.hashCode(),
                            hasExtendedFileListsSupport(), hasChatSupport());
                    filelistReceived = true;
                }
                listener.handshakeCompletedFully(FriendConnection.this);
            } else {
                Debug.out("got file list but the network connection is already closed, setting friend as disconnected instead of connected");
                remoteFriend.disconnected(FriendConnection.this.hashCode());
            }
        }

        private void notifyListenersProgress(int progress) {
            synchronized (listeners) {
                for (PluginCallback<FileList> callback : listeners) {
                    callback.progressUpdate(progress);
                }
            }
        }

        public void sendFileListRequest(PluginCallback<FileList> callback) {
            int lastID = 0;
            FileList previousList = filelistManager.getFriendsList(remoteFriend);
            if (previousList != null) {
                lastID = previousList.getListId();
            }
            OSF2FMessage msg = new OSF2FTextSearch(OSF2FMessage.CURRENT_VERSION,
                    OSF2FMessage.FILE_LIST_TYPE_COMPLETE, 0, "" + lastID);
            sendMessage(msg, true);

            if (callback != null) {
                synchronized (listeners) {
                    listeners.add(callback);
                }
            }
        }

        private void sendNextImageRequest(final List<byte[]> neededThumbnails) {
            if (neededThumbnails.size() > 0) {
                final byte[] hash = neededThumbnails.remove(0);
                logger.finest(getDescription() + ": sending image request for: "
                        + Base32.encode(hash));
                sendMetaInfoRequest(OSF2FMessage.METAINFO_TYPE_THUMBNAIL, 0, hash, 0,
                        new PluginCallback<byte[]>() {
                            @Override
                            public void dataRecieved(long bytes) {
                            }

                            @Override
                            public void errorOccured(String string) {
                            }

                            @Override
                            public void progressUpdate(int progress) {
                            }

                            @Override
                            public void requestCompleted(byte[] data) {
                                filelistManager.getMetaInfoManager().gotImageResponse(hash, data);
                                sendNextImageRequest(neededThumbnails);
                            }
                        });
            }
        }
    }

    private class IncomingQueueListener implements MessageQueueListener {
        @Override
        public void dataBytesReceived(int byte_count) {
            if (debugMessageLog != null) {
                debugMessageLog.bytesReceived(byte_count);
            }
            lastByteRecvTime = System.currentTimeMillis();
            dataBytesDownloaded += byte_count;
            remoteFriend.updateDownloaded(byte_count);
            stats.f2fBytesReceived(byte_count);
        }

        @Override
        public boolean messageReceived(Message message) {
            if (debugMessageLog != null) {
                debugMessageLog.messageReceived(message.getDescription());
            }

            lastByteRecvTime = System.currentTimeMillis();
            if (logger.isLoggable(Level.FINEST)) {
                logger.finest(getDescription() + " got message: " + message.getDescription()
                        + "\t::" + FriendConnection.this);
            }

            if (message.getID().equals(OSF2FMessage.ID_OS_HASH_SEARCH)) {
                handleSearch(message);
            } else if (message.getID().equals(OSF2FMessage.ID_OS_TEXT_SEARCH)) {
                handleSearch(message);
            } else if (message.getID().equals(OSF2FMessage.ID_OS_CHANNEL_DATA_MSG)) {
                handleChannelMsg(message);
            } else if (message.getID().equals(OSF2FMessage.ID_OS_SEARCH_CANCEL)) {
                listener.gotSearchCancel(FriendConnection.this, (OSF2FSearchCancel) message);
            } else if (message.getID().equals(OSF2FMessage.ID_OS_HANDSHAKE)) {
                handleHandshake(message);
            } else if (message.getID().equals(OSF2FMessage.ID_OS_CHANNEL_SETUP)) {
                handleChannelSetup(message);
            } else if (message.getID().equals(OSF2FMessage.ID_OS_CHANNEL_RST)) {
                handleChannelReset(message);
            } else if (message.getID().equals(OSF2FMessage.ID_OS_TEXT_SEARCH_RESP)) {
                handleTextSearchReponse(message);
            } else if (message.getID().equals(OSF2FMessage.ID_OS_METAINFO_REQ)) {
                handleMetainfoRequest(message);
            } else if (message.getID().equals(OSF2FMessage.ID_OS_METAINFO_RESP)) {
                handleMetainfoResponse(message);
            } else if (message.getID().equals(BTKeepAlive.ID_BT_KEEP_ALIVE)) {
                // ignore
            } else if (message.getID().equals(OSF2FMessage.ID_OS_CHAT)) {
                handleChat(message);
            } else if (message.getID().equals(OSF2FMessage.ID_OS_DHT_LOCATION)) {
                handleDhtLocationMessage((OSF2FDhtLocation) message);
            } else if (message.getID().equals(OSF2FMessage.ID_OS_DATAGRAM_INIT)) {
                if (udpConnection != null)
                    udpConnection.initMessageReceived((OSF2FDatagramInit) message);
            } else if (message.getID().equals(OSF2FMessage.ID_OS_DATAGRAM_OK)) {
                if (udpConnection != null)
                    udpConnection.okMessageReceived();
            } else {
                Debug.out(getDescription() + "unknown message: " + message.getDescription());
            }

            return (true);
        }

        @Override
        public void protocolBytesReceived(int byte_count) {
            if (debugMessageLog != null) {
                debugMessageLog.bytesReceived(byte_count);
            }
            lastByteRecvTime = System.currentTimeMillis();
            protocolBytesDownloaded += byte_count;
            remoteFriend.updateDownloaded(byte_count);
            stats.f2fBytesReceived(byte_count);
        }

    }

    private class MetaInfoRequestHandler {

        public final static int MAX_METAINFO_REQUEST_AGE = 10 * 60 * 1000;

        // private final ConcurrentHashMap<Integer, Long> lastMsgTimes = new
        // ConcurrentHashMap<Integer, Long>();
        // private final ConcurrentHashMap<Integer, Long> sentRequests = new
        // ConcurrentHashMap<Integer, Long>();
        // private final HashMap<Integer, List<PluginCallback<byte[]>>>
        // callbacks = new HashMap<Integer, List<PluginCallback<byte[]>>>();

        private final ConcurrentHashMap<Long, MetaInfoRequest> imageRequests = new ConcurrentHashMap<Long, MetaInfoRequest>();

        private final ConcurrentHashMap<Long, MetaInfoRequest> torrentRequests = new ConcurrentHashMap<Long, MetaInfoRequest>();

        private final DelayedExecutor delayedExecutor;

        public MetaInfoRequestHandler() {
            delayedExecutor = DelayedExecutorService.getInstance().getVariableDelayExecutor();
        }

        public void clearOldRequests() {
            for (Iterator<MetaInfoRequest> iterator = imageRequests.values().iterator(); iterator
                    .hasNext();) {
                MetaInfoRequest r = iterator.next();
                if (r.getAge() > MAX_METAINFO_REQUEST_AGE) {
                    iterator.remove();
                }
            }
            for (Iterator<MetaInfoRequest> iterator = torrentRequests.values().iterator(); iterator
                    .hasNext();) {
                MetaInfoRequest r = iterator.next();
                if (r.getAge() > MAX_METAINFO_REQUEST_AGE) {
                    iterator.remove();
                }
            }

        }

        public boolean canRespond(OSF2FMetaInfoReq req) {
            boolean canRespond = false;
            byte[] infoHash = req.getInfoHash();
            byte[] data = filelistManager.getMetaInfoManager().getMetaInfo(remoteFriend,
                    req.getMetaInfoType(), infoHash);
            if (data != null) {
                canRespond = true;
            }
            logger.finest(getDescription() + "can respond: " + canRespond);
            return canRespond;
        }

        private ConcurrentHashMap<Long, MetaInfoRequest> getRequestMap(byte type) {
            ConcurrentHashMap<Long, MetaInfoRequest> requests;
            if (type == OSF2FMessage.METAINFO_TYPE_BITTORRENT) {
                requests = torrentRequests;
            } else if (type == OSF2FMessage.METAINFO_TYPE_THUMBNAIL) {
                requests = imageRequests;
            } else {
                requests = null;
            }
            return requests;
        }

        public void handleMetaInfoRequest(final OSF2FMetaInfoReq req) {

            final byte[] infoHash = req.getInfoHash();
            final byte type = req.getMetaInfoType();
            final byte[] data = filelistManager.getMetaInfoManager().getMetaInfo(remoteFriend,
                    type, infoHash);

            final long infoHashhash = filelistManager.getInfoHashhash(infoHash);
            final int startByte = req.getStartByte();

            final int requestSize = Math.min(OSF2FMessage.METAINFO_CHUNK_SIZE, data.length
                    - startByte);

            // sanity checks
            if (requestSize < 0 || startByte + requestSize > data.length) {
                Debug.out(getDescription() + "got strange metainfo request, length=" + data.length
                        + " startpos=" + startByte + " requestSize=" + requestSize + "\t"
                        + FriendConnection.this);
                return;

            } else {
                int delay = OSF2FMain.getSingelton().getOverlayManager()
                        .getSearchDelayForInfohash(remoteFriend, infoHash);
                delayedExecutor.queue(delay, new TimerTask() {
                    @Override
                    public void run() {
                        byte[] chunk = new byte[requestSize];
                        System.arraycopy(data, startByte, chunk, 0, chunk.length);
                        OSF2FMetaInfoResp msg = new OSF2FMetaInfoResp(OSF2FMessage.CURRENT_VERSION,
                                req.getChannelId(), type, infoHashhash, startByte, data.length,
                                chunk);
                        sendMessage(msg);
                    }
                });
            }
        }

        /**
         * return true if we sent this message
         * 
         * @param msg
         * @return
         */
        public boolean handleMetaInfoResponse(OSF2FMetaInfoResp msg) {
            long infoHashHash = msg.getInfoHashHash();

            logger.finest(getDescription() + "got response for :" + infoHashHash);
            // check if it is from us
            ConcurrentHashMap<Long, MetaInfoRequest> requests = getRequestMap(msg.getMetaInfoType());
            MetaInfoRequest request = requests.get(infoHashHash);
            if (request != null) {

                // great, we want this stuff... add
                request.gotResponse(msg);
                // but it might not have been from us actually, check
                // channel id
                if (request.getChannelId() == msg.getChannelId()) {
                    return true;
                }
            }
            return false;
        }

        public void sendMetaInfoRequest(byte type, int channelId, byte[] infohash, int lengthHint,
                PluginCallback<byte[]> callback) {
            long infohashhash = filelistManager.getInfoHashhash(infohash);
            logger.finest(getDescription() + "sending request for " + infohashhash);

            ConcurrentHashMap<Long, MetaInfoRequest> requests = getRequestMap(type);
            // check if we already have a request for this
            if (!requests.containsKey(infohashhash)) {
                requests.put(infohashhash, new MetaInfoRequest(type, channelId, infohash,
                        lengthHint));
                logger.finest(getDescription() + "adding to requests: " + infohashhash);
            }
            MetaInfoRequest request = requests.get(infohashhash);

            request.addListener(callback);
            request.sendInitialMetaInfoRequest(type);
        }

        private class MetaInfoRequest {
            private final static int REQUEST_TIMEOUT = 60 * 1000;
            private final int channelId;

            private final byte[] infohash;
            private final long infoHashHash;
            private long lastMessageRecieved;
            private final int lengthHint;
            private byte[] metaInfo;
            private int metaInfoLength;
            private boolean[] receivedBytes;
            private boolean sentAllRequest = false;
            private final long createdTime;
            private final byte type;
            // private final long startTime;
            private final List<PluginCallback<byte[]>> subscribers = new LinkedList<PluginCallback<byte[]>>();

            public MetaInfoRequest(byte type, int channelId, byte[] infohash, int lengthHint) {
                this.type = type;
                this.createdTime = System.currentTimeMillis();
                this.infohash = infohash;
                this.infoHashHash = filelistManager.getInfoHashhash(infohash);
                this.channelId = channelId;
                this.lengthHint = lengthHint;
            }

            public void addListener(PluginCallback<byte[]> listener) {
                synchronized (subscribers) {
                    if (isCompleted()) {
                        listener.requestCompleted(metaInfo);
                    } else {
                        subscribers.add(listener);
                    }
                }
            }

            public long getAge() {
                return System.currentTimeMillis() - createdTime;
            }

            public int getChannelId() {
                return channelId;
            }

            public int getPercentComplete() {
                if (receivedBytes == null) {
                    return 0;
                }
                if (receivedBytes.length == 0) {
                    return 100;
                }

                int bytesDownloaded = 0;
                for (int i = 0; i < receivedBytes.length; i++) {
                    if (receivedBytes[i]) {
                        bytesDownloaded++;
                    }
                }

                return (100 * bytesDownloaded) / metaInfoLength;
            }

            public long getTimeSinceLastMsg() {
                return System.currentTimeMillis() - lastMessageRecieved;
            }

            public void gotResponse(OSF2FMetaInfoResp resp) {
                if (resp.getInfoHashHash() != this.infoHashHash) {
                    throw new RuntimeException("Got the wrong infohashhash in a metainforequest");
                }
                this.lastMessageRecieved = System.currentTimeMillis();
                // check if we already know anything about this
                if (metaInfo == null) {
                    // no, lets fill in the blanks
                    this.metaInfoLength = resp.getTotalMetaInfoLength();
                    this.receivedBytes = new boolean[metaInfoLength];
                    this.metaInfo = new byte[metaInfoLength];
                }
                int startPos = resp.getStartByte();
                byte[] payload = resp.getMetaInfo();
                // copy in the payload
                for (int i = 0; i < payload.length; i++) {
                    receivedBytes[startPos + i] = true;
                    metaInfo[startPos + i] = payload[i];
                }

                logger.finest("got metainfo response: %completed=" + getPercentComplete());

                // check if we need to send the big request flood
                if (sentAllRequest == false || getTimeSinceLastMsg() > REQUEST_TIMEOUT) {
                    sendMetaInfoRequests(resp.getMetaInfoType(), metaInfoLength);
                }

                synchronized (subscribers) {
                    for (PluginCallback<byte[]> listener : subscribers) {
                        listener.progressUpdate(getPercentComplete());
                        listener.dataRecieved(payload.length);
                    }

                    if (isCompleted()) {
                        for (PluginCallback<byte[]> listener : subscribers) {
                            listener.requestCompleted(metaInfo);
                        }
                        subscribers.clear();

                        // and remove from the request map
                        getRequestMap(type).remove(infoHashHash);

                    }

                }
            }

            public boolean isCompleted() {
                return getPercentComplete() == 100;
            }

            public void sendInitialMetaInfoRequest(byte type) {
                if (lengthHint > 0) {
                    receivedBytes = new boolean[lengthHint];
                    sendMetaInfoRequests(type, lengthHint);
                } else {
                    int startByte = 0;
                    OSF2FMetaInfoReq req = new OSF2FMetaInfoReq(OSF2FMessage.CURRENT_VERSION,
                            channelId, type, startByte, infohash);
                    sendMessage(req);
                }
            }

            private void sendMetaInfoRequests(byte type, int length) {
                sentAllRequest = true;
                // send requests for everything we don't have yet
                for (int i = 0; i < receivedBytes.length; i += OSF2FMessage.METAINFO_CHUNK_SIZE) {
                    if (!receivedBytes[i]) {
                        int startByte = i;
                        OSF2FMetaInfoReq req = new OSF2FMetaInfoReq(OSF2FMessage.CURRENT_VERSION,
                                channelId, type, startByte, infohash);
                        sendMessage(req);
                    }
                }

            }
        }
    }

    public class OverlayForward {
        private long bytesForwarded = 0;
        Average average = Average.getInstance(1000, 10);
        private final int channelId;
        private final FriendConnection conn;
        private long lastMsgTime;
        private final boolean searcherSide;
        private final OSF2FSearch sourceMessage;
        private final OSF2FSearchResp setupMessage;
        private final long startTime;
        private boolean service;

        public OverlayForward(int channelId, FriendConnection conn, OSF2FSearch sourceMessage,
                OSF2FSearchResp setup, boolean searcherSide) {
            lastMsgTime = System.currentTimeMillis();
            startTime = System.currentTimeMillis();
            this.conn = conn;
            this.channelId = channelId;
            this.sourceMessage = sourceMessage;
            this.setupMessage = setup;
            this.searcherSide = searcherSide;
        }

        public void gotChannelReset() {
            /*
             * the the remote friend conn to stop sending us channel messages on
             * this id
             */
            closeChannel(channelId);
        }

        public void close() {
            deregisterOverlayForward(channelId, true);
        }

        public void forwardMessage(OSF2FChannelMsg message) {
            logger.finest("Packet to be forwarded: " + message.getDescription() + " forwarded="
                    + bytesForwarded);
            message.setByteInChannel(bytesForwarded);
            if (message instanceof OSF2FChannelDataMsg) {
                if (bytesForwarded == 0 || service) {
                    // Check if first packet, detect service or not.
                    try {
                        message = OSF2FServiceDataMsg
                                .fromChannelMessage((OSF2FChannelDataMsg) message);
                        service = true;
                    } catch (MessageException e) {
                        // not service message
                    }
                }
            }
            if (setupPacketListener != null && bytesForwarded == 0) {
                setupPacketListener.packetAddedToForwardQueue(FriendConnection.this, conn,
                        sourceMessage, setupMessage, searcherSide, message);
            }
            lastMsgTime = System.currentTimeMillis();
            int numBytes = message.getMessageSize();
            bytesForwarded += numBytes;
            average.addValue(numBytes);
            /*
             * count it as sent after it actually gets sent
             */
            // stats.protocolBytesSent(numBytes, conn.isLanLocal());
            stats.protocolBytesReceived(numBytes, FriendConnection.this.isLanLocal());
            conn.sendChannelMsg(message, false);
        }

        public long getAge() {
            return System.currentTimeMillis() - startTime;
        }

        public long getBytesForwarded() {
            return bytesForwarded;
        }

        public int getForwardingRate() {
            return (int) average.getAverage();
        }

        public int getChannelId() {
            return channelId;
        }

        public long getLastMsgTime() {
            return System.currentTimeMillis() - lastMsgTime;
        }

        public Friend getRemoteFriend() {
            return conn.getRemoteFriend();
        }

        public String getRemoteIpPort() {
            return conn.getRemoteIp().getHostAddress() + ":" + conn.getRemotePort();
        }

        public OSF2FSearch getSourceMessage() {
            return sourceMessage;
        }

        public OSF2FSearchResp getSetupMessage() {
            return setupMessage;
        }

        public boolean isSearcherSide() {
            return searcherSide;
        }

        public boolean isTimedOut() {
            long timeSinceLastMsg = System.currentTimeMillis() - lastMsgTime;
            if (timeSinceLastMsg > OVERLAY_FORWARD_TIMEOUT) {
                return true;
            }
            return false;
        }

        public void sendReset() {
            conn.sendChannelRst(new OSF2FChannelReset(OSF2FMessage.CURRENT_VERSION, channelId));
        }

    }

    /*
     * used for debugging only
     */
    class OutgoingQueueListener implements OutgoingMessageQueue.MessageQueueListener {

        @Override
        public void dataBytesSent(int byte_count) {
            debugMessageLog.bytesSent(byte_count);
        }

        @Override
        public void flush() {
        }

        @Override
        public boolean messageAdded(Message message) {
            debugMessageLog.messageQueuedListener(message.getDescription());
            return true;
        }

        @Override
        public void messageQueued(Message message) {
        }

        @Override
        public void messageRemoved(Message message) {

        }

        @Override
        public void messageSent(Message message) {
            debugMessageLog.messageSent(message.getDescription());
        }

        @Override
        public void protocolBytesSent(int byte_count) {
            debugMessageLog.bytesSent(byte_count);
        }

    }

    public static class OverlayRegistrationError extends Exception {

        private static final long serialVersionUID = 1L;
        String setupMessageSource;
        final int channelId;
        String direction;

        public OverlayRegistrationError(String setupMessageSource, int channelID, String message) {
            super(message);
            this.setupMessageSource = setupMessageSource;
            this.channelId = channelID;
        }

        @Override
        public String toString() {
            return "source=" + setupMessageSource + " channel=" + channelId;
        }

    }

    public void closeChannel(int channelId) {
        // we must have gotten a channel reset from the remote friend,stop
        // forwarding on this channel and clear any messages that might be
        // queued up
        final OverlayForward overlayForward = overlayForwards.get(channelId);
        if (overlayForward != null) {
            overlayForward.close();

            if (overlayPathLogger.isEnabled()) {
                overlayPathLogger.log(System.currentTimeMillis() + ", close_forward, "
                        + overlayForward.getChannelId() + ", " + overlayForward.getBytesForwarded()
                        + ", " + overlayForward.getAge() + ", "
                        + overlayForward.getRemoteFriend().getNick() + ", "
                        + overlayForward.getRemoteIpPort());
            }
        }

    }

    public boolean isClosing() {
        return mClosing;
    }

    public PacketListener getSetupPacketListener() {
        return setupPacketListener;
    }

    private final static Set<String> UDP_ENABLED_MESSAGES = new HashSet<String>();
    static {
        UDP_ENABLED_MESSAGES.add(OSF2FMessage.ID_OS_CHANNEL_DATA_MSG);
        UDP_ENABLED_MESSAGES.add(OSF2FMessage.ID_OS_DATAGRAM_OK);
    }

    @Override
    public void datagramDecoded(Message message, int size) {
        if (!UDP_ENABLED_MESSAGES.contains(message.getID())) {
            logger.warning("Got invalid message type from udp channel on friendconnection: "
                    + toString());
            return;
        }
        stats.protocolBytesReceived(OSF2FMessage.MESSAGE_HEADER_LEN, isLanLocal());
        if (message.getType() == Message.TYPE_DATA_PAYLOAD) {
            incomingListener.dataBytesReceived(size);
            stats.dataBytesReceived(size, isLanLocal());
        } else {
            incomingListener.protocolBytesReceived(size);
            stats.protocolBytesReceived(size, isLanLocal());
        }
        incomingListener.messageReceived(message);
    }

    private void sendUdpPacket(OSF2FServiceDataMsg message) {
        if (!UDP_ENABLED_MESSAGES.contains(message.getID())) {
            logger.warning("Got invalid message type from udp channel on friendconnection: "
                    + toString());
            return;
        }
        // Notify the setup packet listener
        if (!friendConnectionQueue.packetListenerNotify(message)) {
            logger.warning("Packetlistener told us to drop the packet!!!!!!");
            message.destroy();
            return;
        }
        stats.protocolBytesSent(OSF2FMessage.MESSAGE_HEADER_LEN, isLanLocal());
        int size = message.getMessageSize();
        if (message.getType() == Message.TYPE_DATA_PAYLOAD) {
            stats.dataBytesSent(size, isLanLocal());
        } else {
            stats.protocolBytesSent(size, isLanLocal());
        }
        udpConnection.sendMessage(message);
    }

    @Override
    public void sendDatagramOk(OSF2FDatagramOk osf2fDatagramOk) {
        sendMessage(osf2fDatagramOk, true);
    }
}
