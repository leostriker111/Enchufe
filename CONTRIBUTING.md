# Cómo colaborar

Gracias por asomarte.

## Lo que más falta

1. **Probarlo con otras marcas de enchufe.** Todos los Zengge/MagicHome deberían
   funcionar, pero solo se ha probado con unos pocos. Si el tuyo funciona —o no—
   dilo: el modelo que reporta `enchufe buscar` es el dato clave.
2. **Otros servidores de nube.** El `login` usa el de MagicHue. Algunas marcas
   usan otro host; dar con el correcto para una marca concreta ayuda a mucha
   gente.
3. **Color y brillo.** Hoy solo prende y apaga. Las librerías de abajo pueden
   más, pero estos son enchufes; tendría sentido para los modelos que sí son
   focos.
4. **Guardar la clave fuera de Windows.** El cifrado usa DPAPI. Un equivalente
   con el llavero de macOS o el Secret Service de Linux abriría `--recordar` a
   otros sistemas.

## Antes de mandar nada

```bash
git clone https://github.com/leostriker111/Enchufe.git
cd Enchufe
pip install -e ".[dev]"
pytest pruebas/ -v
```

Las pruebas no tocan la red ni necesitan un enchufe. La de cifrado solo corre en
Windows; en otros sistemas se salta sola. Tienen que estar en verde antes de
abrir un PR.

## Reglas de la casa

**La contraseña nunca sale en claro.** Ni en la bitácora, ni en un mensaje de
error, ni en la config. Si tu cambio toca el login o el guardado, revísalo.

**No romper el seguro.** `revisa_seguro()` impide apagar el enchufe que alimenta
la propia máquina sin `--forzar`. Hay pruebas que lo fijan; si tu cambio las
pone en rojo, el cambio está mal.

**No comprobar es no saber.** Si dices que funciona con tu enchufe, que sea
porque lo probaste con el aparato de verdad, no porque el código no dio error.

**Documenta lo que no funciona.** Un límite honesto vale más que una promesa
falsa.

## Estilo

- Código y comentarios **en español**, sin acentos en los identificadores.
- Los comentarios explican **por qué**, no qué.
- Nada de respaldos a mano (`archivo.py.bak`). Para eso está git.

## Licencia

Al aportar, aceptas que tu contribución se publique bajo la
[AGPL-3.0](LICENSE).
