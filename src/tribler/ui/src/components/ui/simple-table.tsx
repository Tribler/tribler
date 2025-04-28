import { Dispatch, SetStateAction, useEffect, useRef, useState } from 'react';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { getCoreRowModel, useReactTable, flexRender, getFilteredRowModel, getPaginationRowModel, getExpandedRowModel, getSortedRowModel } from '@tanstack/react-table';
import type { ColumnDef, Row, PaginationState, RowSelectionState, ColumnFiltersState, ColumnDefTemplate, HeaderContext, SortingState, VisibilityState, Header, Column, InitialTableState } from '@tanstack/react-table';
import { cn, isMac } from '@/lib/utils';
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from './select';
import { Button } from './button';
import { ArrowDownIcon, ArrowUpIcon, ChevronLeftIcon, ChevronRightIcon, DotsHorizontalIcon, DoubleArrowLeftIcon, DoubleArrowRightIcon } from '@radix-ui/react-icons';
import * as SelectPrimitive from "@radix-ui/react-select"
import type { Table as ReactTable } from '@tanstack/react-table';
import { useTranslation } from 'react-i18next';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from './dropdown-menu';
import { triblerService } from '@/services/tribler.service';
import { useHotkeys } from 'react-hotkeys-hook';
import { notUndefined, useVirtualizer } from '@tanstack/react-virtual';
import { ScrollArea } from './scroll-area';
import { Popover, PopoverAnchor, PopoverContent } from './popover';
import { XIcon } from 'lucide-react';
import { Label } from './label';
import { Input } from './input';


declare module '@tanstack/table-core/build/lib/types' {
    export interface ColumnMeta<TData extends RowData, TValue> {
        hide_by_default: boolean;
    }
}

function ColumnSetup({ name, column, translate, addSorting, addFilter }: { name: string, column: Column<any>, translate: boolean, addSorting: boolean, addFilter: boolean }) {
    const { t } = useTranslation();
    const [isOpen, setIsOpen] = useState<boolean>(false);
    const [filter, setFilter] = useState<string>(column.getFilterValue() as string ?? "");

    useEffect(() => {
        column.setFilterValue(filter)
    }, [filter]);

    return (
        <Popover open={isOpen} onOpenChange={setIsOpen}>
            <PopoverAnchor>
                <span
                    className="cursor-pointer hover:text-black dark:hover:text-white flex flex-row items-center"
                    onClick={(e) => column.toggleSorting(undefined, e.shiftKey)}
                    onContextMenu={(e) => {
                        setIsOpen(true);
                        e.preventDefault();
                    }}>
                    {translate ? t(name) : name}
                    {column.getIsSorted() === "desc" ? (
                        <ArrowDownIcon className="ml-2" />
                    ) : column.getIsSorted() === "asc" ? (
                        <ArrowUpIcon className="ml-2" />
                    ) : (
                        <></>
                    )}
                </span>
            </PopoverAnchor>
            <PopoverContent className="w-80" align="start" alignOffset={-4} onClick={event => event.stopPropagation()} onContextMenu={event => event.stopPropagation()}>
                <div className="grid gap-4">
                    <div className="space-y-2">
                        <h4 className="font-medium leading-none">{t('ColumnSettings')}</h4>
                        <p className="text-sm text-muted-foreground">
                            {t('ColumnSettingsDescription')}
                        </p>
                    </div>
                    <div className="grid gap-2">
                        {addFilter &&
                            <div className="grid grid-cols-3 items-center gap-4">
                                <Label>{t('FilterBy')}</Label>
                                <div className="col-span-2 relative w-full max-w-sm">
                                    <Input className="h-8"
                                        value={filter}
                                        onChange={(event) => setFilter(event.target.value)} />

                                    {filter.length > 0 && <Button
                                        type="button"
                                        variant="ghost"
                                        size="icon"
                                        className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7 text-gray-500
                                            hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100"
                                        onClick={() => setFilter("")}
                                    >
                                        <XIcon className="h-4 w-4" />
                                        <span className="sr-only">{t('Clear')}</span>
                                    </Button>}
                                </div>
                            </div>
                        }

                        {addSorting &&
                            <div className="grid grid-cols-3 items-center gap-4">
                                <Label>{t('SortBy')}</Label>
                                <Select
                                    onValueChange={(value) => value == "none" ? column.clearSorting() : column.toggleSorting(value == "desc", false)}
                                    value={column.getIsSorted() || "none"}
                                >
                                    <SelectTrigger className="col-span-2 h-8">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectGroup>
                                            <SelectItem value="asc">{t('Ascending')}</SelectItem>
                                            <SelectItem value="desc">{t('Descending')}</SelectItem>
                                            <SelectItem value="none">{t('None')}</SelectItem>
                                        </SelectGroup>
                                    </SelectContent>
                                </Select>
                            </div>
                        }
                    </div>
                </div>
            </PopoverContent>
        </Popover>
    )
}

