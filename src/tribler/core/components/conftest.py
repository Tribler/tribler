import pytest
from aiohttp.web_app import Application

from tribler.core.components.restapi.rest.rest_manager import error_middleware


@pytest.fixture(name='web_app')
async def web_app_fixture():
    app = Application(middlewares=[error_middleware])
    yield app
    await app.shutdown()
