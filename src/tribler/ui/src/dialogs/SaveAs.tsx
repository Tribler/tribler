import SimpleTable from "@/components/ui/simple-table";
import { useEffect, useState } from "react";
import toast from 'react-hot-toast';
import { triblerService } from "@/services/tribler.service";
import { isErrorDict } from "@/services/reporting";
import { formatBytes, getFilesFromMetainfo, getRowSelection, translateHeader } from "@/lib/utils";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { DialogProps } from "@radix-ui/react-dialog";
import { JSX } from "react/jsx-runtime";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { ColumnDef } from "@tanstack/react-table";
import { useNavigate } from "react-router-dom";
import { Settings } from "@/models/settings.model";
import { useTranslation } from "react-i18next";
import { TFunction } from 'i18next';
import { PathInput } from "@/components/path-input";


function startDownloadCallback(response: any, t: TFunction) {
    // We have to receive a translation function. Otherwise, we violate React's hook scoping.
    if (response === undefined) {
        toast.error(`${t("ToastErrorDownloadStart")} ${t("ToastErrorGenNetworkErr")}`);
    } else if (isErrorDict(response)){
        toast.error(`${t("ToastErrorDownloadStart")} ${response.error}`);
    }
}

const fileColumns: ColumnDef<TorrentFile>[] = [
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
                onCheckedChange={(value) => row.toggleSelected(!!value)}
                aria-label="Select row"
            />
        ),
        enableSorting: false,
        enableHiding: false,
    },
    {
        accessorKey: "path",
        header: translateHeader('Name'),
    },
    {
        accessorKey: "length",
        header: translateHeader('Size'),
        cell: ({ row }) => {
            return <span className="whitespace-nowrap">{formatBytes(row.original.length)}</span>
        },
    },
]

interface TorrentFile {
    path: string;
    length: number;
    included?: boolean;
}

interface Params {
    destination: string
    anon_hops: number
    selected_files: number[],
    safe_seeding: boolean,
};

interface SaveAsProps {
    uri?: string;
    torrent?: File;
}

