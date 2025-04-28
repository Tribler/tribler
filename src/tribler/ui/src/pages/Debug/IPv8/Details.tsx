import SimpleTable, { getHeader } from "@/components/ui/simple-table";
import { useState } from "react";
import { ipv8Service } from "@/services/ipv8.service";
import { isErrorDict } from "@/services/reporting";
import { OverlayMsgStats } from "@/models/overlay.model";
import { ColumnDef } from "@tanstack/react-table";
import { useInterval } from '@/hooks/useInterval';
import { formatBytes } from "@/lib/utils";
import { ChevronDown, ChevronRight } from "lucide-react";


const statisticColumns: ColumnDef<OverlayMsgStats>[] = [
    {
        accessorKey: "name",
        header: getHeader("Name", false, true, true),
        cell: ({ row }) => {
            return (
                <div
                    className="flex text-start items-center"
                    style={{
                        paddingLeft: `${row.depth * 2}rem`
                    }}
                >
                    {row.original.subRows && row.original.subRows.length > 0 && (
                        <button onClick={row.getToggleExpandedHandler()}>
                            {row.getIsExpanded()
                                ? <ChevronDown size="16" color="#777"></ChevronDown>
                                : <ChevronRight size="16" color="#777"></ChevronRight>}
                        </button>
                    )}
                    {row.original.identifier < 0 && row.original.name}
                </div>
            )
        }
    },
    {
        accessorKey: "identifier",
        header: "Message identifier",
        cell: ({ row }) => {
            if (row.original.identifier < 0) { return }
            return <span>{row.original.identifier}</span>
        },
    },
    {
        accessorKey: "handler",
        header: "Handler",
    },
    {
        accessorKey: "bytes_up",
        header: getHeader("Upload", false),
        cell: ({ row }) => {
            return <span>{formatBytes(row.original.bytes_up)}</span>
        },
    },
    {
        accessorKey: "bytes_down",
        header: getHeader("Download", false),
        cell: ({ row }) => {
            return <span>{formatBytes(row.original.bytes_down)}</span>
        },
    },
    {
        accessorKey: "num_up",
        header: getHeader("# Msgs sent", false),
        cell: ({ row }) => {
            return <span>{row.original.num_up}</span>
        },
    },
    {
        accessorKey: "num_down",
        header: getHeader("# Msgs received", false),
        cell: ({ row }) => {
            return <span>{row.original.num_down}</span>
        },
    },
]

export default function Details() {
    const [statistics, setStatistics] = useState<OverlayMsgStats[]>([])

    useInterval(async () => {
        let stats: OverlayMsgStats[] = [];
        const response = await ipv8Service.getOverlayStatistics();
        if (!(response === undefined) && !isErrorDict(response)) {
            // We ignore errors and correct with the missing information on the next call
            for (var overlayStats of response) {
                for (const [communityName, communityStats] of Object.entries(overlayStats)) {
                    if (Object.entries(communityStats).length === 0) { break }
                    let messageStats = []
                    for (const [msgName, msgStats] of Object.entries(communityStats)) {
                        let [_, handler] = msgName.split(":", 2);
                        msgStats.handler = handler;
                        messageStats.push({name: communityName, ...msgStats});
                    }
                    messageStats.sort((stat1, stat2) => stat1.identifier - stat2.identifier);
                    stats.push({
                        name: communityName,
                        identifier: -1,
                        num_up: messageStats.reduce((n, stat) => n + stat.num_up, 0),
                        num_down: messageStats.reduce((n, stat) => n + stat.num_down, 0),
                        bytes_up: messageStats.reduce((n, stat) => n + stat.bytes_up, 0),
                        bytes_down: messageStats.reduce((n, stat) => n + stat.bytes_down, 0),
                        first_measured_up: 0,
                        first_measured_down: 0,
                        last_measured_up: 0,
                        last_measured_down: 0,
                        subRows: messageStats
                    });
                }
            }
            setStatistics(stats);
        }
    }, 5000, true);

    return <SimpleTable
        className="[&>[data-radix-scroll-area-viewport]]:max-h-[calc(100vh-97px)]"
        data={statistics}
        columns={statisticColumns}
        expandable={true}
        initialState={{ expanded: true }} />
}
