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
| `GITHUB_TOKEN` | Token de GitHub con permiso de lectura de contenido. **Solo hace falta cuando el repositorio pase a privado**: con él, `/api/descargar` pide una URL firmada en vez del enlace público del release | Con el repo público, no pasa nada: cae al enlace público. Con el repo privado, la descarga del cliente deja de funcionar |
| `MP_WEBHOOK_SECRET` | Clave de firma de las notificaciones de MercadoPago | El webhook igual no se puede engañar (siempre re-consulta el pago contra la API), pero se pierde el primer filtro |
| `MVDAX_OWNER_TOKEN` | Contraseña del monitor de ventas (`/monitor.html`). Generala con `openssl rand -base64 24` | El monitor queda **cerrado**, no abierto: sin token configurado devuelve 401 siempre |
| `KV_REST_API_URL` + `KV_REST_API_TOKEN` | Base Redis donde se registran ventas y descargas. Los pone solos la integración de Upstash en el Marketplace de Vercel | Se cobra y se entrega igual, pero no queda registro: el monitor avisa que falta la base en vez de mostrar ceros |
| `MVDAX_COMISION_PCT` | Comisión de MercadoPago para el neto estimado del monitor (por defecto `7.31` = 5,99% + IVA) | Usa el default |

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

El build **falla** si construís la edición `cliente` sin el secreto, en vez de
generar en silencio un instalador que rechaza todo.

En el CI la cosa es un poco distinta, porque ahí hay dos preguntas separadas
—«¿anda el instalador?» y «¿está configurado el secreto?»— y mezclarlas
dejaba el check rojo permanente sin decir nada del código. Si el secreto no
está, el workflow **genera una clave descartable para esa corrida**, prueba el
instalador entero igual, y **no publica** el instalador de cliente: sellado con
esa clave rechazaría las licencias reales. El resumen del job lo dice con todas
las letras. Las ediciones owner y demo se publican igual, porque no dependen
del secreto (una viene desbloqueada, la otra cuenta por fecha).

O sea: **si el artifact `instaladores-windows` no aparece en la corrida, el
secreto no está cargado.** Es la forma de comprobarlo sin tener que leerlo.

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

## El webhook, y por qué la venta ya no depende del navegador

Antes, la licencia se emitía cuando el cliente volvía a `/descarga.html` y la
página preguntaba «¿está aprobado?». Si cerraba el navegador en la pantalla de
MercadoPago —o si el pago se acreditaba veinte minutos después, que con
transferencia y efectivo es lo normal— pagaba y no recibía nada.

`/api/webhook-mp` recibe el aviso de MercadoPago aunque no vuelva nadie: emite
la licencia, **se la manda por mail con el enlace de descarga**, y registra la
venta. El `notification_url` ya viaja en la preferencia (`api/checkout.js`), así
que no hay que configurar nada en el panel de MercadoPago.

Dos candados, y el segundo es el que importa:

1. **Firma** (`MP_WEBHOOK_SECRET`): se verifica el HMAC del aviso.
2. **Nunca se le cree al cuerpo del aviso.** Del POST solo sale el ID; el
   estado, el monto y el pagador se vuelven a pedir a la API de MercadoPago con
   el access token. Por eso, aun sin la firma configurada, un aviso falso no
   puede inventar una venta: tendría que nombrar un pago real y aprobado.

El endpoint responde 200 siempre (salvo firma inválida): un 500 haría que
MercadoPago reintente en bucle, y un error nuestro —el mail, la base— no es
motivo para reintentar un pago que ya está bien.

Para activar la firma: panel de MercadoPago → *Webhooks* → generar la clave
secreta → pegarla en Vercel como `MP_WEBHOOK_SECRET`.

## El monitor de ventas

`https://<tu-sitio>/monitor.html` — pide el `MVDAX_OWNER_TOKEN` y muestra
clientes, ventas, descargas, facturado bruto y neto estimado, más el detalle de
las últimas 50 ventas con el mail de cada cliente.

El token no viaja en la URL (terminaría en el historial y en cualquier captura):
se pega en un campo y queda en la pestaña hasta cerrarla.

Necesita la base Redis. La forma más rápida: en el proyecto de Vercel →
*Storage* → **Upstash for Redis** → crear la base. Vercel inyecta
`KV_REST_API_URL` y `KV_REST_API_TOKEN` solo. Capa gratuita, sin tarjeta.

> El **neto** es una estimación y la página lo dice: descuenta la comisión de
> MercadoPago (5,99% + 22% de IVA sobre esa comisión = 7,31% efectivo para
> acreditación inmediata en Uruguay), no impuestos a la renta. El bruto sí es
> un dato.

## Cómo llega el instalador al que compró

Tres piezas, y ninguna se puede saltear:

1. El workflow **Instaladores de Windows** publica la edición `cliente` en un
   release con tag fijo `programa-ultimo` y nombre de archivo fijo
   `MV-DAX-Lab-Setup.exe`. Solo lo hace si `MVDAX_LICENSE_SECRET` está
   configurado — con una clave descartable el instalador rechazaría las
   licencias reales, así que no se publica.
2. `/api/descargar` recibe el `payment_id` (o el `preapproval_id`), **vuelve a
   preguntarle a MercadoPago si ese pago está aprobado** y recién entonces
   redirige al archivo. Armar la URL a mano no sirve.
3. La página de descarga muestra el botón junto a la clave, ya con el id del
   pago que el servidor acaba de validar.

Que el release sea público no regala nada: sin licencia válida esa copia no
desbloquea generar, transformar, exportar, Fabric ni overlay. Y cuando el
repositorio pase a privado, el enlace sigue andando **si** cargaste
`GITHUB_TOKEN` en Vercel (ver la tabla de variables).

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