export default function SaveAs(props: SaveAsProps & JSX.IntrinsicAttributes & DialogProps) {
    let { uri, torrent } = props;

    const { t } = useTranslation();

    const [settings, setSettings] = useState<Settings | undefined>();
    const [error, setError] = useState<string | undefined>();
    const [exists, setExists] = useState<boolean>(false);
    const [selectedFiles, setSelectedFiles] = useState<TorrentFile[]>([]);
    const [files, setFiles] = useState<TorrentFile[]>([]);
    const [params, setParams] = useState<Params>({
        destination: '',
        anon_hops: 0,
        selected_files: [],
        safe_seeding: false,
    });

    const navigate = useNavigate();

    useEffect(() => {
        async function reload() {
            // Reset state
            setError(undefined);
            setExists(false);
            setFiles([])
            const newSettings = await triblerService.getSettings();
            if (newSettings === undefined) {
                setError(`${t("ToastErrorGetSettings")} ${t("ToastErrorGenNetworkErr")}`);
                return;
            } else if (isErrorDict(newSettings)){
                setError(`${t("ToastErrorGetSettings")} ${newSettings.error}`);
                return;
            }
            const safeSeeding = !!newSettings?.libtorrent?.download_defaults?.safeseeding_enabled;
            const safeDownloading = !!newSettings?.libtorrent?.download_defaults?.anonymity_enabled;
            setSettings(newSettings);
            setParams({
                ...params,
                destination: newSettings?.libtorrent.download_defaults.saveas ?? '',
                anon_hops: safeDownloading ? newSettings.libtorrent.download_defaults.number_hops : 0,
                safe_seeding: safeSeeding,
            });

            // Retrieve metainfo
            let response;
            if (torrent) {
                response = await triblerService.getMetainfoFromFile(torrent);
            }
            else if (uri) {
                response = await triblerService.getMetainfo(uri);
            }

            if (response === undefined) {
                setError(`${t("ToastErrorGetMetainfo")} ${t("ToastErrorGenNetworkErr")}`);
            } else if (isErrorDict(response)) {
                setError(`t("ToastErrorGetMetainfo")} ${response.error}`);
            } else if (response) {
                setFiles(getFilesFromMetainfo(response.metainfo));
                setExists(!!response.download_exists);
            }
        }
        reload();
    }, [uri, torrent]);

    useEffect(() => {
        let indexes = [];
        for (let i = 0; i < selectedFiles.length; i++) {
            for (let j = 0; j < files.length; j++) {
                if (selectedFiles[i].path === files[j].path) {
                    indexes.push(j);
                    break;
                }
            }
        }

        setParams({
            ...params,
            selected_files: indexes,
        })
    }, [selectedFiles]);

    function OnDownloadClicked() {
        if (!settings) return;

        if (torrent) {
            triblerService.startDownloadFromFile(torrent, params).then((response) => {startDownloadCallback(response, t)});
        }
        else if (uri) {
            triblerService.startDownload(uri, params).then((response) => {startDownloadCallback(response, t)});
        }

        if (props.onOpenChange) {
            props.onOpenChange(false)
            navigate("/downloads/all");
        }
    }

    if (props.open && props.onOpenChange && triblerService.guiSettings.ask_download_settings === false) {
        OnDownloadClicked();
        return <></>;
    }

    return (
        <Dialog {...props}>
            <DialogContent className="max-w-5xl">
                <DialogHeader>
                    <DialogTitle>{t('DownloadTorrent')}</DialogTitle>
                    <DialogDescription className="break-all text-xs">
                        {uri ?? torrent?.name ?? ''}
                    </DialogDescription>
                </DialogHeader>

                <div className="flex items-center">
                    <Label htmlFor="dest_dir" className="whitespace-nowrap pr-5">
                        {t('Destination')}
                    </Label>
                    <PathInput
                        path={params.destination || settings?.libtorrent?.download_defaults?.saveas || ''}
                        onPathChange={(path) => setParams({ ...params, destination: path })}
                    />
                </div>

                {error === undefined && files.length > 0 &&
                    <>
                        <SimpleTable
                            data={files}
                            columns={fileColumns}
                            allowSelectCheckbox={true}
                            onSelectedRowsChange={setSelectedFiles}
                            initialRowSelection={getRowSelection(files, () => true)}
                            maxHeight={200} />
                        {exists && <span className="text-center text-tribler text-sm">{t('DownloadExists')}</span>}
                    </>
                }

                {error === undefined && files.length === 0 &&
                    <div className="flex justify-center p-5">
                        {t('LoadingTorrent', { method: params.anon_hops !== 0 ? t('anonymously') : t('directly') })}
                        <svg className="animate-spin -ml-1 mr-3 h-6 w-6 text-black dark:text-white ml-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                    </div>
                }
                {error !== undefined &&
                    <span className="text-center text-tribler text-sm">Error: {error}</span>
                }

                <div className="flex items-center space-x-2 mt-5">
                    <Checkbox
                        checked={params.anon_hops !== 0}
                        onCheckedChange={(value) => {
                            setParams({
                                ...params,
                                anon_hops: (params.anon_hops !== 0) ? 0 : settings?.libtorrent.download_defaults.number_hops ?? 1,
                                safe_seeding: (value) ? true : params.safe_seeding
                            });
                        }}
                        id="download_anonymous" />
                    <label
                        htmlFor="download_anonymous"
                        className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                    >
                        {t('DownloadAnon')}
                    </label>
                </div>
                <div className="flex items-center space-x-2">
                    <Checkbox
                        checked={params.safe_seeding}
                        onCheckedChange={(value) => setParams({ ...params, safe_seeding: !!value })}
                        disabled={params.anon_hops !== 0}
                        id="seed_anonymous" />
                    <label
                        htmlFor="seed_anonymous"
                        className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                    >
                        {t('SeedAnon')}
                    </label>
                </div>
                <DialogFooter>
                    <Button
                        variant="outline"
                        type="submit"
                        onClick={() => OnDownloadClicked()}
                        disabled={exists || (files.length !== 0 && selectedFiles.length === 0)}>
                        {t('Download')}
                    </Button>
                    <DialogClose asChild>
                        <Button variant="outline" type="button">
                            {t('Cancel')}
                        </Button>
                    </DialogClose>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
