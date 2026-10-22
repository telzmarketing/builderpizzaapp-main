from datetime import datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class OpeningIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(default=0, ge=0)
    opened_at: datetime
    opening_rule: str | None = Field(default=None, min_length=1, max_length=120)
    rule_code: str | None = Field(default=None, min_length=1, max_length=80)
    container_code: str | None = Field(default=None, max_length=120)
    resulting_expires_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=500)

    @property
    def effective_rule_code(self):
        return self.opening_rule or self.rule_code or "unspecified"

class OpeningOut(BaseModel):
    id: str; lot_id: str; opened_at: str; rule_code: str; resulting_expires_at: str | None; actor_id: str

class GenealogyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_lot_id: str = Field(min_length=1, max_length=180)
    target_lot_id: str = Field(min_length=1, max_length=180)
    operation_id: str = Field(min_length=1, max_length=180)
    quantity: Decimal = Field(gt=0, max_digits=20, decimal_places=6)
    unit_id: str = Field(min_length=1, max_length=180)
    relation_type: Literal["transformation", "split", "merge"] = "transformation"

class GenealogyOut(GenealogyIn):
    id: str; actor_id: str; created_at: str

class GenealogyPage(BaseModel):
    items: list[GenealogyOut]
