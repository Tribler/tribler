import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { DialogProps } from "@radix-ui/react-dialog";
import { JSX } from "react/jsx-runtime";
import { useTranslation } from "react-i18next";
import { Download } from "@/models/download.model";
import { TFunction } from "i18next";


interface MoveStorageProps {
    selectedDownloads: Download[];
    onRemove: (selectedDownloads: Download[], removeData: boolean, t: TFunction) => void;
}

export default function ConfirmRemove(props: JSX.IntrinsicAttributes & DialogProps & MoveStorageProps) {
    const { t } = useTranslation();

    return (
        <Dialog open={props.open} onOpenChange={props.onOpenChange}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>{t('RemoveDownload')}</DialogTitle>
                    <DialogDescription>
                        {t('RemoveDownloadConfirm', { downloads: props.selectedDownloads.length })}
                    </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                    <Button
                        variant="outline"
                        type="submit"
                        onClick={() => { props.onRemove(props.selectedDownloads, false, t) }}>
                        {t('RemoveDownload')}
                    </Button>
                    <Button
                        variant="outline"
                        type="submit"
                        onClick={() => { props.onRemove(props.selectedDownloads, true, t) }}>
                        {t('RemoveDownloadData')}
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
