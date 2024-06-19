// For compile-time type checking and code completion

export interface Peer {
    id: string;
    extended_version: string;
    ip: string;
    port: number;
    optimistic: boolean;
    direction: string;
    uprate: number;
    uinterested: boolean;
    uchoked: boolean;
    uhasqueries: boolean;
    uflushed: boolean;
    downrate: number;
    dinterested: boolean;
    dchoked: boolean;
    snubbed: boolean;
    utotal: number;
    dtotal: number;
    completed: number;
    speed: number;
    connection_type: number;
    seed: boolean;
    upload_only: boolean;
}
