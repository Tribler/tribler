package edu.washington.cs.oneswarm.f2f.network;

import java.io.IOException;
import java.io.UnsupportedEncodingException;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.LinkedList;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.Set;
import java.util.StringTokenizer;
import java.util.TimerTask;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.logging.Level;
import java.util.logging.Logger;

import org.bouncycastle.util.encoders.Base64;
import org.gudy.azureus2.core3.config.COConfigurationManager;
import org.gudy.azureus2.core3.config.ParameterListener;
import org.gudy.azureus2.core3.config.StringList;
import org.gudy.azureus2.core3.disk.DiskManagerFileInfo;
import org.gudy.azureus2.core3.download.DownloadManager;
import org.gudy.azureus2.core3.download.DownloadManagerStats;
import org.gudy.azureus2.core3.global.GlobalManager;
import org.gudy.azureus2.core3.global.GlobalManagerStats;
import org.gudy.azureus2.core3.peer.PEPeerManager;
import org.gudy.azureus2.core3.util.Debug;
import org.gudy.azureus2.core3.util.HashWrapper;
import org.oneswarm.util.ReflectionUtils;

import com.aelitis.azureus.core.impl.AzureusCoreImpl;

import edu.uw.cse.netlab.utils.BloomFilter;
import edu.washington.cs.oneswarm.f2f.BigFatLock;
import edu.washington.cs.oneswarm.f2f.FileCollection;
import edu.washington.cs.oneswarm.f2f.FileList;
import edu.washington.cs.oneswarm.f2f.FileListManager;
import edu.washington.cs.oneswarm.f2f.Friend;
import edu.washington.cs.oneswarm.f2f.OSF2FMain;
import edu.washington.cs.oneswarm.f2f.TextSearchResult;
import edu.washington.cs.oneswarm.f2f.TextSearchResult.TextSearchResponse;
import edu.washington.cs.oneswarm.f2f.TextSearchResult.TextSearchResponseItem;
import edu.washington.cs.oneswarm.f2f.messaging.OSF2FChannelReset;
import edu.washington.cs.oneswarm.f2f.messaging.OSF2FHashSearch;
import edu.washington.cs.oneswarm.f2f.messaging.OSF2FHashSearchResp;
import edu.washington.cs.oneswarm.f2f.messaging.OSF2FMessage;
import edu.washington.cs.oneswarm.f2f.messaging.OSF2FSearch;
import edu.washington.cs.oneswarm.f2f.messaging.OSF2FSearchCancel;
import edu.washington.cs.oneswarm.f2f.messaging.OSF2FSearchResp;
import edu.washington.cs.oneswarm.f2f.messaging.OSF2FTextSearch;
import edu.washington.cs.oneswarm.f2f.messaging.OSF2FTextSearchResp;
import edu.washington.cs.oneswarm.f2f.network.DelayedExecutorService.DelayedExecutionEntry;
import edu.washington.cs.oneswarm.f2f.network.DelayedExecutorService.DelayedExecutor;
import edu.washington.cs.oneswarm.f2f.network.FriendConnection.OverlayRegistrationError;
import edu.washington.cs.oneswarm.f2f.servicesharing.ServiceConnectionManager;
import edu.washington.cs.oneswarm.f2f.servicesharing.ServiceSharingManager;
import edu.washington.cs.oneswarm.f2f.servicesharing.SharedService;
import edu.washington.cs.oneswarm.f2f.share.ShareManagerTools;
import edu.washington.cs.oneswarm.ui.gwt.BackendErrorLog;

public class SearchManager {

    public static final String SEARCH_QUEUE_THREAD_NAME = "DelayedSearchQueue";

    private final static BigFatLock lock = OverlayManager.lock;
    public static Logger logger = Logger.getLogger(SearchManager.class.getName());
    // search sources are remembered for 1 minute, any replies after this will
    // be dropped
    public static final long MAX_SEARCH_AGE = 60 * 1000;
    public static final int MAX_SEARCH_QUEUE_LENGTH = 100;
    // private static final int MAX_SEARCH_RESP_BEFORE_CANCEL =
    // COConfigurationManager.getIntParameter("f2f_search_max_paths");

    protected int mMaxSearchResponsesBeforeCancel = COConfigurationManager
            .getIntParameter("f2f_search_max_paths");

    // don't respond if average torrent upload rate is less than 10K/s
    private static final double NO_RESPONSE_TORRENT_AVERAGE_RATE = 10000;

    private static final double NO_RESPONSE_TOTAL_FRAC_OF_MAX_UPLOAD = 0.9;

    private static final double NO_RESPONSE_TRANSPORT_FRAC_OF_MAX_UPLOAD = 0.75;
    /*
     * this is to avoid searches living forever, search uid are remembered for
     * 45min-1h, there are 4 bloom filter buckets that are rotating, each one
     * containing 15minutes worth of searches
     */
    private static final int RECENT_SEARCH_BUCKETS = 4;

    private static final long RECENT_SEARCH_MEMORY = 20 * 60 * 1000;
    // static final int SEARCH_DELAY =
    // COConfigurationManager.getIntParameter("f2f_search_forward_delay");
    protected int mSearchDelay = COConfigurationManager.getIntParameter("f2f_search_forward_delay");

    /**
     * This Map is protected by the BigFatLock: lock. We use this to drop
     * searches from friends that are crowding the outgoing search queue early,
     * thus allowing friends that send searches more rarely to get through.
     * 
     * This map is emptied once every 60 seconds to deal with accounting errors
     * that may accumulate.
     */
    class MutableInteger {
        public int v = 0;
    }

    long lastSearchAccountingFlush = System.currentTimeMillis();
    private final Map<Friend, MutableInteger> searchesPerFriend = new HashMap<Friend, MutableInteger>();

    private int bloomSearchesBlockedCurr = 0;

    private int bloomSearchesBlockedPrev = 0;
    private int bloomSearchesSentCurr = 0;
    private int bloomSearchesSentPrev = 0;

    private final HashMap<Integer, Long> canceledSearches;
    private final DebugChannelSetupErrorStats debugChannelIdErrorSetupErrorStats = new DebugChannelSetupErrorStats();

    private final DelayedSearchQueue delayedSearchQueue;

    // private final DeterministicDelayResponseQueue delayedResponseQueue;

    private final FileListManager filelistManager;

    private final HashMap<Integer, ForwardedSearch> forwardedSearches;
    private int forwardedSearchNum = 0;
    private List<Integer> hashSearchStats = new LinkedList<Integer>();

    private boolean includeLanUploads;
    private final double NO_FORWARD_FRAC_OF_MAX_UPLOAD = 0.9;
    private final OverlayManager overlayManager;

    private final Random random = new Random();
    private final RandomnessManager randomnessManager;

    private int rateLimitInKBps;

    private final RotatingBloomFilter recentSearches;
    private final HashMap<Integer, SentSearch> sentSearches;
    private final HashMap<Integer, ServiceSearch> serviceSearches;
    private final GlobalManagerStats stats;
    private final TextSearchManager textSearchManager;

    private List<Integer> textSearchStats = new LinkedList<Integer>();

    private final DelayedExecutor delayedExecutor;

    private String[] filteredKeywords = new String[0];

