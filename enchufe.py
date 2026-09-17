#!/usr/bin/env python3
"""
enchufe - control de los enchufes WiFi (Vanance / app Briturn).

NO son Tuya: son Zengge/MagicHome, protocolo LEDENET.
  - En casa  -> TCP 5577, directo al aparato, sin nube ni llaves.
  - Por nube -> https://wifij01us.magichue.net (para cuando no estas en casa).

El codigo vive aqui; los datos (config, sesiones, bitacora) viven aparte en
%LOCALAPPDATA%\\enchufe. La contrasena, si decides guardarla, se cifra con
DPAPI de Windows: queda atada a tu cuenta de usuario y nadie mas la puede leer,
ni siquiera con el archivo en la mano.

Escribe 'enchufe ayuda' para la lista de subcomandos.
"""

import ctypes
import json
import os
import socket
import sys
import time
import datetime
import concurrent.futures as cf
from ctypes import wintypes

try:
    # Para que los acentos salgan bien en la consola de Windows. No siempre se
    # puede (stdout redirigido, o capturado por las pruebas): si no, ni modo.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

PUERTO = 5577

CODIGO = os.path.dirname(os.path.abspath(__file__))
DATOS = os.path.join(os.environ.get("LOCALAPPDATA", CODIGO), "enchufe")
CONFIG = os.path.join(DATOS, "enchufes.json")
SESIONES = os.path.join(DATOS, "sesiones.json")
SECRETO = os.path.join(DATOS, "secreto.bin")
BITACORA = os.path.join(DATOS, "enchufe.log")

VIEJA_CONFIG = os.path.join(CODIGO, "enchufes.json")
VIEJA_NUBE = os.path.join(CODIGO, "nube.json")


# ------------------------------------------------------------------ #
#  Bitacora. Nunca escribe contrasenas ni tokens.
# ------------------------------------------------------------------ #
def log(evento, detalle=""):
    try:
        os.makedirs(DATOS, exist_ok=True)
        sello = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        linea = "%s  %-18s %s\n" % (sello, evento, detalle)
        with open(BITACORA, "a", encoding="utf-8") as f:
            f.write(linea)
    except Exception:
        pass  # la bitacora nunca debe tumbar el comando


# ------------------------------------------------------------------ #
#  Cifrado con DPAPI de Windows (sin dependencias, via ctypes)
# ------------------------------------------------------------------ #
class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(data: bytes) -> _Blob:
    buf = ctypes.create_string_buffer(data, len(data))
    return _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))


def _leer_blob(blob: _Blob) -> bytes:
    datos = ctypes.string_at(blob.pbData, blob.cbData)
    ctypes.windll.kernel32.LocalFree(blob.pbData)
    return datos


def cifrar(texto: str) -> bytes:
    entrada, salida = _blob(texto.encode("utf-8")), _Blob()
    ok = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(entrada), "enchufe", None, None, None, 0, ctypes.byref(salida)
    )
    if not ok:
        raise OSError("DPAPI no pudo cifrar")
    return _leer_blob(salida)


def descifrar(datos: bytes) -> str:
    entrada, salida = _blob(datos), _Blob()
    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(entrada), None, None, None, None, 0, ctypes.byref(salida)
    )
    if not ok:
        raise OSError("DPAPI no pudo descifrar (otro usuario u otra maquina?)")
    return _leer_blob(salida).decode("utf-8")


def guardar_secreto(password: str):
    os.makedirs(DATOS, exist_ok=True)
    with open(SECRETO, "wb") as f:
        f.write(cifrar(password))
    log("secreto_guardado", "cifrado con DPAPI")


def leer_secreto():
    if not os.path.exists(SECRETO):
        return None
    try:
        with open(SECRETO, "rb") as f:
            return descifrar(f.read())
    except Exception as err:
        print("  No pude descifrar la contrasena guardada: %s" % err)
        return None


