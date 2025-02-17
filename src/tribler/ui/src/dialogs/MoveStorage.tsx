import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { DialogProps } from "@radix-ui/react-dialog";
import { JSX } from "react/jsx-runtime";
import { Label } from "@/components/ui/label";
import { useTranslation } from "react-i18next";
import { PathInput } from "@/components/path-input";
import { useEffect, useState } from "react";
import { Download } from "@/models/download.model";
import { TFunction } from "i18next";


interface MoveStorageProps {
    selectedDownloads: Download[];
    onMove: (selectedDownloads: Download[], storageLocation: string, t: TFunction) => void;
}

export default function MoveStorage(props: JSX.IntrinsicAttributes & DialogProps & MoveStorageProps) {
    const { t } = useTranslation();
    const [storageLocation, setStorageLocation] = useState("");

    useEffect(() => {
        if (props.open) {
            setStorageLocation(props.selectedDownloads[0]?.destination || "");
        }
    }, [props.open]);

    return (
        <Dialog open={props.open} onOpenChange={props.onOpenChange}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>{t('ChangeStorage')}</DialogTitle>
                    <DialogDescription>
                        {t('ChangeStorageDescription')}
                    </DialogDescription>
                </DialogHeader>
                <div className="grid gap-6 py-4">
                    <div className="grid grid-cols-6 items-center gap-4">
                        <Label htmlFor="dest_dir" className="text-right">
                            {t('ChangeStorageLocation')}
                        </Label>
                        <PathInput
                            className="col-span-5"
                            path={storageLocation}
                            onPathChange={(path) => setStorageLocation(path)}
                        />
                    </div>
                </div>
                <DialogFooter>
                    <Button
                        variant="outline"
                        type="submit"
                        disabled={props.selectedDownloads.every((d) => d.destination === storageLocation)}
                        onClick={() => {
                            props.onMove(props.selectedDownloads, storageLocation, t);
                            props.onOpenChange?.(false);
                        }}>
                        {t('ChangeStorageButton')}
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
