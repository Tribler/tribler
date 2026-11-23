import BooleanCell from "../BooleanCell";
import SimpleTable, {getHeader} from "@/components/ui/simple-table";
import {ColumnDef} from "@tanstack/react-table";
import {useState} from "react";
import {ipv8Service} from "@/services/ipv8.service";
import {isErrorDict} from "@/services/reporting";
import {Task} from "@/models/task.model";
import {useInterval} from "@/hooks/useInterval";
import {formatTimeRelativeISO} from "@/lib/utils";

const taskColumns: ColumnDef<Task>[] = [
    {
        accessorKey: "taskmanager",
        header: getHeader("TaskManager", true, true, true),
    },
    {
        accessorKey: "name",
        header: getHeader("Name", true, true, true),
        cell: ({row}) => {
            return <span className="line-clamp-1">{row.original.name}</span>;
        },
    },
    {
        accessorKey: "running",
        header: getHeader("TaskRunning"),
        cell: BooleanCell,
    },
    {
        accessorKey: "interval",
        header: getHeader("Interval"),
    },
    {
        accessorKey: "start_time",
        header: getHeader("TaskStarted"),
        cell: ({row}) => {
            return row.original.start_time && <span>{formatTimeRelativeISO(row.original.start_time)}</span>;
        },
    },
];

export default function Tasks() {
    const [tasks, setTasks] = useState<Task[]>([]);

    useInterval(
        async () => {
            const response = await ipv8Service.getTasks();
            if (!(response === undefined) && !isErrorDict(response)) {
                // We ignore errors and correct with the missing information on the next call
                setTasks(response);
            }
        },
        5000,
        true
    );

    return (
        <SimpleTable
            className="[&>[data-radix-scroll-area-viewport]]:max-h-[calc(100vh-122px)]"
            data={tasks}
            columns={taskColumns}
        />
    );
}