# ------------------------------------------------------------------ #
#  Config y sesiones
# ------------------------------------------------------------------ #
def _leer_json(ruta, default):
    if not os.path.exists(ruta):
        return default
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _escribir_json(ruta, data):
    os.makedirs(DATOS, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def migrar():
    """Mueve los datos viejos que vivian junto al codigo."""
    os.makedirs(DATOS, exist_ok=True)
    if os.path.exists(VIEJA_CONFIG) and not os.path.exists(CONFIG):
        os.replace(VIEJA_CONFIG, CONFIG)
        log("migracion", "enchufes.json -> %s" % DATOS)
    if os.path.exists(VIEJA_NUBE):
        viejo = _leer_json(VIEJA_NUBE, {})
        if viejo.get("token"):
            _escribir_json(SESIONES, {"correo": viejo.get("usuario", ""),
                                      "token": viejo["token"], "desde": ""})
        os.remove(VIEJA_NUBE)
        log("migracion", "nube.json -> sesiones.json")


def cargar():
    return _leer_json(CONFIG, {"enchufes": []})


def guardar(data):
    _escribir_json(CONFIG, data)


def buscar_alias(reg, alias):
    alias = (alias or "").lower()
    for e in reg["enchufes"]:
        if e["alias"].lower() == alias:
            return e
    return None


def normaliza_mac(mac):
    return (mac or "").replace(":", "").replace("-", "").lower()


# ------------------------------------------------------------------ #
#  El seguro: no cortarle la corriente a la maquina donde corro
# ------------------------------------------------------------------ #
def es_suicidio(e):
    if not e.get("alimenta_esta_maquina"):
        return False
    return socket.gethostname().lower() == (e.get("maquina") or "").lower()


def revisa_seguro(e, forzar):
    if not es_suicidio(e):
        return True
    print("  ALTO: '%s' es el enchufe que alimenta a %s," % (e["alias"], e.get("maquina")))
    print("  y estas corriendo esto justamente en esa maquina.")
    print("  Apagarlo le corta la corriente en caliente al servidor.")
    if not forzar:
        print()
        print("  No lo hice. Si de verdad es lo que quieres: agrega --forzar")
        log("seguro_activado", e["alias"])
        return False
    print()
    print("  --forzar recibido. Alla vamos.")
    log("seguro_forzado", e["alias"])
    return True


# ------------------------------------------------------------------ #
#  Local (LAN, puerto 5577)
# ------------------------------------------------------------------ #
def prefijo_local():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "192.168.1.1"
    finally:
        s.close()
    return ip.rsplit(".", 1)[0]


def puerto_abierto(ip, puerto=PUERTO, timeout=1.5):
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((ip, puerto))
        return True
    except Exception:
        return False
    finally:
        try:
            s.close()
        except Exception:
            pass


def identidad(ip):
    """Pregunta por UDP unicast al 48899: devuelve (ip, mac, modelo) o None."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(3)
    try:
        s.sendto(b"HF-A11ASSISTHREAD", (ip, 48899))
        data, _ = s.recvfrom(1024)
        partes = data.decode(errors="replace").split(",")
        if len(partes) >= 3:
            return partes[0], partes[1], partes[2]
    except Exception:
        pass
    finally:
        s.close()
    return None


def bombilla(ip):
    from flux_led import WifiLedBulb

    b = WifiLedBulb(ip)
    b.update_state()
    return b


# ------------------------------------------------------------------ #
#  Nube (magichue)
# ------------------------------------------------------------------ #
def hacer_login(correo, password):
    from magichue import RemoteAPI

    api = RemoteAPI.login_with_user_password(user=correo, password=password)
    _escribir_json(SESIONES, {
        "correo": correo,
        "token": api.token,
        "desde": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    log("login_ok", correo)
    return api


def api_nube(silencioso=False):
    """Devuelve una sesion lista. Si el token no sirve y hay contrasena
    guardada, vuelve a entrar solo, sin molestar a nadie."""
    from magichue import RemoteAPI

    ses = _leer_json(SESIONES, {})
    if ses.get("token"):
        api = RemoteAPI(ses["token"])
        try:
            api.get_online_devices(online_only=False)
            return api
        except Exception as err:
            log("token_invalido", str(err)[:120])
            if not silencioso:
                print("  La sesion guardada ya no sirve.")

    password = leer_secreto()
    correo = ses.get("correo")
    if password and correo:
        if not silencioso:
            print("  Volviendo a entrar solo con la contrasena guardada...")
        try:
            return hacer_login(correo, password)
        except Exception as err:
            print("  No pude reconectar: %s" % err)
            log("relogin_falla", str(err)[:120])
            return None

    print("  No hay sesion. Corre:  enchufe nube login")
    return None


# ------------------------------------------------------------------ #
#  Subcomandos
# ------------------------------------------------------------------ #
AYUDA = """
  En casa (directo al aparato, no necesita internet)
    enchufe estado [alias]      Ver si esta prendido o apagado
    enchufe buscar              Barrer la red y registrar los que encuentre
    enchufe prender <alias>
    enchufe apagar <alias>

  Desde fuera (por la nube de Briturn/MagicHue)
    enchufe nube login [correo] [--recordar]   Entrar (--recordar cifra tu clave)
    enchufe nube cuenta         Ver que sesion hay guardada
    enchufe nube estado         Listar los enchufes de tu cuenta
    enchufe nube prender <alias>
    enchufe nube apagar <alias>
    enchufe nube ciclo <alias> [seg]   Apagar, esperar y prender
    enchufe nube salir [--todo]        Cerrar sesion (--todo borra la clave)

  Bitacora
    enchufe log [n]             Ver las ultimas n lineas (por defecto 20)
    enchufe donde               Ver donde vive cada cosa

  El enchufe marcado como 'alimenta_esta_maquina' no se apaga desde esa misma
  maquina salvo que agregues --forzar.
"""


def cmd_ayuda():
    print(__doc__.strip())
    print(AYUDA)


def cmd_donde():
    print("  Codigo    %s" % CODIGO)
    print("  Datos     %s" % DATOS)
    print("    config    %s" % os.path.basename(CONFIG))
    print("    sesion    %s" % os.path.basename(SESIONES))
    print("    clave     %s   (cifrada con DPAPI)" % os.path.basename(SECRETO))
    print("    bitacora  %s" % os.path.basename(BITACORA))


def cmd_log(args):
    n = int(args[0]) if args and args[0].isdigit() else 20
    if not os.path.exists(BITACORA):
        print("  Todavia no hay bitacora.")
        return
    with open(BITACORA, encoding="utf-8") as f:
        lineas = f.readlines()
    for linea in lineas[-n:]:
        print("  " + linea.rstrip())


def cmd_estado(args):
    reg = cargar()
    if not reg["enchufes"]:
        print("  No hay enchufes registrados. Corre: enchufe buscar")
        return
    objetivo = args[0] if args else None
    for e in reg["enchufes"]:
        if objetivo and e["alias"].lower() != objetivo.lower():
            continue
        etiqueta = e["alias"]
        if e.get("alimenta_esta_maquina"):
            etiqueta += "  (alimenta %s)" % e.get("maquina")
        try:
            b = bombilla(e["ip"])
            print("  %-9s  %-15s  %s" % ("PRENDIDO" if b.is_on else "apagado",
                                         e["ip"], etiqueta))
        except Exception as err:
            print("  %-9s  %-15s  %s   (%s)" % ("sin linea", e["ip"], etiqueta, err))


def cmd_buscar():
    prefijo = prefijo_local()
    print("  Barriendo %s.0/24 en el puerto %d..." % (prefijo, PUERTO))
    hosts = ["%s.%d" % (prefijo, i) for i in range(1, 255)]
    encontrados = []
    with cf.ThreadPoolExecutor(max_workers=120) as ex:
        for ip, abierto in zip(hosts, ex.map(puerto_abierto, hosts)):
            if abierto:
                encontrados.append(ip)

    if not encontrados:
        print("  Nada. Revisa que los enchufes esten conectados al WiFi de 2.4 GHz.")
        log("buscar", "0 encontrados")
        return

    reg = cargar()
    conocidas = set(e["ip"] for e in reg["enchufes"])
    nuevos = 0
    for ip in encontrados:
        ident = identidad(ip)
        mac = normaliza_mac(ident[1]) if ident else ""
        modelo = ident[2] if ident else "?"
        if ip in conocidas:
            print("  ya registrado  %s  %s" % (ip, modelo))
            continue
        alias = "enchufe%d" % (len(reg["enchufes"]) + 1)
        reg["enchufes"].append({"alias": alias, "ip": ip, "mac": mac,
                                "modelo": modelo, "alimenta_esta_maquina": False})
        print("  NUEVO          %s  %s  -> lo registre como '%s'" % (ip, modelo, alias))
        nuevos += 1
    guardar(reg)
    log("buscar", "%d en linea, %d nuevos" % (len(encontrados), nuevos))
    print()
    print("  Config en %s (ahi puedes cambiarle el alias)." % CONFIG)


def cmd_conmutar(args, prender):
    verbo = "prender" if prender else "apagar"
    forzar = "--forzar" in args
    args = [a for a in args if a != "--forzar"]
    if not args:
        print("  Uso: enchufe %s <alias>" % verbo)
        return
    reg = cargar()
    e = buscar_alias(reg, args[0])
    if not e:
        print("  No conozco '%s'. Los que tengo: %s"
              % (args[0], ", ".join(x["alias"] for x in reg["enchufes"])))
        return
    if not prender and not revisa_seguro(e, forzar):
        return
    try:
        b = bombilla(e["ip"])
        if prender:
            b.turnOn()
        else:
            b.turnOff()
        time.sleep(0.6)
        b.update_state()
        estado = "PRENDIDO" if b.is_on else "apagado"
        print("  %s: ahora esta %s" % (e["alias"], estado))
        log("local_" + verbo, "%s -> %s" % (e["alias"], estado))
    except Exception as err:
        print("  No pude: %s" % err)
        log("local_" + verbo + "_falla", "%s: %s" % (e["alias"], str(err)[:120]))


def cmd_nube(args):
    if not args:
        print("  Uso: enchufe nube <login|cuenta|estado|prender|apagar|ciclo|salir>")
        return
    accion = args[0].lower()
    resto = args[1:]

    if accion == "cuenta":
        ses = _leer_json(SESIONES, {})
        if not ses.get("token"):
            print("  No hay sesion guardada.")
        else:
            print("  Correo   %s" % ses.get("correo", "?"))
            print("  Entro    %s" % (ses.get("desde") or "?"))
            print("  Token    guardado (%d caracteres)" % len(ses["token"]))
        print("  Clave    %s" % ("guardada y cifrada con DPAPI"
                                 if os.path.exists(SECRETO) else "no guardada"))
        return

    if accion in ("salir", "olvidar"):
        borrados = []
        if os.path.exists(SESIONES):
            os.remove(SESIONES)
            borrados.append("sesion")
        if "--todo" in resto and os.path.exists(SECRETO):
            os.remove(SECRETO)
            borrados.append("contrasena cifrada")
        print("  Borre: %s" % (", ".join(borrados) if borrados else "nada, no habia"))
        if os.path.exists(SECRETO) and "--todo" not in resto:
            print("  (La contrasena cifrada sigue ahi. Para borrarla: --todo)")
        log("logout", ", ".join(borrados))
        return

    if accion == "login":
        import getpass

        recordar = "--recordar" in resto
        resto = [a for a in resto if a != "--recordar"]
        ses = _leer_json(SESIONES, {})
        correo = resto[0] if resto else ses.get("correo")

        print("  Entra con la MISMA cuenta de la app Briturn/MagicHue.")
        if not correo:
            correo = input("  Correo de la cuenta: ").strip()
            if not correo:
                print("  Sin correo no puedo entrar.")
                return
        print("  Correo: %s" % correo)
        password = leer_secreto()
        if password:
            print("  Usando la contrasena que ya tenias guardada (cifrada).")
        else:
            print("  Se manda solo para pedir el token. No se imprime ni se registra.")
            print()
            password = getpass.getpass("  Contrasena (no se ve al escribir): ")

        try:
            hacer_login(correo, password)
        except Exception as err:
            print()
            print("  No entro: %s" % err)
            print("  Si en la app si entras con esa clave, puede que Briturn use otro")
            print("  servidor que MagicHue. Avisame y buscamos el host correcto.")
            log("login_falla", str(err)[:120])
            return

        print()
        print("  Listo. Sesion guardada en %s" % SESIONES)
        if recordar and not os.path.exists(SECRETO):
            guardar_secreto(password)
            print("  Contrasena cifrada con DPAPI en %s" % SECRETO)
            print("  (Queda atada a tu usuario de Windows: en otra cuenta no se abre.)")
        elif not recordar and not os.path.exists(SECRETO):
            print("  Si quieres que no te la vuelva a pedir nunca:")
            print("    enchufe nube login --recordar")
        return

    api = api_nube()
    if api is None:
        return

    if accion == "estado":
        try:
            for d in api.get_online_devices(online_only=False):
                print("  mac %s   ip %s   tipo %s   %s"
                      % (d.macaddr, d.local_ip, d.device_type, d.state_str))
            log("nube_estado", "ok")
        except Exception as err:
            print("  Fallo la consulta: %s" % err)
            log("nube_estado_falla", str(err)[:120])
        return

    if accion in ("prender", "apagar", "ciclo"):
        from magichue.commands import TurnON, TurnOFF

        forzar = "--forzar" in resto
        resto = [a for a in resto if a != "--forzar"]
        if not resto:
            print("  Uso: enchufe nube %s <alias>" % accion)
            return
        reg = cargar()
        e = buscar_alias(reg, resto[0])
        if not e or not e.get("mac"):
            print("  Necesito la MAC de '%s'. Corre 'enchufe buscar' en casa." % resto[0])
            return
        if accion in ("apagar", "ciclo") and not revisa_seguro(e, forzar):
            return
        try:
            if accion == "prender":
                api._send_command(TurnON, e["mac"])
                print("  %s: mande prender por la nube." % e["alias"])
            elif accion == "apagar":
                api._send_command(TurnOFF, e["mac"])
                print("  %s: mande apagar por la nube." % e["alias"])
            else:
                espera = int(resto[1]) if len(resto) > 1 else 15
                api._send_command(TurnOFF, e["mac"])
                print("  Corte la corriente. Esperando %ds..." % espera)
                time.sleep(espera)
                api._send_command(TurnON, e["mac"])
                print("  Corriente de vuelta.")
            log("nube_" + accion, e["alias"])
        except Exception as err:
            print("  Fallo: %s" % err)
            log("nube_" + accion + "_falla", "%s: %s" % (e["alias"], str(err)[:120]))
        return

    print("  No conozco 'nube %s'." % accion)


def main():
    migrar()
    args = sys.argv[1:]
    if not args or args[0] in ("ayuda", "-h", "--help", "help"):
        cmd_ayuda()
        return
    cmd = args[0].lower()
    resto = args[1:]
    if cmd == "estado":
        cmd_estado(resto)
    elif cmd == "buscar":
        cmd_buscar()
    elif cmd == "prender":
        cmd_conmutar(resto, True)
    elif cmd == "apagar":
        cmd_conmutar(resto, False)
    elif cmd == "nube":
        cmd_nube(resto)
    elif cmd == "log":
        cmd_log(resto)
    elif cmd == "donde":
        cmd_donde()
    else:
        print("  No conozco '%s'. Escribe: enchufe ayuda" % cmd)


if __name__ == "__main__":
    main()