export function getHeader<T>(name: string, translate: boolean = true, addSorting: boolean = true, addFilter: boolean = false): ColumnDefTemplate<HeaderContext<T, unknown>> | undefined {
    if (!addSorting) {
        return () => {
            const { t } = useTranslation();
            return <span className='select-none'>{translate ? t(name) : name}</span>;
        }
    }

    return ({ column }) => {
        return <ColumnSetup name={name} column={column} translate={translate} addSorting={addSorting} addFilter={addFilter}></ColumnSetup>
    }
}

function getState(type: "columns" | "sorting", name?: string) {
    let stateString = triblerService.guiSettings[type];
    if (stateString && name) {
        return JSON.parse(stateString)[name];
    }
}

function setState(type: "columns" | "sorting", name: string, state: SortingState | VisibilityState) {
    let stateString = triblerService.guiSettings[type];
    let stateSettings = stateString ? JSON.parse(stateString) : {};
    stateSettings[name] = state;

    triblerService.guiSettings[type] = JSON.stringify(stateSettings);
    triblerService.setSettings({ ui: triblerService.guiSettings });
}

function updateRowSelection(
    table: ReactTable<any>,
    rowSelection: RowSelectionState,
    setRowSelection: Dispatch<SetStateAction<RowSelectionState>>,
    fromId: string | undefined,
    change: number,
    allowMulti?: boolean) {

    if (fromId === undefined) return;

    let rows = table.getSortedRowModel().rows;
    let fromIndex = rows.findIndex((row) => row.id === fromId);
    if (fromIndex < 0) return;

    let selectedRowIndexes = [];
    for (let rowID of Object.keys(rowSelection)) {
        const index = rows.findIndex((row) => row.id === rowID);
        if (index >= 0) {
            selectedRowIndexes.push(index);
        }
    }
    let maxIndex = Math.max(...selectedRowIndexes);
    let minIndex = Math.min(...selectedRowIndexes);

    // If there are gaps in the selection, ignore all but the most recently clicked item.
    let gaps = false;
    for (let i = minIndex; i <= maxIndex; i++) {
        if (!selectedRowIndexes.includes(i)) gaps = true;
    }
    let toIndex = fromIndex === maxIndex ? minIndex : maxIndex;
    if (gaps) toIndex = fromIndex

    // Calculate new toIndex, depending on whether we're going up/down in the list
    let newIndex = toIndex + change;
    if (newIndex >= 0 && newIndex < rows.length) {
        toIndex = newIndex;
    }

    if (!allowMulti) fromIndex = toIndex;

    // Set fromIndex..toIndex as the new row selection
    if (fromIndex > toIndex) {
        [fromIndex, toIndex] = [toIndex, fromIndex];
    }
    let selection: any = {};
    for (let i = fromIndex; i <= toIndex; i += 1) {
        selection[rows[i].id] = true;
    }
    setRowSelection(selection);

    document.querySelector("[data-state='selected']")?.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'center' });
}

interface ReactTableProps<T extends object> {
    data: T[];
    columns: ColumnDef<T>[];
    renderSubComponent?: (props: { row: Row<T> }) => React.ReactElement;
    pageIndex?: number;
    pageSize?: number;
    pageCount?: number;
    onPaginationChange?: (pagination: PaginationState) => void;
    onRowDoubleClick?: (rowDoubleClicked: T) => void;
    onSelectedRowsChange?: (rowSelection: T[]) => void;
    initialRowSelection?: Record<string, boolean>;
    allowSelect?: boolean;
    allowSelectCheckbox?: boolean;
    allowMultiSelect?: boolean;
    allowColumnToggle?: string;
    filters?: { id: string, value: string }[];
    expandable?: boolean;
    storeSortingState?: string;
    rowId?: (originalRow: T, index: number, parent?: Row<T>) => string,
    selectOnRightClick?: boolean,
    initialState?: InitialTableState,
    className?: string,
    style?: React.CSSProperties
}

