from pathlib import Path

import libtorrent
from pytest import fixture

from tribler.core.components.libtorrent.torrent_file_tree import TorrentFileTree
from tribler.core.tests.tools.common import TORRENT_UBUNTU_FILE, TORRENT_WITH_DIRS


@fixture(name="file_storage_ubuntu", scope="module")
def fixture_file_storage_flat():
    """
    Torrent structure:

      > [File] ubuntu-15.04-desktop-amd64.iso (1150844928 bytes)
    """
    yield libtorrent.torrent_info(str(TORRENT_UBUNTU_FILE)).files()


@fixture(name="file_storage_with_dirs", scope="module")
def fixture_file_storage_wdirs():
    """
    Torrent structure:

      > [Directory] torrent_create
      > > [Directory] abc
      > > > [File] file2.txt (6 bytes)
      > > > [File] file3.txt (6 bytes)
      > > > [File] file4.txt (6 bytes)
      > > [Directory] def
      > > > [File] file5.txt (6 bytes)
      > > > [File] file6.avi (6 bytes)
      > > [File] file1.txt (6 bytes)
    """
    yield libtorrent.torrent_info(str(TORRENT_WITH_DIRS)).files()


def test_file_natsort_numbers():
    """
    Test the natural sorting of File instances for numbers only.
    """
    assert TorrentFileTree.File("01", 0, 0) < TorrentFileTree.File("10", 0, 0)
    assert TorrentFileTree.File("010", 0, 0) <= TorrentFileTree.File("10", 0, 0)
    assert TorrentFileTree.File("010", 0, 0) == TorrentFileTree.File("10", 0, 0)
    assert TorrentFileTree.File("010", 0, 0) >= TorrentFileTree.File("10", 0, 0)
    assert TorrentFileTree.File("011", 0, 0) > TorrentFileTree.File("10", 0, 0)
    assert TorrentFileTree.File("11", 0, 0) > TorrentFileTree.File("10", 0, 0)
    assert TorrentFileTree.File("11", 0, 0) != TorrentFileTree.File("10", 0, 0)


def test_file_natsort_compound():
    """
    Test the natural sorting of File instances for names mixing numbers and text.
    """
    assert TorrentFileTree.File("a1b", 0, 0) != TorrentFileTree.File("a10b", 0, 0)
    assert TorrentFileTree.File("a1b", 0, 0) < TorrentFileTree.File("a10b", 0, 0)
    assert TorrentFileTree.File("a10b", 0, 0) < TorrentFileTree.File("b10b", 0, 0)
    assert TorrentFileTree.File("a10b", 0, 0) <= TorrentFileTree.File("a010b", 0, 0)
    assert TorrentFileTree.File("a10b", 0, 0) == TorrentFileTree.File("a010b", 0, 0)
    assert TorrentFileTree.File("a10b", 0, 0) >= TorrentFileTree.File("a010b", 0, 0)
    assert TorrentFileTree.File("a010c", 0, 0) > TorrentFileTree.File("a10b", 0, 0)
    assert TorrentFileTree.File("a010c", 0, 0) > TorrentFileTree.File("a0010b", 0, 0)


def test_create_from_flat_torrent(file_storage_ubuntu):
    """
    Test if we can correctly represent a torrent with a single file.
    """
    tree = TorrentFileTree.from_lt_file_storage(file_storage_ubuntu)

    assert len(tree.root.directories) == 0
    assert len(tree.root.files) == 1
    assert tree.root.files[0].index == 0
    assert tree.root.files[0].name == "ubuntu-15.04-desktop-amd64.iso"
    assert tree.root.files[0].size == tree.root.size == 1150844928


def test_create_from_torrent_wdirs(file_storage_with_dirs):
    """
    Test if we can correctly represent a torrent with multiple files and directories.
    """
    tree = TorrentFileTree.from_lt_file_storage(file_storage_with_dirs)

    assert len(tree.root.directories) == 1
    assert len(tree.root.files) == 0
    assert tree.root.size == 36
    assert tree.root.directories["torrent_create"].collapsed


