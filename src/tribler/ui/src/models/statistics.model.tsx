// For compile-time type checking and code completion

export interface TriblerStatistics {
    peers: number;
    db_size: number;
    num_torrents: number;
    libtorrent?: {
        total_sent_bytes: number;
        total_recv_bytes: number;
        sessions:  {
            hops: boolean;
            recv_bytes: number;
            sent_bytes: string;
        }[];
    };
}
