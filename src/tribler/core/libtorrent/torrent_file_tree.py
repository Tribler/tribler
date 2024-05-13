from __future__ import annotations

import os
import re
from bisect import bisect
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Generator, ItemsView, cast

if TYPE_CHECKING:
    import libtorrent


class TorrentFileTree:
    """
    A tree of directories that contain other directories and files.
    """

    @dataclass
    class Directory:
        """
        A directory that contains other directories and files.
        """

        directories: dict[str, TorrentFileTree.Directory] = field(default_factory=dict)
        files: list[TorrentFileTree.File] = field(default_factory=list)
        collapsed: bool = True
        size: int = 0

        def calc_size(self) -> None:
            """
            Calculate the size of this Directory, assuming all subdirectories already have their size calculated.
            """
            self.size = sum(d.size for d in self.directories.values()) + sum(f.size for f in self.files)

        def iter_dirs(self) -> Generator[TorrentFileTree.Directory, None, None]:
            """
            Iterate through the subdirectories in this directory and then this directory itself.

            We do it this way so that calc_size() can be easily/efficiently executed!
            """
            for directory in self.directories.values():
                yield from directory.iter_dirs()
            yield self

        def tostr(self, depth: int = 0, name: str = "") -> str:
            """
            Create a beautifully formatted string representation of this directory.
            """
            tab = "\t"
            if self.collapsed:
                return "\n" + "\t" * depth + f"CollapsedDirectory({name!r}, {self.size} bytes)"

            # Pretty directories
            has_no_directories = len(self.directories) == 0
            pretty_directories = ",".join(v.tostr(depth + 2, k) for k, v in self.directories.items())
            dir_closure = "" if has_no_directories else "\n" + tab * (depth + 1)
            pretty_directories = f"\n{tab * (depth + 1)}directories=[{pretty_directories}{dir_closure}]"

            # Pretty files
            pretty_files = "".join("\n" + v.tostr(depth + 2) for v in self.files)
            pretty_files = f"\n{tab * (depth + 1)}files=[{pretty_files}]"

            return "\n" + "\t" * depth + f"Directory({name!r},{pretty_directories},{pretty_files}, {self.size} bytes)"

    @dataclass(unsafe_hash=True)
    class File:
        """
        A File object that has a name (relative to its parent directory) and a file index in the torrent's file list.
        """

        name: str
        index: int
        size: int = 0
        selected: bool = True

        _sort_pattern = re.compile('([0-9]+)')  # We use this for natural sorting (see sort_key())

        def tostr(self, depth: int = 0) -> str:
            """
            Create a beautifully formatted string representation of this File.
            """
            return "\t" * depth + f"File({self.index}, {self.name}, {self.size} bytes)"

        def sort_key(self) -> tuple[int | str, ...]:
            """
            Sort File instances using natural sort based on their names, which SHOULD be unique.
            """
            return tuple(int(part) if part.isdigit() else part for part in self._sort_pattern.split(self.name))

        def __lt__(self, other: TorrentFileTree.File) -> bool:
            """
            Python 3.8 quirk/shortcoming is that File needs to be a SupportsRichComparisonT (instead of using a key).
            """
            return self.sort_key() < other.sort_key()

        def __le__(self, other: TorrentFileTree.File) -> bool:
            """
            Python 3.8 quirk/shortcoming is that File needs to be a SupportsRichComparisonT (instead of using a key).
            """
            return self.sort_key() <= other.sort_key()

        def __gt__(self, other: TorrentFileTree.File) -> bool:
            """
            Python 3.8 quirk/shortcoming is that File needs to be a SupportsRichComparisonT (instead of using a key).
            """
            return self.sort_key() > other.sort_key()

        def __ge__(self, other: TorrentFileTree.File) -> bool:
            """
            Python 3.8 quirk/shortcoming is that File needs to be a SupportsRichComparisonT (instead of using a key).
            """
            return self.sort_key() >= other.sort_key()

        def __eq__(self, other: object) -> bool:
            """
            Python 3.8 quirk/shortcoming is that File needs to be a SupportsRichComparisonT (instead of using a key).
            """
            if isinstance(other, TorrentFileTree.File):
                return self.sort_key() == other.sort_key()
            return False

        def __ne__(self, other: object) -> bool:
            """
            Python 3.8 quirk/shortcoming is that File needs to be a SupportsRichComparisonT (instead of using a key).
            """
            if isinstance(other, TorrentFileTree.File):
                return self.sort_key() != other.sort_key()
            return True

    def __init__(self, file_storage: libtorrent.file_storage) -> None:
        """
        Construct an empty tree data structure belonging to the given file storage.

        Note that the file storage contents are not loaded in yet at this point.
        """
        self.root = TorrentFileTree.Directory()
        self.root.collapsed = False
        self.file_storage = file_storage
        self.paths: Dict[Path, TorrentFileTree.Directory | TorrentFileTree.File] = {}

    def __str__(self) -> str:
        """
        Represent the tree as a string, which is actually just the tostr() of its root directory.
        """
        return f"TorrentFileTree({self.root.tostr()}\n)"

    @classmethod
    def from_lt_file_storage(cls: type[TorrentFileTree], file_storage: libtorrent.file_storage) -> TorrentFileTree:
        """
        Load in the tree contents from the given file storage, sorting the files in each directory.
        """
        tree = cls(file_storage)

        # Map libtorrent's flat list to a tree structure.
        for i in range(file_storage.num_files()):
            full_file_path = Path(file_storage.file_path(i))
            *subdirs, fname = full_file_path.parts

            # Register all directories on each file's path.
            current_dir = tree.root
            full_path = Path("")
            for subdir in subdirs:
                d = current_dir.directories.get(subdir, TorrentFileTree.Directory())
                current_dir.directories[subdir] = d
                current_dir = d

                # Register the current path in `tree.paths` to enable later searches with O(1) complexity.
                full_path = full_path / subdir
                tree.paths[full_path] = d

            # After the 'for' loop iteration, `current_dir` points to the rightmost directory in the current file path.
            file_instance = cls.File(fname, i, file_storage.file_size(i))
            current_dir.files.append(file_instance)
            tree.paths[full_file_path] = file_instance  # As with directories, register the file path for searching

        # Sorting afterward is faster than sorting during insertion (roughly 4x speedup)
        for directory in tree.root.iter_dirs():
            directory.files.sort()
            directory.calc_size()
        return tree

    def expand(self, path: Path) -> None:
        """
        Expand all directories that are necessary to view the given path.
        """
        current_dir = self.root
        for directory in path.parts:
            if directory not in current_dir.directories:
                break
            current_dir = current_dir.directories[directory]
            current_dir.collapsed = False

    def collapse(self, path: Path) -> None:
        """
        Collapse ONLY the specific given directory.
        """
        element = self.find(path)
        if isinstance(element, TorrentFileTree.Directory) and element != self.root:
            element.collapsed = True

    def set_selected(self, path: Path, selected: bool) -> list[int]:
        """
        Set the selected status for a File or entire Directory.

        :returns: the list of modified file indices.
        """
        item = self.find(path)
        if item is None:
            return []
        if isinstance(item, TorrentFileTree.File):
            item.selected = selected
            return [item.index]
        out = []
        for key in item.directories:
            out += self.set_selected(path / key, selected)
        for file in item.files:
            file.selected = selected
            out.append(file.index)
        return out

    def find(self, path: Path) -> Directory | File | None:
        """
        Get the Directory or File object at the given path, or None if it does not exist.

        Searching for files is "expensive" (use libtorrent instead).
        """
        if path == Path(""):
            return self.root
        current_dir = self.root
        for directory in path.parts:
            if directory not in current_dir.directories:
                # Not a directory but a file?
                if len(current_dir.files) == 0:
                    return None
                search = self.File(directory, 0)
                found_at = bisect(current_dir.files, search)
                element = current_dir.files[found_at - 1]
                return element if element == search else None
            current_dir = current_dir.directories[directory]
        return current_dir

    def path_is_dir(self, path: Path) -> bool:
        """
        Check if the given path points to a Directory (instead of a File).
        """
        if path == Path(""):  # Note that Path("") == Path(".") but "" != "."
            return True
        current_dir = self.root
        for directory in path.parts:
            if directory not in current_dir.directories:
                # We ended up at a File (or a Path that does not exist, which is also not a directory)
                return False
            current_dir = current_dir.directories[directory]
        return True

    def find_next_directory(self, from_path: Path) -> tuple[Directory, Path] | None:
        """
        Get the next unvisited directory from a given path.

        When we ran out of files, we have to go up in the tree. However, when we go up, we may immediately be at the
        end of the list of that parent directory and we may have to go up again. If we are at the end of the list all
        the way up to the root of the tree, we return None.
        """
        from_parts = from_path.parts
        for i in range(1, len(from_parts) + 1):
            parent_path = Path(os.sep.join(from_parts[:-i]))
            parent = cast(TorrentFileTree.Directory, self.find(parent_path))
            dir_in_parent = from_parts[-i]
            dir_indices = list(parent.directories.keys())  # Python 3 "quirk": dict keys() order is stable
            index_in_parent = dir_indices.index(dir_in_parent)
            if index_in_parent != len(dir_indices) - 1:
                # We did not run through all available directories in the parent yet
                dirname = dir_indices[index_in_parent + 1]
                return parent.directories[dirname], parent_path / dirname
            if len(parent.files) > 0:
                # We did not run through all available files in the parent yet
                return parent, parent_path / parent.files[0].name
        return None

    def _view_get_fetch_path_and_dir(self, start_path: tuple[Directory, Path] | Path) -> tuple[Directory, Path, Path]:
        """
        Given a start path, which may be a file, get the containing Directory object and directory path.

        In the case that we start from a given Directory object and a file path, we only correct the file path to
        start at the given Directory's path.
        """
        if isinstance(start_path, Path):
            fetch_path = start_path if self.path_is_dir(start_path) else start_path.parent
            fetch_directory = cast(TorrentFileTree.Directory, self.find(fetch_path))
            return fetch_directory, fetch_path, start_path
        fetch_directory, fetch_path = start_path
        requested_fetch_path = fetch_path
        if not self.path_is_dir(fetch_path):
            fetch_path = fetch_path.parent
        return fetch_directory, fetch_path, requested_fetch_path

    def _view_up_after_files(self, number: int, fetch_path: Path) -> list[str]:
        """
        Run up the tree to the next available directory (if it exists) and continue building a view.
        """
        next_dir_desc = self.find_next_directory(fetch_path)
        view: list[str] = []
        if next_dir_desc is None:
            return view

        next_dir, next_dir_path = next_dir_desc

        view.append(str(next_dir_path))

        number -= 1
        if number == 0:
            return view

        return view + self.view((next_dir, next_dir_path), number)

    def _view_process_directories(self, number: int, directory_items: ItemsView[str, Directory],
                                  fetch_path: Path) -> tuple[list[str], int]:
        """
        Process the directories dictionary of a given (parent directory) path.

        Note that we only need to process the first directory and the remainder is visited through recursion.
        """
        view = []
        for dirname, dirobj in directory_items:
            full_path = fetch_path / dirname

            # The subdirectory is an item of the tree itself.
            view.append(str(full_path))
            number -= 1
            if number == 0:  # Exit early if we don't need anymore items
                return view, number

            # If the elements of the subdirectory are not collapsed, recurse into a view of those elements.
            if not dirobj.collapsed:
                elems = self.view((dirobj, full_path), number)
                view += elems
                number -= len(elems)
                break

        # We exhausted all subdirectories (note that the number may still be larger than 0)
        return view, number

    def view(self, start_path: tuple[Directory, Path] | Path, number: int) -> list[str]:
        """
        Construct a view of a given number of path names (directories and files) in the tree.

        The view is constructed AFTER the given starting path. To view the root folder contents, simply call this
        method with Path("") or Path(".").
        """
        fetch_directory, fetch_path, element_path = self._view_get_fetch_path_and_dir(start_path)

        # This is a collapsed directory, it has no elements.
        if fetch_directory.collapsed:
            return self._view_up_after_files(number, fetch_path)

        view: list[str] = []
        if self.path_is_dir(element_path):
            # This is a directory: loop through its directories, then process its files.
            view, number = self._view_process_directories(number, fetch_directory.directories.items(), fetch_path)
            if number == 0:
                return view
            # We either landed here when:
            # 1. We went up to a file to continue processing from this fetch_directory (added to the view).
            #    > This is the case if (and only if) the last file in the view is the currently requested view. The
            #    > last file in the view is not necessarily equal the first file in the fetch_directory though!
            #    > In this case, we ignore the first file in the fetch_directory and then pull the "number" of files
            #    > that was requested of us.
            # 2. We went up and discovered a folder to evaluate.
            #    > We simply fetch the first "number" of files starting at the first file in the fetch_directory.
            if (len(view) > 0 and len(fetch_directory.files) > 0
                    and view[-1] == self.file_storage.file_path(fetch_directory.files[0].index)):  # O(1) index lookup
                files = [str(element_path / f.name) for f in fetch_directory.files[1:number + 1]]
            else:
                files = [str(element_path / f.name) for f in fetch_directory.files[:number]]
        else:
            # Starting in the middle of the files of a directory. Because the file list is presorted, we can efficiently
            # search for our starting index by using bisect.
            fetch_index = bisect(fetch_directory.files, self.File(element_path.parts[-1], 0))
            files = [str(fetch_path / f.name) for f in fetch_directory.files[fetch_index:fetch_index + number]]

        # At this point we run through the given files ("files") and go up one folder in the tree if we need more.
        view += files
        number -= len(files)
        return view if number == 0 else view + self._view_up_after_files(number, fetch_path)