def test_create_from_torrent_wdirs_expand(file_storage_with_dirs):
    """
    Test if we can expand directories.
    """
    tree = TorrentFileTree.from_lt_file_storage(file_storage_with_dirs)
    tree.expand(Path("") / "torrent_create")
    subdir = tree.root.directories["torrent_create"]

    assert len(subdir.directories) == 2
    assert len(subdir.files) == 1
    assert subdir.size == 36
    assert not subdir.collapsed


def test_create_from_torrent_wdirs_collapse(file_storage_with_dirs):
    """
    Test if we can collapse directories, remembering the uncollapsed state of child directories.
    """
    tree = TorrentFileTree.from_lt_file_storage(file_storage_with_dirs)
    tree.expand(Path("") / "torrent_create" / "abc")
    subdir = tree.root.directories["torrent_create"]

    tree.collapse(Path("") / "torrent_create")

    assert len(tree.root.directories) == 1
    assert len(tree.root.files) == 0
    assert tree.root.size == 36
    assert subdir.collapsed
    assert not subdir.directories["abc"].collapsed  # Note: this is not visible to the user!


def test_expand_drop_nonexistent(file_storage_with_dirs):
    """
    Test if we expand the directory up to the point where we have it.

    This is edge-case behavior.
    """
    tree = TorrentFileTree.from_lt_file_storage(file_storage_with_dirs)
    subdir = tree.root.directories["torrent_create"].directories["abc"]

    tree.expand(Path("") / "torrent_create" / "abc" / "idontexist")

    assert not tree.root.directories["torrent_create"].collapsed
    assert not subdir.collapsed


def test_collapse_drop_nonexistent(file_storage_with_dirs):
    """
    Test if we collapse the directory only if it exists.

    This is edge-case behavior.
    """
    tree = TorrentFileTree.from_lt_file_storage(file_storage_with_dirs)
    tree.expand(Path("") / "torrent_create" / "abc")
    subdir = tree.root.directories["torrent_create"].directories["abc"]

    tree.collapse(Path("") / "torrent_create" / "abc" / "idontexist")

    assert not subdir.collapsed


def test_to_str_flat(file_storage_ubuntu):
    """
    Test if we can print trees with a single file.
    """
    tree = TorrentFileTree.from_lt_file_storage(file_storage_ubuntu)
    expected = """TorrentFileTree(
Directory('',
	directories=[],
	files=[
		File(0, ubuntu-15.04-desktop-amd64.iso, 1150844928 bytes)], 1150844928 bytes)
)"""

    assert expected == str(tree)


def test_to_str_wdirs_collapsed(file_storage_with_dirs):
    """
    Test if we can print trees with a collapsed directories.
    """
    tree = TorrentFileTree.from_lt_file_storage(file_storage_with_dirs)
    expected = """TorrentFileTree(
Directory('',
	directories=[
		CollapsedDirectory('torrent_create', 36 bytes)
	],
	files=[], 36 bytes)
)"""

    assert expected == str(tree)


def test_to_str_wdirs_expanded(file_storage_with_dirs):
    """
    Test if we can print trees with files and collapsed and uncollapsed directories.
    """
    tree = TorrentFileTree.from_lt_file_storage(file_storage_with_dirs)
    tree.expand(Path("") / "torrent_create")
    tree.expand(Path("") / "torrent_create" / "def")
    expected = """TorrentFileTree(
Directory('',
	directories=[
		Directory('torrent_create',
			directories=[
				CollapsedDirectory('abc', 18 bytes),
				Directory('def',
					directories=[],
					files=[
						File(4, file5.txt, 6 bytes)
						File(3, file6.avi, 6 bytes)], 12 bytes)
			],
			files=[
				File(5, file1.txt, 6 bytes)], 36 bytes)
	],
	files=[], 36 bytes)
)"""

    assert expected == str(tree)


