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
