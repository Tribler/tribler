import type {TFunction} from "i18next";
import {capitalize} from "@/lib/utils";
import {Status} from "@/models/download.model";

export function downloadStatusLabel(status: Status, t: TFunction): string {
    return t(`DownloadStatus_${status}`, {defaultValue: capitalize(status.replaceAll("_", " "))});
}
