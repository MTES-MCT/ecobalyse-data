from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


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
    etf_c: float = Field(default=0, alias="etf-c")
    fru: float = 0
    fwe: float = 0
    htc: float = 0
    htc_c: float = Field(default=0, alias="htc-c")
    htn: float = 0
    htn_c: float = Field(default=0, alias="htn-c")
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
    alias: Optional[str] = None
    categories: List[str]
    comment: str
    density: float = Field(ge=0)
    displayName: Optional[str] = None
    elec_MJ: float = Field(ge=0)
    heat_MJ: float = Field(ge=0)
    id: UUID
    sourceId: Optional[str] = None
    impacts: Impacts
    name: str
    source: str
    unit: Optional[UnitEnum]
    waste: float = Field(ge=0, le=1)

    class Config:
        use_enum_values = True
        populate_by_name = True


class BwProcess(BaseModel):
    categories: List[str]
    comment: str
    impacts: Optional[Impacts] = None
    name: str
    source: str
    # Process identifier in Simapro
    sourceId: Optional[str] = None
    unit: Optional[UnitEnum]

    class Config:
        populate_by_name = True
        use_enum_values = True
