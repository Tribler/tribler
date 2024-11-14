import { useEffect, useRef, useState } from 'react';
import toast from 'react-hot-toast';
import { ipv8Service } from '@/services/ipv8.service';
import { isErrorDict } from "@/services/reporting";
import { Drift } from "@/models/drift.model";
import { average, median } from '@/lib/utils';
import { useInterval } from '@/hooks/useInterval';
import { useTranslation } from "react-i18next";


export default function Health() {
    const [drifts, setDrifts] = useState<Drift[]>([]);
    const ref = useRef<HTMLCanvasElement>(null);
    const { t } = useTranslation();

    useInterval(async () => {
        let measurements = await ipv8Service.getDrift();

        if (!(measurements === undefined) && !isErrorDict(measurements)) {
            // We ignore errors and correct with the missing information on the next call
            const now = new Date().getTime() / 1000;
            setDrifts(measurements.filter((drift: Drift) => drift.timestamp > now - 11.0));

            updateCanvas();
        }
    }, 250, true);

    useEffect(() => {
        (async () => {
            const response = await ipv8Service.enableDrift(true);
            if (response === undefined) {
                toast.error(`${t("ToastErrorEnableHealth")} ${t("ToastErrorGenNetworkErr")}`);
            } else if (isErrorDict(response)){
                toast.error(`${t("ToastErrorEnableHealth")} ${response.error.message}`);
            }
        })();
        return () => {
            (async () => {
                const response = await ipv8Service.enableDrift(false);
                if (response === undefined) {
                    toast.error(`${t("ToastErrorDisableHealth")} ${t("ToastErrorGenNetworkErr")}`);
                } else if (isErrorDict(response)){
                    toast.error(`${t("ToastErrorDisableHealth")} ${response.error.message}`);
                }
            })();
        }
    }, []);

    const updateCanvas = () => {
        if (ref.current) {
            const canvas = ref.current.getContext('2d')
            if (!canvas) return;

            ref.current.style.width = "100%";
            ref.current.style.height = "300px";
            ref.current.width = ref.current.offsetWidth;
            ref.current.height = ref.current.offsetHeight;

            // Get size from the HTML canvas element
            const width = canvas.canvas.width;
            const height = canvas.canvas.height;
            canvas.clearRect(0, 0, width, height);

            // Draw the baseline frequency bands (a perfect score of 0.0 drift).
            const midy = Math.round((height - 1) / 2);
            drawLine(canvas, "gray", 0, midy + 40, width - 1, midy + 40);
            drawLine(canvas, "gray", 0, midy - 50, width - 1, midy - 50);

            // Draw the centerline.
            drawLine(canvas, "#84D684", 0, midy, width - 1, midy);

            // Calculate the required scaling.
            const current_time = new Date().getTime() / 1000;
            const time_window = 10.0;
            const x_time_start = current_time - time_window;
            const boop_px = 60;
            const boop_secs = 0.25;
            const boop_xscale = width / boop_px / time_window * boop_secs;

            drifts.forEach((drift) => {
                const x = Math.round((drift.timestamp - x_time_start) / time_window * width);
                drawBoop(canvas, x, boop_xscale, 1 + drift.drift * 10);
            });
        }
    }

    const drawLine = (ctx: CanvasRenderingContext2D, strokeStyle: string, x1: number, y1: number, x2: number, y2: number) => {
        ctx.strokeStyle = strokeStyle;
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
    }

    const drawBoop = (ctx: CanvasRenderingContext2D, x: number, xscale: number, yscale: number) => {
        const midy = Math.round((ctx.canvas.height - 1) / 2);

        // Erase the centerline on the area we will be drawing.
        ctx.clearRect(x, midy - 1, Math.round(60 * xscale), 2);


        // The boop shape.
        drawLine(ctx, "#84D684", x, midy, x + Math.round(5 * xscale), midy - Math.round(10 * yscale));
        drawLine(ctx, "#84D684", x + Math.round(5 * xscale), midy - Math.round(10 * yscale), x + Math.round(10 * xscale), midy);
        drawLine(ctx, "#84D684", x + Math.round(10 * xscale), midy, x + Math.round(15 * xscale), midy);
        drawLine(ctx, "#84D684", x + Math.round(15 * xscale), midy, x + Math.round(20 * xscale), midy + Math.round(10 * yscale));
        drawLine(ctx, "#84D684", x + Math.round(20 * xscale), midy + Math.round(10 * yscale), x + Math.round(30 * xscale), midy - Math.round(50 * yscale));
        drawLine(ctx, "#84D684", x + Math.round(30 * xscale), midy - Math.round(50 * yscale), x + Math.round(50 * xscale), midy + Math.round(40 * yscale));
        drawLine(ctx, "#84D684", x + Math.round(50 * xscale), midy + Math.round(40 * yscale), x + Math.round(60 * xscale), midy);
    }

    const target = (drifts.length >= 2) ? (drifts[drifts.length - 1].timestamp
        - drifts[drifts.length - 2].timestamp
        - drifts[drifts.length - 1].drift).toFixed(2) : 'N/A';

    return (
        <div className="flex flex-col h-full p-4 text-sm">
            <div className="flex flex-row">
                <div className="basis-20">Target:</div>
                <div>{target}</div>
            </div>
            <div className="flex flex-row">
                <div className="basis-20">Mean:</div>
                <div>{(drifts.length !== 0) ? '+' + average(drifts.map((drift) => drift.drift)).toFixed(2) : 'N/A'}</div>
            </div>
            <div className="flex flex-row">
                <div className="basis-20">Median:</div>
                <div>{(drifts.length !== 0) ? '+' + median(drifts.map((drift) => drift.drift)).toFixed(2) : 'N/A'}</div>
            </div>
            <canvas ref={ref} />
        </div>
    )
}