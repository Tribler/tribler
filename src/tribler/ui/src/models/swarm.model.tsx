// For compile-time type checking and code completion

export interface Swarm {
    info_hash: string;
    num_seeders: number;
    num_connections: number;
    num_connections_incomplete: number;
    seeding: boolean;
    last_lookup: number;
    bytes_up: number;
    bytes_down: number;
}
