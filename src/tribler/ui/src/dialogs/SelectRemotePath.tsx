import { useEffect, useState } from "react";
import toast from 'react-hot-toast';
import { triblerService } from "@/services/tribler.service";
import { isErrorDict } from "@/services/reporting";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { DialogProps } from "@radix-ui/react-dialog";
import { JSX } from "react/jsx-runtime";
import { useTranslation } from "react-i18next";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Folder, File as FileIcon } from "lucide-react";
import { Path } from "@/models/path.model";


interface SelectRemotePathProps {
    initialPath: string,
    selectDir: boolean,
    showFiles?: boolean;
    onSelect: (selected: string, dir: boolean) => void;
}

export default function SelectRemotePath(props: SelectRemotePathProps & JSX.IntrinsicAttributes & DialogProps) {
    let { initialPath, selectDir, showFiles } = props;

    if (showFiles === undefined) {
        showFiles = !selectDir;
    }

    const [paths, setPaths] = useState<Path[]>([]);
    const [currentPath, setCurrentPath] = useState<string>(initialPath);
    const [lastClicked, setLastClicked] = useState<Path | undefined>();

    const { t } = useTranslation();

    useEffect(() => {
        if (props.open)
            reloadPaths(initialPath);
    }, [initialPath, showFiles, props.open]);

    async function reloadPaths(dir: string) {
        const response = await triblerService.browseFiles(dir, showFiles || false);
        if (response === undefined) {
            toast.error(`${t("ToastErrorBrowseFiles")} ${t("ToastErrorGenNetworkErr")}`);
        } else if (isErrorDict(response)){
            toast.error(`${t("ToastErrorBrowseFiles")} ${response.error}`);
        } else {
            setPaths(response.paths);
            setCurrentPath(response.current);
            setLastClicked((selectDir) ? { name: '', path: response.current, dir: true } : undefined);
        }
    }

    return (
        <Dialog {...props}>
            <DialogContent className="max-w-3xl">
                <DialogHeader>
                    <DialogTitle>Please select a {selectDir ? 'directory' : 'file'}</DialogTitle>
                    <DialogDescription className="text-base">{currentPath || initialPath}</DialogDescription>
                </DialogHeader>

                <ScrollArea className="max-h-[380px] border">
                    <div className="flex-col">
                        {paths.map((item, index) => (
                            <div
                                className="p-2 shadow hover:bg-accent border border-input flex"
                                key={index}
                                onClick={(event) => {
                                    if (item.dir)
                                        reloadPaths(item.path)
                                    setLastClicked(item);
                                }}
                            >
                                {item.dir && <Folder className="pr-2" />}
                                {!item.dir && <FileIcon className="pr-2" />}
                                {item.name}
                            </div>
                        ))}
                    </div>
                </ScrollArea>

                <DialogFooter className="items-baseline">
                    {!selectDir && <p className="grow text-base">{lastClicked?.path || initialPath}</p>}
                    <Button
                        variant="outline"
                        type="submit"
                        onClick={() => {
                            if (props.onOpenChange)
                                props.onOpenChange(false);
                            if (lastClicked)
                                props.onSelect(lastClicked.path, lastClicked?.dir === true);
                        }}
                        disabled={!lastClicked || lastClicked.dir != selectDir}>
                        Accept
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
