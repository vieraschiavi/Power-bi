# Deploy de la landing (MV DAX Lab) en Vercel

Lo que se publica es `daxlingo/web` (landing estática trilingüe) más las
funciones Node de `api/`. El resto del repo —el proyecto Power BI de Adium, el
motor Python, el escritorio— no viaja a la web.

**Producción: https://power-bi-mv13.vercel.app** — es la URL que va en el
formulario de credenciales de producción de MercadoPago, y la que el programa
y el instalador traen por defecto (`dxl.SITIO`, `desktop/edicion.json`).

## Configuración del proyecto en Vercel

| Ajuste | Valor | Por qué |
|---|---|---|
| Framework Preset | **Other** | Este repo tiene `requirements.txt` en la raíz (del proyecto Adium). Con eso alcanza para que Vercel lo autodetecte como app Python y falle con «No python entrypoint found»: busca un entrypoint que no existe, porque lo que hay que publicar es HTML. |
| Root Directory | *(vacío, la raíz)* | Las funciones serverless viven en `/api` de la raíz; el `outputDirectory` del `vercel.json` ya apunta a `daxlingo/web`. |
| Build Command | *(lo pone `vercel.json`)* | No hay nada que compilar: la landing es HTML/CSS/JS vanilla. |

`vercel.json` deja los tres puntos escritos (`framework: null`, comandos vacíos
y `outputDirectory`), pero **si el proyecto ya quedó importado con el preset
Python, hay que cambiarlo a «Other» a mano una vez**: el preset guardado en el
proyecto es más pegajoso que el archivo. Está en *Settings → Build and
Deployment → Framework Settings*.

`vercel.json` no admite claves de comentario (`"//"` hace fallar la validación
del schema con `should NOT have additional property`), así que la explicación
vive acá y no ahí.

## Protección de deployments (esto tenía la web invisible)

El proyecto quedó importado con **Vercel Authentication** en
`all_except_custom_domains`: cualquiera que entrara a
`power-bi-mv13.vercel.app` recibía un `302` al login de Vercel en vez de la
landing. Compilaba perfecto y no se veía nada — y MercadoPago, que entra sin
sesión, tampoco podía validar el sitio.

Ahora está en **`preview`**: producción es pública y los previews de cada PR
siguen pidiendo login. Está en *Settings → Deployment Protection → Vercel
Authentication*. Si alguna vez la landing empieza a redirigir a
`vercel.com/sso-api`, mirá acá primero.

> El header `x-robots-tag: noindex` que devuelve el dominio `*.vercel.app` lo
> pone Vercel y no se saca: es para que las URLs de deployment no compitan en
> Google con el dominio propio. No afecta a MercadoPago ni a quien tenga el
> enlace. Se va solo cuando conectes un dominio propio.

## Variables de entorno

En *Settings → Environment Variables*, para Production y Preview:

| Variable | Qué es | Sin ella |
|---|---|---|
| `MP_ACCESS_TOKEN` | Access Token de MercadoPago | Los botones de compra responden `medio_pago_no_configurado` |
| `MVDAX_LICENSE_SECRET` | Clave que firma las licencias. Generala con `openssl rand -base64 48` | El pago se aprueba pero no se emite ninguna clave |
| `MP_CURRENCY` | Moneda del cobro (por defecto `UYU`) | — |
| `MP_TASA_UYU` | Cotización de referencia USD→UYU (por defecto 40) | — |
| `MVDAXLAB_SITIO` | Dominio público, solo como respaldo | Las URLs de retorno igual salen del header `Host` |

⚠️ **`MVDAX_LICENSE_SECRET` no se cambia a la ligera**: las claves ya emitidas
se validan contra ella, así que cambiarla invalida todas las licencias vendidas.

⚠️ **Este repositorio es público.** Nunca commitees el secreto de licencias ni
publiques el instalador de la edición OWNER en un release: regala el producto
entero.

## Verificar que quedó bien

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://power-bi-mv13.vercel.app/
# 200 → la landing es pública. 302 a vercel.com/sso-api → mirá la sección de
# protección de arriba.

curl -s https://power-bi-mv13.vercel.app/api/checkout       # {"error":"metodo"} con 405:
                                                            # la función está viva (solo acepta POST)

curl -s -X POST https://power-bi-mv13.vercel.app/api/checkout \
     -H 'content-type: application/json' \
     -d '{"plan":"perpetua"}'                    # {"url":"https://..."} si hay token
```

Si `/api/checkout` devuelve `medio_pago_no_configurado`, la función corre bien
y lo que falta es la variable de entorno.

## Si más adelante cambia el dominio

Con un dominio propio, para que el programa, el instalador y el video apunten
ahí (hoy los tres traen `power-bi-mv13.vercel.app`):

```bash
export MVDAXLAB_SITIO="https://<dominio>"
# el mismo valor en el campo "sitio" de daxlingo/desktop/edicion.json
python3 daxlingo/media/build_video.py   # el cierre del video toma el dominio real
```
