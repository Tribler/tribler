import SimpleTable, { getHeader } from "@/components/ui/simple-table";
import { useState } from "react";
import { ipv8Service } from "@/services/ipv8.service";
import { isErrorDict } from "@/services/reporting";
import { Exit } from "@/models/exit.model";
import { ColumnDef } from "@tanstack/react-table";
import { formatBytes, formatTimeRelativeISO } from "@/lib/utils";
import { useInterval } from '@/hooks/useInterval';


const exitColumns: ColumnDef<Exit>[] = [
    {
        accessorKey: "circuit_from",
        header: getHeader("From circuit", false),
    },
    {
        accessorKey: "enabled",
        header: getHeader("Enabled?", false),
    },
    {
        accessorKey: "bytes_up",
        header: getHeader("Up", false),
        cell: ({ row }) => {
            return <span>{formatBytes(row.original.bytes_up)}</span>
        },
    },
    {
        accessorKey: "bytes_down",
        header: getHeader("Down", false),
        cell: ({ row }) => {
            return <span>{formatBytes(row.original.bytes_down)}</span>
        },
    },
    {
        accessorKey: "uptime",
        header: getHeader("Uptime", false),
        cell: ({ row }) => {
            return <span>{formatTimeRelativeISO(row.original.creation_time)}</span>
        },
    },
]

export default function Exits() {
    const [exits, setExits] = useState<Exit[]>([])

    useInterval(async () => {
        const response = await ipv8Service.getExits();
        if (!(response === undefined) && !isErrorDict(response)) {
            // We ignore errors and correct with the missing information on the next call
            setExits(response);
        }
    }, 5000, true);

    return <SimpleTable data={exits} columns={exitColumns} />
}
