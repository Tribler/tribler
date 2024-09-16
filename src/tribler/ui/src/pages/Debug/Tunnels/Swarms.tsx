import SimpleTable from "@/components/ui/simple-table";
import { useState } from "react";
import { ipv8Service } from "@/services/ipv8.service";
import { isErrorDict } from "@/services/reporting";
import { Swarm } from "@/models/swarm.model";
import { ColumnDef } from "@tanstack/react-table";
import { formatBytes, formatTimeDiff } from "@/lib/utils";
import { useInterval } from '@/hooks/useInterval';


const swarmColumns: ColumnDef<Swarm>[] = [
    {
        accessorKey: "info_hash",
        header: "Infohash",
    },
    {
        accessorKey: "num_seeders",
        header: "# Seeders",
    },
    {
        accessorKey: "num_connections",
        header: "# Connections",
    },
    {
        accessorKey: "num_connections_incomplete",
        header: "# Pending",
    },
    {
        accessorKey: "seeding",
        header: "Seeding?",
    },
    {
        accessorKey: "last_lookup",
        header: "Last lookup",
        cell: ({ row }) => {
            return <span>{formatTimeDiff(row.original.last_lookup)}</span>
        },
    },
    {
        accessorKey: "bytes_up",
        header: "Up",
        cell: ({ row }) => {
            return <span>{formatBytes(row.original.bytes_down)}</span>
        },
    },
    {
        accessorKey: "bytes_down",
        header: "Down",
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
