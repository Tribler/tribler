import SimpleTable, {getHeader} from "@/components/ui/simple-table";
import {triblerService} from "@/services/tribler.service";
import {isErrorDict} from "@/services/reporting";
import {ColumnDef} from "@tanstack/react-table";
import {useState} from "react";
import {useInterval} from "@/hooks/useInterval";
import {Health} from "@/models/health.model";
import {formatTimeRelative} from "@/lib/utils";

export const popularityColumns: ColumnDef<Health>[] = [
    {
        accessorKey: "infohash",
        header: getHeader("Infohash", false, true, true),
        cell: ({row}) => <p className="font-mono select-text">{row.original.infohash}</p>,
    },
    {
        accessorKey: "seeders",
        header: getHeader("Seeders", false),
        cell: ({row}) => (
            <p className={`${row.original.seeders > 0 ? "text-green-400" : "text-red-500"}`}>{row.original.seeders}</p>
        ),
    },
    {
        accessorKey: "leechers",
        header: getHeader("Leechers", false),
        cell: ({row}) => (
            <p className={`${row.original.leechers > 0 ? "text-green-400" : "text-red-500"}`}>
                {row.original.leechers}
            </p>
        ),
    },
    {
        accessorKey: "tracker",
        header: getHeader("Tracker", false),
    },
    {
        accessorKey: "last_check",
        header: getHeader("Last check", false),
        cell: ({row}) => {
            return (
                <span className="whitespace-nowrap">
                    {row.original.last_check > 24 * 3600 ? formatTimeRelative(row.original.last_check) : "unknown"}
                </span>
            );
        },
    },
];

export default function Popularity() {
    const [healthChecks, setHealthChecks] = useState<Health[]>([]);

    useInterval(
        async () => {
            const healthChecks = await triblerService.getHealthCheckHistory();
            if (!(healthChecks === undefined) && !isErrorDict(healthChecks)) {
                setHealthChecks(healthChecks);
            }
        },
        5000,
        true
    );

    return (
        <SimpleTable
            className="[&>[data-radix-scroll-area-viewport]]:max-h-[calc(100vh-82px)]"
            data={healthChecks}
            columns={popularityColumns}
            initialState={{sorting: [{id: "last_check", desc: true}]}}
        />
    );
}
