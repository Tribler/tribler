// For compile-time type checking and code completion

type direction = 'forward' | 'backward';

export interface Relay {
    circuit_from: number;
    circuit_to: number;
    is_rendezvous: boolean;
    direction: direction;
    bytes_up: number;
    bytes_down: number;
    creation_time: number;
}