    public SearchManager(OverlayManager overlayManager, FileListManager filelistManager,
            RandomnessManager randomnessManager, GlobalManagerStats stats) {
        this.stats = stats;
        this.delayedExecutor = DelayedExecutorService.getInstance().getVariableDelayExecutor();
        // this.delayedResponseQueue = new DeterministicDelayResponseQueue();
        this.overlayManager = overlayManager;
        this.sentSearches = new HashMap<Integer, SentSearch>();
        this.forwardedSearches = new HashMap<Integer, ForwardedSearch>();
        this.canceledSearches = new HashMap<Integer, Long>();
        this.serviceSearches = new HashMap<Integer, ServiceSearch>();
        this.filelistManager = filelistManager;
        this.randomnessManager = randomnessManager;
        this.textSearchManager = new TextSearchManager();
        this.recentSearches = new RotatingBloomFilter(RECENT_SEARCH_MEMORY, RECENT_SEARCH_BUCKETS);
        this.delayedSearchQueue = new DelayedSearchQueue(mSearchDelay);
        COConfigurationManager.addAndFireParameterListeners(new String[] { "LAN Speed Enabled",
                "Max Upload Speed KBs", "oneswarm.search.filter.keywords", "f2f_search_max_paths",
                "f2f_search_forward_delay" }, new ParameterListener() {
            @Override
            public void parameterChanged(String parameterName) {
                includeLanUploads = !COConfigurationManager
                        .getBooleanParameter("LAN Speed Enabled");
                rateLimitInKBps = COConfigurationManager.getIntParameter("Max Upload Speed KBs");

                StringList keywords = COConfigurationManager
                        .getStringListParameter("oneswarm.search.filter.keywords");
                if (keywords != null) {
                    String[] neu = new String[keywords.size()];
                    for (int i = 0; i < keywords.size(); i++) {
                        String firstTok = (new StringTokenizer(keywords.get(i))).nextToken();
                        neu[i] = firstTok;
                    }
                    filteredKeywords = neu;
                    logger.fine("Updated filtered keywords " + keywords.size());
                }

                mMaxSearchResponsesBeforeCancel = COConfigurationManager
                        .getIntParameter("f2f_search_max_paths");

                mSearchDelay = COConfigurationManager.getIntParameter("f2f_search_forward_delay");
                delayedSearchQueue.setDelay(mSearchDelay);
            }
        });
    }

    private boolean canForwardSearch() {
        double util = fracUpload();
        if (util == -1 || util < NO_FORWARD_FRAC_OF_MAX_UPLOAD) {
            return true;
        } else {
            logger.finest("not forwarding search (overloaded, util=" + util + ")");
            return false;
        }
    }

    private boolean canRespondToSearch() {
        double totalUtil = fracUpload();
        if (totalUtil == -1) {
            return true;
        }
        // ok, check if we are using more than 90% of total
        if (totalUtil < NO_RESPONSE_TOTAL_FRAC_OF_MAX_UPLOAD) {
            return true;
        }
        double transUtil = fracTransportUpload();
        // check if we are using more than 75% for transports
        if (transUtil < NO_RESPONSE_TRANSPORT_FRAC_OF_MAX_UPLOAD) {
            return true;
        }

        double torrentAvgSpeed = getAverageUploadPerRunningTorrent();
        if (torrentAvgSpeed == -1) {
            return true;
        }
        if (torrentAvgSpeed > NO_RESPONSE_TORRENT_AVERAGE_RATE) {
            return true;
        }
        if (logger.isLoggable(Level.FINER)) {
            logger.finer("not responding to search (overloaded, util=" + transUtil + ")");
        }
        return false;
    }

    public void clearTimedOutSearches() {
        lock.lock();
        try {
            /*
             * check if we need to rotate the bloom filter of recent searches
             */
            boolean rotated = recentSearches.rotateIfNeeded();
            if (rotated) {
                bloomSearchesBlockedPrev = bloomSearchesBlockedCurr;
                bloomSearchesBlockedCurr = 0;
                bloomSearchesSentPrev = bloomSearchesSentCurr;
                bloomSearchesSentCurr = 0;
            }

            for (Iterator<ForwardedSearch> iterator = forwardedSearches.values().iterator(); iterator
                    .hasNext();) {
                ForwardedSearch fs = iterator.next();
                if (fs.isTimedOut()) {
                    iterator.remove();
                }
            }

            for (Iterator<SentSearch> iterator = sentSearches.values().iterator(); iterator
                    .hasNext();) {
                SentSearch sentSearch = iterator.next();
                if (sentSearch.isTimedOut()) {
                    iterator.remove();
                    if (sentSearch.getSearch() instanceof OSF2FHashSearch) {
                        hashSearchStats.add(sentSearch.getResponseNum());
                    } else if (sentSearch.getSearch() instanceof OSF2FTextSearch) {
                        textSearchStats.add(sentSearch.getResponseNum());
                    }
                }
            }

            for (Iterator<ServiceSearch> iterator = serviceSearches.values().iterator(); iterator
                    .hasNext();) {
                ServiceSearch serviceSearch = iterator.next();
                if (serviceSearch.isTimedOut()) {
                    iterator.remove();
                }
            }

            /*
             * Delete any expired canceled searches
             */
            LinkedList<Integer> toDelete = new LinkedList<Integer>();
            for (Integer key : canceledSearches.keySet()) {
                long age = System.currentTimeMillis() - canceledSearches.get(key);
                if (age > MAX_SEARCH_AGE) {
                    toDelete.add(key);
                }
            }

            for (Integer key : toDelete) {
                canceledSearches.remove(key);
            }

            textSearchManager.clearOldResponses();
        } finally {
            lock.unlock();
        }
    }

    public List<String> debugCanceledSearches() {
        List<String> l = new LinkedList<String>();
        lock.lock();
        try {
            for (Integer s : canceledSearches.keySet()) {
                l.add("search=" + Integer.toHexString(s) + " age="
                        + ((System.currentTimeMillis() - canceledSearches.get(s)) / 1000) + "s");
            }
        } finally {
            lock.unlock();
        }
        return l;
    }

    public List<String> debugForwardedSearches() {
        List<String> l = new LinkedList<String>();
        lock.lock();
        try {
            for (ForwardedSearch f : forwardedSearches.values()) {
                l.add("search=" + Integer.toHexString(f.getSearchId()) + " responses="
                        + f.getResponseNum() + " age=" + (f.getAge() / 1000) + "s");
            }
        } finally {
            lock.unlock();
        }
        return l;
    }

    public List<String> debugSentSearches() {
        List<String> l = new LinkedList<String>();
        lock.lock();
        try {
            for (SentSearch s : sentSearches.values()) {
                l.add("search=" + Integer.toHexString(s.getSearch().getSearchID()) + " responses="
                        + s.getResponseNum() + " age=" + (s.getAge() / 1000) + "s");
            }
        } finally {
            lock.unlock();
        }
        return l;
    }

    private void forwardSearch(FriendConnection source, OSF2FSearch search) {
        lock.lock();
        try {

            // check if search is canceled or forwarded first
            int searchID = search.getSearchID();
            if (forwardedSearches.containsKey(searchID)) {
                logger.finest("not forwarding search, already forwarded. id: " + searchID);
                return;
            }

            if (canceledSearches.containsKey(searchID)) {
                logger.finest("not forwarding search, cancel received. id: " + searchID);
                return;
            }

            int valueID = search.getValueID();
            if (recentSearches.contains(searchID, valueID)) {
                bloomSearchesBlockedCurr++;
                logger.finest("not forwarding search, in recent filter. id: " + searchID);
                return;
            }
            bloomSearchesSentCurr++;
            forwardedSearchNum++;
            if (logger.isLoggable(Level.FINEST)) {
                logger.finest("forwarding search " + search.getDescription() + " id: " + searchID);
            }
            forwardedSearches.put(searchID, new ForwardedSearch(source, search));
            recentSearches.insert(searchID, valueID);
        } finally {
            lock.unlock();
        }

        overlayManager.forwardSearchOrCancel(source, search.clone());
    }

    private double fracTransportUpload() {

        if (rateLimitInKBps < 1) {
            return -1;
        }
        long uploadRate = overlayManager.getTransportSendRate(includeLanUploads);

        double util = uploadRate / (rateLimitInKBps * 1024.0);
        return util;
    }

    private double fracUpload() {

        if (rateLimitInKBps < 1) {
            return -1;
        }
        long uploadRate;
        if (!includeLanUploads) {
            uploadRate = stats.getProtocolSendRateNoLAN() + stats.getDataSendRateNoLAN();
        } else {
            uploadRate = stats.getProtocolSendRate() + stats.getDataSendRate();
        }

        double util = uploadRate / (rateLimitInKBps * 1024.0);
        return util;
    }

    public int getAndClearForwardedSearchNum() {
        lock.lock();
        try {
            int ret = forwardedSearchNum;
            forwardedSearchNum = 0;
            return ret;
        } finally {
            lock.unlock();
        }
    }

