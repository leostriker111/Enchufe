# -*- coding: utf-8 -*-
"""Las partes puras de enchufe: nada de red ni de hardware.

Lo que habla con los enchufes (TCP 5577, UDP 48899, la nube) no se puede probar
sin un aparato de verdad; eso queda documentado como limite. Aqui se prueba la
logica que decide QUE hacer, que es donde un fallo silencioso duele mas: sobre
todo el seguro que impide cortarse la corriente a si mismo.
"""
import sys

import pytest

import enchufe


# --- normalizar MAC ----------------------------------------------------------

def test_normaliza_mac_quita_separadores_y_baja():
    assert enchufe.normaliza_mac("AA:BB:CC:DD:EE:FF") == "aabbccddeeff"
    assert enchufe.normaliza_mac("aa-bb-cc-dd-ee-ff") == "aabbccddeeff"
    assert enchufe.normaliza_mac("AaBbCc") == "aabbcc"


def test_normaliza_mac_aguanta_lo_vacio():
    assert enchufe.normaliza_mac("") == ""
    assert enchufe.normaliza_mac(None) == ""


# --- buscar por alias --------------------------------------------------------

def _reg():
    return {"enchufes": [
        {"alias": "sala", "ip": "192.168.1.10"},
        {"alias": "Cuarto", "ip": "192.168.1.11"},
    ]}


def test_buscar_alias_ignora_mayusculas():
    assert enchufe.buscar_alias(_reg(), "SALA")["ip"] == "192.168.1.10"
    assert enchufe.buscar_alias(_reg(), "cuarto")["ip"] == "192.168.1.11"


def test_buscar_alias_devuelve_none_si_no_esta():
    assert enchufe.buscar_alias(_reg(), "cocina") is None
    assert enchufe.buscar_alias(_reg(), None) is None


# --- el seguro: no cortarse la corriente a si mismo --------------------------

def test_el_seguro_salta_en_la_maquina_que_alimenta(monkeypatch):
    monkeypatch.setattr(enchufe.socket, "gethostname", lambda: "MiServidor")
    e = {"alias": "srv", "alimenta_esta_maquina": True, "maquina": "MiServidor"}
    assert enchufe.es_suicidio(e) is True


def test_el_seguro_no_salta_en_otra_maquina(monkeypatch):
    monkeypatch.setattr(enchufe.socket, "gethostname", lambda: "OtraPC")
    e = {"alias": "srv", "alimenta_esta_maquina": True, "maquina": "MiServidor"}
    assert enchufe.es_suicidio(e) is False


def test_un_enchufe_normal_nunca_es_suicidio(monkeypatch):
    monkeypatch.setattr(enchufe.socket, "gethostname", lambda: "MiServidor")
    e = {"alias": "lampara", "alimenta_esta_maquina": False, "maquina": "MiServidor"}
    assert enchufe.es_suicidio(e) is False


def test_sin_forzar_el_seguro_impide_apagar(monkeypatch, capsys):
    monkeypatch.setattr(enchufe.socket, "gethostname", lambda: "MiServidor")
    e = {"alias": "srv", "alimenta_esta_maquina": True, "maquina": "MiServidor"}
    assert enchufe.revisa_seguro(e, forzar=False) is False
    assert "ALTO" in capsys.readouterr().out


def test_con_forzar_el_seguro_deja_pasar(monkeypatch):
    monkeypatch.setattr(enchufe.socket, "gethostname", lambda: "MiServidor")
    e = {"alias": "srv", "alimenta_esta_maquina": True, "maquina": "MiServidor"}
    assert enchufe.revisa_seguro(e, forzar=True) is True


# --- JSON de ida y vuelta ----------------------------------------------------

def test_json_ida_y_vuelta(tmp_path, monkeypatch):
    monkeypatch.setattr(enchufe, "DATOS", str(tmp_path))
    ruta = str(tmp_path / "x.json")
    datos = {"enchufes": [{"alias": "sala", "ip": "192.168.1.10"}]}
    enchufe._escribir_json(ruta, datos)
    assert enchufe._leer_json(ruta, {}) == datos


def test_leer_json_devuelve_el_default_si_no_existe(tmp_path):
    assert enchufe._leer_json(str(tmp_path / "no.json"), {"x": 1}) == {"x": 1}


def test_leer_json_no_revienta_con_basura(tmp_path):
    malo = tmp_path / "malo.json"
    malo.write_text("{ esto no es json", encoding="utf-8")
    assert enchufe._leer_json(str(malo), {"ok": True}) == {"ok": True}


# --- DPAPI (solo Windows): cifrar y descifrar de ida y vuelta ----------------

@pytest.mark.skipif(sys.platform != "win32", reason="DPAPI es de Windows")
def test_dpapi_ida_y_vuelta():
    secreto = "contrasena-de-prueba-áéí-123"
    cifrado = enchufe.cifrar(secreto)
    assert isinstance(cifrado, bytes)
    assert secreto.encode("utf-8") not in cifrado   # no queda en claro
    assert enchufe.descifrar(cifrado) == secreto
