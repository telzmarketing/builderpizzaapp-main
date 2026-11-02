from pathlib import Path


ROOT = Path(__file__).parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_audit_detail_projects_private_original_evidence_for_gallery():
    service = read("backend/services/kds_audit_service.py")
    assert "audit_evidence" in service
    assert "asset.storage_key" in service
    assert '"image_role": "original"' in service
    assert '"processing_status": "not_processed"' in service


def test_frontend_reloads_persisted_evidence_and_marks_unprocessed_images():
    page = read("client/pages/admin/KdsAuditoria.tsx")
    api = read("client/lib/api.ts")
    assert "detail.audit_evidence ?? []" in page
    assert "resolveOptimizedAssetUrl" in page
    assert "Detecção ainda não processada" in page
    assert "audit_evidence?: KdsAuditoriaEvidence[]" in api