    public List<Integer> getAndClearHashSearchStats() {
        lock.lock();
        try {
            List<Integer> ret = hashSearchStats;
            hashSearchStats = new LinkedList<Integer>();
            return ret;
        } finally {
            lock.unlock();
        }
    }

    public List<Integer> getAndClearTextSearchStats() {
        lock.lock();
        try {
            List<Integer> ret = textSearchStats;
            textSearchStats = new LinkedList<Integer>();
            return ret;
        } finally {
            lock.unlock();
        }
    }

    @SuppressWarnings("unchecked")
    private double getAverageUploadPerRunningTorrent() {
        LinkedList<DownloadManager> dms = new LinkedList<DownloadManager>();
        final List<DownloadManager> downloadManagers = AzureusCoreImpl.getSingleton()
                .getGlobalManager().getDownloadManagers();
        dms.addAll(downloadManagers);

        long total = 0;
        int num = 0;

        for (DownloadManager dm : dms) {
            final DownloadManagerStats s = dm.getStats();
            if (s == null) {
                continue;
            }
            final PEPeerManager p = dm.getPeerManager();
            if (p == null) {
                continue;
            }

            if (p.getNbPeers() == 0 && p.getNbSeeds() == 0) {
                continue;
            }

            long uploadRate = s.getDataSendRate() + s.getProtocolSendRate();
            total += uploadRate;
            num++;
        }
        if (num == 0) {
            return -1;
        }

        return ((double) total) / num;

    }

    public String getSearchDebug() {
        StringBuilder b = new StringBuilder();
        b.append("total_frac=" + fracUpload() + "\ntransport_frac=" + fracTransportUpload()
                + "\ntorrent_avg=" + getAverageUploadPerRunningTorrent());
        b.append("\ncan forward=" + canForwardSearch());
        b.append("\ncan respond=" + canRespondToSearch());

        b.append("\n\nforwarded searches size=" + forwardedSearches.size() + " canceled size="
                + canceledSearches.size() + " sent size=" + sentSearches.size());
        b.append("\nbloom: stored=" + recentSearches.getPrevFilterNumElements()
                + " est false positives="
                + (100 * recentSearches.getPrevFilterFalsePositiveEst() + "%"));
        b.append("\nbloom blocked|sent curr=" + bloomSearchesBlockedCurr + "|"
                + bloomSearchesSentCurr + " prev=" + bloomSearchesBlockedPrev + "|"
                + bloomSearchesSentPrev);
        b.append("\n\n" + debugChannelIdErrorSetupErrorStats.getDebugStats());

        long sum = 0, now = System.currentTimeMillis(), count = 0;

        // Include per-friend queue stats
        lock.lock();
        try {
            Map<String, MutableInteger> counts = new HashMap<String, MutableInteger>();
            for (DelayedSearchQueueEntry e : delayedSearchQueue.queuedSearches.values()) {

                count++;
                sum += (now - e.insertionTime);

                String nick = e.source.getRemoteFriend().getNick();
                if (counts.containsKey(nick) == false) {
                    counts.put(nick, new MutableInteger());
                }
                counts.get(nick).v++;
            }
            for (String nick : counts.keySet()) {
                b.append("\n\t" + nick + " -> " + counts.get(nick).v);
            }
            b.append("\n\nQueue size: " + delayedSearchQueue.queuedSearches.size());
        } finally {
            lock.unlock();
        }

        b.append("\nAverage queued search delay: " + (double) sum / (double) count);

        return b.toString();
    }

    public List<TextSearchResult> getSearchResult(int searchId) {
        return textSearchManager.getResults(searchId);
    }

    /**
     * Process a given hash search message from a given friend. Returns true iff
     * the message should be forwarded (i.e., it wasn't handled by us locally).
     */
    private boolean handleHashSearch(final FriendConnection source, final OSF2FHashSearch msg) {
        // Check if this is a service
        SharedService service = ServiceSharingManager.getInstance().handleSearch(msg);
        if (service != null) {
            logger.info("found matching service: " + service);
            try {
                // TODO: support artificial delays and merge with normal search
                // handling code
                final int newChannelId = random.nextInt();
                final int pathID = randomnessManager.getDeterministicRandomInt((int) msg
                        .getInfohashhash());
                final OSF2FHashSearchResp response = new OSF2FHashSearchResp(
                        OSF2FMessage.CURRENT_VERSION, msg.getSearchID(), newChannelId, pathID);
                response.updatePathID(random.nextInt());
                if (serviceSearches.containsKey(msg.getSearchID())) {
                    ServiceSearch search = serviceSearches.get(msg.getSearchID());
                    search.addSource(source, response);
                } else {
                    ServiceSearch search = new ServiceSearch(service, msg);
                    search.addSource(source, response);
                    serviceSearches.put(msg.getSearchID(), search);
                }
                // send the channel setup message
                source.sendChannelSetup(response, false);
            } catch (OverlayRegistrationError e) {
                Debug.out("got an error when registering incoming transport to '"
                        + source.getRemoteFriend().getNick() + "': " + e.getMessage());
            }
            return false;
        }
        // second, we might actually have this data
        byte[] infohash = filelistManager.getMetainfoHash(msg.getInfohashhash());
        // If this is an experiment search, we might not have a download
        // manager. If so, don't
        // consider the download manager when responding to the search.
        boolean considerDownloadManager = true;
        boolean foundExperimentalMatch = false;
        if (infohash == null && ReflectionUtils.isExperimental()) {
            infohash = (byte[]) ReflectionUtils.invokeExperimentalMethod(
                    "getInfohashForHashSearch", new Object[] { source, msg }, new Class<?>[] {
                            FriendConnection.class, OSF2FHashSearch.class });

            // If we got a special infohash, don't consider the download
            // manager, and set the
            // response bytes
            if (infohash != null) {
                considerDownloadManager = false;
                foundExperimentalMatch = true;
            }
        }

        // If we didn't find any infohash, we should forward the search.
        if (infohash == null) {
            return true;
        }

        DownloadManager dm = null;

        if (considerDownloadManager) {
            dm = AzureusCoreImpl.getSingleton().getGlobalManager()
                    .getDownloadManager(new HashWrapper(infohash));
        }

        if (dm != null) {
            logger.fine("found dm match: " + new String(Base64.encode(infohash)));
        }

        // check if the torrent allow osf2f search peers
        boolean allowed = false;

        if (dm != null) {
            allowed = OverlayTransport.checkOSF2FAllowed(dm.getDownloadState().getPeerSources(), dm
                    .getDownloadState().getNetworks());
        } else {
            allowed = foundExperimentalMatch;
        }

        if (!allowed) {
            logger.finer("got search match for torrent " + "that does not allow osf2f peers");
            return true;
        }

        if (foundExperimentalMatch == false) {
            boolean completedOrDownloading = FileListManager.completedOrDownloading(dm);
            if (!completedOrDownloading) {
                return true;
            }
        }

        // check if we have the capacity to respond
        if (canRespondToSearch() == false) {
            return false;
        }

        // yeah, we actually have this stuff and we have spare capacity
        // create an overlay transport
        final int newChannelId = random.nextInt();
        final int transportFakePathId = random.nextInt();
        // set the path id for the overlay transport for something
        // random (since otherwise all transports for this infohash will
        // get the same pathid, which will limit it to be only one. The
        // path id set in the channel setup message will be
        // deterministic. It is the responsibility of the source to
        // monitor for duplicate paths

        // set the path id to something that will persist between
        // searches, for example a deterministic random seeded with
        // the infohashhash
        final int pathID = randomnessManager.getDeterministicRandomInt((int) msg.getInfohashhash());

        // get the delay for this overlaytranport, that is the latency
        // component of the delay
        final int overlayDelay = overlayManager.getLatencyDelayForInfohash(
                source.getRemoteFriend(), infohash);

        final byte[] infohashShadow = infohash;
        TimerTask task = new TimerTask() {
            @Override
            public void run() {
                try {
                    /*
                     * check if the search got canceled while we were
                     * sleeping
                     */
                    if (!isSearchCanceled(msg.getSearchID())) {
                        final OSF2FHashSearchResp response = new OSF2FHashSearchResp(
                                OSF2FMessage.CURRENT_VERSION, msg.getSearchID(), newChannelId,
                                pathID);

                        final OverlayTransport transp = new OverlayTransport(source,
                                infohashShadow, transportFakePathId, false, overlayDelay, msg,
                                response);
                        // register it with the friendConnection
                        source.registerOverlayTransport(transp);
                        // send the channel setup message
                        source.sendChannelSetup(response, false);
                    }
                } catch (OverlayRegistrationError e) {
                    Debug.out("got an error when registering incoming transport to '"
                            + source.getRemoteFriend().getNick() + "': " + e.getMessage());
                }
            }

        };
        // get the search delay.
        int searchDelay = overlayManager.getSearchDelayForInfohash(source.getRemoteFriend(),
                infohash);

        delayedExecutor.queue(searchDelay + overlayDelay, task);

        // we are still forwarding if there are files in the torrent
        // that we chose not to download
        if (considerDownloadManager) {
            DiskManagerFileInfo[] diskManagerFileInfo = dm.getDiskManagerFileInfo();
            for (DiskManagerFileInfo d : diskManagerFileInfo) {
                if (d.isSkipped()) {
                    return true;
                }
            }
        }

        /*
         * ok, we shouldn't forward this, already sent a hash response
         * and we have/are downloading all the files
         */
        return false;
    }

