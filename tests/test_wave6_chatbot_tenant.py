from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_chatbot_service_and_context_builder_are_tenant_scoped():
    service = (ROOT / "backend/services/chatbot_service.py").read_text(encoding="utf-8")
    builder = (ROOT / "backend/services/context_builder.py").read_text(encoding="utf-8")
    assert "def __init__(self, db: Session, tenant_id: str)" in service
    assert "tenant_id=self._tenant_id" in service
    assert "ChatbotConversation.tenant_id == self._tenant_id" in service
    assert "ChatbotMessage.tenant_id == self._tenant_id" in service
    assert "ContextBuilder(self._db, self._tenant_id)" in service
    for model in ("Customer", "Order", "Product", "Promotion", "ChatbotFAQ", "ChatbotKnowledgeDoc", "ChatbotMessage"):
        assert f"{model}.tenant_id == self._tenant_id" in builder


def test_chatbot_schema_migration_removes_global_identity_contracts():
    migration = (ROOT / "backend/migrations/versions/20261003_chatbot_tenant_keys.py").read_text(encoding="utf-8")
    model = (ROOT / "backend/models/chatbot.py").read_text(encoding="utf-8")
    assert "ALTER COLUMN id DROP DEFAULT" in migration
    assert "_drop_global_session_unique" in migration
    assert 'session_id           = Column(String, nullable=False, index=True)' in model