def test_get_dir(file_storage_with_dirs):
    """
    Tests if we can retrieve a Directory instance.
    """
    tree = TorrentFileTree.from_lt_file_storage(file_storage_with_dirs)

    result = tree.find(Path("") / "torrent_create")

    assert isinstance(result, TorrentFileTree.Directory)
    assert len(result.directories) == 2
    assert len(result.files) == 1
    assert result.collapsed


def test_get_file(file_storage_with_dirs):
    """
    Tests if we can retrieve a File instance.
    """
    tree = TorrentFileTree.from_lt_file_storage(file_storage_with_dirs)

    result = tree.find(Path("") / "torrent_create" / "def" / "file6.avi")

    assert isinstance(result, TorrentFileTree.File)
    assert result.size == 6
    assert result.name == "file6.avi"
    assert result.index == 3


def test_get_none(file_storage_with_dirs):
    """
    Tests if we get a None result when getting a non-existent Path.
    """
    tree = TorrentFileTree.from_lt_file_storage(file_storage_with_dirs)

    result = tree.find(Path("") / "torrent_create" / "def" / "file6.txt")

    assert result is None


def test_get_from_empty():
    """
    Tests if we get a None result when getting from an empty folder.
    """
    tree = TorrentFileTree(None)

    result = tree.find(Path("") / "file.txt")

    assert result is None


def test_is_dir_dir(file_storage_with_dirs):
    """
    Tests if we correctly classify a Directory instance as a dir.
    """
    tree = TorrentFileTree.from_lt_file_storage(file_storage_with_dirs)

    result = tree.path_is_dir(Path("") / "torrent_create")

    assert result


def test_is_dir_file(file_storage_with_dirs):
    """
    Tests if we correctly classify a File to not be a dir.
    """
    tree = TorrentFileTree.from_lt_file_storage(file_storage_with_dirs)

    result = tree.path_is_dir(Path("") / "torrent_create" / "def" / "file6.avi")

    assert not result


def test_is_dir_none(file_storage_with_dirs):
    """
    Tests if we correctly classify a non-existent Path to not be a dir.
    """
    tree = TorrentFileTree.from_lt_file_storage(file_storage_with_dirs)

    result = tree.path_is_dir(Path("") / "torrent_create" / "def" / "file6.txt")

    assert not result


def test_find_next_dir_next_in_list(file_storage_with_dirs):
    """
    Test if we can get the full path of the next dir in a list of dirs.
    """
    tree = TorrentFileTree.from_lt_file_storage(file_storage_with_dirs)

    _, path = tree.find_next_directory(Path("") / "torrent_create" / "abc")

    assert path == Path("torrent_create") / "def"


def test_find_next_dir_last_in_torrent(file_storage_with_dirs):
    """
    Test if we can get the directory after the final directory is None.
    """
    tree = TorrentFileTree.from_lt_file_storage(file_storage_with_dirs)

    result = tree.find_next_directory(Path("") / "torrent_create")

    assert result is None


def test_find_next_dir_jump_to_files(file_storage_with_dirs):
    """
    Test if we can get the directory after reaching the final directory in a list of subdirectories.

    From torrent_create/abc/newdir we should jump up to torrent_create/abc.
    """
    tree = TorrentFileTree.from_lt_file_storage(file_storage_with_dirs)

    _, path = tree.find_next_directory(Path("") / "torrent_create" / "def")

    assert path == Path("torrent_create") / "file1.txt"


def test_view_lbl_flat(file_storage_ubuntu):
    """
    Test if we can loop through a single-file torrent line-by-line.
    """
    tree = TorrentFileTree.from_lt_file_storage(file_storage_ubuntu)

    results = []
    result = ""
    while result := tree.view(Path(result), 1):
        result, = result
        results.append(result)

    assert results == ["ubuntu-15.04-desktop-amd64.iso"]