function SimpleTable<T extends object>({
    data,
    columns,
    pageIndex,
    pageSize,
    pageCount,
    onPaginationChange,
    onRowDoubleClick,
    onSelectedRowsChange,
    initialRowSelection,
    allowSelect,
    allowSelectCheckbox,
    allowMultiSelect,
    allowColumnToggle,
    filters,
    expandable,
    storeSortingState,
    rowId,
    selectOnRightClick,
    initialState,
    className,
    style
}: ReactTableProps<T>) {
    const [pagination, setPagination] = useState<PaginationState>({
        pageIndex: pageIndex ?? 0,
        pageSize: pageSize ?? 20,
    });
    const [rowSelection, setRowSelection] = useState<RowSelectionState>(initialRowSelection || {});
    const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>(filters || [])
    const [sorting, setSorting] = useState<SortingState>([]);
    const [startId, setStartId] = useState<string | undefined>(undefined);
    const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({});

    useHotkeys(isMac() ? 'meta+a' : 'ctrl+a', event => {
        if (allowMultiSelect) {
            table.toggleAllRowsSelected(true);
        }
        event.preventDefault();
    });
    useHotkeys('shift+ArrowUp', () => {
        updateRowSelection(table, rowSelection, setRowSelection, startId, -1, allowMultiSelect)
    }, [rowSelection, startId]);
    useHotkeys('shift+ArrowDown', () => {
        updateRowSelection(table, rowSelection, setRowSelection, startId, 1, allowMultiSelect)
    }, [rowSelection, startId]);
    useHotkeys('ArrowUp', () => {
        updateRowSelection(table, rowSelection, setRowSelection, startId, -1, false)
    }, [rowSelection, startId]);
    useHotkeys('ArrowDown', () => {
        updateRowSelection(table, rowSelection, setRowSelection, startId, 1, false)
    }, [rowSelection, startId]);

    const table = useReactTable({
        data,
        columns,
        getCoreRowModel: getCoreRowModel(),
        getSortedRowModel: getSortedRowModel(),
        getPaginationRowModel: !!pageSize ? getPaginationRowModel() : undefined,
        getExpandedRowModel: expandable ? getExpandedRowModel() : undefined,
        enableRowSelection: true,
        pageCount,
        state: {
            pagination,
            rowSelection,
            columnFilters,
            columnVisibility,
            sorting
        },
        getFilteredRowModel: getFilteredRowModel(),
        onColumnFiltersChange: setColumnFilters,
        onColumnVisibilityChange: setColumnVisibility,
        onPaginationChange: setPagination,
        onRowSelectionChange: (arg: SetStateAction<RowSelectionState>) => {
            if (allowSelect || allowSelectCheckbox || allowMultiSelect) setRowSelection(arg);
        },
        onSortingChange: setSorting,
        getSubRows: (row: any) => row?.subRows,
        getRowId: rowId,
        autoResetPageIndex: false,
        filterFromLeafRows: true,
        initialState: initialState
    });

    // If we're on an empty page, reset the pageIndex to 0
    if (table.getRowModel().rows.length == 0 && table.getExpandedRowModel().rows.length != 0) {
        setPagination(p => ({ ...p, pageIndex: 0 }));
    }

    const { t } = useTranslation();

    useEffect(() => {
        if (onPaginationChange) {
            onPaginationChange(pagination);
        }
    }, [pagination, onPaginationChange]);

    useEffect(() => {
        if (onSelectedRowsChange)
            onSelectedRowsChange(
                table.getSelectedRowModel().flatRows.map((row) => row.original),
            )

        const rowIds = Object.keys(rowSelection);
        if (rowIds.length === 1) {
            setStartId(rowIds[0]);
        }

    }, [rowSelection, table, onSelectedRowsChange])

    useEffect(() => {
        if (filters) {
            for (let filter of filters) {
                table.getColumn(filter.id)?.setFilterValue(filter.value);
            }
        }
    }, [filters])

    useEffect(() => {
        (async () => {
            // Ensure GUI settings are loaded
            await triblerService.getSettings();

            // Init sorting and column visibility
            const sortingState = getState("sorting", storeSortingState) || [];
            setSorting(sortingState)

            const visibilityState = getState("columns", allowColumnToggle) || {};
            let col: any;
            for (col of columns) {
                if (col.accessorKey && col.accessorKey in visibilityState === false) {
                    visibilityState[col.accessorKey] = col.meta?.hide_by_default !== true;
                }
            }
            setColumnVisibility(visibilityState);
        })()
    }, []);

    useEffect(() => {
        if (storeSortingState && sorting.length > 0) {
            setState("sorting", storeSortingState, sorting);
        }
    }, [sorting]);

    useEffect(() => {
        if (allowColumnToggle && Object.keys(columnVisibility).length > 0) {
            setState("columns", allowColumnToggle, columnVisibility);
        }
    }, [columnVisibility]);

    const parentRef = useRef<HTMLTableElement>(null);
    const columnCount = table.getAllColumns().length;
    const { rows } = table.getRowModel();
    const virtualizer = useVirtualizer({
        count: rows.length,
        getScrollElement: () => parentRef.current,
        estimateSize: () => 40, // if set too low the last row will start flickering
        overscan: 20,
    })

    const items = virtualizer.getVirtualItems();
    const [before, after] =
        items.length > 0
            ? [
                notUndefined(items[0]).start - virtualizer.options.scrollMargin,
                virtualizer.getTotalSize() - notUndefined(items[items.length - 1]).end
            ]
            : [0, 0];

    return (
        <>
            <ScrollArea
                className={cn("relative w-full overflow-auto", className)}
                ref={parentRef}
                style={style}
            >
                <Table>
                    <TableHeader className='z-10'>
                        {table.getHeaderGroups().map((headerGroup) => (
                            <TableRow key={headerGroup.id} className="bg-neutral-100 hover:bg-neutral-100 dark:bg-neutral-900 dark:hover:bg-neutral-900">
                                {headerGroup.headers.map((header, index) => {
                                    return (
                                        <TableHead
                                            key={header.id}
                                            className={cn({
                                                'pl-4': index === 0,
                                                'pr-4': !allowColumnToggle && index + 1 === headerGroup.headers.length,
                                                'pr-0': !!allowColumnToggle
                                            })}
                                        >
                                            {header.isPlaceholder
                                                ? null
                                                : flexRender(
                                                    header.column.columnDef.header,
                                                    header.getContext()
                                                )}
                                        </TableHead>
                                    )
                                })}
                                {allowColumnToggle && <TableHead key="toggleColumns" className="w-2 pl-1 pr-3 cursor-pointer hover:text-black dark:hover:text-white">
                                    <DropdownMenu>
                                        <DropdownMenuTrigger asChild>
                                            <DotsHorizontalIcon className="h-4 w-4" />
                                        </DropdownMenuTrigger>
                                        <DropdownMenuContent align="end">
                                            <DropdownMenuLabel>{t('Toggle columns')}</DropdownMenuLabel>
                                            <DropdownMenuSeparator />
                                            {table.getAllLeafColumns().map(column => {
                                                const fakeColumn = {
                                                    ...column,
                                                    toggleSorting: () => { },
                                                    getIsSorted: () => { },
                                                } as Column<any, unknown>;
                                                return (
                                                    <DropdownMenuItem key={`toggleColumns-${column.id}`}>
                                                        <label onClick={(evt) => evt.stopPropagation()} className='flex space-x-1'>
                                                            <input
                                                                {...{
                                                                    type: 'checkbox',
                                                                    checked: column.getIsVisible(),
                                                                    onChange: column.getToggleVisibilityHandler(),
                                                                }}
                                                            />{flexRender(column.columnDef.header, {
                                                                table,
                                                                column: fakeColumn,
                                                                header: { column: fakeColumn } as Header<any, unknown>,
                                                            })}
                                                        </label>
                                                    </DropdownMenuItem>
                                                )
                                            })}
                                        </DropdownMenuContent>
                                    </DropdownMenu>
                                </TableHead>}
                            </TableRow>
                        ))}
                    </TableHeader>
                    <TableBody>
                        {before > 0 && <TableRow><td colSpan={columnCount} style={{ height: before }} /></TableRow>}

                        {rows.length ? (
                            items.map((item, rowIndex) => {
                                const row = rows[item.index];

                                return (
                                    <TableRow
                                        key={row.id}
                                        data-state={row.getIsSelected() && "selected"}
                                        className={`select-none ${allowSelect || allowMultiSelect ? "cursor-pointer" : ""}`}
                                        onContextMenu={(event) => {
                                            if (selectOnRightClick && !row.getIsSelected()) {
                                                event.target.dispatchEvent(new MouseEvent("click", {
                                                    bubbles: true,
                                                    cancelable: true,
                                                    view: window,
                                                }));
                                            }
                                        }}
                                        onClick={(event) => {
                                            if (!allowSelect && !allowMultiSelect)
                                                return;

                                            if (allowMultiSelect && (isMac() ? event.metaKey : event.ctrlKey)) {
                                                row.toggleSelected(!row.getIsSelected());
                                                if (!row.getIsSelected()) setStartId(row.id)
                                                return;
                                            }

                                            let rows = table.getSortedRowModel().rows;
                                            let startRow = rows.find((row) => row.id === startId);

                                            if (startRow && allowMultiSelect && event.shiftKey) {
                                                let selection: any = {};
                                                let startIndex = rows.findIndex((r) => r.id == startRow.id);
                                                let stopIndex = rows.findIndex((r) => r.id == row.id);
                                                for (let i = Math.min(startIndex, stopIndex); i <= Math.max(startIndex, stopIndex); i++) {
                                                    selection[rows[i].id] = true;
                                                }
                                                setRowSelection(selection);
                                            } else {
                                                const selected = row.getIsSelected()
                                                table.resetRowSelection();
                                                row.toggleSelected(!selected);
                                                if (!selected) setStartId(row.id)
                                            }
                                        }}
                                        onDoubleClick={() => {
                                            if (onRowDoubleClick) {
                                                onRowDoubleClick(row.original)
                                            }
                                        }}>

                                        {row.getVisibleCells().map((cell, colIndex) => (
                                            <TableCell
                                                key={cell.id}
                                                className={cn({ 'pl-4': colIndex === 0, 'pr-4': colIndex + 1 === row.getVisibleCells().length, })}
                                            >
                                                {flexRender(cell.column.columnDef.cell, cell.getContext())}
                                            </TableCell>
                                        ))}
                                    </TableRow>
                                )
                            })
                        ) : (
                            <TableRow>
                                <TableCell colSpan={columns.length} className="h-24 text-center text-muted-foreground">
                                    {t('NoResults')}
                                </TableCell>
                            </TableRow>
                        )}

                        {after > 0 && <TableRow><td colSpan={columnCount} style={{ height: after }} /></TableRow>}
                    </TableBody>
                </Table>
            </ScrollArea>

            {!!pageSize && table.getPageCount() > 1 && <Pagination table={table} />}
        </>
    )
}

