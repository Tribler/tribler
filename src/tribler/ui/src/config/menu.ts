import { triblerService } from "@/services/tribler.service";
import { DownloadIcon, ExclamationTriangleIcon, GearIcon, StarIcon } from "@radix-ui/react-icons";
import { IconProps } from "@radix-ui/react-icons/dist/types";

type IconType = React.ForwardRefExoticComponent<IconProps & React.RefAttributes<SVGSVGElement>>

interface NavItem {
    title: string
    to?: string
    href?: string
    disabled?: boolean
    external?: boolean
    icon?: IconType
    label?: string
    hide?: () => boolean
}

interface NavItemWithChildren extends NavItem {
    items?: NavItem[]
}

export const sideMenu: NavItemWithChildren[] = [

    {
        title: 'Downloads',
        icon: DownloadIcon,
        items: [
            {
                title: 'All',
                to: '/downloads/all',
            },
            {
                title: 'Downloading',
                to: '/downloads/downloading',
            },
            {
                title: 'Completed',
                to: '/downloads/completed',
            },
            {
                title: 'Active',
                to: '/downloads/active',
            },
            {
                title: 'Inactive',
                to: '/downloads/inactive',
            },
        ],
    },
    {
        title: 'Popular',
        icon: StarIcon,
        to: '/popular',
    },
    {
        title: 'Settings',
        icon: GearIcon,
        items: [
            {
                title: 'General',
                to: '/settings/general',
            },
            {
                title: 'Connection',
                to: '/settings/connection',
            },
            {
                title: 'Bandwidth',
                to: '/settings/bandwidth',
            },
            {
                title: 'Seeding',
                to: '/settings/seeding',
            },
            {
                title: 'Anonymity',
                to: '/settings/anonymity',
            },
            {
                title: 'Debug',
                to: '/settings/debugging',
            },
            {
                title: 'Versions',
                to: '/settings/versions',
            },
        ],
    },
    {
        title: 'Debug',
        icon: ExclamationTriangleIcon,
        hide: () => triblerService.guiSettings.dev_mode !== true,
        items: [
            {
                title: 'General',
                to: '/debug/general',
            },
            {
                title: 'Asyncio',
                to: '/debug/asyncio',
            },
            {
                title: 'IPv8',
                to: '/debug/ipv8',
            },
            {
                title: 'Tunnels',
                to: '/debug/tunnels',
            },
            {
                title: 'DHT',
                to: '/debug/dht',
            },
            {
                title: 'Libtorrent',
                to: '/debug/libtorrent',
            },
        ],
    },
]
