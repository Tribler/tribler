from pathlib import Path

from tribler.core.components.reporter.reported_error import ReportedError


def test_get_filename():
    reported_error = ReportedError('type', 'text', {})
    assert reported_error.get_filename() == f"{reported_error.created_at}-{reported_error.type}.json"


def test_serialize_deserialize():
    reported_error = ReportedError('type', 'text', {})
    serialized_error = reported_error.serialize()
    deserialized_error = ReportedError.deserialize(serialized_error)
    assert deserialized_error == reported_error

    serialized_error_with_change = reported_error.serialize(should_stop=False)
    deserialized_error_with_change = ReportedError.deserialize(serialized_error_with_change)
    assert deserialized_error_with_change == reported_error.copy(should_stop=False)


def test_copy():
    reported_error = ReportedError('type', 'text', {})
    copied_error = reported_error.copy()
    assert copied_error == reported_error

    copied_error_with_change = reported_error.copy(should_stop=False)
    assert copied_error_with_change == reported_error.copy(should_stop=False)


def test_save_to_dir(tmp_path):
    reported_error = ReportedError('type', 'text', {})
    reported_error.save_to_dir(tmp_path)
    file_path = tmp_path / reported_error.get_filename()
    assert file_path.exists()
    assert file_path.read_text() == reported_error.serialized_copy().serialize()


def test_load_from_file(tmp_path):
    reported_error = ReportedError('type', 'text', {})
    reported_error.save_to_dir(tmp_path)
    file_path = tmp_path / reported_error.get_filename()
    loaded_error = ReportedError.load_from_file(file_path)
    assert loaded_error == reported_error.serialized_copy()


def test_load_errors_from_dir(tmp_path):
    """
    Test that load_errors_from_dir returns the correct list of errors.
    """
    loaded_errors = ReportedError.load_errors_from_dir(None)
    print(loaded_errors)

    loaded_errors = ReportedError.load_errors_from_dir(Path('non-existent-dir'))
    assert loaded_errors == []

    reported_error = ReportedError('type', 'text', {})
    reported_error.save_to_dir(tmp_path)
    file_path = tmp_path / reported_error.get_filename()
    loaded_errors = ReportedError.load_errors_from_dir(tmp_path)
    assert loaded_errors == [(file_path, reported_error.serialized_copy())]