def test_view_lbl_collapsed(file_storage_with_dirs):
    """
    Test if we can loop through a collapsed torrent line-by-line.
    """
    tree = TorrentFileTree.from_lt_file_storage(file_storage_with_dirs)

    results = []
    result = ""
    while result := tree.view(Path(result), 1):
        result, = result
        results.append(result)

    assert results == ["torrent_create"]


def test_view_lbl_expanded(file_storage_with_dirs):
    """
    Test if we can loop through a expanded torrent line-by-line.
    """
    tree = TorrentFileTree.from_lt_file_storage(file_storage_with_dirs)
    tree.expand(Path("") / "torrent_create" / "abc")
    tree.expand(Path("") / "torrent_create" / "def")

    results = []
    result = ""
    while result := tree.view(Path(result), 1):
        result, = result
        results.append(Path(result))

    assert results == [
        Path("torrent_create"),
        Path("torrent_create") / "abc",
        Path("torrent_create") / "abc" / "file2.txt",
        Path("torrent_create") / "abc" / "file3.txt",
        Path("torrent_create") / "abc" / "file4.txt",
        Path("torrent_create") / "def",
        Path("torrent_create") / "def" / "file5.txt",
        Path("torrent_create") / "def" / "file6.avi",
        Path("torrent_create") / "file1.txt"
    ]


def test_view_2_expanded(file_storage_with_dirs):
    """
    Test if we can loop through an expanded torrent with a view of two items.
    """
    tree = TorrentFileTree.from_lt_file_storage(file_storage_with_dirs)
    tree.expand(Path("") / "torrent_create" / "abc")
    tree.expand(Path("") / "torrent_create" / "def")

    results = []
    result = [""]
    while result := tree.view(Path(result[-1]), 2):
        results.append([Path(r) for r in result])

    assert results == [
        [Path("torrent_create"), Path("torrent_create") / "abc"],
        [Path("torrent_create") / "abc" / "file2.txt", Path("torrent_create") / "abc" / "file3.txt",],
        [Path("torrent_create") / "abc" / "file4.txt", Path("torrent_create") / "def"],
        [Path("torrent_create") / "def" / "file5.txt", Path("torrent_create") / "def" / "file6.avi"],
        [Path("torrent_create") / "file1.txt"]
    ]


def test_view_full_expanded(file_storage_with_dirs):
    """
    Test if we can loop through a expanded torrent with a view the size of the tree.
    """
    tree = TorrentFileTree.from_lt_file_storage(file_storage_with_dirs)
    tree.expand(Path("") / "torrent_create" / "abc")
    tree.expand(Path("") / "torrent_create" / "def")

    result = tree.view(Path(""), 9)

    assert [Path(r) for r in result] == [
        Path("torrent_create"),
        Path("torrent_create") / "abc",
        Path("torrent_create") / "abc" / "file2.txt",
        Path("torrent_create") / "abc" / "file3.txt",
        Path("torrent_create") / "abc" / "file4.txt",
        Path("torrent_create") / "def",
        Path("torrent_create") / "def" / "file5.txt",
        Path("torrent_create") / "def" / "file6.avi",
        Path("torrent_create") / "file1.txt"
    ]


def test_view_over_expanded(file_storage_with_dirs):
    """
    Test if we can loop through an expanded torrent with a view larger than the size of the tree.
    """
    tree = TorrentFileTree.from_lt_file_storage(file_storage_with_dirs)
    tree.expand(Path("") / "torrent_create" / "abc")
    tree.expand(Path("") / "torrent_create" / "def")

    result = tree.view(Path(""), 10)

    assert [Path(r) for r in result] == [
        Path("torrent_create"),
        Path("torrent_create") / "abc",
        Path("torrent_create") / "abc" / "file2.txt",
        Path("torrent_create") / "abc" / "file3.txt",
        Path("torrent_create") / "abc" / "file4.txt",
        Path("torrent_create") / "def",
        Path("torrent_create") / "def" / "file5.txt",
        Path("torrent_create") / "def" / "file6.avi",
        Path("torrent_create") / "file1.txt"
    ]
