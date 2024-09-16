// For compile-time type checking and code completion

interface DHTPeer {
    ip: string;
    port: number;
    mid: string;
    id: string;
    failed: number;
    last_contact: number;
    distance: number;
    }

type endpoint = "UDPIPv4" | "UDPIPv6";

export interface Bucket {
    prefix: string;
    last_changed: number;
    endpoint: endpoint;
    peers: DHTPeer[];
}

export interface Endpoint {
    endpoint: string;
    node_id: string;
    routing_table_size: number;
    routing_table_buckets: number;
    num_keys_in_store: number;
}

export interface DHTStats {
    peer_id: string;
    num_tokens: number;
    endpoints: Endpoint[];
    num_peers_in_store?: Map<string, number>;
    num_store_for_me?: Map<string, number>;
}

export interface Values {
    values: {
        public_key: string | null;
        key: string;
        value: string;
    }[];
    debug: {
        requests: number;
        responses: number;
        responses_with_nodes: number;
        responses_with_values: number;
        time: number;
    };
}