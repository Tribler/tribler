import SimpleTable, {getHeader} from "@/components/ui/simple-table";
import {triblerService} from "@/services/tribler.service";
import {isErrorDict} from "@/services/reporting";
import {ColumnDef} from "@tanstack/react-table";
import {useState} from "react";
import {useInterval} from "@/hooks/useInterval";
import {Health} from "@/models/health.model";
import {formatTimeRelative} from "@/lib/utils";
import {Tabs, TabsContent, TabsList, TabsTrigger} from "@/components/ui/tabs";

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
        header: getHeader("Tracker", false, true, true),
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
    const [healthChecks, setHealthChecks] = useState<{local: Health[], remote: Health[]}>({local: [], remote: []});

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
        <Tabs defaultValue="local" className="w-full flex flex-col flex-wrap">
            <TabsList className="flex-rows-4 border-b">
                <TabsTrigger value="local">Local</TabsTrigger>
                <TabsTrigger value="remote">Remote</TabsTrigger>
            </TabsList>
            <TabsContent value="local" className="contents">
                <SimpleTable
                    className="[&>[data-radix-scroll-area-viewport]]:max-h-[calc(100vh-122px)]"
                    data={healthChecks?.local || []}
                    columns={popularityColumns}
                    initialState={{sorting: [{id: "last_check", desc: true}]}}
                />
            </TabsContent>
            <TabsContent value="remote" className="contents">
                <SimpleTable
                    className="[&>[data-radix-scroll-area-viewport]]:max-h-[calc(100vh-122px)]"
                    data={healthChecks?.remote || []}
                    columns={popularityColumns}
                    initialState={{sorting: [{id: "last_check", desc: true}]}}
                />
            </TabsContent>
        </Tabs>

    );
}
