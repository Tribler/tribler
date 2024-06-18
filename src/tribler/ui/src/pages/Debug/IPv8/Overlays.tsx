import SimpleTable from "@/components/ui/simple-table";
import { ColumnDef } from "@tanstack/react-table";
import { useState } from "react";
import { ipv8Service } from "@/services/ipv8.service";
import { Overlay, Peer } from "@/models/overlay.model";
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable";
import { useInterval } from '@/hooks/useInterval';
import { useResizeObserver } from "@/hooks/useResizeObserver";


const overlayColumns: ColumnDef<Overlay>[] = [
    {
        accessorKey: "overlay_name",
        header: "Name",
    },
    {
        accessorKey: "id",
        header: "Community ID",
        cell: ({ row }) => {
            return <span>{row.original.id.slice(0, 10)}</span>
        },
    },
    {
        accessorKey: "my_peer",
        header: "My peer",
        cell: ({ row }) => {
            return <span>{row.original.my_peer.slice(0, 10)}</span>
        },
    },
    {
        accessorKey: "peers",
        header: "Peers",
        cell: ({ row }) => {
            return (
                <span className={`font-medium ${(row.original.peers.length < 20) ? `text-green-400` :
                        ((row.original.peers.length < row.original.max_peers) ? 'text-yellow-400' : 'text-red-400')}`}>
                    {row.original.peers.length}
                </span>
            )
        },
    },
    {
        accessorKey: "statistics.bytes_up",
        header: "Upload (MB)",
        cell: ({ row }) => {
            if (Object.keys(row.original.statistics).length === 0) { return 'N/A' }
            return <span>{(row.original.statistics.bytes_up / 1024 ** 2).toFixed(3)}</span>
        },
    },
    {
        accessorKey: "statistics.bytes_down",
        header: "Download (MB)",
        cell: ({ row }) => {
            if (Object.keys(row.original.statistics).length === 0) { return 'N/A' }
            return <span>{(row.original.statistics.bytes_down / 1024 ** 2).toFixed(3)}</span>
        },
    },
    {
        accessorKey: "statistics.num_up",
        header: "# Msg sent",
        cell: ({ row }) => {
            if (Object.keys(row.original.statistics).length === 0) { return 'N/A' }
            return <span>{row.original.statistics.num_up}</span>
        },
    },
    {
        accessorKey: "statistics.num_down",
        header: "# Msg received",
        cell: ({ row }) => {
            if (Object.keys(row.original.statistics).length === 0) { return 'N/A' }
            return <span>{row.original.statistics.num_down}</span>
        },
    },
    {
        accessorKey: "statistics.diff_time",
        header: "Diff (sec)",
        cell: ({ row }) => {
            if (Object.keys(row.original.statistics).length === 0) { return 'N/A' }
            return <span>{row.original.statistics.diff_time.toFixed(3)}</span>
        },
    },
]

const peerColumns: ColumnDef<Peer>[] = [
    {
        accessorKey: "ip",
        header: "IP",
    },
    {
        accessorKey: "port",
        header: "Port",
    },
    {
        accessorKey: "public_key",
        header: "Public key",
        cell: ({ row }) => {
            return <p className="max-w-[700px] text-ellipsis overflow-hidden">{row.original.public_key}</p>
        },
    },
]

export default function Overlays() {
    const [overlays, setOverlays] = useState<Overlay[]>([])
    const [selectedOverlay, setSelectedOverlay] = useState<Overlay | undefined>()

    useInterval(async () => {
        setOverlays((await ipv8Service.getOverlays()));
    }, 5000, true);

    // We're not getting resize event for elements within ResizeablePanel, so we track the ResizablePanel itself.
    const parentRect = useResizeObserver({ element: document.querySelector('#overlay-list') });

    return (
        <ResizablePanelGroup direction="vertical">
            <ResizablePanel defaultSize={50} id="overlay-list">
                <SimpleTable
                    data={overlays}
                    columns={overlayColumns}
                    allowSelect={true}
                    onSelectedRowsChange={(rows) => setSelectedOverlay(rows[0])}
                    maxHeight={Math.max((parentRect?.height ?? 50) - 0, 50)}
                />
            </ResizablePanel>
            <ResizableHandle className="border-2 border-gray-600" />
            <ResizablePanel defaultSize={50} className={`${selectedOverlay ? "flex" : "hidden"}`}>
                <SimpleTable
                    data={selectedOverlay?.peers || []}
                    columns={peerColumns}
                />
            </ResizablePanel>
        </ResizablePanelGroup>
    )
}
