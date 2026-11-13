from backend.services.agente_whatsapp_service import _baileys_contact_value, _baileys_phone


def test_baileys_prefers_real_alternate_phone_for_lid():
    item = {
        "remote_jid": "160129634803851@lid",
        "remote_jid_alt": "5511999999999@s.whatsapp.net",
        "phone": "160129634803851",
    }

    assert _baileys_contact_value(item) == "5511999999999@s.whatsapp.net"
    assert _baileys_phone(item) == "5511999999999"


def test_baileys_falls_back_to_phone_and_remote_jid():
    assert _baileys_phone({"remote_jid": "5511888888888@s.whatsapp.net"}) == "5511888888888"
    assert _baileys_phone({"remote_jid": "160129634803851@lid", "phone": "5511777777777"}) == "5511777777777"
