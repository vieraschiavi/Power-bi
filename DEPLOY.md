# Deploy de la landing (MV DAX Lab) en Vercel

Lo que se publica es `daxlingo/web` (landing estática trilingüe) más las
funciones Node de `api/`. El resto del repo —el proyecto Power BI de Farma Demo, el
motor Python, el escritorio— no viaja a la web.

**Producción: https://power-bi-mv13.vercel.app** — es la URL que va en el
formulario de credenciales de producción de MercadoPago, y la que el programa
y el instalador traen por defecto (`dxl.SITIO`, `desktop/edicion.json`).

## Configuración del proyecto en Vercel

| Ajuste | Valor | Por qué |
|---|---|---|
| Framework Preset | **Other** | Este repo tiene `requirements.txt` en la raíz (del proyecto Farma Demo). Con eso alcanza para que Vercel lo autodetecte como app Python y falle con «No python entrypoint found»: busca un entrypoint que no existe, porque lo que hay que publicar es HTML. |
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
| `RESEND_API_KEY` | Clave de Resend, para que el formulario de demo te mande el pedido por mail | El formulario avisa y cae a un `mailto:` — el pedido no se pierde, pero es peor experiencia |
| `RESEND_FROM` | Remitente (opcional). Sin dominio propio dejá el default `onboarding@resend.dev`, que solo puede escribirte a vos mismo — justo lo que hace falta | Usa el default |
| `MP_CURRENCY` | Moneda del cobro (por defecto `UYU`) | — |
| `MP_TASA_UYU` | Cotización de referencia USD→UYU (por defecto 40) | — |
| `MVDAXLAB_SITIO` | Dominio público, solo como respaldo | Las URLs de retorno igual salen del header `Host` |

⚠️ **`MVDAX_LICENSE_SECRET` no se cambia a la ligera**: las claves ya emitidas
se validan contra ella, así que cambiarla invalida todas las licencias vendidas.

## El mismo secreto, también en GitHub (esto es lo que rompe las ventas)

`MVDAX_LICENSE_SECRET` va en **dos lugares**, con **exactamente el mismo
valor**:

| Dónde | Para qué | Cómo se pone |
|---|---|---|
| Vercel · *Environment Variables* | La web **firma** la licencia cuando MercadoPago confirma el pago | Settings → Environment Variables |
| GitHub · *Actions secrets* | El instalador **verifica** esa licencia en la PC del cliente | Settings → Secrets and variables → Actions → New repository secret |

Son dos implementaciones distintas del mismo HMAC —`api/_licencia.js` firma en
JS, `dxl/licencia.py` verifica en Python— y hay un test que compara las dos
byte a byte. Si los valores no coinciden, **todo se ve bien hasta que un
cliente paga**: MercadoPago aprueba, la web emite la clave, y el programa la
rechaza con «licencia inválida». No lo agarra ningún test, porque cada lado
funciona perfecto por separado.

Desde ahora el build **falla** si construís la edición `cliente` sin el
secreto, en vez de generar en silencio un instalador que rechaza todo. Así que
si el secreto no está en GitHub, el workflow de instaladores se cae con el
motivo escrito — es la forma de comprobarlo sin tener que leer el secreto.

La demo no lo necesita (es por fecha, no por clave) y la edición owner tampoco
(viene desbloqueada, sin vencimiento).

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

## Checklist de producción — de cero a vender

Seis cosas. Ninguna necesita tocar código.

### 1. Credenciales de MercadoPago

<https://www.mercadopago.com.uy/developers/panel/app> → tu aplicación →
**Credenciales de producción** → copiar el **Access Token** (empieza con
`APP_USR-`).

> Las de **prueba** (`TEST-`) sirven para simular compras sin plata real; las
> de producción cobran de verdad. Es la misma variable, solo cambia el valor.

### 2. El secreto de licencias

Se **genera**, no se elige a mano — tiene que ser aleatorio y largo:

```bash
openssl rand -base64 48
```

Ese valor va en los dos lugares de la sección de arriba: Vercel y GitHub.
Guardalo en tu gestor de contraseñas: si lo perdés no podés emitir licencias
nuevas que las copias ya instaladas acepten.

### 3. Variables en Vercel

<https://vercel.com/mv13/power-bi/settings/environment-variables> — para
**Production** y **Preview**:

| Nombre | Valor |
|---|---|
| `MP_ACCESS_TOKEN` | el Access Token del paso 1 |
| `MVDAX_LICENSE_SECRET` | el del paso 2 |
| `MP_CURRENCY` | `UYU` (solo si cobrás en otra moneda hace falta cambiarlo) |
| `MP_TASA_UYU` | `40` (cotización de referencia USD→UYU) |

### 4. Resend, para el formulario de demo (gratis)

<https://resend.com/signup> — capa gratuita de 3.000 mails al mes, sin tarjeta.
Creá una API key en *API Keys → Create* y pegala en Vercel como
`RESEND_API_KEY`.

Mientras no tengas dominio propio no hace falta verificar nada: el remitente
por defecto (`onboarding@resend.dev`) solo puede mandarte mails **a vos
mismo**, que es exactamente lo que este formulario necesita.

Sin esta clave el formulario no se rompe: avisa y abre el correo del visitante
con los datos ya cargados. Pero perdés a los que no tienen cliente de correo
configurado, así que conviene ponerla.

### 5. El secreto en GitHub

<https://github.com/vieraschiavi/Power-bi/settings/secrets/actions> → **New
repository secret** → nombre `MVDAX_LICENSE_SECRET`, valor **el mismo del paso 2**.

### 6. Comprobar que quedó andando

```bash
# la landing responde
curl -s -o /dev/null -w '%{http_code}\n' https://power-bi-mv13.vercel.app/

# el checkout devuelve un link de pago (no "medio_pago_no_configurado")
curl -s -X POST https://power-bi-mv13.vercel.app/api/checkout \
     -H 'content-type: application/json' -d '{"plan":"perpetua"}'
```

Y una compra de punta a punta con las credenciales de **prueba**: comprar,
recibir la clave, pegarla en la pestaña Licencia del programa y ver que
desbloquea. Es el único paso que no se puede automatizar desde acá, porque
necesita el checkout real de MercadoPago.

## Qué NO necesita configuración

- **La demo de 7 días**: no usa clave ni servidor. Cuenta desde la primera
  vez que se abre; vencida, siguen abiertos analizador, explicador,
  relaciones y Academia, y se cierran generar, transformar, exportar, Fabric
  y overlay.
- **La edición owner**: viene desbloqueada y sin vencimiento horneadas en el
  paquete. No hay ninguna licencia que emitir ni que pegar. Se baja del
  release borrador `owner-ultimo`, que solo ve quien tiene permiso de
  escritura en el repo.
- **Las claves de IA** (Claude, OpenAI, Gemini…): las pone cada usuario en
  ⚙️ Configuración. Sin ninguna, el motor de reglas, el analizador, el
  explicador, el mapa de relaciones, la Academia y todo el export funcionan
  igual.
