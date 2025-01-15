import SimpleTable, { getHeader } from "@/components/ui/simple-table";
import { useState } from "react";
import { ipv8Service } from "@/services/ipv8.service";
import { isErrorDict } from "@/services/reporting";
import { Bucket } from "@/models/bucket.model";
import { ColumnDef } from "@tanstack/react-table";
import { formatTimeRelativeISO } from "@/lib/utils";
import { useInterval } from '@/hooks/useInterval';


const bucketColumns: ColumnDef<Bucket>[] = [
    {
        accessorKey: "prefix",
        header: getHeader("Prefix", false),
    },
    {
        accessorKey: "last_changed",
        header: getHeader("Last changed", false),
        cell: ({ row }) => {
            return <span>{formatTimeRelativeISO(row.original.last_changed)}</span>
        },
    },
    {
        accessorKey: "peer",
        header: getHeader("# Peers", false),
        cell: ({ row }) => {
            return <span>{row.original.peers.length}</span>
        },
    },
]

export default function Buckets() {
    const [buckets, setBuckets] = useState<Bucket[]>([])

    useInterval(async () => {
        const response = await ipv8Service.getBuckets();
        if (!(response === undefined) && !isErrorDict(response)) {
            // We ignore errors and correct with the missing information on the next call
            setBuckets(response);
        }
    }, 5000, true);

    return <SimpleTable data={buckets} columns={bucketColumns} />
}