    private boolean isSearchCanceled(int searchId) {
        boolean canceled = false;
        lock.lock();
        try {
            if (canceledSearches.containsKey(searchId)) {
                canceled = true;
            }
        } finally {
            lock.unlock();
        }
        return canceled;
    }

    /**
     * Returns the probability of rejecting a search from this friend given the
     * share of the overall queue
     */
    public double getFriendSearchDropProbability(Friend inFriend) {

        lock.lock();
        try {

            // Always accept if we don't have any searches from friend.
            if (searchesPerFriend.get(inFriend) == null) {
                return 0;
            }

            // Reject proportionally to recent rate. Do not admit more than
            // X/sec.
            // Also, proportional to processing queue size.
            double rateBound = delayedSearchQueue.searchCount / 80.0;
            double queueBound = (double) delayedSearchQueue.queuedSearches.size()
                    / (double) MAX_SEARCH_QUEUE_LENGTH;

            return Math.max(rateBound, queueBound);

        } finally {
            lock.unlock();
        }
    }

    private void handleIncomingHashSearchResponse(OSF2FHashSearch hashSearch,
            FriendConnection source, OSF2FHashSearchResp searchResponse) {

        // Check that it is a fresh path
        if (source.hasRegisteredPath(searchResponse.getPathID())) {
            logger.finer("got channel setup response, "
                    + "but path is already used: sending back a reset");
            source.sendChannelRst(new OSF2FChannelReset(OSF2FMessage.CURRENT_VERSION,
                    searchResponse.getChannelID()));
            return;
        }

        // Check if this should be handled by a listener
        List<HashSearchListener> listeners = hashSearch.getListeners();
        if (listeners.size() > 0) {
            for (HashSearchListener listener : listeners) {
                listener.searchResponseReceived(hashSearch, source, searchResponse);
            }
            return;
        }

        // Verify that we searched for this.
        byte[] infoHash = filelistManager.getMetainfoHash(hashSearch.getInfohashhash());
        if (infoHash == null) {
            logger.warning("got channel setup request, " + "but the infohash we searched for "
                    + "is not in filelistmananger");
            return;
        }
        DownloadManager dm = AzureusCoreImpl.getSingleton().getGlobalManager()
                .getDownloadManager(new HashWrapper(infoHash));
        if (dm == null) {
            logger.warning("got channel setup request, " + "but the downloadmanager is null");
            return;
        }

        OverlayTransport overlayTransport = new OverlayTransport(source, infoHash,
                searchResponse.getPathID(), true, overlayManager.getLatencyDelayForInfohash(
                        source.getRemoteFriend(), infoHash), hashSearch, searchResponse);
        // register it with the friendConnection
        try {
            source.registerOverlayTransport(overlayTransport);
            // safe to start it since we know that the other party is interested
            overlayTransport.start();
        } catch (OverlayRegistrationError e) {
            Debug.out("got an error when registering outgoing transport: " + e.getMessage());
            return;
        }

    }

    public void handleIncomingSearch(FriendConnection source, OSF2FSearch msg) {
        lock.lock();
        try {
            logger.finest("got search: " + msg.getDescription());
            // first, check if we either sent or forwarded this search before
            if (forwardedSearches.containsKey(msg.getSearchID())
                    || sentSearches.containsKey(msg.getSearchID())
                    || delayedSearchQueue.isQueued(msg)) {
                return;
            }
        } finally {
            lock.unlock();
        }

        boolean shouldForward = true;
        // second, check if we actually can do something about this
        if (msg instanceof OSF2FHashSearch) {
            shouldForward = handleHashSearch(source, (OSF2FHashSearch) msg);
        } else if (msg instanceof OSF2FTextSearch) {
            shouldForward = handleTextSearch(source, (OSF2FTextSearch) msg);
        } else {
            logger.warning("received unrecgonized search type: " + msg.getID() + " / "
                    + msg.getClass().getCanonicalName());
        }

        /*
         * check if we are at full capacity
         */
        if (canForwardSearch() == false) {
            shouldForward = false;
        }

        if (shouldForward) {
            // ok, seems like we should attempt to forward this, put it in
            // the queue
            delayedSearchQueue.add(source, msg);
        }

    }

    public void handleIncomingSearchCancel(FriendConnection source, OSF2FSearchCancel msg) {

        boolean forward = false;
        lock.lock();
        try {

            /*
             * if this is the first time we see the cancel, check if we
             * forwarded this search, if we did, send a cancel
             */
            if (!canceledSearches.containsKey(msg.getSearchID())) {
                canceledSearches.put(msg.getSearchID(), System.currentTimeMillis());
                /*
                 * we only forward the cancel if we already sent the search
                 */
                if (forwardedSearches.containsKey(msg.getSearchID())) {
                    forward = true;
                } else {
                    logger.fine("got search cancel for unknown search id");
                }
            }
        } finally {
            lock.unlock();
        }
        if (forward) {
            overlayManager.forwardSearchOrCancel(source, msg);
        }
    }

