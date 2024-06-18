import SimpleTable from "@/components/ui/simple-table";
import { useState } from "react";
import { ipv8Service } from "@/services/ipv8.service";
import { OverlayMsgStats } from "@/models/overlay.model";
import { ColumnDef } from "@tanstack/react-table";
import { useInterval } from '@/hooks/useInterval';


const statisticColumns: ColumnDef<OverlayMsgStats>[] = [
    {
        accessorKey: "name",
        header: "Name",
    },
    {
        accessorKey: "bytes_up",
        header: "Upload (MB)",
        cell: ({ row }) => {
            if (row.original.identifier < 0) { return }
            return <span>{(row.original.bytes_up / 1024 ** 2).toFixed(3)}</span>
        },
    },
    {
        accessorKey: "bytes_down",
        header: "Download (MB)",
        cell: ({ row }) => {
            if (row.original.identifier < 0) { return }
            return <span>{(row.original.bytes_down / 1024 ** 2).toFixed(3)}</span>
        },
    },
    {
        accessorKey: "num_up",
        header: "# Msgs sent",
        cell: ({ row }) => {
            if (row.original.identifier < 0) { return }
            return <span>{row.original.num_up}</span>
        },
    },
    {
        accessorKey: "num_down",
        header: "# Msgs received",
        cell: ({ row }) => {
            if (row.original.identifier < 0) { return }
            return <span>{row.original.num_down}</span>
        },
    },
]

export default function Details() {
    const [statistics, setStatistics] = useState<OverlayMsgStats[]>([])

    useInterval(async () => {
        let stats: OverlayMsgStats[] = [];
        for (var overlayStats of (await ipv8Service.getOverlayStatistics())) {
            for (const [communityName, communityStats] of Object.entries(overlayStats)) {
                if (Object.entries(communityStats).length === 0) { break }
                stats.push({
                    name: communityName,
                    identifier: -1,
                    num_up: 0,
                    num_down: 0,
                    bytes_up: 0,
                    bytes_down: 0,
                    first_measured_up: 0,
                    first_measured_down: 0,
                    last_measured_up: 0,
                    last_measured_down: 0,
                });
                for (const [msgName, msgStats] of Object.entries(communityStats)) {
                    msgStats.name = msgName;
                    stats.push(msgStats);
                }
            }
        }
        setStatistics(stats);
    }, 5000, true);

    if (statistics.length === 0) {
        return (
            <div className="w-3/4 px-4">
                <div className="whitespace-pre-wrap">
                    <br />
                    The details are not available because the statistics measurement is not enabled.
                    To enable the statistics measurement, go to:
                    <br /><br />
                    Settings -&gt; Debugging -&gt; Network (IPv8) Statistics
                    <br /><br />
                    After enabling the checkbox and saving the settings, restart Tribler.
                    Then the details will be available here.
                </div>
            </div>
        )
    }

    return <SimpleTable data={statistics} columns={statisticColumns} />
}
