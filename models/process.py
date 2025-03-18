import uuid
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field
from typing_extensions import Annotated


class ComputedBy(str, Enum):
    brightway = "brightway"
    hardcoded = "hardcoded"
    simapro = "simapro"


class UnitEnum(str, Enum):
    KG = "kg"
    TKM = "t⋅km"
    KWH = "kWh"
    MJ = "MJ"
    L = "L"
    ITEMS = "Item(s)"
    M2 = "m2"
    M3 = "m3"


class Impacts(BaseModel):
    acd: float = 0
    cch: float = 0
    etf: float = 0
    etf_c: Annotated[float, Field(alias="etf-c")] = 0
    fru: float = 0
    fwe: float = 0
    htc: float = 0
    htc_c: Annotated[float, Field(alias="htc-c")] = 0
    htn: float = 0
    htn_c: Annotated[float, Field(alias="htn-c")] = 0
    ior: float = 0
    ldu: float = 0
    mru: float = 0
    ozd: float = 0
    pco: float = 0
    pma: float = 0
    swe: float = 0
    tre: float = 0
    wtu: float = 0
    ecs: float = 0
    pef: float = 0


class Process(BaseModel):
    bw_activity: Optional[Any]
    categories: List[str]
    comment: str
    computed_by: Optional[ComputedBy]
    density: float = 0
    displayName: str
    elecMJ: float = 0
    heatMJ: float = 0
    id: Optional[uuid.UUID]
    impacts: Optional[Impacts] = None
    name: str
    source: str
    # Process identifier in Simapro
    sourceId: Optional[str] = None
    unit: Optional[UnitEnum]
    waste: float

    class Config:
        use_enum_values = True
