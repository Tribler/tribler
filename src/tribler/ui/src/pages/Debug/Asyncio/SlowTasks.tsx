import { useEffect, useState } from "react";
import { ipv8Service } from "@/services/ipv8.service";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { useInterval } from '@/hooks/useInterval';
import { ScrollArea } from "@/components/ui/scroll-area";


export default function SlowTasks() {
    const [debug, setDebug] = useState<{ messages?: { message: string }[] }>({})
    const [slownessThreshold, setSlownessThreshold] = useState<number>(0.1)

    useInterval(async () => {
        setDebug(await ipv8Service.getAsyncioDebug());
    }, 5000, true);

    useEffect(() => {
        (async () => { await ipv8Service.setAsyncioDebug(true, slownessThreshold) })();
        return () => {
            (async () => { await ipv8Service.setAsyncioDebug(false, slownessThreshold) })();
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
                        onClick={() => ipv8Service.setAsyncioDebug(true, slownessThreshold)}
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
