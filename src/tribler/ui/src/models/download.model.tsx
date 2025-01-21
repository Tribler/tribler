// For compile-time type checking and code completion

import { Peer } from "./bittorrentpeer.model";
import { Tracker } from "./tracker.model ";


type state = 'ALLOCATING_DISKSPACE' | 'WAITING_FOR_HASHCHECK' | 'HASHCHECKING' | 'DOWNLOADING'  |
             'SEEDING' | 'STOPPED' | 'STOPPED_ON_ERROR' | 'METADATA'  | 'CIRCUITS' | 'EXIT_NODES';

export interface Download {
    name: string;
    progress: number;
    infohash: string;
    speed_down: number;
    speed_up: number;
    status: state;
    status_code: number;
    size: number;
    eta: number;
    num_peers: number;
    num_seeds: number;
    num_connected_peers: number;
    num_connected_seeds: number;
    all_time_upload: number;
    all_time_download: number;
    all_time_ratio: number;
    trackers: Tracker[];
    hops: number;
    anon_download: boolean;
    safe_seeding: boolean;
    max_upload_speed: number;
    max_download_speed: number;
    destination: string;
    completed_dir: string;
    total_pieces: number;
    error: string;
    time_added: number;
    availability?: number;
    pieces?: string;
    peers: Peer[];
}
