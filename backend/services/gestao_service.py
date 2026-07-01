from __future__ import annotations

import json
from copy import deepcopy

from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.models.gestao import GestaoModuleSettings
from backend.schemas.gestao import GestaoModuleSettingsUpdate

TENANT_ID = "default"

MODULE_DEFAULTS: dict[str, dict] = {
    "inventory": {
        "title": "Estoque",
        "description": "Cadastros e configuracoes para controle de insumos, saldos e disponibilidade.",
        "notes": "Nasce desabilitado. Nao altera pedidos, checkout ou cozinha nesta fase.",
        "settings": {
            "auto_consume_on_preparing": False,
            "negative_stock_policy": "warn_only",
            "sales_control_enabled": False,
            "out_of_stock_behavior": "show_unavailable",
            "alerts_enabled": False,
        },
    },
    "cmv": {
        "title": "CMV",
        "description": "Base para custo de mercadoria vendida, snapshots e classificacao da DRE.",
        "notes": "Analitico e sem side effects. Nao bloqueia pedido nem interfere na cozinha.",
        "settings": {
            "mode": "disabled",
            "target_percent": None,
            "estimated_mode_allowed": True,
        },
    },
    "finance": {
        "title": "Financeiro",
        "description": "Base para contas, lancamentos, recebiveis, caixa, competencia e DRE.",
        "notes": "Nao substitui PaymentService nesta fase.",
        "settings": {
            "auto_create_receivables": False,
            "auto_create_payables_from_purchases": False,
            "default_receivable_account_id": None,
            "default_payable_account_id": None,
            "cash_basis_enabled": True,
            "accrual_basis_enabled": True,
            "dre_enabled": True,
        },
    },
    "fiscal": {
        "title": "Fiscal SEFAZ",
        "description": "Base para fiscal nativo com SEFAZ direta, sem Saipos ou middleware fiscal.",
        "notes": "Preparacao cadastral. Nenhum XML e transmitido nesta fase.",
        "settings": {
            "sefaz_integration_enabled": False,
            "environment": "homologation",
            "certificate_configured": False,
            "external_middleware_allowed": False,
            "default_document_model": "NFCe",
        },
    },
}


class GestaoModuleNotFound(DomainError):
    http_status = 404

    def __init__(self):
        super().__init__("Modulo de Gestao nao encontrado.", code="GestaoModuleNotFound")


class GestaoService:
    def __init__(self, db: Session, tenant_id: str = TENANT_ID):
        self._db = db
        self._tenant_id = tenant_id

    def list_settings(self) -> list[dict]:
        self._ensure_defaults()
        rows = (
            self._db.query(GestaoModuleSettings)
            .filter(GestaoModuleSettings.tenant_id == self._tenant_id)
            .order_by(GestaoModuleSettings.module_key)
            .all()
        )
        order = {key: idx for idx, key in enumerate(MODULE_DEFAULTS)}
        rows.sort(key=lambda item: order.get(item.module_key, 999))
        return [self.serialize(item) for item in rows]

    def update_settings(self, module_key: str, payload: GestaoModuleSettingsUpdate) -> dict:
        item = self._get(module_key)
        data = payload.model_dump(exclude_unset=True)
        if "enabled" in data:
            item.enabled = bool(data["enabled"])
            if item.enabled and item.status == "disabled":
                item.status = "setup"
            if not item.enabled:
                item.status = "disabled"
        if "status" in data and data["status"] is not None:
            item.status = data["status"]
            item.enabled = item.status != "disabled"
        if "settings" in data and data["settings"] is not None:
            item.settings_json = json.dumps(self._merge_settings(module_key, data["settings"]), ensure_ascii=False)
        if "notes" in data and data["notes"] is not None:
            item.notes = data["notes"].strip()
        self._db.commit()
        self._db.refresh(item)
        return self.serialize(item)

    def serialize(self, item: GestaoModuleSettings) -> dict:
        return {
            "id": item.id,
            "tenant_id": item.tenant_id,
            "module_key": item.module_key,
            "title": item.title,
            "description": item.description,
            "enabled": item.enabled,
            "status": item.status,
            "settings": self._safe_settings(item),
            "notes": item.notes,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }

    def _get(self, module_key: str) -> GestaoModuleSettings:
        if module_key not in MODULE_DEFAULTS:
            raise GestaoModuleNotFound()
        self._ensure_defaults()
        item = (
            self._db.query(GestaoModuleSettings)
            .filter(
                GestaoModuleSettings.tenant_id == self._tenant_id,
                GestaoModuleSettings.module_key == module_key,
            )
            .first()
        )
        if not item:
            raise GestaoModuleNotFound()
        return item

    def _ensure_defaults(self) -> None:
        changed = False
        for module_key, defaults in MODULE_DEFAULTS.items():
            item = (
                self._db.query(GestaoModuleSettings)
                .filter(
                    GestaoModuleSettings.tenant_id == self._tenant_id,
                    GestaoModuleSettings.module_key == module_key,
                )
                .first()
            )
            if item:
                continue
            self._db.add(GestaoModuleSettings(
                id=f"gestao-{self._tenant_id}-{module_key}",
                tenant_id=self._tenant_id,
                module_key=module_key,
                title=defaults["title"],
                description=defaults["description"],
                enabled=False,
                status="disabled",
                settings_json=json.dumps(defaults["settings"], ensure_ascii=False),
                notes=defaults["notes"],
            ))
            changed = True
        if changed:
            self._db.commit()

    def _merge_settings(self, module_key: str, patch: dict) -> dict:
        settings = deepcopy(MODULE_DEFAULTS[module_key]["settings"])
        settings.update(patch)
        return settings

    def _safe_settings(self, item: GestaoModuleSettings) -> dict:
        settings = deepcopy(MODULE_DEFAULTS.get(item.module_key, {}).get("settings", {}))
        try:
            raw = json.loads(item.settings_json or "{}")
            if isinstance(raw, dict):
                settings.update(raw)
        except json.JSONDecodeError:
            pass
        return settings
