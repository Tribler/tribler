import { ColumnDef } from "@tanstack/react-table";
import { formatBytes } from "@/lib/utils";
import { Download } from "@/models/download.model";
import { Peer } from "@/models/bittorrentpeer.model";
import SimpleTable, { getHeader } from "@/components/ui/simple-table";
import { EasyTooltip } from "@/components/ui/tooltip";
import { useTranslation } from "react-i18next";

const peerFlags = (peer: Peer): [string, string[]] => {
    const { t } = useTranslation();

    let state = "";
    let stateDescription = [];
    if (peer.optimistic) {
        state += "O,";
        stateDescription.push(`O = ${t("O")}`);
    }
    if (peer.uinterested) {
        state += "UI,";
        stateDescription.push(`UI = ${t("UI")}`);
    }
    if (peer.uchoked) {
        state += "UC,";
        stateDescription.push(`UC = ${t("UC")}`);
    }
    if (peer.uhasqueries) {
        state += "UQ,";
        stateDescription.push(`UQ = ${t("UQ")}`);
    }
    if (peer.uflushed) {
        state += "UBL,";
        stateDescription.push(`UBL = ${t("UBL")}`);
    }
    if (peer.dinterested) {
        state += "DI,";
        stateDescription.push(`DI = ${t("DI")}`);
    }
    if (peer.dchoked) {
        state += "DC,";
        stateDescription.push(`DC = ${t("DC")}`);
    }
    if (peer.snubbed) {
        state += "S,";
        stateDescription.push(`S = ${t("S")}`);
    }
    if (peer["direction"] == "R") {
        state += "R";
        stateDescription.push(`R = ${t("R")}`);
    }
    if (peer["direction"] == "L") {
        state += "L";
        stateDescription.push(`L = ${t("L")}`);
    }
    return [state, stateDescription];
};

const peerColumns: ColumnDef<Peer>[] = [
    {
        accessorKey: "ip",
        header: getHeader("PeerIpPort"),
        cell: ({ row }) => {
            return (
                <span>
                    {row.original.ip} ({row.original.port})
                </span>
            );
        },
    },
    {
        accessorKey: "completed",
        header: getHeader("Completed"),
        cell: ({ row }) => {
            return <span>{(row.original.completed * 100).toFixed(0)}%</span>;
        },
    },
    {
        accessorKey: "downrate",
        header: getHeader("SpeedDown"),
        cell: ({ row }) => {
            return <span>{formatBytes(row.original.downrate)}/s</span>;
        },
    },
    {
        accessorKey: "uprate",
        header: getHeader("SpeedUp"),
        cell: ({ row }) => {
            return <span>{formatBytes(row.original.uprate)}/s</span>;
        },
    },
    {
        accessorKey: "flags",
        header: getHeader("Flags"),
        cell: ({ row }) => {
            const [state, stateDescription] = peerFlags(row.original);
            return <EasyTooltip content={stateDescription}><span>{state}</span></EasyTooltip>
        },
    },
    {
        accessorKey: "extended_version",
        header: getHeader("Client"),
    },
];

export default function Peers({ download, style }: { download: Download; style?: React.CSSProperties }) {
    if (!download.peers) return null;

    return <SimpleTable data={download.peers} columns={peerColumns} style={style} />;
}
