from pathlib import Path

from ipv8.test.base import TestBase

from tribler.core.libtorrent.torrent_file_tree import TorrentFileTree
from tribler.test_unit.core.libtorrent.mocks import TORRENT_UBUNTU_FILE, TORRENT_WITH_DIRS


class TestTorrentFileTree(TestBase):
    """
    Tests for the TorrentFileTree class.
    """

    def test_file_natsort_numbers(self) -> None:
        """
        Test the natural sorting of File instances for numbers only.
        """
        self.assertLess(TorrentFileTree.File("01", 0, 0), TorrentFileTree.File("10", 0, 0))
        self.assertLessEqual(TorrentFileTree.File("010", 0, 0), TorrentFileTree.File("10", 0, 0))
        self.assertEqual(TorrentFileTree.File("010", 0, 0), TorrentFileTree.File("10", 0, 0))
        self.assertGreaterEqual(TorrentFileTree.File("010", 0, 0), TorrentFileTree.File("10", 0, 0))
        self.assertGreater(TorrentFileTree.File("011", 0, 0), TorrentFileTree.File("10", 0, 0))
        self.assertGreater(TorrentFileTree.File("11", 0, 0), TorrentFileTree.File("10", 0, 0))
        self.assertNotEqual(TorrentFileTree.File("11", 0, 0), TorrentFileTree.File("10", 0, 0))

    def test_file_natsort_compound(self) -> None:
        """
        Test the natural sorting of File instances for names mixing numbers and text.
        """
        self.assertNotEqual(TorrentFileTree.File("a1b", 0, 0), TorrentFileTree.File("a10b", 0, 0))
        self.assertLess(TorrentFileTree.File("a1b", 0, 0), TorrentFileTree.File("a10b", 0, 0))
        self.assertLess(TorrentFileTree.File("a10b", 0, 0), TorrentFileTree.File("b10b", 0, 0))
        self.assertLessEqual(TorrentFileTree.File("a10b", 0, 0), TorrentFileTree.File("a010b", 0, 0))
        self.assertEqual(TorrentFileTree.File("a10b", 0, 0), TorrentFileTree.File("a010b", 0, 0))
        self.assertGreaterEqual(TorrentFileTree.File("a10b", 0, 0), TorrentFileTree.File("a010b", 0, 0))
        self.assertGreater(TorrentFileTree.File("a010c", 0, 0), TorrentFileTree.File("a10b", 0, 0))
        self.assertGreater(TorrentFileTree.File("a010c", 0, 0), TorrentFileTree.File("a0010b", 0, 0))

    def test_create_from_flat_torrent(self) -> None:
        """
        Test if we can correctly represent a torrent with a single file.
        """
        tree = TorrentFileTree.from_lt_file_storage(TORRENT_UBUNTU_FILE.files())

        self.assertEqual(0, len(tree.root.directories))
        self.assertEqual(1, len(tree.root.files))
        self.assertEqual(0, tree.root.files[0].index)
        self.assertEqual("ubuntu-15.04-desktop-amd64.iso", tree.root.files[0].name)
        self.assertEqual(1150844928, tree.root.files[0].size)
        self.assertEqual(1150844928, tree.root.size)

    def test_create_from_torrent_wdirs(self) -> None:
        """
        Test if we can correctly represent a torrent with multiple files and directories.
        """
        tree = TorrentFileTree.from_lt_file_storage(TORRENT_WITH_DIRS.files())

        self.assertEqual(1, len(tree.root.directories))
        self.assertEqual(0, len(tree.root.files))
        self.assertEqual(36, tree.root.size)
        self.assertTrue(tree.root.directories["torrent_create"].collapsed)

    def test_create_from_torrent_wdirs_expand(self) -> None:
        """
        Test if we can expand directories.
        """
        tree = TorrentFileTree.from_lt_file_storage(TORRENT_WITH_DIRS.files())
        tree.expand(Path("") / "torrent_create")
        subdir = tree.root.directories["torrent_create"]

        self.assertEqual(2, len(subdir.directories))
        self.assertEqual(1, len(subdir.files))
        self.assertEqual(36, subdir.size)
        self.assertFalse(subdir.collapsed)

    def test_create_from_torrent_wdirs_collapse(self) -> None:
        """
        Test if we can collapse directories, remembering the uncollapsed state of child directories.
        """
        tree = TorrentFileTree.from_lt_file_storage(TORRENT_WITH_DIRS.files())
        tree.expand(Path("") / "torrent_create" / "abc")
        subdir = tree.root.directories["torrent_create"]

        tree.collapse(Path("") / "torrent_create")

        self.assertEqual(1, len(tree.root.directories))
        self.assertEqual(0, len(tree.root.files))
        self.assertEqual(36, tree.root.size)
        self.assertTrue(subdir.collapsed)
        self.assertFalse(subdir.directories["abc"].collapsed)  # Note: this is not visible to the user!

    def test_expand_drop_nonexistent(self) -> None:
        """
        Test if we expand the directory up to the point where we have it.

        This is edge-case behavior.
        """
        tree = TorrentFileTree.from_lt_file_storage(TORRENT_WITH_DIRS.files())
        subdir = tree.root.directories["torrent_create"].directories["abc"]

        tree.expand(Path("") / "torrent_create" / "abc" / "idontexist")

        self.assertFalse(tree.root.directories["torrent_create"].collapsed)
        self.assertFalse(subdir.collapsed)

    def test_collapse_drop_nonexistent(self) -> None:
        """
        Test if we collapse the directory only if it exists.

        This is edge-case behavior.
        """
        tree = TorrentFileTree.from_lt_file_storage(TORRENT_WITH_DIRS.files())
        tree.expand(Path("") / "torrent_create" / "abc")
        subdir = tree.root.directories["torrent_create"].directories["abc"]

        tree.collapse(Path("") / "torrent_create" / "abc" / "idontexist")

        self.assertFalse(subdir.collapsed)

    def test_to_str_flat(self) -> None:
        """
        Test if we can print trees with a single file.
        """
        tree = TorrentFileTree.from_lt_file_storage(TORRENT_UBUNTU_FILE.files())
        expected = """TorrentFileTree(
Directory('',
\tdirectories=[],
\tfiles=[
\t\tFile(0, ubuntu-15.04-desktop-amd64.iso, 1150844928 bytes)], 1150844928 bytes)
)"""

        self.assertEqual(expected, str(tree))

    def test_to_str_wdirs_collapsed(self) -> None:
        """
        Test if we can print trees with a collapsed directories.
        """
        tree = TorrentFileTree.from_lt_file_storage(TORRENT_WITH_DIRS.files())
        expected = """TorrentFileTree(
Directory('',
\tdirectories=[
\t\tCollapsedDirectory('torrent_create', 36 bytes)
\t],
\tfiles=[], 36 bytes)
)"""

        self.assertEqual(expected, str(tree))

    def test_to_str_wdirs_expanded(self) -> None:
        """
        Test if we can print trees with files and collapsed and uncollapsed directories.
        """
        tree = TorrentFileTree.from_lt_file_storage(TORRENT_WITH_DIRS.files())
        tree.expand(Path("") / "torrent_create")
        tree.expand(Path("") / "torrent_create" / "def")
        expected = """TorrentFileTree(
Directory('',
\tdirectories=[
\t\tDirectory('torrent_create',
\t\t\tdirectories=[
\t\t\t\tCollapsedDirectory('abc', 18 bytes),
\t\t\t\tDirectory('def',
\t\t\t\t\tdirectories=[],
\t\t\t\t\tfiles=[
\t\t\t\t\t\tFile(4, file5.txt, 6 bytes)
\t\t\t\t\t\tFile(3, file6.avi, 6 bytes)], 12 bytes)
\t\t\t],
\t\t\tfiles=[
\t\t\t\tFile(5, file1.txt, 6 bytes)], 36 bytes)
\t],
\tfiles=[], 36 bytes)
)"""

        self.assertEqual(expected, str(tree))

    def test_get_dir(self) -> None:
        """
        Tests if we can retrieve a Directory instance.
        """
        tree = TorrentFileTree.from_lt_file_storage(TORRENT_WITH_DIRS.files())

        result = tree.find(Path("") / "torrent_create")

        self.assertIsInstance(result, TorrentFileTree.Directory)
        self.assertEqual(2, len(result.directories))
        self.assertEqual(1, len(result.files))
        self.assertTrue(result.collapsed)

    def test_get_file(self) -> None:
        """
        Tests if we can retrieve a File instance.
        """
        tree = TorrentFileTree.from_lt_file_storage(TORRENT_WITH_DIRS.files())

        result = tree.find(Path("") / "torrent_create" / "def" / "file6.avi")

        self.assertIsInstance(result, TorrentFileTree.File)
        self.assertEqual(6, result.size)
        self.assertEqual("file6.avi", result.name)
        self.assertEqual(3, result.index)

    def test_get_none(self) -> None:
        """
        Tests if we get a None result when getting a non-existent Path.
        """
        tree = TorrentFileTree.from_lt_file_storage(TORRENT_WITH_DIRS.files())

        result = tree.find(Path("") / "torrent_create" / "def" / "file6.txt")

        self.assertIsNone(result)

    def test_get_from_empty(self) -> None:
        """
        Tests if we get a None result when getting from an empty folder.
        """
        tree = TorrentFileTree(None)

        result = tree.find(Path("") / "file.txt")

        self.assertIsNone(result)

    def test_is_dir_dir(self) -> None:
        """
        Tests if we correctly classify a Directory instance as a dir.
        """
        tree = TorrentFileTree.from_lt_file_storage(TORRENT_WITH_DIRS.files())

        result = tree.path_is_dir(Path("") / "torrent_create")

        self.assertTrue(result)

    def test_is_dir_file(self) -> None:
        """
        Tests if we correctly classify a File to not be a dir.
        """
        tree = TorrentFileTree.from_lt_file_storage(TORRENT_WITH_DIRS.files())

        result = tree.path_is_dir(Path("") / "torrent_create" / "def" / "file6.avi")

        self.assertFalse(result)

    def test_is_dir_none(self) -> None:
        """
        Tests if we correctly classify a non-existent Path to not be a dir.
        """
        tree = TorrentFileTree.from_lt_file_storage(TORRENT_WITH_DIRS.files())

        result = tree.path_is_dir(Path("") / "torrent_create" / "def" / "file6.txt")

        self.assertFalse(result)

    def test_find_next_dir_next_in_list(self) -> None:
        """
        Test if we can get the full path of the next dir in a list of dirs.
        """
        tree = TorrentFileTree.from_lt_file_storage(TORRENT_WITH_DIRS.files())

        _, path = tree.find_next_directory(Path("") / "torrent_create" / "abc")

        self.assertEqual(Path("torrent_create") / "def", path)

    def test_find_next_dir_last_in_torrent(self) -> None:
        """
        Test if we can get the directory after the final directory is None.
        """
        tree = TorrentFileTree.from_lt_file_storage(TORRENT_WITH_DIRS.files())

        result = tree.find_next_directory(Path("") / "torrent_create")

        self.assertIsNone(result)

    def test_find_next_dir_jump_to_files(self) -> None:
        """
        Test if we can get the directory after reaching the final directory in a list of subdirectories.

        From torrent_create/abc/newdir we should jump up to torrent_create/abc.
        """
        tree = TorrentFileTree.from_lt_file_storage(TORRENT_WITH_DIRS.files())

        _, path = tree.find_next_directory(Path("") / "torrent_create" / "def")

        self.assertEqual(Path("torrent_create") / "file1.txt", path)

    def test_view_lbl_flat(self) -> None:
        """
        Test if we can loop through a single-file torrent line-by-line.
        """
        tree = TorrentFileTree.from_lt_file_storage(TORRENT_UBUNTU_FILE.files())

        results = []
        result = ""
        while result := tree.view(Path(result), 1):
            result, = result
            results.append(result)

        self.assertEqual(["ubuntu-15.04-desktop-amd64.iso"], results)

    def test_view_lbl_collapsed(self) -> None:
        """
        Test if we can loop through a collapsed torrent line-by-line.
        """
        tree = TorrentFileTree.from_lt_file_storage(TORRENT_WITH_DIRS.files())

        results = []
        result = ""
        while result := tree.view(Path(result), 1):
            result, = result
            results.append(result)

        self.assertEqual(["torrent_create"], results)

    def test_view_lbl_expanded(self) -> None:
        """
        Test if we can loop through a expanded torrent line-by-line.
        """
        tree = TorrentFileTree.from_lt_file_storage(TORRENT_WITH_DIRS.files())
        tree.expand(Path("") / "torrent_create" / "abc")
        tree.expand(Path("") / "torrent_create" / "def")

        results = []
        result = ""
        while result := tree.view(Path(result), 1):
            result, = result
            results.append(Path(result))

        self.assertEqual([
            Path("torrent_create"),
            Path("torrent_create") / "abc",
            Path("torrent_create") / "abc" / "file2.txt",
            Path("torrent_create") / "abc" / "file3.txt",
            Path("torrent_create") / "abc" / "file4.txt",
            Path("torrent_create") / "def",
            Path("torrent_create") / "def" / "file5.txt",
            Path("torrent_create") / "def" / "file6.avi",
            Path("torrent_create") / "file1.txt"
        ], results)

    def test_view_2_expanded(self) -> None:
        """
        Test if we can loop through an expanded torrent with a view of two items.
        """
        tree = TorrentFileTree.from_lt_file_storage(TORRENT_WITH_DIRS.files())
        tree.expand(Path("") / "torrent_create" / "abc")
        tree.expand(Path("") / "torrent_create" / "def")

        results = []
        result = [""]
        while result := tree.view(Path(result[-1]), 2):
            results.append([Path(r) for r in result])

        self.assertEqual([
            [Path("torrent_create"), Path("torrent_create") / "abc"],
            [Path("torrent_create") / "abc" / "file2.txt", Path("torrent_create") / "abc" / "file3.txt",],
            [Path("torrent_create") / "abc" / "file4.txt", Path("torrent_create") / "def"],
            [Path("torrent_create") / "def" / "file5.txt", Path("torrent_create") / "def" / "file6.avi"],
            [Path("torrent_create") / "file1.txt"]
        ], results)

    def test_view_full_expanded(self) -> None:
        """
        Test if we can loop through a expanded torrent with a view the size of the tree.
        """
        tree = TorrentFileTree.from_lt_file_storage(TORRENT_WITH_DIRS.files())
        tree.expand(Path("") / "torrent_create" / "abc")
        tree.expand(Path("") / "torrent_create" / "def")

        result = tree.view(Path(""), 9)

        self.assertEqual([
            Path("torrent_create"),
            Path("torrent_create") / "abc",
            Path("torrent_create") / "abc" / "file2.txt",
            Path("torrent_create") / "abc" / "file3.txt",
            Path("torrent_create") / "abc" / "file4.txt",
            Path("torrent_create") / "def",
            Path("torrent_create") / "def" / "file5.txt",
            Path("torrent_create") / "def" / "file6.avi",
            Path("torrent_create") / "file1.txt"
        ], [Path(r) for r in result])

    def test_view_over_expanded(self) -> None:
        """
        Test if we can loop through an expanded torrent with a view larger than the size of the tree.
        """
        tree = TorrentFileTree.from_lt_file_storage(TORRENT_WITH_DIRS.files())
        tree.expand(Path("") / "torrent_create" / "abc")
        tree.expand(Path("") / "torrent_create" / "def")

        result = tree.view(Path(""), 10)

        self.assertEqual([
            Path("torrent_create"),
            Path("torrent_create") / "abc",
            Path("torrent_create") / "abc" / "file2.txt",
            Path("torrent_create") / "abc" / "file3.txt",
            Path("torrent_create") / "abc" / "file4.txt",
            Path("torrent_create") / "def",
            Path("torrent_create") / "def" / "file5.txt",
            Path("torrent_create") / "def" / "file6.avi",
            Path("torrent_create") / "file1.txt"
        ], [Path(r) for r in result])

    def test_view_full_collapsed(self) -> None:
        """
        Test if we can loop through a expanded directory with only collapsed dirs.
        """
        tree = TorrentFileTree.from_lt_file_storage(TORRENT_WITH_DIRS.files())
        tree.expand(Path("") / "torrent_create")

        result = tree.view(Path(""), 4)

        self.assertEqual([
            Path("torrent_create"),
            Path("torrent_create") / "abc",
            Path("torrent_create") / "def",
            Path("torrent_create") / "file1.txt"
        ], [Path(r) for r in result])

    def test_view_start_at_collapsed(self) -> None:
        """
        Test if we can form a view starting at a collapsed directory.
        """
        tree = TorrentFileTree.from_lt_file_storage(TORRENT_WITH_DIRS.files())

        tree.expand(Path("torrent_create"))

        result = tree.view(Path("torrent_create") / "abc", 2)

        self.assertEqual([Path("torrent_create") / "def", Path("torrent_create") / "file1.txt"],
                         [Path(r) for r in result])

    def test_select_start_selected(self) -> None:
        """
        Test if all files start selected.
        """
        tree = TorrentFileTree.from_lt_file_storage(TORRENT_WITH_DIRS.files())

        self.assertTrue(tree.find(Path("torrent_create") / "abc" / "file2.txt").selected)
        self.assertTrue(tree.find(Path("torrent_create") / "abc" / "file3.txt").selected)
        self.assertTrue(tree.find(Path("torrent_create") / "abc" / "file4.txt").selected)
        self.assertTrue(tree.find(Path("torrent_create") / "def" / "file5.txt").selected)
        self.assertTrue(tree.find(Path("torrent_create") / "def" / "file6.avi").selected)
        self.assertTrue(tree.find(Path("torrent_create") / "file1.txt").selected)

    def test_select_nonexistent(self) -> None:
        """
        Test selecting a non-existent path.
        """
        tree = TorrentFileTree.from_lt_file_storage(TORRENT_WITH_DIRS.files())
        tree.set_selected(Path("."), False)

        tree.set_selected(Path("I don't exist"), True)

        self.assertFalse(tree.find(Path("torrent_create") / "abc" / "file2.txt").selected)
        self.assertFalse(tree.find(Path("torrent_create") / "abc" / "file3.txt").selected)
        self.assertFalse(tree.find(Path("torrent_create") / "abc" / "file4.txt").selected)
        self.assertFalse(tree.find(Path("torrent_create") / "def" / "file5.txt").selected)
        self.assertFalse(tree.find(Path("torrent_create") / "def" / "file6.avi").selected)
        self.assertFalse(tree.find(Path("torrent_create") / "file1.txt").selected)

    def test_select_file(self) -> None:
        """
        Test selecting a path pointing to a single file.
        """
        tree = TorrentFileTree.from_lt_file_storage(TORRENT_WITH_DIRS.files())
        tree.set_selected(Path("."), False)

        tree.set_selected(Path("torrent_create") / "abc" / "file2.txt", True)

        self.assertTrue(tree.find(Path("torrent_create") / "abc" / "file2.txt").selected)
        self.assertFalse(tree.find(Path("torrent_create") / "abc" / "file3.txt").selected)
        self.assertFalse(tree.find(Path("torrent_create") / "abc" / "file4.txt").selected)
        self.assertFalse(tree.find(Path("torrent_create") / "def" / "file5.txt").selected)
        self.assertFalse(tree.find(Path("torrent_create") / "def" / "file6.avi").selected)
        self.assertFalse(tree.find(Path("torrent_create") / "file1.txt").selected)

    def test_select_flatdir(self) -> None:
        """
        Test selecting a path pointing to a directory with no subdirectories, only files.
        """
        tree = TorrentFileTree.from_lt_file_storage(TORRENT_WITH_DIRS.files())
        tree.set_selected(Path("."), False)

        tree.set_selected(Path("torrent_create") / "abc", True)

        self.assertTrue(tree.find(Path("torrent_create") / "abc" / "file2.txt").selected)
        self.assertTrue(tree.find(Path("torrent_create") / "abc" / "file3.txt").selected)
        self.assertTrue(tree.find(Path("torrent_create") / "abc" / "file4.txt").selected)
        self.assertFalse(tree.find(Path("torrent_create") / "def" / "file5.txt").selected)
        self.assertFalse(tree.find(Path("torrent_create") / "def" / "file6.avi").selected)
        self.assertFalse(tree.find(Path("torrent_create") / "file1.txt").selected)

    def test_select_deepdir(self) -> None:
        """
        Test selecting a path pointing to a directory with no bdirectories and files.
        """
        tree = TorrentFileTree.from_lt_file_storage(TORRENT_WITH_DIRS.files())
        tree.set_selected(Path("."), False)

        tree.set_selected(Path("torrent_create"), True)

        self.assertTrue(tree.find(Path("torrent_create") / "abc" / "file2.txt").selected)
        self.assertTrue(tree.find(Path("torrent_create") / "abc" / "file3.txt").selected)
        self.assertTrue(tree.find(Path("torrent_create") / "abc" / "file4.txt").selected)
        self.assertTrue(tree.find(Path("torrent_create") / "def" / "file5.txt").selected)
        self.assertTrue(tree.find(Path("torrent_create") / "def" / "file6.avi").selected)
        self.assertTrue(tree.find(Path("torrent_create") / "file1.txt").selected)
