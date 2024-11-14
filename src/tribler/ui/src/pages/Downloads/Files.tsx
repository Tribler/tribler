import toast from 'react-hot-toast';
import { ColumnDef, Row } from "@tanstack/react-table";
import { FileTreeItem } from "@/models/file.model";
import { Download } from "@/models/download.model";
import { Dispatch, MutableRefObject, SetStateAction, useEffect, useMemo, useRef, useState } from "react";
import { isErrorDict } from "@/services/reporting";
import { triblerService } from "@/services/tribler.service";
import SimpleTable, { getHeader } from "@/components/ui/simple-table";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { filesToTree, formatBytes, getSelectedFilesFromTree } from "@/lib/utils";
import { useTranslation } from "react-i18next";

const getFileColumns = ({ onSelectedFiles }: { onSelectedFiles: (row: Row<FileTreeItem>) => void }): ColumnDef<FileTreeItem>[] => [
    {
        header: getHeader("Path"),
        accessorKey: "path",
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
                    <span className="break-all line-clamp-1">{row.original.name}</span>
                </div>
            )
        }
    },
    {
        header: getHeader("Size"),
        accessorKey: "size",
        cell: ({ row }) => {
            return (
                <div className='flex items-center'>
                    <Checkbox className='mr-2' checked={row.original.included} onCheckedChange={() => onSelectedFiles(row)}></Checkbox>
                    <span>{formatBytes(row.original.size)}</span>
                </div>
            )
        },
    },
    {
        header: getHeader("Progress"),
        accessorKey: "progress",
        cell: ({ row }) => {
            return <span>{((row.original.progress || 0) * 100).toFixed(1)}%</span>
        },
    },
];

async function updateFiles(setFiles: Dispatch<SetStateAction<FileTreeItem[]>>, download: Download, initialized: MutableRefObject<boolean>) {
    const response = await triblerService.getDownloadFiles(download.infohash);
    if (response !== undefined && !isErrorDict(response)) {
        const files = filesToTree(response, download.name, '/');
        setFiles(files);
    } else {
        // Don't bother the user on error, just try again later.
        initialized.current = false;
    }
}

export default function Files({ download }: { download: Download }) {
    const { t } = useTranslation();
    const [files, setFiles] = useState<FileTreeItem[]>([]);
    const initialized = useRef(false)

    function OnSelectedFilesChange(row: Row<FileTreeItem>) {
        // Are we including or excluding files?
        const shouldInclude = row.original.included == false;
        // Get all indices that need toggling
        const toggleIndices = getSelectedFilesFromTree(row.original, !shouldInclude);
        const currentIndcices = getSelectedFilesFromTree(files[0]);
        if (shouldInclude)
            var selectedIndices = [...new Set(currentIndcices).union(new Set(toggleIndices))];
        else
            var selectedIndices = [...new Set(currentIndcices).difference(new Set(toggleIndices))];

        triblerService.setDownloadFiles(download.infohash, selectedIndices).then((response) => {
            if (response === undefined) {
                toast.error(`${t("ToastErrorDownloadSetFiles")} ${t("ToastErrorGenNetworkErr")}`);
            } else if (isErrorDict(response)) {
                toast.error(`${t("ToastErrorDownloadSetFiles")} ${response.error.message}`);
            }
        });
        updateFiles(setFiles, download, initialized);
    }

    useEffect(() => {
        // Getting the files can take a lot of time, so we avoid doing this twice (due to StrictMode).
        if (initialized.current) {
            return;
        }
        initialized.current = true;
        updateFiles(setFiles, download, initialized);
    }, []);

    useEffect(() => {
        if (download.status_code === 3)
            updateFiles(setFiles, download, initialized);
    }, [download]);

    const fileColumns = useMemo(() => getFileColumns({ onSelectedFiles: OnSelectedFilesChange }), [OnSelectedFilesChange]);

    // The API call may not be finished yet or the download is still getting metainfo.
    if (files.length === 0)
        return <span className="flex pl-4 pt-2 text-muted-foreground">No files available</span>;

    return <SimpleTable
        data={files}
        columns={fileColumns}
        expandable={true}
        pageSize={50}
        maxHeight={'none'}
    />
}