    /**
     * There are 2 possible explanations for getting a search response, either
     * we got a response for a search we sent ourselves, or we got a response
     * for a search we forwarded
     * 
     * @param source
     *            connection from where we got the setup
     * @param msg
     *            the channel setup message
     */
    public void handleIncomingSearchResponse(FriendConnection source, OSF2FSearchResp msg) {
        SentSearch sentSearch;
        lock.lock();
        try {
            sentSearch = sentSearches.get(msg.getSearchID());
        } finally {
            lock.unlock();
        }
        // first, if might be a search we sent
        if (sentSearch != null) {
            logger.finest("got response to search: " + sentSearch.getSearch().getDescription());
            OSF2FSearch search = sentSearch.getSearch();
            // update response stats
            sentSearch.gotResponse();
            /*
             * check if we got enough search responses to cancel this search
             * 
             * we will still use the data, even if the search is canceled. I
             * mean, since it already made it here why not use it...
             */
            if (sentSearch.getResponseNum() > mMaxSearchResponsesBeforeCancel) {
                /*
                 * only send a cancel message once
                 */
                boolean sendCancel = false;
                lock.lock();
                try {
                    if (!canceledSearches.containsKey(msg.getSearchID())) {
                        canceledSearches.put(msg.getSearchID(), System.currentTimeMillis());
                        logger.finer("canceling search " + msg);
                        sendCancel = true;
                    }
                } finally {
                    lock.unlock();
                }
                if (sendCancel) {
                    overlayManager.sendSearchOrCancel(new OSF2FSearchCancel(
                            OSF2FMessage.CURRENT_VERSION, msg.getSearchID()), true, false);
                }
            }
            if (search instanceof OSF2FHashSearch) {
                // ok, it was a hash search that we sent
                handleIncomingHashSearchResponse((OSF2FHashSearch) search, source,
                        (OSF2FHashSearchResp) msg);
            } else if (search instanceof OSF2FTextSearch) {
                // this was from a text search we sent
                FileList fileList;
                try {
                    OSF2FTextSearchResp textSearchResp = (OSF2FTextSearchResp) msg;
                    fileList = FileListManager.decode_basic(textSearchResp.getFileList());

                    textSearchManager.gotSearchResponse(search.getSearchID(),
                            source.getRemoteFriend(), fileList, textSearchResp.getChannelID(),
                            source.hashCode());

                    logger.fine("results so far:");
                    List<TextSearchResult> res = getSearchResult(search.getSearchID());
                    for (TextSearchResult textSearchResult : res) {
                        logger.fine(textSearchResult.toString());
                    }
                } catch (IOException e) {
                    logger.warning("got malformed search response");
                }
            } else {
                logger.warning("unknown search response type");
            }
        }
        // sentsearch == null
        else {
            // ok, this is for a search we forwarded
            ForwardedSearch search;
            lock.lock();
            try {
                search = forwardedSearches.get(msg.getSearchID());
                if (search == null) {
                    // Search responses after 60 seconds are dropped (not that
                    // unusual)
                    logger.fine("got response for slow/unknown search:" + source + ":"
                            + msg.getDescription());
                    return;
                }

                logger.finest("got response to forwarded search: "
                        + search.getSearch().getDescription());

                if (canceledSearches.containsKey(msg.getSearchID())) {
                    logger.finer("not forwarding search, it is already canceled, "
                            + msg.getSearchID());
                    return;
                }
            } finally {
                lock.unlock();
            }

            FriendConnection searcher = search.getSource();
            FriendConnection responder = source;

            if (search.getResponseNum() > mMaxSearchResponsesBeforeCancel) {
                /*
                 * we really shouldn't cancel other peoples searches, but if
                 * they don't do it we have to
                 */
                lock.lock();
                try {
                    canceledSearches.put(msg.getSearchID(), System.currentTimeMillis());
                } finally {
                    lock.unlock();
                }
                logger.finest("Sending cancel for someone elses search!, searcher="
                        + searcher.getRemoteFriend() + " responder=" + responder.getRemoteFriend()
                        + ":\t" + search);
                overlayManager.forwardSearchOrCancel(source, new OSF2FSearchCancel(
                        OSF2FMessage.CURRENT_VERSION, msg.getSearchID()));
            } else {
                search.gotResponse();
                // register the forwarding
                logger.finest("registering overlay forward: "
                        + searcher.getRemoteFriend().getNick() + "<->"
                        + responder.getRemoteFriend().getNick());
                try {
                    responder.registerOverlayForward(msg, searcher, search.getSearch(), false);
                    searcher.registerOverlayForward(msg, responder, search.getSearch(), true);
                } catch (FriendConnection.OverlayRegistrationError e) {
                    String direction = "'" + responder.getRemoteFriend().getNick() + "'->'"
                            + searcher.getRemoteFriend().getNick() + "'";
                    e.direction = direction;
                    e.setupMessageSource = responder.getRemoteFriend().getNick();
                    logger.warning("not forwarding overlay setup request " + direction
                            + e.getMessage());
                    debugChannelIdErrorSetupErrorStats.add(e);
                    return;
                }

                // and send out the search
                if (msg instanceof OSF2FHashSearchResp) {
                    searcher.sendChannelSetup((OSF2FHashSearchResp) msg.clone(), true);
                } else if (msg instanceof OSF2FTextSearchResp) {
                    searcher.sendTextSearchResp((OSF2FTextSearchResp) msg.clone(), true);
                } else {
                    Debug.out("got unknown message: " + msg.getDescription());
                }
            }
        }

    }

    /**
     * 
     * @param source
     * @param msg
     * @return
     */
    private boolean handleTextSearch(final FriendConnection source, final OSF2FTextSearch msg) {

        boolean shouldForward = true;

        if (logger.isLoggable(Level.FINER)) {
            logger.finer("handleTextSearch: " + msg.getSearchString() + " from "
                    + source.getRemoteFriend().getNick());
        }

        String searchString = msg.getSearchString();

        // common case is no filtering.
        if (filteredKeywords.length > 0) {
            StringTokenizer toks = new StringTokenizer(searchString);

            for (String filter : filteredKeywords) {
                if (searchString.contains(filter)) {
                    logger.fine("Blocking search due to filter: " + searchString + " matched by: "
                            + filter);
                    return false;
                }
            }
        }

        List<FileCollection> results = filelistManager.handleSearch(source.getRemoteFriend(),
                searchString);

        if (results.size() > 0) {
            if (canRespondToSearch()) {
                logger.finer("found matches: " + results.size());
                // long fileListSize = results.getFileNum();

                List<DelayedExecutionEntry> delayedExecutionTasks = new LinkedList<DelayedExecutionEntry>();
                long time = System.currentTimeMillis();
                for (FileCollection c : results) {
                    // send back a response
                    int channelId = random.nextInt();
                    LinkedList<FileCollection> list = new LinkedList<FileCollection>();
                    list.add(c);
                    byte[] encoded = FileListManager.encode_basic(new FileList(list), false);

                    final OSF2FTextSearchResp resp = new OSF2FTextSearchResp(
                            OSF2FMessage.CURRENT_VERSION, OSF2FMessage.FILE_LIST_TYPE_PARTIAL,
                            msg.getSearchID(), channelId, encoded);
                    int delay = overlayManager.getSearchDelayForInfohash(source.getRemoteFriend(),
                            c.getUniqueIdBytes());
                    delayedExecutionTasks.add(new DelayedExecutionEntry(time + delay, 0,
                            new TimerTask() {
                                @Override
                                public void run() {
                                    /*
                                     * check if the search got canceled while we
                                     * were sleeping
                                     */
                                    if (!isSearchCanceled(msg.getSearchID())) {
                                        source.sendTextSearchResp(resp, false);
                                    }
                                }
                            }));
                }
                delayedExecutor.queue(delayedExecutionTasks);

            } else {
                // not enough capacity :-(
                shouldForward = false;
            }
        }

        return shouldForward;
    }

    public void sendDirectedHashSearch(FriendConnection target, byte[] infoHash) {

        long metainfohashhash = filelistManager.getInfoHashhash(infoHash);

        int newSearchId = 0;
        while (newSearchId == 0) {
            newSearchId = random.nextInt();
        }
        OSF2FHashSearch search = new OSF2FHashSearch(OSF2FMessage.CURRENT_VERSION, newSearchId,
                metainfohashhash);
        lock.lock();
        try {
            sentSearches.put(newSearchId, new SentSearch(search));
        } finally {
            lock.unlock();
        }
        overlayManager.sendDirectedSearch(target, search);

    }

    public long getInfoHashHashFromSearchId(int searchId) {
        lock.lock();
        try {
            SentSearch sentSearch = sentSearches.get(searchId);
            if (sentSearch != null && sentSearch.search instanceof OSF2FHashSearch) {
                return ((OSF2FHashSearch) sentSearch.search).getInfohashhash();
            }
        } finally {
            lock.unlock();
        }
        return -1;
    }

    public void sendHashSearch(byte[] infoHash) {
        long metainfohashhash = filelistManager.getInfoHashhash(infoHash);

        int newSearchId = 0;
        while (newSearchId == 0) {
            newSearchId = random.nextInt();
        }
        OSF2FSearch search = new OSF2FHashSearch(OSF2FMessage.CURRENT_VERSION, newSearchId,
                metainfohashhash);

        sendSearch(newSearchId, search, true, false);
    }

    public void sendServiceSearch(long searchKey, HashSearchListener listener) {

        int newSearchId = 0;
        while (newSearchId == 0) {
            newSearchId = random.nextInt();
        }
        OSF2FHashSearch search = new OSF2FHashSearch(OSF2FMessage.CURRENT_VERSION, newSearchId,
                searchKey);
        search.addListener(listener);
        // For service sharing, send to all friends and skip queue.
        sendSearch(newSearchId, search, true, true);
    }

