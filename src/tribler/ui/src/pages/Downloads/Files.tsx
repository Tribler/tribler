import { ColumnDef } from "@tanstack/react-table";
import { File } from "@/models/file.model";
import { Download } from "@/models/download.model";
import { useEffect, useRef, useState } from "react";
import { triblerService } from "@/services/tribler.service";
import SimpleTable from "@/components/ui/simple-table";
import { Checkbox } from "@/components/ui/checkbox";
import { formatBytes, getRowSelection, translateHeader } from "@/lib/utils";


const fileColumns: ColumnDef<File>[] = [
    {
        id: "select",
        header: ({ table }) => (
            <Checkbox
                checked={
                    table.getIsAllPageRowsSelected() ||
                    (table.getIsSomePageRowsSelected() && "indeterminate")
                }
                onCheckedChange={(value) => table.toggleAllPageRowsSelected(!!value)}
                aria-label="Select all"
            />
        ),
        cell: ({ row }) => (
            <Checkbox
                checked={row.getIsSelected()}
                onCheckedChange={(value) => {
                    console.log(value);
                    row.toggleSelected(!!value)
                }}
                aria-label="Select row"
            />
        ),
        enableSorting: false,
        enableHiding: false,
    },
    {
        accessorKey: "name",
        header: translateHeader('Name'),
    },
    {
        accessorKey: "size",
        header: translateHeader('Size'),
        cell: ({ row }) => {
            return <span>{formatBytes(row.original.size)}</span>
        },
    },
    {
        accessorKey: "progress",
        header: translateHeader('Progress'),
        cell: ({ row }) => {
            return <span>{(row.original.progress * 100).toFixed(1)}%</span>
        },
    },
]

export default function Files({ download }: { download: Download }) {
    const [files, setFiles] = useState<File[]>([]);
    const initialized = useRef(false)

    function OnSelectedFilesChange(selectedFiles: File[]) {
        let shouldUpdate = false;
        let selectIndices: number[] = [];

        for (let file of files) {
            let otherFile = undefined
            for (let f of selectedFiles) {
                if (f.index === file.index) {
                    otherFile = f;
                    selectIndices.push(otherFile.index);
                    break;
                }
            }

            const otherIncluded = !!otherFile;
            shouldUpdate = shouldUpdate || (file.included !== otherIncluded);
            file.included = otherIncluded;
        }

        if (shouldUpdate)
            triblerService.setDownloadFiles(download.infohash, selectIndices);
    }

    useEffect(() => {
        // Getting the files can take a lot of time, so we avoid doing this twice (due to StrictMode).
        if (initialized.current) {
            return;
        }
        initialized.current = true;
        (async () => setFiles(await triblerService.getDownloadFiles(download.infohash)))();
    }, []);

    // We'll wait until the API call returns so the selection gets set by initialRowSelection
    if (files.length === 0)
        return <></>;

    return <SimpleTable
        data={files}
        columns={fileColumns}
        pageSize={10}
        allowSelectCheckbox={true}
        onSelectedRowsChange={OnSelectedFilesChange}
        initialRowSelection={getRowSelection(files, (file) => file.included)}
        maxHeight={'none'}
    />
}
