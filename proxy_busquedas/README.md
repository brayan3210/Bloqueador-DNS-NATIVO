# Capa extra: bloqueo de BÚSQUEDAS por palabra (proxy local)

Módulo **opcional** del [Bloqueador DNS](../README.md). El filtro DNS bloquea
**destinos** (dominios). Esta capa bloquea el **texto que escribes en el
buscador** (Google, Bing, YouTube, DuckDuckGo, Yandex…) y en la **búsqueda de
imágenes**, sin usar el SafeSearch de Google.

> Es una capa **aparte**: se suma al filtro DNS sin tocarlo. Puedes tener solo
> el DNS, o DNS + esta capa.

---

## ¿Por qué hace falta y cómo funciona?

Cuando escribes `chubby` en Google, tu equipo solo le pregunta al DNS por
`www.google.com`; la palabra viaja **cifrada dentro del HTTPS**, así que el
filtro DNS **no la ve**. Para leer ese texto sin SafeSearch, esta capa monta un
**proxy local con inspección TLS** (mitmproxy) **en tu propio equipo**:

1. Instala un **certificado raíz local** (solo en tu PC) para poder leer tu
   propio HTTPS. No manda tu tráfico a ningún lado.
2. Se pone como **proxy del sistema** (`127.0.0.1:8080`).
3. En cada búsqueda lee el texto (`q`, `p`, `text`, `search_query`…) y lo pasa
   al **motor** (`motor_busqueda.py`). Si es explícito, en vez de resultados
   muestra una **página de bloqueo** → no cargan ni imágenes ni videos.
4. Se mantiene vivo con una **tarea SYSTEM** (arranca con Windows, se reinicia
   sola), igual que el filtro DNS.

Para poder inspeccionar, el instalador **desactiva QUIC/HTTP3** (si no, Chrome
usaría un canal que el proxy no ve).

---

## El "cerebro": catálogo + excepciones

Dos listas en `listas/` (edítalas a tu gusto):

- **`catalogo_busqueda.txt`** — términos porno que **bloquean**. Palabra suelta
  = coincide por inicio de palabra (`porn` atrapa *porn/porno/pornografía* pero
  **no** *essex*); frase con espacios = coincide como subcadena (`nasty ass`).
- **`excepciones_educativas.txt`** — palabras anatómicas/de salud (`pene`,
  `vagina`, `menstruación`, `útero`…) que **NUNCA bloquean solas**, para que
  puedas estudiar biología o leer. Se **restan** del catálogo al cargar.

**Regla:** se bloquea si aparece un término explícito del catálogo. Una palabra
anatómica sola **pasa**; pero si en la misma búsqueda hay además un término
explícito, se bloquea.

| Búsqueda | Resultado |
|---|---|
| `pene anatomía humana` | ✅ permite (educativo) |
| `menstruación ciclo` | ✅ permite |
| `vagina xxx` | ⛔ bloquea (por `xxx`) |
| `chubby`, `nasty ass`, `videos porno` | ⛔ bloquea |
| `noticias bbc`, `análisis de datos` | ✅ permite (sin falsos positivos) |

> `bbc` **no** está en el catálogo a propósito: rompería noticias de la BBC.

Probar el motor sin instalar nada:
```bash
python motor_busqueda.py     # corre 14 casos de autoprueba
```

---

## Instalar / aplicar cambios / quitar

```powershell
# Instalar la capa (pide admin; instala mitmproxy, certificado, proxy, tarea)
proxy_busquedas\instalar_proxy.ps1

# Tras editar catalogo_busqueda.txt / excepciones_educativas.txt:
proxy_busquedas\aplicar_proxy.ps1

# Quitar la capa (PIDE LA CONTRASEÑA, la misma del filtro DNS):
proxy_busquedas\desactivar_proxy.ps1
```

Comparte la **misma contraseña** (`password_hash` en `config.json`) que el
filtro DNS. Ajusta el puerto en `config.json → proxy_busquedas.puerto`.

---

## Límites honestos

- **Solo navegador (HTTPS).** Apps con *certificate pinning* (banca, algunas
  nativas) no se inspeccionan; si alguna se rompe con el proxy activo, se
  excluye. La mayoría de tus búsquedas ocurren en el navegador.
- **Es fricción, no una cárcel.** Como eres administrador, podrías quitar el
  certificado o el proxy. Por eso la desactivación limpia **pide contraseña**.
- **Imágenes:** se bloquea la **búsqueda** antes de mostrar resultados. Una
  miniatura suelta sin texto no se clasifica; lo que se frena es que escribas
  las palabras explícitas.
- **Mantenimiento:** el catálogo lo afinas tú (puede haber falsos positivos;
  los términos ambiguos vienen comentados).

---

## Archivos del módulo

```
proxy_busquedas/
├── motor_busqueda.py        cerebro: catálogo + excepciones (con autoprueba)
├── addon_proxy.py           addon de mitmproxy que bloquea la búsqueda
├── iniciar_proxy.py         arranca mitmdump con el addon (lee config.json)
├── vigilante_proxy.py       mantiene vivo el proxy (relanzador)
├── bloqueo.html             página que ve el usuario al bloquear
├── instalar_proxy.ps1       instala todo (admin)
├── aplicar_proxy.ps1        aplica cambios de listas y reinicia
├── desactivar_proxy.ps1     quita la capa (pide contraseña)
├── requirements.txt         mitmproxy
└── listas/
    ├── catalogo_busqueda.txt        términos que bloquean
    └── excepciones_educativas.txt   anatómicos que NO bloquean solos
```