    public void sendSearch(int newSearchId, OSF2FSearch search, boolean skipQueue, boolean forceSend) {
        lock.lock();
        try {
            sentSearches.put(newSearchId, new SentSearch(search));
        } finally {
            lock.unlock();
        }
        overlayManager.sendSearchOrCancel(search, skipQueue, forceSend);
    }

    public int sendTextSearch(String searchString, TextSearchListener listener) {
        int newSearchId = 0;
        while (newSearchId == 0) {
            newSearchId = random.nextInt();
        }

        if (FileCollection.containsKeyword(searchString)) {
            searchString = searchString.replaceAll(":", ";");
            searchString = handleKeyWords(searchString);
        }

        OSF2FSearch search = new OSF2FTextSearch(OSF2FMessage.CURRENT_VERSION,
                OSF2FMessage.FILE_LIST_TYPE_PARTIAL, newSearchId, searchString);
        textSearchManager.sentSearch(newSearchId, searchString, listener);
        sendSearch(newSearchId, search, true, false);
        return newSearchId;
    }

    private static String handleKeyWords(String searchString) {
        searchString = FileCollection.removeWhiteSpaceAfteKeyChars(searchString);
        String[] interestingKeyWords = new String[] { "id", "sha1", "ed2k" };
        int[] interestingKeyWordExectedKeyLen = { 20, 20, 16 };
        StringBuilder b = new StringBuilder();
        String[] split = searchString.split(" ");
        for (String s : split) {
            // check for id
            String toAdd = s;
            for (int i = 0; i < interestingKeyWords.length; i++) {
                String fromId = convertToBase64(s, interestingKeyWords[i],
                        interestingKeyWordExectedKeyLen[i]);
                if (fromId != null) {
                    toAdd = fromId;
                }
            }
            b.append(toAdd + " ");
            if (!toAdd.equals(s)) {
                logger.fine("converted search: " + s + "->" + toAdd);
            }
        }
        return b.toString().trim();
    }

    private static String convertToBase64(String searchTerm, String _keyword, int expectedBytes) {
        for (String sep : FileCollection.KEYWORDENDINGS) {
            String keyword = _keyword + sep;
            if (searchTerm.contains(keyword)) {
                logger.finer("converting base: " + searchTerm);
                try {
                    String baseXHash = searchTerm.substring(keyword.length());
                    logger.finer("basex hash: " + baseXHash);
                    String hash = ShareManagerTools.baseXtoBase64(baseXHash, expectedBytes);
                    String toAdd = keyword + hash;
                    logger.finer("new string: " + toAdd);
                    return toAdd;
                } catch (UnsupportedEncodingException e) {
                    // TODO Auto-generated catch block
                    e.printStackTrace();
                }
            }
        }
        return null;
    }

    static class DebugChannelIdEntry implements Comparable<DebugChannelIdEntry> {
        final int count;
        final String name;

        public DebugChannelIdEntry(String name, int count) {
            super();
            this.name = name;
            this.count = count;
        }

        @Override
        public int compareTo(DebugChannelIdEntry o) {
            if (o.count > count) {
                return 1;
            } else if (o.count == count) {
                return 0;
            } else {
                return -1;
            }
        }
    }

    private static class DebugChannelSetupErrorStats {
        private final LinkedList<FriendConnection.OverlayRegistrationError> errorList = new LinkedList<FriendConnection.OverlayRegistrationError>();

        int MAX_SIZE = 10000;

        public void add(FriendConnection.OverlayRegistrationError error) {
            lock.lock();
            try {
                if (errorList.size() > MAX_SIZE) {
                    errorList.removeLast();
                }
                errorList.addFirst(error);
            } finally {
                lock.unlock();
            }
        }
        handleIncomingSearchResponse
        public String getDebugStats() {
            StringBuilder b = new StringBuilder();
            HashMap<String, Integer> errorsPerFriend = new HashMap<String, Integer>();
            HashMap<String, Integer> errorsPerPair = new HashMap<String, Integer>();
            lock.lock();
            try {

                for (FriendConnection.OverlayRegistrationError error : errorList) {
                    final String s = error.setupMessageSource;
                    if (!errorsPerFriend.containsKey(s)) {
                        errorsPerFriend.put(s, 0);
                    }
                    errorsPerFriend.put(s, errorsPerFriend.get(s) + 1);

                    String d = error.direction;
                    if (!errorsPerPair.containsKey(d)) {
                        errorsPerPair.put(d, 0);
                    }
                    errorsPerPair.put(d, errorsPerPair.get(d) + 1);
                }

                ArrayList<DebugChannelIdEntry> friendTotalOrder = new ArrayList<DebugChannelIdEntry>();
                for (String f : errorsPerFriend.keySet()) {
                    friendTotalOrder.add(new DebugChannelIdEntry(f, errorsPerFriend.get(f)));
                }
                Collections.sort(friendTotalOrder);
                b.append("by source:\n");
                for (DebugChannelIdEntry e : friendTotalOrder) {
                    b.append("  " + e.name + " " + e.count + "\n");
                }

                ArrayList<DebugChannelIdEntry> byPairOrder = new ArrayList<DebugChannelIdEntry>();
                for (String f : errorsPerPair.keySet()) {
                    byPairOrder.add(new DebugChannelIdEntry(f, errorsPerPair.get(f)));
                }
                Collections.sort(byPairOrder);
                b.append("by pair:\n");
                for (DebugChannelIdEntry e : byPairOrder) {
                    b.append("  " + e.name + " " + e.count + "\n");
                }

            } finally {
                lock.unlock();
            }
            return b.toString();
        }
    }

    class DelayedSearchQueue {

        long lastSearchesPerSecondLogTime = 0;
        long lastBytesPerSecondCount = 0;
        int searchCount = 0;

        private long mDelay;
        private final LinkedBlockingQueue<DelayedSearchQueueEntry> queue = new LinkedBlockingQueue<DelayedSearchQueueEntry>();
        private final HashMap<Integer, DelayedSearchQueueEntry> queuedSearches = new HashMap<Integer, DelayedSearchQueueEntry>();

        public DelayedSearchQueue(long delay) {
            this.mDelay = delay;
            Thread t = new Thread(new DelayedSearchQueueThread());
            t.setDaemon(true);
            t.setName(SEARCH_QUEUE_THREAD_NAME);
            t.start();
        }

        /**
         * Warning -- changing this won't re-order things already in the queue,
         * so if you add something with a much smaller delay than the current
         * head of the queue, it will wait until that's removed before sending
         * the new message.
         */
        public void setDelay(long inDelay) {
            this.mDelay = inDelay;
        }

