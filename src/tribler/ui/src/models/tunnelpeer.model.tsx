// For compile-time type checking and code completion

export interface Peer {
    ip: string;
    port: number;
    mid: string;
    is_key_compatible: boolean;
    flags: number[];
}
