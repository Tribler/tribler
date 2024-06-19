import SimpleTable from "@/components/ui/simple-table";
import { useState } from "react";
import { ipv8Service } from "@/services/ipv8.service";
import { Bucket } from "@/models/bucket.model";
import { ColumnDef } from "@tanstack/react-table";
import { formatTimeDiff } from "@/lib/utils";
import { useInterval } from '@/hooks/useInterval';


const bucketColumns: ColumnDef<Bucket>[] = [
    {
        accessorKey: "prefix",
        header: "Prefix",
    },
    {
        accessorKey: "last_changed",
        header: "Last changed",
        cell: ({ row }) => {
            return <span>{formatTimeDiff(row.original.last_changed)}</span>
        },
    },
    {
        accessorKey: "peer",
        header: "# Peers",
        cell: ({ row }) => {
            return <span>{row.original.peers.length}</span>
        },
    },
]

export default function Buckets() {
    const [buckets, setBuckets] = useState<Bucket[]>([])

    useInterval(async () => {
        setBuckets((await ipv8Service.getBuckets()));
    }, 5000, true);

    return <SimpleTable data={buckets} columns={bucketColumns} />
}