        public void add(FriendConnection source, OSF2FSearch search) {

            if (lastSearchesPerSecondLogTime + 1000 < System.currentTimeMillis()) {

                lock.lock();
                try {
                    logger.fine("Searches/sec: " + searchCount + " bytes: "
                            + lastBytesPerSecondCount + " searchQueueSize: "
                            + queuedSearches.size());
                } finally {
                    lock.unlock();
                }

                lastSearchesPerSecondLogTime = System.currentTimeMillis();
                searchCount = 0;
                lastBytesPerSecondCount = 0;
            }

            searchCount++;
            lastBytesPerSecondCount += FriendConnectionQueue.getMessageLen(search);

            lock.lock();
            try {

                // Flush the accounting info every 60 seconds
                if (SearchManager.this.lastSearchAccountingFlush + 60 * 1000 < System
                        .currentTimeMillis()) {
                    lastSearchAccountingFlush = System.currentTimeMillis();
                    searchesPerFriend.clear();
                }

                // If the search queue is more than half full, start dropping
                // searches
                // proportional to how much of the total queue each person is
                // consuming
                if (queuedSearches.size() > 0.25 * MAX_SEARCH_QUEUE_LENGTH) {
                    if (searchesPerFriend.containsKey(source.getRemoteFriend())) {
                        int outstanding = searchesPerFriend.get(source.getRemoteFriend()).v;

                        // We add a hard limit on the number of searches from
                        // any one person.
                        if (outstanding > 0.15 * MAX_SEARCH_QUEUE_LENGTH) {
                            logger.fine("Dropping due to 25% of total queue consumption "
                                    + source.getRemoteFriend().getNick() + " " + outstanding
                                    + " / " + MAX_SEARCH_QUEUE_LENGTH);
                            return;
                        }

                        // In other cases, we drop proportional to the
                        // consumption of the overall queue.
                        double acceptProb = (double) outstanding / (double) queuedSearches.size();
                        if (random.nextDouble() < acceptProb) {
                            if (logger.isLoggable(Level.FINE)) {
                                logger.fine("*** RED for search from " + source + " outstanding: "
                                        + outstanding + " total: " + queuedSearches.size());
                            }
                            return;
                        }
                    }
                }

                if (queuedSearches.size() > MAX_SEARCH_QUEUE_LENGTH) {
                    if (logger.isLoggable(Level.FINER)) {
                        logger.finer("not forwarding search, queue length too large. id: "
                                + search.getSearchID());
                    }
                    return;
                }
                if (!queuedSearches.containsKey(search.getSearchID())) {
                    logger.finest("adding search to forward queue, will forward in " + mDelay
                            + " ms");
                    DelayedSearchQueueEntry entry = new DelayedSearchQueueEntry(search, source,
                            System.currentTimeMillis() + mDelay);

                    if (searchesPerFriend.containsKey(source.getRemoteFriend()) == false) {
                        searchesPerFriend.put(source.getRemoteFriend(),
                                new SearchManager.MutableInteger());
                    }
                    searchesPerFriend.get(source.getRemoteFriend()).v++;
                    logger.finest("Search for friend: " + source.getRemoteFriend().getNick() + " "
                            + searchesPerFriend.get(source.getRemoteFriend()).v);

                    queuedSearches.put(search.getSearchID(), entry);
                    queue.add(entry);

                } else {
                    logger.finer("search already in queue, not adding");
                }
            } finally {
                lock.unlock();
            }
        }

        /*
         * make sure to already have the lock when calling this
         */
        public boolean isQueued(OSF2FSearch search) {
            return queuedSearches.containsKey(search.getSearchID());
        }

        class DelayedSearchQueueThread implements Runnable {

            @Override
            public void run() {
                while (true) {
                    try {
                        DelayedSearchQueueEntry e = queue.take();
                        long timeUntilSend = e.dontSendBefore - System.currentTimeMillis();
                        if (timeUntilSend > 0) {
                            logger.finer("got search (" + e.search.getDescription()
                                    + ") to forward, waiting " + timeUntilSend
                                    + " ms until sending");
                            Thread.sleep(timeUntilSend);
                        }
                        forwardSearch(e.source, e.search);
                        /*
                         * remove the search from the queuedSearchesMap
                         */
                        lock.lock();
                        try {
                            queuedSearches.remove(e.search.getSearchID());
                            // If searchesPerFriend was flushed while this
                            // search was in the
                            // queue, the get() call will return null.
                            if (searchesPerFriend.containsKey(e.source.getRemoteFriend())) {
                                searchesPerFriend.get(e.source.getRemoteFriend()).v--;
                            }
                        } finally {
                            lock.unlock();
                        }
                        /*
                         * if we didn't sleep at all, sleep the min time between
                         * searches
                         */
                        if (timeUntilSend < 1) {
                            double ms = 1000.0 / FriendConnection.MAX_OUTGOING_SEARCH_RATE;
                            int msFloor = (int) Math.floor(ms);
                            int nanosLeft = (int) Math.round((ms - msFloor) * 1000000.0);
                            logger.finest("sleeping " + msFloor + "ms + " + nanosLeft + " ns");
                            Thread.sleep(msFloor, Math.min(999999, nanosLeft));
                        }

                    } catch (Exception e1) {
                        logger.warning("*** Delayed search queue thread error: " + e1.toString());
                        e1.printStackTrace();
                        BackendErrorLog.get().logException(e1);
                    }
                }
            }
        }
    }

    static class DelayedSearchQueueEntry {
        final long dontSendBefore;
        final OSF2FSearch search;
        final FriendConnection source;
        final long insertionTime;

        public DelayedSearchQueueEntry(OSF2FSearch search, FriendConnection source,
                long dontSendBefore) {
            this.insertionTime = System.currentTimeMillis();
            this.search = search;
            this.source = source;
            this.dontSendBefore = dontSendBefore;
        }
    }

    class ForwardedSearch {
        private int responsesForwarded = 0;
        private final OSF2FSearch search;
        private final FriendConnection source;
        private final long time;

        public ForwardedSearch(FriendConnection source, OSF2FSearch search) {
            this.time = System.currentTimeMillis();
            this.source = source;
            this.search = search;

        }

        public long getAge() {
            return System.currentTimeMillis() - this.time;
        }

        public int getResponseNum() {
            return responsesForwarded;
        }

        public OSF2FSearch getSearch() {
            return search;
        }

        public int getSearchId() {
            return search.getSearchID();
        }

        public FriendConnection getSource() {
            return source;
        }

        public void gotResponse() {
            responsesForwarded++;
        }

        public boolean isTimedOut() {
            return getAge() > MAX_SEARCH_AGE;
        }
    }

    class ServiceSearch {
        private final OSF2FHashSearch search;
        private final List<FriendConnection> sources;
        private final long time;
    
        public ServiceSearch(SharedService service, OSF2FHashSearch search) {
            this.time = System.currentTimeMillis();
            this.search = search;
            this.sources = new LinkedList<FriendConnection>();
        }

        public OSF2FSearch getSearch() {
            return search;
        }

        public int getSearchId() {
            return search.getSearchID();
        }

        public void addSource(FriendConnection source, OSF2FHashSearchResp response)
                throws OverlayRegistrationError {
            ServiceConnectionManager.getInstance().createChannel(
                    source, search, response, false);
            sources.add(source);

            Debug.out("Created a channel for a service search. (now " + sources.size()
                        + ").");
        }

        public List<FriendConnection> getSources() {
            return sources;
        }

        public boolean isTimedOut() {
            return (System.currentTimeMillis() - time) > MAX_SEARCH_AGE;
        }
    }

    public static class RotatingBloomFilter {
        private static final int OBJECTS_TO_STORE = 1000000;

        private static final int SIZE_IN_BITS = 10240 * 1024;

        private long currentFilterCreated;
        private final LinkedList<BloomFilter> filters = new LinkedList<BloomFilter>();
        private final int maxBuckets;
        private final long maxFilterAge;

        public RotatingBloomFilter(long totalAge, int buckets) {
            this.maxBuckets = buckets;
            this.maxFilterAge = (totalAge / buckets) + 1;
            rotate();
        }

        public boolean contains(int searchId, int searchValue) {
            try {
                byte[] bytes = bytesFromInts(searchId, searchValue);
                for (BloomFilter f : filters) {
                    if (f.test(bytes)) {
                        return true;
                    }
                }
            } catch (Exception e) {
                Debug.out("Error when checking bloom filter, searchId=" + searchId + " value="
                        + searchValue, e);
            }
            return false;
        }

        public double getPrevFilterFalsePositiveEst() {
            if (filters.size() > 1) {
                return filters.get(1).getPredictedFalsePositiveRate();
            } else {
                return filters.getFirst().getPredictedFalsePositiveRate();
            }
        }

        public int getPrevFilterNumElements() {
            if (filters.size() > 1) {
                return filters.get(1).getUniqueObjectsStored();
            } else {
                return filters.getFirst().getUniqueObjectsStored();
            }
        }

        public void insert(int searchId, int searchValue) {
            try {
                byte[] bytes = bytesFromInts(searchId, searchValue);
                filters.getFirst().insert(bytes);
            } catch (Exception e) {
                Debug.out("Error when inserting into bloom filter, searchId=" + searchId
                        + " value=" + searchValue, e);
            }
        }

