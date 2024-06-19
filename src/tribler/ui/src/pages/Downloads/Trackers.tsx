import SimpleTable from "@/components/ui/simple-table";
import { translateHeader } from "@/lib/utils";
import { Download } from "@/models/download.model";
import { Tracker } from "@/models/tracker.model ";
import { ColumnDef } from "@tanstack/react-table";


const trackerColumns: ColumnDef<Tracker>[] = [
    {
        accessorKey: "url",
        header: translateHeader('Name'),
    },
    {
        accessorKey: "status",
        header: translateHeader('Status'),
    },
    {
        accessorKey: "peers",
        header: translateHeader('Peers'),
    },
]

export default function Trackers({ download }: { download: Download }) {
    return <SimpleTable data={download.trackers} columns={trackerColumns} />
}
