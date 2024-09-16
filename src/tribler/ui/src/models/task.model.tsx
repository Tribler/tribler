export interface Task {
    name: string;
    running: boolean;
    stack: string[];
    taskmanager?: string;
    start_time?: number;
    interval?: number;
}
