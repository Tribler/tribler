// For compile-time type checking and code completion

export interface Exit {
    circuit_from: number;
    enabled: boolean;
    bytes_up: number;
    bytes_down: number;
    creation_time: number;
    is_introduction: boolean;
    is_rendezvous: boolean;
}
