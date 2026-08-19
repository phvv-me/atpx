from typing import Annotated

from cyclopts import Parameter

Slug = Annotated[str, Parameter(help="the blueprint directory name")]
StatusName = Annotated[str, Parameter(help="the target lifecycle status")]
TagName = Annotated[str, Parameter(help="the strategy or pass tag inside the brackets")]
DataPath = Annotated[str, Parameter(help="path to a CSV whose named column is the target")]
ClaimRef = Annotated[
    str | None, Parameter(help="claim id of a persisted certificate in the node's ledgers")
]
