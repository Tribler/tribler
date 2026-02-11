import SimpleTable, {getHeader} from "@/components/ui/simple-table";
import {useEffect, useMemo, useState} from "react";
import toast from "react-hot-toast";
import {triblerService} from "@/services/tribler.service";
import {isErrorDict} from "@/services/reporting";
import {filesToTree, fixTreeProps, formatBytes, getSelectedFilesFromTree, unwrapMagnetSO} from "@/lib/utils";
import {
    Dialog,
    DialogClose,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import {Button} from "@/components/ui/button";
import {DialogProps} from "@radix-ui/react-dialog";
import {JSX} from "react/jsx-runtime";
import {Checkbox} from "@/components/ui/checkbox";
import {Label} from "@/components/ui/label";
import {Slider} from "@/components/ui/slider";
import {ColumnDef, Row} from "@tanstack/react-table";
import {useNavigate} from "react-router-dom";
import {Settings} from "@/models/settings.model";
import {DirspaceStatistics} from "@/models/statistics.model";
import {useTranslation} from "react-i18next";
import {TFunction} from "i18next";
import {PathInput} from "@/components/path-input";
import {ChevronDown, ChevronRight, AlertTriangle} from "lucide-react";
import {FileTreeItem} from "@/models/file.model";
import {DownloadConfig} from "@/models/downloadconfig.model";
import {Icons} from "@/components/icons";
import {EasyTooltip} from "@/components/ui/tooltip";

function startDownloadCallback(response: any, t: TFunction) {
    // We have to receive a translation function. Otherwise, we violate React's hook scoping.
    if (response === undefined) {
        toast.error(`${t("ToastErrorDownloadStart")} ${t("ToastErrorGenNetworkErr")}`);
    } else if (isErrorDict(response)) {
        toast.error(`${t("ToastErrorDownloadStart")} ${response.error.message}`);
    }
}

const getFileColumns = ({
    onSelectedFiles,
}: {
    onSelectedFiles: (row: Row<FileTreeItem>) => void;
}): ColumnDef<FileTreeItem>[] => [
    {
        accessorKey: "name",
        header: getHeader("Name", true, true, true),
        filterFn: (row, columnId, filterValue) => {
            return row.original.name.includes(filterValue);
        },
        cell: ({row}) => {
            return (
                <div
                    className="flex text-start items-center"
                    style={{
                        paddingLeft: `${row.depth * 2}rem`,
                    }}>
                    {row.original.subRows && row.original.subRows.length > 0 && (
                        <button onClick={row.getToggleExpandedHandler()}>
                            {row.getIsExpanded() ? (
                                <ChevronDown size="16" color="#777"></ChevronDown>
                            ) : (
                                <ChevronRight size="16" color="#777"></ChevronRight>
                            )}
                        </button>
                    )}
                    <span className="break-all line-clamp-1">{row.original.name}</span>
                </div>
            );
        },
    },
    {
        accessorKey: "size",
        header: getHeader("Size"),
        cell: ({row}) => {
            return (
                <div className="flex items-center">
                    <Checkbox
                        className="mr-2"
                        checked={row.original.included}
                        onCheckedChange={() => onSelectedFiles(row)}></Checkbox>
                    <span>{formatBytes(row.original.size)}</span>
                </div>
            );
        },
    },
];

interface SaveAsProps {
    uri?: string;
    torrent?: File;
}

const toggleTree = (tree: FileTreeItem, included: boolean = true) => {
    if (tree.subRows && tree.subRows.length) {
        for (const item of tree.subRows) {
            toggleTree(item, included);
        }
    }
    tree.included = included;
};

export default function SaveAs(props: SaveAsProps & JSX.IntrinsicAttributes & DialogProps) {
    let {uri, torrent} = props;

    const {t} = useTranslation();

    const [settings, setSettings] = useState<Settings | undefined>();
    const [moveCompleted, setMoveCompleted] = useState<boolean>(false);
    const [error, setError] = useState<string | undefined>();
    const [warning, setWarning] = useState<string | undefined>();
    const [exists, setExists] = useState<boolean>(false);
    const [description, setDescription] = useState<string>("");
    const [files, setFiles] = useState<FileTreeItem[]>([]);
    const [torrentSize, setTorrentSize] = useState<number>(0);
    const [dirspaceStatistics, setDirspaceStatistics] = useState<DirspaceStatistics | undefined>(undefined);

    function OnSelectedFilesChange(row: Row<FileTreeItem>) {
        toggleTree(row.original, !row.original.included);
        fixTreeProps(files[0]);
        setFiles([...files]);
        setParams({
            ...params,
            selected_files: getSelectedFilesFromTree(files[0]),
        });
    }

    const fileColumns = useMemo(
        () => getFileColumns({onSelectedFiles: OnSelectedFilesChange}),
        [OnSelectedFilesChange]
    );
    const [params, setParams] = useState<DownloadConfig>({
        destination: "",
        anon_hops: 0,
        selected_files: undefined,
        safe_seeding: false,
        auto_managed: undefined,
    });

    useEffect(() => {
        if (params.selected_files !== undefined) {
            let total = 0;
            let remaining = [files[0]];
            while (remaining.length > 0) {
                let f = remaining.shift();
                if (f === undefined) continue;
                if (params.selected_files.indexOf(f.index) > -1) total += f.size;
                if (f.subRows !== undefined) remaining = remaining.concat(f.subRows);
            }
            setTorrentSize(total);
        }
        if (params.destination !== undefined)
            triblerService.getDirspaceStatistics(params.destination).then((response) => {
                if (response !== undefined && !isErrorDict(response)) {
                    setDirspaceStatistics(response);
                } else {
                    setDirspaceStatistics(undefined);
                }
            });
    }, [params]);

    const navigate = useNavigate();

    useEffect(() => {
        const controller = new AbortController();

        async function reload() {
            // Reset state
            setMoveCompleted(false);
            setError(undefined);
            setExists(false);
            setFiles([]);
            const newSettings = await triblerService.getSettings();
            if (newSettings === undefined) {
                setError(`${t("ToastErrorGetSettings")} ${t("ToastErrorGenNetworkErr")}`);
                return;
            } else if (isErrorDict(newSettings)) {
                setError(`${t("ToastErrorGetSettings")} ${newSettings.error.message}`);
                return;
            }
            const safeSeeding = !!newSettings?.libtorrent?.download_defaults?.safeseeding_enabled;
            const safeDownloading = !!newSettings?.libtorrent?.download_defaults?.anonymity_enabled;
            setSettings(newSettings);
            setParams((prev) => ({
                ...prev,
                destination: newSettings?.libtorrent.download_defaults.saveas ?? "",
                completed_dir: newSettings?.libtorrent.download_defaults.completed_dir ?? "",
                anon_hops: safeDownloading ? newSettings.libtorrent.download_defaults.number_hops : 0,
                safe_seeding: safeSeeding,
                selected_files: undefined,
                auto_managed: newSettings?.libtorrent.download_defaults.auto_managed === true,
            }));
            setMoveCompleted((newSettings?.libtorrent?.download_defaults.completed_dir ?? "").length > 0);

            // Retrieve metainfo
            let response;
            let magnet_selected_files = null;
            if (torrent) {
                response = await triblerService.getMetainfoFromFile(torrent);
            } else if (uri) {
                response = await triblerService.getMetainfo(uri, false, {signal: controller.signal});
                magnet_selected_files = new URLSearchParams(uri).get("so");
            }

            if (controller.signal.aborted) return;

            if (response === undefined) {
                setError(`${t("ToastErrorGetMetainfo")} ${t("ToastErrorGenNetworkErr")}`);
            } else if (isErrorDict(response)) {
                setError(`${t("ToastErrorGetMetainfo")} ${response.error.message}`);
            } else if (response) {
                var files = response.files;
                files.sort((f1: any, f2: any) => (f1.name > f2.name ? 1 : -1));
                files = filesToTree(
                    files,
                    response.name,
                    magnet_selected_files === null ? new Set() : unwrapMagnetSO(magnet_selected_files)
                );
                setFiles(files);
                setParams((prev) => ({...prev, selected_files: getSelectedFilesFromTree(files[0])}));
                setExists(!!response.download_exists);
                setDescription(response.description);
                setWarning(
                    !("valid_certificate" in response) || response.valid_certificate == true
                        ? undefined
                        : t("HTTPSCertificateInvalid")
                );
            }
        }
        reload();

        return () => {
            controller.abort();
        };
    }, [uri, torrent]);

    function OnDownloadClicked() {
        if (!settings) return;

        const completed_dir = moveCompleted ? params.completed_dir : "";

        if (torrent) {
            triblerService.startDownloadFromFile(torrent, {...params, completed_dir}).then((response) => {
                startDownloadCallback(response, t);
            });
        } else if (uri) {
            triblerService.startDownload(uri, {...params, completed_dir}).then((response) => {
                startDownloadCallback(response, t);
            });
        }

        if (props.onOpenChange) {
            props.onOpenChange(false);
            navigate("/downloads/all");
        }
    }

    if (props.open && props.onOpenChange && settings?.libtorrent?.ask_download_settings === false) {
        OnDownloadClicked();
        return <></>;
    }

    return (
        <Dialog {...props}>
            <DialogContent className="max-w-5xl">
                <DialogHeader>
                    <DialogTitle>{t("DownloadTorrent")}</DialogTitle>
                    <DialogDescription className="break-all text-xs">{uri ?? torrent?.name ?? ""}</DialogDescription>
                </DialogHeader>

                <div className="flex flex-cols-[theme(spacing.64)_1fr] flex-rows-2 mt-2">
                    {description && (
                        <>
                            <Label htmlFor="dest_dir" className="whitespace-nowrap mr-5">
                                {t("Description")}
                            </Label>
                            <div className="text-sm">{description}</div>
                        </>
                    )}
                </div>
                <div className="flex flex-cols-[theme(spacing.64)_1fr] flex-rows-2 mt-2">
                    <div className="flex flex-cols-2 items-center flex-rows-1 whitespace-nowrap mr-5">
                        <Label className="align-middle" htmlFor="dest_dir">
                            {t("Destination")}
                        </Label>
                        <div className="ml-2" hidden={files.length == 0 || dirspaceStatistics === undefined}>
                            {dirspaceStatistics === undefined ? (
                                <Label />
                            ) : torrentSize > dirspaceStatistics.free ? (
                                <EasyTooltip content={t("DestinationFull")}>
                                    <Icons.redcross />
                                </EasyTooltip>
                            ) : (
                                <EasyTooltip
                                    content={`(${formatBytes(torrentSize)}+${formatBytes(dirspaceStatistics.used)})/${formatBytes(dirspaceStatistics.total)}`}>
                                    <Icons.diskusage
                                        disktotal={dirspaceStatistics.total}
                                        diskused={dirspaceStatistics.used}
                                        torrentsize={torrentSize}
                                    />
                                </EasyTooltip>
                            )}
                        </div>
                    </div>
                    <PathInput
                        path={params.destination || settings?.libtorrent?.download_defaults?.saveas || ""}
                        onPathChange={(path) => setParams({...params, destination: path})}
                    />
                </div>

                <div className="flex items-center">
                    <div className="w-64 flex items-center">
                        <Checkbox
                            checked={moveCompleted}
                            id="move_completed"
                            onCheckedChange={(value) => setMoveCompleted(value === true)}
                        />
                        <label
                            htmlFor="move_completed"
                            className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 whitespace-nowrap pl-2">
                            {t("MoveAfterCompletion")}
                        </label>
                    </div>
                    <PathInput
                        disabled={!moveCompleted}
                        path={params.completed_dir || ""}
                        onPathChange={(path) => setParams({...params, completed_dir: path})}
                    />
                </div>

                {error === undefined && files.length > 0 && (
                    <>
                        <SimpleTable
                            data={files}
                            columns={fileColumns}
                            allowSelectCheckbox={true}
                            expandable={true}
                            style={{maxHeight: 200}}
                        />
                        {exists && <span className="text-center text-tribler text-sm">{t("DownloadExists")}</span>}
                    </>
                )}

                {error === undefined && files.length === 0 && (
                    <div className="flex justify-center p-5">
                        {t("LoadingTorrent", {method: params.anon_hops !== 0 ? t("anonymously") : t("directly")})}
                        <Icons.spinner className="h-6 w-6 mx-3" />
                    </div>
                )}
                {error !== undefined && <span className="text-center text-tribler text-sm">Error: {error}</span>}

                <div className="flex items-center space-x-2 mt-5">
                    <Checkbox
                        checked={params.auto_managed || false}
                        id="auto_managed"
                        onCheckedChange={(value) => setParams({...params, auto_managed: !!value})}
                    />
                    <label
                        htmlFor="auto_managed"
                        className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                        {t("AutoManageEnable")}
                    </label>
                </div>
                <div className="flex items-center space-x-2">
                    <Checkbox
                        checked={params.anon_hops !== 0}
                        onCheckedChange={(value) => {
                            setParams({
                                ...params,
                                anon_hops:
                                    params.anon_hops !== 0
                                        ? 0
                                        : (settings?.libtorrent.download_defaults.number_hops ?? 1),
                                safe_seeding: value ? true : params.safe_seeding,
                            });
                        }}
                        id="download_anonymous"
                    />
                    <label
                        htmlFor="download_anonymous"
                        className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                        {t("DownloadAnon")}
                    </label>
                    <div className="grow" />
                    <div className="relative items-enter mb-3">
                        <Slider
                            className="w-64"
                            value={[params.anon_hops === undefined ? 0 : params.anon_hops]}
                            min={0}
                            max={3}
                            step={1}
                            onValueChange={(value) => {
                                setParams({...params, anon_hops: value[0]});
                            }}
                        />
                        <label className="absolute left-0 text-xs">
                            {params.anon_hops == 0
                                ? ""
                                : params.anon_hops == 1
                                  ? t("OneHop")
                                  : params.anon_hops == 2
                                    ? t("TwoHops")
                                    : t("ThreeHops")}
                        </label>
                    </div>
                </div>
                <div className="flex items-center space-x-2">
                    <Checkbox
                        checked={params.safe_seeding}
                        onCheckedChange={(value) => setParams({...params, safe_seeding: !!value})}
                        disabled={params.anon_hops !== 0}
                        id="seed_anonymous"
                    />
                    <label
                        htmlFor="seed_anonymous"
                        className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                        {t("SeedAnon")}
                    </label>
                </div>
                <div className="flex items-center space-x-2">
                    <Checkbox
                        checked={params.only_metadata}
                        hidden={files.length !== 0}
                        onCheckedChange={(value) => setParams({...params, only_metadata: !!value})}
                        id="only_metadata"
                    />
                    <label
                        htmlFor="only_metadata"
                        hidden={files.length !== 0}
                        className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                        {t("StopAfterMetadata")}
                    </label>
                </div>
                <DialogFooter>
                    {warning && (
                        <div className="flex flex-row text-muted-foreground space-x-2">
                            <AlertTriangle className="self-center" />
                            <label className="whitespace-pre-line text-xs self-center">{warning}</label>
                        </div>
                    )}
                    <Button variant="outline" type="submit" onClick={() => OnDownloadClicked()} disabled={exists}>
                        {t("Download")}
                    </Button>
                    <DialogClose asChild>
                        <Button variant="outline" type="button">
                            {t("Cancel")}
                        </Button>
                    </DialogClose>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