function Pagination<T>({ table }: React.PropsWithChildren<{ table: ReactTable<T> }>) {
    const pageIndex = table.getState().pagination.pageIndex;
    const pageSize = table.getState().pagination.pageSize;
    const rowCount = table.getExpandedRowModel().rows.length;

    const { t } = useTranslation();

    return (
        <div className="flex items-center justify-end px-4 py-0.5">
            <div className="flex items-center space-x-4">
                <Select defaultValue="0"
                    value={`${pageSize}`}
                    onValueChange={(value) => {
                        let size = Number(value);
                        if (size === 0) {
                            for (let row of table.getExpandedRowModel().rows) {
                                size += row.getLeafRows().length;
                            }
                        }
                        table.setPageSize(size);
                    }}>
                    <SelectPrimitive.Trigger>
                        <div className="px-1 py-0 hover:bg-inherit text-muted-foreground text-xs">
                            {pageIndex * pageSize}&nbsp;-&nbsp;
                            {Math.min((pageIndex + 1) * pageSize, rowCount)}&nbsp;of&nbsp;
                            {rowCount}
                        </div>
                    </SelectPrimitive.Trigger>
                    <SelectContent side="top">
                        <SelectGroup>
                            <SelectLabel>Rows per page</SelectLabel>
                            {[10, 20, 30, 40, 50, 0].map((pageSize) => (
                                <SelectItem key={pageSize} value={`${pageSize}`}>
                                    {pageSize > 0 ? pageSize : 'disable pagination'}
                                </SelectItem>
                            ))}
                        </SelectGroup>
                    </SelectContent>
                </Select>
                <div className="flex items-center space-x-2">
                    <Button
                        variant="outline"
                        className="hidden h-8 w-8 p-0 lg:flex"
                        onClick={() => table.setPageIndex(0)}
                        disabled={!table.getCanPreviousPage()}>
                        <span className="sr-only">{t('GotoFirst')}</span>
                        <DoubleArrowLeftIcon className="h-4 w-4" />
                    </Button>
                    <Button
                        variant="outline"
                        className="h-8 w-8 p-0"
                        onClick={() => table.previousPage()}
                        disabled={!table.getCanPreviousPage()}>
                        <span className="sr-only">{t('GotoPrev')}</span>
                        <ChevronLeftIcon className="h-4 w-4" />
                    </Button>
                    <Button
                        variant="outline"
                        className="h-8 w-8 p-0"
                        onClick={() => table.nextPage()}
                        disabled={!table.getCanNextPage()}>
                        <span className="sr-only">{t('GotoNext')}</span>
                        <ChevronRightIcon className="h-4 w-4" />
                    </Button>
                    <Button
                        variant="outline"
                        className="hidden h-8 w-8 p-0 lg:flex"
                        onClick={() => table.setPageIndex(table.getPageCount() - 1)}
                        disabled={!table.getCanNextPage()}>
                        <span className="sr-only">{t('GotoLast')}</span>
                        <DoubleArrowRightIcon className="h-4 w-4" />
                    </Button>
                </div>
            </div>
        </div>
    )
}

export default SimpleTable;
