// For compile-time type checking and code completion

export interface Address {
    ip: string,
    port: number,
}

export interface Strategy {
    name: string,
    target_peers: number,
}

export interface Peer {
    ip: string,
    port: number,
    public_key: string,
}

export interface Statistics {
    num_up: number,
    num_down: number,
    bytes_up: number,
    bytes_down: number,
    diff_time: number,
}

export interface Overlay {
    id: string;
    my_peer: string;
    global_time: number;
    peers: Peer[];
    overlay_name: string;
    statistics: Statistics;
    max_peers: number;
    is_isolated: boolean;
    my_estimated_wan: Address;
    my_estimated_lan: Address;
    strategies: Strategy[];
}

export interface OverlayMsgStats {
    name?: string;
    identifier: number;
    num_up: number;
    num_down: number;
    bytes_up: number;
    bytes_down: number;
    first_measured_up: number;
    first_measured_down: number;
    last_measured_up: number;
    last_measured_down: number;
}

export type OverlayStats = Record<string, Record<string, OverlayMsgStats>>;
