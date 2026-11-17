from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field

DeliveryAppOrigin = Literal["partner_99", "ifood", "keeta"]
AppRuleType = Literal["commission", "fee", "freight", "store_discount", "deduction"]
CalculationType = Literal["percentage", "fixed"]

class AppFinanceConfigIn(BaseModel):
    app_key: DeliveryAppOrigin
    app_name: str = Field(min_length=2, max_length=120)
    active: bool = True

class AppFinanceRuleIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    rule_type: AppRuleType
    calculation_type: CalculationType
    value: Decimal = Field(ge=0, max_digits=20, decimal_places=2)
    sort_order: int = Field(default=0, ge=0, le=1000)
    active: bool = True

class AppFinanceRuleOut(AppFinanceRuleIn):
    id: str

class AppFinanceConfigOut(AppFinanceConfigIn):
    id: str
    rules: list[AppFinanceRuleOut] = Field(default_factory=list)

