import { useEffect, useState } from "react";
import toast from 'react-hot-toast';
import { useTranslation } from "react-i18next";
import { ipv8Service } from "@/services/ipv8.service";
import { isErrorDict } from "@/services/reporting";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { useInterval } from '@/hooks/useInterval';
import { ScrollArea } from "@/components/ui/scroll-area";


export default function SlowTasks() {
    const { t } = useTranslation();
    const [debug, setDebug] = useState<{ messages?: { message: string }[] }>({})
    const [slownessThreshold, setSlownessThreshold] = useState<number>(0.1)

    useInterval(async () => {
        const response = await ipv8Service.getAsyncioDebug();
        if (!(response === undefined) && !isErrorDict(response)) {
            // We ignore errors and correct with the missing information on the next call
            setDebug(response);
        }
    }, 5000, true);

    useEffect(() => {
        (async () => {
            const response = await ipv8Service.setAsyncioDebug(true, slownessThreshold);
            if (response === undefined) {
                toast.error(`${t("ToastErrorEnableAsyncio")} ${t("ToastErrorGenNetworkErr")}`);
            } else if (isErrorDict(response)){
                toast.error(`${t("ToastErrorEnableAsyncio")} ${response.error.message}`);
            }
        })();
        return () => {
            (async () => {
                const response = await ipv8Service.setAsyncioDebug(false, slownessThreshold);
                if (response === undefined) {
                    toast.error(`${t("ToastErrorDisableAsyncio")} ${t("ToastErrorGenNetworkErr")}`);
                } else if (isErrorDict(response)){
                    toast.error(`${t("ToastErrorDisableAsyncio")} ${response.error.message}`);
                }
            })();
        }
    }, []);

    return (
        <div className="flex" style={{ height: 'calc(100vh - 100px)' }}>
            <ScrollArea>
                <div className="p-4 pb-0 grid grid-cols-3 gap-2 items-center w-fit">
                    <Label htmlFor="slowness" className="whitespace-nowrap pr-5">
                        Slowness threshold (s)
                    </Label>
                    <Input
                        id="slowness"
                        type="number"
                        step={0.01}
                        value={slownessThreshold}
                        onChange={(event) => setSlownessThreshold(+event.target.value)}
                    />
                    <Button
                        variant="outline"
                        className="h-8 w-8 p-0"
                        onClick={() => {
                            ipv8Service.setAsyncioDebug(true, slownessThreshold).then((response) => {
                                if (response === undefined) {
                                    toast.error(`${t("ToastErrorSlowness")} ${t("ToastErrorGenNetworkErr")}`);
                                } else if (isErrorDict(response)){
                                    toast.error(`${t("ToastErrorSlowness")} ${response.error.message}`);
                                }
                            });
                        }}
                    >
                        OK
                    </Button>
                </div>
                {debug.messages && debug.messages.map((msg, index) => (
                    <Card className="m-4">
                        <CardContent className="p-4">
                            <span key={index} className="line-clamp-2 text-xs font-mono">{msg.message}</span>
                        </CardContent>
                    </Card>
                ))}
            </ScrollArea>
        </div>
    )
}
