import BooleanCell from "../BooleanCell";
import SimpleTable, {getHeader} from "@/components/ui/simple-table";
import {ColumnDef} from "@tanstack/react-table";
import {useState} from "react";
import {ipv8Service} from "@/services/ipv8.service";
import {isErrorDict} from "@/services/reporting";
import {Relay} from "@/models/relay.model";
import {formatBytes, formatTimeRelativeISO} from "@/lib/utils";
import {useInterval} from "@/hooks/useInterval";

const relayColumns: ColumnDef<Relay>[] = [
    {
        accessorKey: "circuit_from",
        header: getHeader("FromCircuit"),
    },
    {
        accessorKey: "circuit_to",
        header: getHeader("ToCircuit"),
    },
    {
        accessorKey: "is_rendezvous",
        header: getHeader("IsRendezvous"),
        cell: BooleanCell,
    },
    {
        accessorKey: "bytes_up",
        header: getHeader("TrafficUp"),
        cell: ({row}) => {
            return <span>{formatBytes(row.original.bytes_up)}</span>;
        },
    },
    {
        accessorKey: "bytes_down",
        header: getHeader("TrafficDown"),
        cell: ({row}) => {
            return <span>{formatBytes(row.original.bytes_down)}</span>;
        },
    },
    {
        accessorKey: "uptime",
        header: getHeader("Uptime"),
        cell: ({row}) => {
            return <span>{formatTimeRelativeISO(row.original.creation_time)}</span>;
        },
    },
];

export default function Relays() {
    const [relays, setRelays] = useState<Relay[]>([]);

    useInterval(
        async () => {
            const response = await ipv8Service.getRelays();
            if (!(response === undefined) && !isErrorDict(response)) {
                // We ignore errors and correct with the missing information on the next call
                setRelays(response);
            }
        },
        5000,
        true
    );

    return (
        <SimpleTable
            className="[&>[data-radix-scroll-area-viewport]]:max-h-[calc(100vh-122px)]"
            data={relays}
            columns={relayColumns}
        />
    );
}