        private void rotate() {

            if (filters.size() > 0) {
                BloomFilter prevFilter = filters.getFirst();
                String str = "Rotating bloom filter: objects="
                        + prevFilter.getUniqueObjectsStored() + " predicted false positive rate="
                        + (100 * prevFilter.getPredictedFalsePositiveRate() + "%");
                logger.info(str);
            }
            currentFilterCreated = System.currentTimeMillis();
            try {
                filters.addFirst(new BloomFilter(SIZE_IN_BITS, OBJECTS_TO_STORE));
            } catch (NoSuchAlgorithmException e) {
                // TODO Auto-generated catch block
                e.printStackTrace();
            }
            if (filters.size() > maxBuckets) {
                filters.removeLast();
            }
        }

        public boolean rotateIfNeeded() {
            long currentFilterAge = System.currentTimeMillis() - currentFilterCreated;
            if (currentFilterAge > maxFilterAge) {
                rotate();
                return true;
            }
            return false;
        }

        private static byte[] bytesFromInts(int int1, int int2) {
            byte[] bytes = new byte[8];

            bytes[0] = (byte) (int1 >>> 24);
            bytes[1] = (byte) (int1 >>> 16);
            bytes[2] = (byte) (int1 >>> 8);
            bytes[3] = (byte) int1;

            bytes[4] = (byte) (int2 >>> 24);
            bytes[5] = (byte) (int2 >>> 16);
            bytes[6] = (byte) (int2 >>> 8);
            bytes[7] = (byte) int2;
            return bytes;
        }

        public static void main(String[] args) {
            OSF2FMain.getSingelton();
            logger.setLevel(Level.FINE);
            Random rand = new Random();

            RotatingBloomFilter bf = new RotatingBloomFilter(60 * 1000, 4);

            Set<String> inserts = new HashSet<String>();
            for (int j = 0; j < 8; j++) {
                for (int i = 0; i < 20000; i++) {
                    int r1 = rand.nextInt();
                    int r2 = rand.nextInt();
                    byte[] bytes = bytesFromInts(r1, r2);
                    inserts.add(new String(Base64.encode(bytes)));
                    bf.insert(r1, r2);
                    if (!bf.contains(r1, r2)) {
                        System.err.println("insert failes (does not contain it anymore)");
                    }
                }
                bf.rotate();
            }

            int fps = 0, to_check = 200000;
            for (int i = 0; i < to_check; i++) {
                int int1;
                int int2;
                byte[] bytes;
                do {
                    int1 = rand.nextInt();
                    int2 = rand.nextInt();
                    bytes = bytesFromInts(int1, int2);
                } while (inserts.contains(new String(Base64.encode(bytes))) == true);
                if (bf.contains(int1, int2) == true) {
                    fps++;
                }
            }

            System.out.println("false positive check, " + fps + "/" + to_check);

            System.out.println("mem: "
                    + (Runtime.getRuntime().totalMemory() - Runtime.getRuntime().freeMemory()));

        }

    }

    class SentSearch {
        private int responses = 0;
        private final OSF2FSearch search;

        private final long time;

        public SentSearch(OSF2FSearch search) {
            this.search = search;
            this.time = System.currentTimeMillis();
        }

        public long getAge() {
            return System.currentTimeMillis() - this.time;
        }

        public int getResponseNum() {
            return responses;
        }

        public OSF2FSearch getSearch() {
            return search;
        }

        public void gotResponse() {
            responses++;
        }

        public boolean isTimedOut() {
            return getAge() > MAX_SEARCH_AGE;
        }

    }

    public interface HashSearchListener {
        public void searchResponseReceived(OSF2FHashSearch search, FriendConnection source,
                OSF2FHashSearchResp msg);
    }

    public interface TextSearchListener {
        public void searchResponseReceived(TextSearchResponseItem r);
    }

    class TextSearchManager {
        private final ConcurrentHashMap<Integer, TextSearchResponse> responses;
        private final ConcurrentHashMap<Integer, TextSearchListener> listeners;

        public TextSearchManager() {
            responses = new ConcurrentHashMap<Integer, TextSearchResponse>();
            listeners = new ConcurrentHashMap<Integer, TextSearchListener>();
        }

        public List<TextSearchResult> getResults(int searchId) {
            TextSearchResponse resps = responses.get(searchId);

            HashMap<String, TextSearchResult> result = new HashMap<String, TextSearchResult>();

            if (resps != null) {
                /*
                 * group into file collections
                 */
                for (TextSearchResponseItem item : resps.getItems()) {
                    for (FileCollection collection : item.getFileList().getElements()) {
                        if (result.containsKey(collection.getUniqueID())) {
                            TextSearchResult existing = result.get(collection.getUniqueID());
                            existing.merge(item, collection);
                        } else {
                            // mark stuff that we already have
                            boolean alreadyInLibrary = true;
                            GlobalManager globalManager = AzureusCoreImpl.getSingleton()
                                    .getGlobalManager();
                            DownloadManager dm = globalManager.getDownloadManager(new HashWrapper(
                                    collection.getUniqueIdBytes()));
                            if (dm == null) {
                                alreadyInLibrary = false;
                            }
                            result.put(collection.getUniqueID(), new TextSearchResult(item,
                                    collection, alreadyInLibrary));
                        }
                    }
                }

                // /*
                // * verify that we didn't get any bad data
                // */
                // for (TextSearchResult item : result.values()) {
                // FileCollection collection = item.getCollection();
                // String searchString = resps.getSearchString();
                // boolean collectionMatch = collection.nameMatch(searchString);
                //
                // Set<FileListFile> filteredFiles = new
                // HashSet<FileListFile>();
                // List<FileListFile> allChildren = collection.getChildren();
                // for (int i = 0; i < allChildren.size(); i++) {
                // FileListFile f = allChildren.get(i);
                // if (filteredFiles.contains(f)) {
                // continue;
                // }
                // if (collectionMatch) {
                // filteredFiles.add(f);
                // } else if (f.searchMatch(searchString)) {
                // filteredFiles.add(f);
                // } else {
                // logger.fine("got search result that doesn't match search: " +
                // f.getFileName() + " ! " + searchString);
                // }
                // }
                // logger.fine(collection.getName() + " totalResp: " +
                // allChildren.size() + " afterFiler=" + filteredFiles.size());
                // collection.setChildren(new
                // ArrayList<FileListFile>(filteredFiles));
                // }

                return new ArrayList<TextSearchResult>(result.values());
            }
            logger.fine("no responses for searchId=" + searchId);
            return new ArrayList<TextSearchResult>();
        }

        public void gotSearchResponse(int searchId, Friend throughFriend, FileList fileList,
                int channelId, int connectionId) {
            TextSearchResponse r = responses.get(searchId);
            if (r != null) {
                long age = System.currentTimeMillis() - r.getTime();
                TextSearchResponseItem item = new TextSearchResponseItem(throughFriend, fileList,
                        age, channelId, connectionId);
                r.add(item);
                TextSearchListener listener = listeners.get(searchId);
                if (listener != null) {
                    listener.searchResponseReceived(item);
                }
            } else {
                logger.warning("got response for unknown search");
            }
        }

        public void sentSearch(int searchId, String searchString, TextSearchListener listener) {
            responses.put(searchId, new TextSearchResponse(searchString));
            if (listener != null) {
                listeners.put(searchId, listener);
            }
        }

        public void clearOldResponses() {
            for (Iterator<Integer> iterator = responses.keySet().iterator(); iterator.hasNext();) {
                Integer key = iterator.next();
                TextSearchResponse response = responses.get(key);
                if (System.currentTimeMillis() - response.getTime() > 10 * 60 * 1000) {
                    iterator.remove();
                    listeners.remove(key);
                }

            }
        }
    }

    public boolean isSearchInBloomFilter(OSF2FSearch search) {
        lock.lock();
        try {
            int searchID = search.getSearchID();
            int valueID = search.getValueID();
            if (recentSearches.contains(searchID, valueID)) {
                bloomSearchesBlockedCurr++;
            }
        } finally {
            lock.unlock();
        }
        return false;
    }

    // Only visible for the analytics code
    public RotatingBloomFilter getRecentSearchesBloomFilter() {
        return recentSearches;
    }
}
