from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4
from sqlalchemy.orm import Session
from backend.core.exceptions import DomainError
from backend.models.app_finance import DeliveryAppFinanceConfig, DeliveryAppFinanceRule
from backend.schemas.app_finance import AppFinanceConfigIn, AppFinanceRuleIn

CENT = Decimal("0.01")
class DeliveryAppFinanceService:
    def __init__(self, db: Session, tenant_id: str): self.db, self.tenant_id = db, tenant_id
    def _config(self, config_id: str):
        row = self.db.query(DeliveryAppFinanceConfig).filter_by(id=config_id, tenant_id=self.tenant_id).first()
        if not row: raise DomainError("Configuração do aplicativo não encontrada.", code="AppFinanceConfigNotFound")
        return row
    def list(self):
        rows = self.db.query(DeliveryAppFinanceConfig).filter_by(tenant_id=self.tenant_id).order_by(DeliveryAppFinanceConfig.app_name).all()
        return [self._out(row) for row in rows]
    def create(self, body: AppFinanceConfigIn):
        if self.db.query(DeliveryAppFinanceConfig).filter_by(tenant_id=self.tenant_id, app_key=body.app_key).first():
            raise DomainError("Aplicativo já cadastrado.", code="AppFinanceConfigDuplicate")
        row = DeliveryAppFinanceConfig(id=str(uuid4()), tenant_id=self.tenant_id, **body.model_dump()); self.db.add(row); self.db.commit(); self.db.refresh(row); return self._out(row)
    def update(self, config_id: str, body: AppFinanceConfigIn):
        row = self._config(config_id)
        duplicate = self.db.query(DeliveryAppFinanceConfig).filter(DeliveryAppFinanceConfig.tenant_id == self.tenant_id, DeliveryAppFinanceConfig.app_key == body.app_key, DeliveryAppFinanceConfig.id != config_id).first()
        if duplicate: raise DomainError("Aplicativo já cadastrado.", code="AppFinanceConfigDuplicate")
        for key, value in body.model_dump().items(): setattr(row, key, value)
        self.db.commit(); self.db.refresh(row); return self._out(row)
    def delete(self, config_id: str):
        row = self._config(config_id); self.db.delete(row); self.db.commit(); return {"id": config_id, "deleted": True}
    def add_rule(self, config_id: str, body: AppFinanceRuleIn):
        self._config(config_id)
        if self.db.query(DeliveryAppFinanceRule).filter_by(tenant_id=self.tenant_id, config_id=config_id, name=body.name).first():
            raise DomainError("Regra financeira ja cadastrada.", code="AppFinanceRuleDuplicate")
        row = DeliveryAppFinanceRule(id=str(uuid4()), tenant_id=self.tenant_id, config_id=config_id, **body.model_dump()); self.db.add(row); self.db.commit(); self.db.refresh(row); return self._rule(row)
    def delete_rule(self, rule_id: str):
        row = self.db.query(DeliveryAppFinanceRule).filter_by(id=rule_id, tenant_id=self.tenant_id).first()
        if not row: raise DomainError("Regra financeira não encontrada.", code="AppFinanceRuleNotFound")
        self.db.delete(row); self.db.commit(); return {"id": rule_id, "deleted": True}
    def calculate(self, app_key: str, gross_amount: Decimal, delivery_fee: Decimal = Decimal("0")):
        if app_key not in {"partner_99", "ifood", "keeta"}:
            raise DomainError("Aplicativo de entrega invalido.", code="AppFinanceInvalidOrigin")
        gross = Decimal(str(gross_amount)).quantize(CENT, rounding=ROUND_HALF_UP)
        delivery_fee = Decimal(str(delivery_fee)).quantize(CENT, rounding=ROUND_HALF_UP)
        if gross < 0 or delivery_fee < 0:
            raise DomainError("Os valores financeiros nao podem ser negativos.", code="AppFinanceInvalidAmount")
        config = self.db.query(DeliveryAppFinanceConfig).filter_by(tenant_id=self.tenant_id, app_key=app_key, active=True).first()
        if not config: return {"app_key": app_key, "gross_amount": gross, "deductions": Decimal("0.00"), "net_amount": gross, "rules": []}
        total = Decimal("0.00"); details = []
        rules = self.db.query(DeliveryAppFinanceRule).filter_by(tenant_id=self.tenant_id, config_id=config.id, active=True).order_by(DeliveryAppFinanceRule.sort_order, DeliveryAppFinanceRule.id).all()
        for rule in rules:
            base = delivery_fee if rule.rule_type == "freight" else gross
            amount = base * Decimal(str(rule.value)) / Decimal("100") if rule.calculation_type == "percentage" else Decimal(str(rule.value))
            amount = amount.quantize(CENT, rounding=ROUND_HALF_UP); total += amount; details.append({"rule_id": rule.id, "name": rule.name, "amount": amount})
        if total > gross:
            raise DomainError("As deducoes nao podem superar o valor bruto do pedido.", code="AppFinanceDeductionsExceedGross")
        return {"app_key": app_key, "gross_amount": gross, "deductions": total, "net_amount": gross - total, "rules": details}
    def _rule(self, row): return {"id": row.id, "name": row.name, "rule_type": row.rule_type, "calculation_type": row.calculation_type, "value": row.value, "sort_order": row.sort_order, "active": row.active}
    def _out(self, row): return {"id": row.id, "app_key": row.app_key, "app_name": row.app_name, "active": row.active, "rules": [self._rule(r) for r in sorted(self.db.query(DeliveryAppFinanceRule).filter_by(tenant_id=self.tenant_id, config_id=row.id).all(), key=lambda x: (x.sort_order, x.id))]}
