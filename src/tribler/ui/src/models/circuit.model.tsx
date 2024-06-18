// For compile-time type checking and code completion

export interface Circuit {
    circuit_id: number;
    goal_hops: number;
    actual_hops: number;
    verified_hops: string[];
    unverified_hop: string;
    type: string;
    state: string;
    bytes_up: number;
    bytes_down: number;
    creation_time: number;
    exit_flags: number[];
}
