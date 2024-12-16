import { SetStateAction, useEffect, useRef, useState } from 'react';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { getCoreRowModel, useReactTable, flexRender, getFilteredRowModel, getPaginationRowModel, getExpandedRowModel, getSortedRowModel } from '@tanstack/react-table';
import type { ColumnDef, Row, PaginationState, RowSelectionState, ColumnFiltersState, ExpandedState, ColumnDefTemplate, HeaderContext, SortingState } from '@tanstack/react-table';
import { cn } from '@/lib/utils';
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel } from './select';
import { Button } from './button';
import { ArrowDownIcon, ArrowUpIcon, ChevronLeftIcon, ChevronRightIcon, DoubleArrowLeftIcon, DoubleArrowRightIcon } from '@radix-ui/react-icons';
import * as SelectPrimitive from "@radix-ui/react-select"
import type { Table as ReactTable } from '@tanstack/react-table';
import { useTranslation } from 'react-i18next';
import { useResizeObserver } from '@/hooks/useResizeObserver';
import useKeyboardShortcut from 'use-keyboard-shortcut';


export function getHeader<T>(name: string, translate: boolean = true, addSorting: boolean = true): ColumnDefTemplate<HeaderContext<T, unknown>> | undefined {
    if (!addSorting) {
        return () => {
            const { t } = useTranslation();
            return <span className='select-none'>{translate ? t(name) : name}</span>;
        }
    }

    return ({ column }) => {
        const { t } = useTranslation();
        return (
            <div className='select-none flex'>
                <span
                    className="cursor-pointer hover:text-black dark:hover:text-white flex flex-row items-center"
                    onClick={() => column.toggleSorting()}>
                    {translate ? t(name) : name}
                    {column.getIsSorted() === "desc" ? (
                        <ArrowDownIcon className="ml-2" />
                    ) : column.getIsSorted() === "asc" ? (
                        <ArrowUpIcon className="ml-2" />
                    ) : (
                        <></>
                    )}
                </span>
            </div>
        )
    }
}

