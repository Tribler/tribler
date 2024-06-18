import SimpleTable from "@/components/ui/simple-table";
import { ColumnDef } from "@tanstack/react-table";
import { useState } from "react";
import { ipv8Service } from "@/services/ipv8.service";
import { useInterval } from '@/hooks/useInterval';
import { formatTimeDiff } from "@/lib/utils";


interface Task {
    taskmanager: string;
    name: string;
    running: boolean;
    interval: number;
    start_time: number;
}

const taskColumns: ColumnDef<Task>[] = [
    {
        accessorKey: "taskmanager",
        header: "Taskmanager",
    },
    {
        accessorKey: "name",
        header: "Name",
        cell: ({ row }) => {
            return <span className="line-clamp-1">{row.original.name}</span>
        },
    },
    {
        accessorKey: "running",
        header: "Running?",
    },
    {
        accessorKey: "interval",
        header: "Interval",
    },
    {
        accessorKey: "start_time",
        header: "Started",
        cell: ({ row }) => {
            return row.original.start_time && <span>{formatTimeDiff(row.original.start_time)}</span>
        },
    },
]

export default function Tasks() {
    const [tasks, setTasks] = useState<Task[]>([])

    useInterval(async () => {
        setTasks((await ipv8Service.getTasks()));
    }, 5000, true);

    return (
        <SimpleTable
            data={tasks}
            columns={taskColumns}
        />
    )
}
