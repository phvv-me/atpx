import json

import respx

from atpx import Capability, Engine
from atpx.engines import LoogleEngine, OeisEngine
from atpx.engines.importable import is_importable
from atpx.support import drive


def test_search_engines_enroll_in_precedence_order() -> None:
    names = [engine().name for engine in Engine.supporting(Capability.SEARCH)]
    assert names == ["oeis", "loogle", "arxiv", "zbmath"]


def test_search_engines_stamp_atpx_own_version() -> None:
    assert OeisEngine().version() == LoogleEngine().version()
    assert OeisEngine().available()


@respx.mock
def test_the_async_search_seam_is_awaitable_directly() -> None:
    respx.get("https://oeis.org/search").respond(json=[{"number": 2, "name": "n."}])
    hits = json.loads(drive(OeisEngine().search("1,2")))
    assert hits[0]["id"] == "A000002"


def test_is_importable_handles_submodules_of_missing_packages() -> None:
    assert is_importable("json")
    assert not is_importable("nosuch_pkg_anywhere.sub")
