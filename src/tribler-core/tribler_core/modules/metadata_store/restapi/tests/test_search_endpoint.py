import pytest

from tribler_core.restapi.base_api_test import do_request


@pytest.mark.asyncio
async def test_search_no_query(enable_chant, enable_api, session):  # pylint: disable=unused-argument
    """
    Testing whether the API returns an error 400 if no query is passed when doing a search
    """
    await do_request(session, 'search', expected_code=400)


@pytest.mark.asyncio
async def test_search_wrong_mdtype(enable_chant, enable_api, session):  # pylint: disable=unused-argument
    """
    Testing whether the API returns an error 400 if wrong metadata type is passed in the query
    """
    await do_request(session, 'search?txt_filter=bla&metadata_type=ddd', expected_code=400)


@pytest.mark.asyncio
async def test_search(needle_in_haystack):
    """
    Test a search query that should return a few new type channels
    """
    session = needle_in_haystack

    parsed = await do_request(session, 'search?txt_filter=needle', expected_code=200)
    assert len(parsed["results"]) == 1

    parsed = await do_request(session, 'search?txt_filter=hay', expected_code=200)
    assert len(parsed["results"]) == 50

    parsed = await do_request(session, 'search?txt_filter=test&type=channel', expected_code=200)
    assert len(parsed["results"]) == 1

    parsed = await do_request(session, 'search?txt_filter=needle&type=torrent', expected_code=200)
    assert parsed["results"][0]['name'] == 'needle'

    parsed = await do_request(session, 'search?txt_filter=needle&sort_by=name', expected_code=200)
    assert len(parsed["results"]) == 1

    parsed = await do_request(session, 'search?txt_filter=needle%2A&sort_by=name&sort_desc=1', expected_code=200)
    assert len(parsed["results"]) == 2
    assert parsed["results"][0]['name'] == "needle2"


@pytest.mark.asyncio
async def test_search_with_include_total_and_max_rowid(needle_in_haystack):
    """
    Test search queries with include_total and max_rowid options
    """
    session = needle_in_haystack

    parsed = await do_request(session, 'search?txt_filter=needle', expected_code=200)
    assert len(parsed["results"]) == 1
    assert "total" not in parsed
    assert "max_rowid" not in parsed

    parsed = await do_request(session, 'search?txt_filter=needle&include_total=1', expected_code=200)
    assert parsed["total"] == 1
    assert parsed["max_rowid"] == 103

    parsed = await do_request(session, 'search?txt_filter=hay&include_total=1', expected_code=200)
    assert parsed["total"] == 100
    assert parsed["max_rowid"] == 103

    parsed = await do_request(session, 'search?txt_filter=hay', expected_code=200)
    assert len(parsed["results"]) == 50

    parsed = await do_request(session, 'search?txt_filter=hay&max_rowid=0', expected_code=200)
    assert len(parsed["results"]) == 0

    parsed = await do_request(session, 'search?txt_filter=hay&max_rowid=20', expected_code=200)
    assert len(parsed["results"]) == 19

    parsed = await do_request(session, 'search?txt_filter=needle&sort_by=name', expected_code=200)
    assert len(parsed["results"]) == 1

    parsed = await do_request(session, 'search?txt_filter=needle&sort_by=name&max_rowid=20', expected_code=200)
    assert len(parsed["results"]) == 0

    parsed = await do_request(session, 'search?txt_filter=needle&sort_by=name&max_rowid=200', expected_code=200)
    assert len(parsed["results"]) == 1


@pytest.mark.asyncio
async def test_completions_no_query(enable_chant, enable_api, session):  # pylint: disable=unused-argument
    """
    Testing whether the API returns an error 400 if no query is passed when getting search completion terms
    """
    await do_request(session, 'search/completions', expected_code=400)


@pytest.mark.asyncio
async def test_completions(enable_chant, enable_api, session):  # pylint: disable=unused-argument
    """
    Testing whether the API returns the right terms when getting search completion terms
    """
    json_response = await do_request(session, 'search/completions?q=tribler', expected_code=200)
    assert json_response['completions'] == []
