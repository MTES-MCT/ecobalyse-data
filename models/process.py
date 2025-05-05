import uuid
from enum import Enum
from typing import Any, List, Optional

from pydantic import AfterValidator, AliasGenerator, BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel, to_snake
from typing_extensions import Annotated

from common.export import (
    validate_id,
)


class Domain(str, Enum):
    food = "food"
    object = "object"
    textile = "textile"


class EcoModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=AliasGenerator(
            validation_alias=to_snake,
            serialization_alias=to_camel,
        ),
    )


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

    model_config = ConfigDict(
        alias_generator=AliasGenerator(
            validation_alias=to_snake,
            serialization_alias=to_camel,
        ),
    )


class Cff(EcoModel):
    manufacturer_allocation: float
    recycled_quality_ratio: float


class Material(EcoModel):
    id: Annotated[str, AfterValidator(validate_id)]
    material_process_uuid: uuid.UUID
    recycled_process_uuid: Optional[uuid.UUID]
    recycled_from: Optional[str]
    name: str
    short_name: str
    origin: str
    primary: Optional[bool]
    geographic_origin: str
    default_country: str
    cff: Optional[Cff]
    process_id: uuid.UUID


class EcosystemicServices(EcoModel):
    crop_diversity: float
    hedges: float
    livestock_density: Optional[float] = None
    permanent_pasture: Optional[float] = None
    plot_size: float


class Ingredient(EcoModel):
    alias: Annotated[str, AfterValidator(validate_id)]
    categories: List[str]
    crop_group: Optional[str]
    default_origin: str
    density: float
    ecosystemic_services: Optional[EcosystemicServices]
    id: uuid.UUID
    inedible_part: float
    land_occupation: Optional[float]
    name: str
    raw_to_cooked_ratio: float
    scenario: Optional[str]
    search: str
    transport_cooling: str
    visible: bool
    process_id: uuid.UUID


class Process(EcoModel):
    bw_activity: Optional[Any]
    categories: List[str]
    comment: str
    computed_by: Optional[ComputedBy]
    density: float = 0
    display_name: str
    elec_mj: Annotated[float, Field(serialization_alias="elecMJ")]
    heat_mj: Annotated[float, Field(serialization_alias="heatMJ")]
    id: Optional[uuid.UUID]
    impacts: Optional[Impacts] = None
    scopes: List[str]
    source: str
    # Process identifier in Simapro
    source_id: str
    unit: Optional[UnitEnum]
    waste: float
