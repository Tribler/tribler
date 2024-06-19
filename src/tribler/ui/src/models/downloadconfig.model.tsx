// For compile-time type checking and code completion

export interface DownloadConfig {
    uri?: string,
    destination?: string,
    anon_hops?: number,
    selected_files?: number[],
    safe_seeding?: boolean
}
