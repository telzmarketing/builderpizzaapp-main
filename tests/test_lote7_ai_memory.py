from backend.models.crm import CustomerCommercialMemory
from backend.schemas.customer_commercial_memory import CustomerCommercialMemoryIn
from backend.services.agente_whatsapp_tools import AgenteWhatsAppToolService, PUBLIC_ALLOWED_TOOLS


class _DB:
    def add(self, _row):
        pass

    def flush(self):
        pass


def test_public_agent_tools_are_server_side_allowlisted(monkeypatch):
    monkeypatch.setattr(
        "backend.services.agente_whatsapp_tools.AgenteWhatsAppToolCall",
        lambda **kwargs: kwargs,
    )
    service = AgenteWhatsAppToolService(_DB())
    names = {tool["name"] for tool in service.list_tools()}
    assert names == set(PUBLIC_ALLOWED_TOOLS)
    assert "consultar_pagamento" not in names
    assert "buscar_fidelidade" not in names
    assert "gerar_pagamento" not in names

    blocked = service.execute_tool(tool_name="consultar_pagamento", arguments={})
    assert blocked["success"] is False
    assert "fora do escopo" in blocked["error"]


def test_memory_contract_is_tenant_and_customer_scoped():
    table = CustomerCommercialMemory.__table__
    assert {column.name for column in table.c}.issuperset({"tenant_id", "customer_id", "memory_key", "value"})
    constraint = next(item for item in table.constraints if item.name == "uq_customer_commercial_memory_key")
    assert {column.name for column in constraint.columns} == {"tenant_id", "customer_id", "memory_key"}
    payload = CustomerCommercialMemoryIn(memory_key="favorite:calabresa", value="Calabresa", source="agente_whatsapp")
    assert payload.memory_type == "preference"
