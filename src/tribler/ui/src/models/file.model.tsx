// For compile-time type checking and code completion

export interface File {
    index: number;
    name: string;
    size: number;
    included: boolean;
    progress: number;
}
