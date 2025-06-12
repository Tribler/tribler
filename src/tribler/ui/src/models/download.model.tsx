// For compile-time type checking and code completion

import { Peer } from "./bittorrentpeer.model";
import { File } from "./file.model";
import { Tracker } from "./tracker.model";


export enum StatusCode {
    ALLOCATING_DISKSPACE = 0,
    WAITING_FOR_HASHCHECK = 1,
    HASHCHECKING = 2,
    DOWNLOADING = 3,
    SEEDING = 4,
    STOPPED = 5,
    STOPPED_ON_ERROR = 6,
    METADATA = 7,
    LOADING = 8,
    EXIT_NODES = 9
}

export type Status = keyof typeof StatusCode;

export interface Download {
    name: string;
    progress: number;
    infohash: string;
    speed_down: number;
    speed_up: number;
    status: Status;
    status_code: StatusCode;
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
    upload_limit: number;
    download_limit: number;
    destination: string;
    completed_dir: string;
    total_pieces: number;
    error: string;
    time_added: number;
    availability?: number;
    pieces?: string;
    peers: Peer[];
    files: File[] | undefined;
    streamable?: boolean;
    queue_position: number;
    auto_managed: boolean;
    user_stopped: boolean;
}
