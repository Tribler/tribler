import SimpleTable, { getHeader } from "@/components/ui/simple-table";
import { useState } from "react";
import { ipv8Service } from "@/services/ipv8.service";
import { isErrorDict } from "@/services/reporting";
import { Swarm } from "@/models/swarm.model";
import { ColumnDef } from "@tanstack/react-table";
import { formatBytes, formatTimeRelativeISO } from "@/lib/utils";
import { useInterval } from '@/hooks/useInterval';


const swarmColumns: ColumnDef<Swarm>[] = [
    {
        accessorKey: "info_hash",
        header: getHeader("Infohash", false),
    },
    {
        accessorKey: "num_seeders",
        header: getHeader("# Seeders", false),
    },
    {
        accessorKey: "num_connections",
        header: getHeader("# Connections", false),
    },
    {
        accessorKey: "num_connections_incomplete",
        header: getHeader("# Pending", false),
    },
    {
        accessorKey: "seeding",
        header: getHeader("Seeding?", false),
    },
    {
        accessorKey: "last_lookup",
        header: getHeader("Last lookup", false),
        cell: ({ row }) => {
            return <span>{formatTimeRelativeISO(row.original.last_lookup)}</span>
        },
    },
    {
        accessorKey: "bytes_up",
        header: getHeader("Up", false),
        cell: ({ row }) => {
            return <span>{formatBytes(row.original.bytes_down)}</span>
        },
    },
    {
        accessorKey: "bytes_down",
        header: getHeader("Down", false),
        cell: ({ row }) => {
            return <span>{formatBytes(row.original.bytes_down)}</span>
        },
    },
]

export default function Swarms() {
    const [swarms, setSwarms] = useState<Swarm[]>([])

    useInterval(async () => {
        const response = await ipv8Service.getSwarms();
        if (!(response === undefined) && !isErrorDict(response)) {
            // We ignore errors and correct with the missing information on the next call
            setSwarms(response);
        }
    }, 5000, true);

    return <SimpleTable data={swarms} columns={swarmColumns} />
}
