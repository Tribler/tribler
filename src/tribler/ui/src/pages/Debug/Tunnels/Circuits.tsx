import SimpleTable, { getHeader } from "@/components/ui/simple-table";
import { useEffect, useState } from "react";
import { ipv8Service } from "@/services/ipv8.service";
import { isErrorDict } from "@/services/reporting";
import { Circuit } from "@/models/circuit.model";
import { ColumnDef } from "@tanstack/react-table";
import { formatBytes, formatFlags, formatTimeRelativeISO } from "@/lib/utils";
import { useInterval } from '@/hooks/useInterval';
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable";
import { useResizeObserver } from "@/hooks/useResizeObserver";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, YAxis } from "recharts";
import { Button } from "@/components/ui/button";
import { usePrevious } from "@/hooks/usePrevious";


const circuitColumns: ColumnDef<Circuit>[] = [
    {
        accessorKey: "circuit_id",
        header: getHeader("Circuit ID", false),
    },
    {
        accessorKey: "actual_hops",
        header: getHeader("Hops", false),
        cell: ({ row }) => {
            return <span>{row.original.actual_hops} / {row.original.goal_hops}</span>
        },
    },
    {
        accessorKey: "type",
        header: getHeader("Type", false),
    },
    {
        accessorKey: "state",
        header: getHeader("State", false),
    },
    {
        accessorKey: "bytes_up",
        header: getHeader("Up", false),
        cell: ({ row }) => {
            return <span>{formatBytes(row.original.bytes_up)}</span>
        },
    },
    {
        accessorKey: "bytes_down",
        header: getHeader("Down", false),
        cell: ({ row }) => {
            return <span>{formatBytes(row.original.bytes_down)}</span>
        },
    },
    {
        accessorKey: "uptime",
        header: getHeader("Uptime", false),
        cell: ({ row }) => {
            return <span>{formatTimeRelativeISO(row.original.creation_time)}</span>
        },
    },
    {
        accessorKey: "exit_flags",
        header: getHeader("Exit flags", false),
        cell: ({ row }) => {
            return <span>{formatFlags(row.original.exit_flags)}</span>
        },
    },
]

export default function Circuits() {
    const [circuits, setCircuits] = useState<Circuit[]>([])
    const [selectedCircuit, setSelectedCircuit] = useState<Circuit | undefined>()
    const prevSelectedCircuit = usePrevious(selectedCircuit);
    const [speeds, setSpeeds] = useState<{ speed: any; }[]>([]);

    useInterval(async () => {
        const response = await ipv8Service.getCircuits();
        if (!(response === undefined) && !isErrorDict(response)) {
            // We ignore errors and correct with the missing information on the next call
            setCircuits(response);
        }
    }, 5000, true);

    useEffect(() => {
        if (selectedCircuit?.circuit_id != prevSelectedCircuit?.circuit_id) {
            setSpeeds([]);
        }
    }, [selectedCircuit])

    // We're not getting resize event for elements within ResizeablePanel, so we track the ResizablePanel itself.
    const parentRect = useResizeObserver({ element: document.querySelector('#circuit-list') });

    return (
        <ResizablePanelGroup direction="vertical">
            <ResizablePanel defaultSize={50} id="circuit-list">
                <SimpleTable
                    data={circuits}
                    columns={circuitColumns}
                    onSelectedRowsChange={(rows) => setSelectedCircuit(rows[0])}
                    allowSelect={true}
                    style={{
                        height: parentRect?.height ?? 50,
                        maxHeight: parentRect?.height ?? 50
                    }}
                />
            </ResizablePanel>
            <ResizableHandle className={`border-2 border-gray-300 dark:border-gray-600 ${selectedCircuit ? "flex" : "hidden"}`} />
            <ResizablePanel defaultSize={50} className={`${selectedCircuit ? "flex" : "hidden"}`}>
                <ResponsiveContainer width="95%" height="95%">
                    <LineChart data={speeds}
                        margin={{ top: 20, right: 10, left: 20, bottom: 5 }}>
                        <CartesianGrid
                            strokeDasharray="3 3"
                            stroke={`${window.document.documentElement.classList.contains("dark") ? "#404040" : "#d4d4d4"}`} />
                        <YAxis />
                        <Legend />
                        <Line
                            type="monotone"
                            name="Throughput MB/s"
                            dataKey="speed"
                            isAnimationActive={false} stroke={`${window.document.documentElement.classList.contains("dark") ? "#38bdf8" : "#0369a1"}`} />
                    </LineChart>
                </ResponsiveContainer>
                <div className="p-5 flex flex-col items-center">
                    <Button
                        className="whitespace-nowrap"
                        onClick={() => {
                            setSpeeds([]);
                            if (selectedCircuit) {
                                ipv8Service.testCircuit(selectedCircuit?.circuit_id, (event) => {
                                    setSpeeds((prevState) => [...prevState, { speed: event.down.toFixed(2) }])
                                });
                            }
                        }}>Run test
                    </Button>
                </div>
            </ResizablePanel>
        </ResizablePanelGroup>
    )

}
