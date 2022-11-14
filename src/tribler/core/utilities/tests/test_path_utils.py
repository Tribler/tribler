import pytest

from tribler.core.utilities.path_util import Path, tail


def test_put_path_relative(tmpdir):
    assert Path(tmpdir).normalize_to(None) == Path(tmpdir)
    assert Path(tmpdir).normalize_to('') == Path(tmpdir)
    assert Path(tmpdir).normalize_to('1/2') == Path(tmpdir)

    assert Path(tmpdir / '1').normalize_to(tmpdir) == Path('1')


def test_normalize_to(tmpdir):
    assert Path(tmpdir).normalize_to(None) == Path(tmpdir)
    assert Path(tmpdir).normalize_to('') == Path(tmpdir)
    assert Path(tmpdir / '1' / '2').normalize_to(Path(tmpdir)) == Path('1') / '2'


def test_tail_no_file():
    """Test that in the case of missed file, an exception raises"""
    with pytest.raises(FileNotFoundError):
        tail('missed_file.txt')


def test_tail_small_file(tmpdir: Path):
    """Test that tail works correct with a small file """
    log_file = tmpdir / 'log.txt'
    log_file.write_text('text', 'utf-8')
    assert tail(log_file) == 'text'


def test_tail_count(tmpdir: Path):
    """Test that tail returns desired count of lines"""
    log_file = tmpdir / 'log.txt'

    # add 100 lines
    content = '\n'.join(f'{i}' for i in range(100))
    log_file.write_text(content, 'utf-8')

    assert tail(log_file, 0) == ''
    assert tail(log_file, 1) == '99'
    assert tail(log_file, 2) == '98\n99'
    assert tail(log_file, 1000) == content

    with pytest.raises(ValueError):
        tail(log_file, -1)


def test_tail_encodings(tmpdir: Path):
    """Test that the `tail` function can read logs with "utf-8", "ascii", "latin-1" encodings """
    encodings = ["utf-8", "ascii", "latin-1"]
    log_files = []

    content = '\n'.join(f'{i}' for i in range(100))

    # create files for all available encodings
    for encoding in encodings:
        path = tmpdir / encoding
        path.write_text(content, encoding)
        log_files.append(path)

    # make sure they were read all encoding correctly
    for log in log_files:
        assert tail(log, 100) == content
