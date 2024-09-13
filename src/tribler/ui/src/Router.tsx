import { createHashRouter, Await, useRouteError } from "react-router-dom";
import { Suspense } from 'react';
import { SideLayout } from "./components/layouts/SideLayout";
import { filterActive, filterAll, filterCompleted, filterDownloading, filterInactive } from "./pages/Downloads";
import { handleHTTPError } from "./services/reporting";
import NoMatch from "./pages/NoMatch";
import Dashboard from "./pages/Dashboard";
import Downloads from "./pages/Downloads";
import Search from "./pages/Search";
import Popular from "./pages/Popular";
import GeneralSettings from "./pages/Settings/General";
import Connection from "./pages/Settings/Connection";
import Bandwidth from "./pages/Settings/Bandwidth";
import Seeding from "./pages/Settings/Seeding";
import Anonymity from "./pages/Settings/Anonymity";
import Debugging from "./pages/Settings/Debugging";
import Versions from "./pages/Settings/Versions";
import GeneralDebug from "./pages/Debug/General";
import IPv8 from "./pages/Debug/IPv8";
import Tunnels from "./pages/Debug/Tunnels";
import DHT from "./pages/Debug/DHT";
import Libtorrent from "./pages/Debug/Libtorrent";
import Asyncio from "./pages/Debug/Asyncio";

var raiseUnhandledError: (reason?: any) => void;
const errorPromise = new Promise(function(resolve, reject){
  raiseUnhandledError = reject;
});


function ErrorBoundary() {
  handleHTTPError(useRouteError() as Error);
  return <div>The GUI crashed beyond repair. Please report the error and refresh the page.</div>;
}

export const router = createHashRouter([
    {
        path: "/",
        element: <div className="flex-1 flex"><SideLayout /><div className="h-0 hidden invisible"><Suspense><Await children={[]} resolve={errorPromise}></Await></Suspense></div></div>,
        errorElement: <ErrorBoundary />,
        children: [
            {
                path: "",
                element: <Dashboard />,
            },
            {
                path: "popular",
                element: <Popular />,
            },
            {
                path: "search",
                element: <Search />,
            },
            {
                path: "downloads/all",
                element: <Downloads statusFilter={filterAll} />,
            },
            {
                path: "downloads/downloading",
                element: <Downloads statusFilter={filterDownloading} />,
            },
            {
                path: "downloads/completed",
                element: <Downloads statusFilter={filterCompleted} />,
            },
            {
                path: "downloads/active",
                element: <Downloads statusFilter={filterActive} />,
            },
            {
                path: "downloads/inactive",
                element: <Downloads statusFilter={filterInactive} />,
            },
            {
                path: "settings/general",
                element: <GeneralSettings />,
            },
            {
                path: "settings/connection",
                element: <Connection />,
            },
            {
                path: "settings/bandwidth",
                element: <Bandwidth />,
            },
            {
                path: "settings/seeding",
                element: <Seeding />,
            },
            {
                path: "settings/anonymity",
                element: <Anonymity />,
            },
            {
                path: "settings/debugging",
                element: <Debugging />,
            },
            {
                path: "settings/versions",
                element: <Versions />,
            },
            {
                path: "debug/general",
                element: <GeneralDebug />,
            },
            {
                path: "debug/asyncio",
                element: <Asyncio />,
            },
            {
                path: "debug/ipv8",
                element: <IPv8 />,
            },
            {
                path: "debug/tunnels",
                element: <Tunnels />,
            },
            {
                path: "debug/dht",
                element: <DHT />,
            },
            {
                path: "debug/libtorrent",
                element: <Libtorrent />,
            },
        ],
    },
    {
        path: "*",
        element: <NoMatch />,
    },
])

window.addEventListener("unhandledrejection", (event) => {
  let exc = event.reason;
  raiseUnhandledError(exc as Error);
  event.preventDefault();
});
