import { useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Header } from "./Header";
import { Accordion } from "@radix-ui/react-accordion";
import { sideMenu } from "@/config/menu";
import { AccordionContent, AccordionItem, AccordionTrigger } from "../ui/accordion";
import { Button, buttonVariants } from "../ui/button";
import { Label } from "../ui/label";
import { cn } from "@/lib/utils";
import { Separator } from "../ui/separator";
import { HamburgerMenuIcon } from "@radix-ui/react-icons";
import { AddTorrent } from "../add-torrent";
import { useTranslation } from "react-i18next";

export function SideLayout() {
    const { t } = useTranslation();
    const location = useLocation();
    const navigate = useNavigate();
    const [history, setHistory] = useState(new Map());
    const [accordionValue, setAccordionValue] = useState(() => {
        return "item-" + sideMenu.findIndex(item => item.items !== undefined ? item.items.filter(subitem => subitem.to !== undefined).map(subitem => subitem.to).includes(location.pathname) : false)
    });
    const [showNav, setShowNav] = useState(false)

    return (
        <div className="flex-grow flex flex-col">
            <Header />
            <div className="flex-grow container px-0 flex flex-col md:flex-row md:space-x-4 lg:space-x-4 md:pl-6">
                <div>
                    <div className="pt-6 md:hidden">
                        <Button variant="outline"
                            onClick={() => setShowNav(old => !old)}
                            className="w-full justify-start">
                            <HamburgerMenuIcon className="mr-2.5" />
                            Navigation
                        </Button>
                    </div>
                    <aside className={cn(
                        "md:-mx-4 md:w-[16rem] border-r h-full pr-2",
                        showNav ? '' : "hidden md:block",
                    )}>
                        <Accordion type="single" collapsible className="w-full"
                            value={accordionValue} onValueChange={setAccordionValue}>
                            <nav className="flex flex-col space-y-1">
                                <AddTorrent />
                                {sideMenu.filter((item) => !item.hide || item.hide() !== true).map((item, index) => (
                                    item.items !== undefined ? (
                                        <AccordionItem key={index} value={`item-${index}`} className="border-b-0">
                                            <AccordionTrigger
                                                className={cn(
                                                    buttonVariants({ variant: "ghost" }),
                                                    (item.items.filter(subitem => subitem.to !== undefined).map(subitem => subitem.to))
                                                        .includes(location.pathname) ? 'bg-accent' : 'hover:bg-accent',
                                                    "justify-between hover:no-underline"
                                                )}
                                                onClick={() => {
                                                    const target = history.get(item.title) || item.items?.at(0)?.to;
                                                    if (target) {
                                                        navigate(target);
                                                    }
                                                }}>
                                                <div className="flex items-center">{item.icon && <item.icon className="mr-2" />} {t(item.title)}</div>
                                            </AccordionTrigger>
                                            <AccordionContent className="pb-2 pl-6">
                                                <div className="flex flex-col space-y-0.5 pt-1">
                                                    {item.items.map((submenu, subindex) => (
                                                        submenu.to !== undefined ? (
                                                            <NavLink
                                                                key={subindex}
                                                                to={submenu.to}
                                                                onClick={() => {
                                                                    setShowNav(false);
                                                                    if (item.title && submenu.to) {
                                                                        // Keep track of which submenus we navigated to
                                                                        setHistory(map => new Map(map.set(item.title, submenu.to)));
                                                                    }
                                                                }}
                                                                className={({ isActive }) => cn(
                                                                    buttonVariants({ variant: "ghost" }),
                                                                    isActive ? "bg-accent" : "hover:bg-accent",
                                                                    "justify-start py-1.5 px-3 pl-4 h-auto font-normal"
                                                                )}>
                                                                {t(submenu.title)}
                                                            </NavLink>
                                                        ) : (
                                                            submenu.title !== '' ? (
                                                                null
                                                            ) : (
                                                                <div key={subindex} className="px-3">
                                                                    {/* <Separator /> */}
                                                                </div>
                                                            )
                                                        )
                                                    ))}
                                                </div>
                                            </AccordionContent>
                                        </AccordionItem>
                                    ) : (
                                        item.to !== undefined ? (
                                            <NavLink
                                                key={index}
                                                to={item.to}
                                                onClick={() => {
                                                    setAccordionValue("")
                                                    setShowNav(false)
                                                }}
                                                className={({ isActive }) => cn(
                                                    buttonVariants({ variant: "ghost" }),
                                                    isActive ? "bg-accent" : "hover:bg-accent",
                                                    "justify-start"
                                                )}>
                                                {item.icon && <item.icon className="mr-2" />} {t(item.title)}
                                            </NavLink>
                                        ) : (
                                            item.title !== '' ? (
                                                <div className="px-4 pt-2">
                                                    <Label className="text-xs text-muted-foreground">{t(item.title)}</Label>
                                                </div>
                                            ) : (
                                                <div className="px-4">
                                                    <Separator />
                                                </div>
                                            )
                                        )
                                    )
                                ))}
                            </nav>
                        </Accordion>
                    </aside>
                </div>
                <div className="flex-grow flex flex-col">
                    <div className="flex-grow flex">
                        <Outlet />
                    </div>
                </div>
            </div>
        </div>
    )
}
