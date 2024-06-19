import SimpleTable from "@/components/ui/simple-table";
import { useState } from "react";
import { ipv8Service } from "@/services/ipv8.service";
import { Exit } from "@/models/exit.model";
import { ColumnDef } from "@tanstack/react-table";
import { formatBytes, formatTimeDiff } from "@/lib/utils";
import { useInterval } from '@/hooks/useInterval';


const exitColumns: ColumnDef<Exit>[] = [
    {
        accessorKey: "circuit_from",
        header: "From circuit",
    },
    {
        accessorKey: "enabled",
        header: "Enabled?",
    },
    {
        accessorKey: "bytes_up",
        header: "Up",
        cell: ({ row }) => {
            return <span>{formatBytes(row.original.bytes_up)}</span>
        },
    },
    {
        accessorKey: "bytes_down",
        header: "Down",
        cell: ({ row }) => {
            return <span>{formatBytes(row.original.bytes_down)}</span>
        },
    },
    {
        accessorKey: "uptime",
        header: "Uptime",
        cell: ({ row }) => {
            return <span>{formatTimeDiff(row.original.creation_time)}</span>
        },
    },
]

export default function Exits() {
    const [exits, setExits] = useState<Exit[]>([])

    useInterval(async () => {
        setExits((await ipv8Service.getExits()));
    }, 5000, true);

    return <SimpleTable data={exits} columns={exitColumns} />
}