function getStoredSortingState(key?: string) {
    if (key) {
        let sortingString = localStorage.getItem(key);
        if (sortingString) {
            return JSON.parse(sortingString);
        }
    }
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
    filters?: { id: string, value: string }[];
    maxHeight?: string | number;
    expandable?: boolean;
    storeSortingState?: string;
    rowId?: (originalRow: T, index: number, parent?: Row<T>) => string,
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
    filters,
    maxHeight,
    expandable,
    storeSortingState,
    rowId
}: ReactTableProps<T>) {
    const [pagination, setPagination] = useState<PaginationState>({
        pageIndex: pageIndex ?? 0,
        pageSize: pageSize ?? 20,
    });
    const [rowSelection, setRowSelection] = useState<RowSelectionState>(initialRowSelection || {});
    const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>(filters || [])
    const [expanded, setExpanded] = useState<ExpandedState>({});
    const [sorting, setSorting] = useState<SortingState>(getStoredSortingState(storeSortingState) || []);

    useKeyboardShortcut(
        ["Control", "A"],
        keys => {
            if (allowMultiSelect) {
                table.toggleAllRowsSelected(true);
            }
        },
        {
            overrideSystem: true,
            ignoreInputFields: true,
            repeatOnHold: false
        }
    );

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
            expanded,
            sorting
        },
        getFilteredRowModel: getFilteredRowModel(),
        onColumnFiltersChange: setColumnFilters,
        onPaginationChange: setPagination,
        onRowSelectionChange: (arg: SetStateAction<RowSelectionState>) => {
            if (allowSelect || allowSelectCheckbox || allowMultiSelect) setRowSelection(arg);
        },
        onExpandedChange: setExpanded,
        onSortingChange: setSorting,
        getSubRows: (row: any) => row?.subRows,
        getRowId: rowId,
        autoResetPageIndex: false,
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
    }, [rowSelection, table, onSelectedRowsChange])

    useEffect(() => {
        if (filters) {
            for (let filter of filters) {
                table.getColumn(filter.id)?.setFilterValue(filter.value);
            }
        }
    }, [filters])

    useEffect(() => {
        if (storeSortingState) {
            localStorage.setItem(storeSortingState, JSON.stringify(sorting));
        }
    }, [sorting]);

    // For some reason the ScrollArea scrollbar is only shown when it's set to a specific height.
    // So, we wrap it in a parent div, monitor its size, and set the height of the table accordingly.
    const parentRef = useRef<HTMLTableElement>(null);
    const parentRect = (!maxHeight) ? useResizeObserver({ ref: parentRef }) : undefined;

    return (
        <>
            <div ref={parentRef} className='flex-grow flex'>
                <Table maxHeight={maxHeight ?? (parentRect?.height ?? 200)}>
                    <TableHeader>
                        {table.getHeaderGroups().map((headerGroup) => (
                            <TableRow key={headerGroup.id} className="bg-neutral-100 hover:bg-neutral-100 dark:bg-neutral-900 dark:hover:bg-neutral-900">
                                {headerGroup.headers.map((header, index) => {
                                    return (
                                        <TableHead key={header.id} className={cn({ 'pl-4': index === 0, 'pr-4': index + 1 === headerGroup.headers.length, })}>
                                            {header.isPlaceholder
                                                ? null
                                                : flexRender(
                                                    header.column.columnDef.header,
                                                    header.getContext()
                                                )}
                                        </TableHead>
                                    )
                                })}
                            </TableRow>
                        ))}
                    </TableHeader>
                    <TableBody>
                        {table.getRowModel().rows?.length ? (
                            table.getPaginationRowModel().rows.map((row) => (
                                <TableRow
                                    key={row.id}
                                    data-state={row.getIsSelected() && "selected"}
                                    className={`${allowSelect || allowMultiSelect ? "cursor-pointer" : ""}`}
                                    onClick={(event) => {
                                        if (!allowSelect && !allowMultiSelect)
                                            return

                                        if (allowMultiSelect && (event.ctrlKey || event.shiftKey)) {
                                            row.toggleSelected(!row.getIsSelected());
                                        } else {
                                            const selected = row.getIsSelected()
                                            table.resetRowSelection();
                                            row.toggleSelected(!selected);
                                        }
                                    }}
                                    onDoubleClick={() => {
                                        if (onRowDoubleClick) {
                                            onRowDoubleClick(row.original)
                                        }
                                    }}>
                                    {row.getVisibleCells().map((cell, index) => (
                                        <TableCell key={cell.id} className={cn({ 'pl-4': index === 0, 'pr-4': index + 1 === row.getVisibleCells().length, })}>
                                            {flexRender(cell.column.columnDef.cell, cell.getContext())}
                                        </TableCell>
                                    ))}
                                </TableRow>
                            ))
                        ) : (
                            <TableRow>
                                <TableCell colSpan={columns.length} className="h-24 text-center text-muted-foreground">
                                    {t('NoResults')}
                                </TableCell>
                            </TableRow>
                        )}
                    </TableBody>
                </Table>
            </div>

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
                    onValueChange={(value) => table.setPageSize(Number(value))}>
                    <SelectPrimitive.Trigger>
                        <div className="px-1 py-0 hover:bg-inherit text-muted-foreground text-xs">
                            {pageIndex * pageSize}&nbsp;-&nbsp;
                            {Math.min((pageIndex + 1) * pageSize, rowCount)}&nbsp;of&nbsp;
                            {rowCount}
                        </div>
                    </SelectPrimitive.Trigger>
                    <SelectContent side="top"><SelectGroup>
                        <SelectLabel>Rows per page</SelectLabel>
                        {[10, 20, 30, 40, 50].map((pageSize) => (
                            <SelectItem key={pageSize} value={`${pageSize}`}>
                                {pageSize}
                            </SelectItem>
                        ))}</SelectGroup>
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
