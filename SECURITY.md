# Seguridad

`enchufe` maneja la contraseña de tu cuenta de la nube y puede cortarle la
corriente a aparatos. Vale la pena ser claro con lo que hace y lo que no.

## Reportar un problema

Para fallos de seguridad **no abras una incidencia pública**. Usa
[Security Advisories](https://github.com/leostriker111/Enchufe/security/advisories/new),
que permite un reporte privado.

Se responde en cuanto se pueda. Es un proyecto de una sola persona en su tiempo
libre: no hay acuerdos de nivel de servicio ni programa de recompensas.

## Versiones con soporte

| Versión | Soporte |
|---|---|
| 1.0.x | Sí |

## Qué cuenta como fallo de seguridad aquí

- **Que la contraseña acabe en claro** en algún lado: la bitácora, un mensaje de
  error, la config. La clave solo debe existir cifrada con DPAPI, y nunca se
  imprime ni se registra.
- **Cortar la corriente a la máquina equivocada.** El seguro que impide apagar
  el enchufe que alimenta la propia máquina no debe poder saltarse sin
  `--forzar`. Está fijado por pruebas.
- **Mandar tus datos a un servidor que no sea tu propio enchufe o la nube de tu
  cuenta.**
- **Ejecución de código** al leer un `enchufes.json` o una respuesta de red
  manipulada.

## Cómo se guarda la contraseña

Solo si tú lo pides con `--recordar`. Se cifra con **DPAPI de Windows**
(`CryptProtectData`): queda atada a tu cuenta de usuario. Nadie puede leerla
desde otra cuenta ni copiando `secreto.bin` a otra máquina. El token de sesión
sí se guarda en claro en `sesiones.json` —es lo que la propia app haría— así que
ese archivo tampoco se publica (está en `.gitignore`).

## Lo que este proyecto no promete

- **El protocolo LEDENET no tiene cifrado ni autenticación.** Cualquiera en tu
  red local puede mandarle órdenes a estos enchufes, con o sin este programa.
  Es del hardware, no de aquí.
- **No expongas el puerto 5577 a internet.** Estos aparatos son para la red
  local; si necesitas llegar de fuera, usa la nube o una VPN.
- **La nube es de un tercero** (MagicHue/Briturn). Lo que hagan con tu cuenta
  está fuera del alcance de este programa.
