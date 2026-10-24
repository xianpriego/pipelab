# Pipelab

Herramienta web para **prototipar pipelines de GStreamer de forma gráfica e
interactiva**: arrastras elementos a un lienzo, los conectas, el sistema
comprueba que cada unión sea correcta en teoría (caps, pads, hilos) y te
sugiere buenas prácticas; después ejecutas la pipeline, ves los mensajes del
bus, previsualizas lo que produce y la exportas a código para integrarla en
un producto real.

Todo corre en Docker. La imagen trae **GStreamer 1.28** con base, good, bad,
ugly, libav, **todos los plugins de Rust (gst-plugins-rs 0.15)**, nvcodec
(NVENC/NVDEC/CUDA), VA-API, QSV/MSDK, HIP, OpenCV, ONNX, WebRTC, RTSP server,
GES… unos **1 470 elementos**.

## Arranque rápido

```bash
make up            # construye y arranca en http://localhost:8080
make up GPU=1      # igual, con acceso a la GPU NVIDIA (nvh264enc, cudaupload…)
make up DEVICES=1  # con /dev/video0 y puertos UDP/RTSP publicados (ajusta docker-compose.devices.yml)
make logs          # logs de los contenedores
make down          # parar
make test          # tests + linters de backend y frontend (en Docker)
```

Requisitos: Docker con Compose v2. Para la GPU, driver NVIDIA y NVIDIA
Container Toolkit en el host. La primera vez el backend introspecciona todo el
registro de GStreamer (unos segundos) y lo cachea en `data/cache`.

Con `GPU=1` está todo `nvcodec`: decodificadores y codificadores NVDEC/NVENC
(`nvh264dec`, `nvh265enc`…), `cudaupload`/`cudadownload` y los filtros que
trabajan sin sacar el vídeo de la GPU (`cudaconvertscale`, `cudaconvert`,
`cudascale`, `cudacompositor`; la imagen incluye NVRTC para compilarlos). Los
elementos se registran según la tarjeta: p. ej. AV1 (`nvav1enc`/`nvav1dec`)
solo aparece en GPUs que lo soportan por hardware (RTX 30/40 o superiores).

Los datos viven en `./data`: `projects/` (un JSON por espacio de trabajo),
`media/` (ficheros de entrada y salida de las pipelines) y `cache/`.

## Qué puedes hacer

### Espacios de trabajo
- Crear pipelines vacías o desde **plantillas** (patrón de test, tono de audio,
  grabación MP4, tee preview+grabación, input-selector, picture-in-picture,
  RTP loopback, reproducción de fichero, HLS, análisis de audio, NVENC/NVDEC).
  Solo se ofrecen las plantillas cuyos elementos existen en la máquina.
- **Importar** una línea `gst-launch-1.0` existente (se convierte en grafo y se
  autodistribuye) o un JSON exportado. Duplicar, renombrar, borrar.

### Editor
- **Paleta agrupada por categorías** (fuentes, sinks, demuxers, muxers,
  decoders, encoders, parsers, payloaders, conversores, efectos, mezcladores y
  selectores, red…) con búsqueda y filtros por categoría y por familia (base,
  good, bad, ugly, libav, rs). Arrastrar al lienzo o doble clic.
- **Selectores en el propio nodo**: en `input-selector`/`output-selector` se
  elige el pad activo pinchando en él; las ramas inactivas se dibujan como
  descartadas (sus buffers llegan pero el selector los tira).
- **Pads reales** en cada nodo: *always*, *request* (`sink_%u` crea `sink_0`,
  `sink_1`…) y *sometimes* (punteados, se enlazan en tiempo de ejecución).
- **Inspector** con la ficha del elemento (clase, plugin, rango, jerarquía,
  pad templates con sus caps y enlace a la documentación oficial) y
  **todas las propiedades** de cada elemento con un control
  adecuado a su tipo (booleanos, rangos numéricos, enums, flags, caps,
  fracciones, pads…), valores por defecto, reset, y **propiedades de pad**
  (p. ej. `xpos`/`alpha` de `compositor.sink_1`).
- Deshacer/rehacer, copiar/pegar, autolayout, autoguardado.

### Validación teórica de cada unión
Al conectar dos pads el backend calcula las **caps efectivas** que fluyen por
el grafo (atravesando queue, tee, capsfilter…) y:
- **bloquea** uniones imposibles (caps incompatibles, pad ya enlazado, ciclos,
  direcciones erróneas) y **sugiere los elementos intermedios** que las hacen
  posibles, buscándolos en el catálogo (p. ej. `x264enc`, `cudadownload`,
  `opusenc`, `h264parse`…). Un clic los inserta;
- **avisa** de uniones válidas pero frágiles y propone el patrón seguro:
  `videoconvert`/`audioconvert ! audioresample` cuando los formatos podrían no
  negociar, parsers entre depayloaders/encoders y decoders/muxers, `tee` con
  `queue` por rama si intentas sacar dos enlaces de un mismo pad.

Además, el grafo completo se revisa continuamente con reglas modulares
(`backend/pipelab/graph/rules/`):

| Regla | Qué detecta |
| --- | --- |
| `missing-element`, `duplicate-name` | elementos no instalados, nombres repetidos |
| `invalid-property`, `required-property` | valores fuera de rango/enum inválido, `location`/`uri` sin rellenar |
| `no-source`, `no-sink`, `unlinked-pad` | pipelines incompletas, pads sin enlazar (errores *not-linked*) |
| `caps-incompatible`, `pad-in-use`, `cycle` | lo mismo que al conectar, para enlaces existentes |
| `tee-queue`, `demuxer-queue` | ramas sin `queue` (bloqueos/deadlocks al hacer preroll) |
| `aggregator-queue`, `live-source-queue` | entradas de muxers/mixers y fuentes en vivo sin desacoplar hilos |
| `source-caps` | fuentes flexibles sin `capsfilter` que fije resolución/frecuencia |
| `safety-converter`, `missing-parser` | conversores y parsers recomendados |
| `encoder-latency`, `rtp-config-interval`, `muxer-eos` | `tune=zerolatency` al emitir por red, SPS/PPS repetidos, MP4 que necesita EOS |
| `loopback-async` | emisor y receptor de red en la misma pipeline (interbloqueo de preroll → `async=false`) |

Cada aviso trae una o varias **soluciones aplicables con un clic**.

### Ejecución
- **Play / Pause / Stop (EOS, finaliza ficheros) / Kill**. Cada pipeline corre
  en **su propio proceso**: un plugin que falla no tumba la aplicación.
- **Mensajes del bus** en tiempo real (errores, warnings, EOS, tags, QoS,
  mensajes de elementos como `level`/`spectrum`…) con el **nodo de origen
  resaltado** y una **pista** de causa probable (not-negotiated, not-linked,
  fichero no encontrado, CUDA no disponible…).
- **Diagnóstico exacto de negociación**: ante un `not-negotiated` se señala el
  enlace culpable y el campo que no encaja (p. ej. `h264parse0.src →
  nvh264dec0.sink: width=5120 not in [ 48, 4096 ]`), aunque el error lo
  publique la fuente; igual para pads dinámicos que no pueden enlazar.
- Log de `GST_DEBUG` con nivel configurable por proyecto.
- **Caps negociadas, fps y bitrate de cada enlace** sobre el propio lienzo,
  con **animación de los buffers** viajando por los enlaces (densidad según
  fps, color según el tipo de medio; desactivable).
- **Probes ("pinchar cables")**: sobre cualquier enlace en ejecución, un
  probe registra cada buffer (pts, dts, duración, tamaño, flags como
  keyframe/delta) y cada evento (caps, segment, tags, EOS…) en la pestaña
  **Probe**, al estilo de un mini-Wireshark.
- **Cambios en caliente**: las propiedades mutables en PLAYING (o
  controlables) se aplican al vuelo y se muestra el valor realmente en efecto
  (p. ej. `input-selector.active-pad`, `videobalance`, `volume`, `pattern`).
  Lectura de valores vivos (niveles de `queue`, estadísticas…).
- **Grafo real** de la pipeline en ejecución (volcado DOT → SVG).
- **Rendimiento** (pestaña *Performance* y sobre los propios nodos):
  - tiempo que pasa cada buffer dentro de cada elemento (mismo PTS entrando y
    saliendo; en una `queue` es el tiempo de espera);
  - nivel de cada `queue`/`queue2` con barra de llenado y desbordes;
  - hilos de streaming con su CPU y los elementos que recorre cada uno;
    *Colour links by thread* pinta cada enlace del color de su hilo, para ver
    dónde hacen falta queues;
  - avisos de cuellos de botella: queue llena (lo que viene detrás no da
    abasto) o hilo cerca del 100 % de un núcleo.

### Funciones avanzadas (ocultas por defecto)
Los scripts de probe, los slots dinámicos, las funciones de API y los probes
sin código descritos a continuación están **ocultos en el editor** para
mantenerlo sencillo: en cada enlace quedan **Watch** (ver lo que pasa) y
**Probe** (lista de buffers y eventos). Para activarlos:
`PIPELAB_ADVANCED=1 make up GPU=1`.

### Scripts de probe (lógica sobre pads)
Para prototipar la lógica que en producción irá en *pad probes*, cada enlace o
elemento puede llevar **scripts en Python** con callbacks opcionales:
`setup(ctx)`, `on_buffer(ctx, pad, buffer)` y `on_event(ctx, pad, event)` (que
pueden devolver `DROP`), `on_property(ctx, name, value)` (intercepta un cambio
de propiedad pedido desde la UI) y `on_trigger(ctx, value)` (botón *Trigger*).
`ctx` ofrece `element`, `pad`, `state`, `get(nombre)`, `pad_named()`,
`is_keyframe(buffer)`, `request_keyframe()`, `set(elemento, prop, valor)` y
`log()` (los mensajes salen en la pestaña Probe).

Recetas incluidas, editables: **cambio de `input-selector`/`output-selector`
solo en keyframe** (pide además un keyframe al encoder para que sea rápido),
descartar hasta el primer keyframe, compuerta abrir/cerrar, simular pérdida de
paquetes, pedir keyframes periódicos, detector de cortes, EOS tras N segundos y
registro de eventos. Los scripts se validan (errores de sintaxis con línea), un
fallo en tiempo de ejecución se notifica sin parar la pipeline y la
**exportación a Python los incluye y ejecuta igual** (con `set_property()` y
`trigger()` para tu aplicación); en C/Rust quedan como notas para portarlos.

### Componentes (macrobloques)
Selecciona varios elementos y **agrúpalos en un componente** (p. ej. una
entrada RTSP: `rtspsrc → depay → parse → decoder`). Los componentes viven en
una **biblioteca global** compartida por todos los proyectos; sus instancias
están enlazadas (editar el componente actualiza todas) y se pueden *expandir*
para obtener una copia independiente. Doble clic para entrar y editar el
interior, con migas de pan para salir. Exponen **puertos** (pads internos) y
**parámetros** (propiedades internas, p. ej. `location`, `latency`). En
ejecución y al exportar cada instancia es un `GstBin` con *ghost pads*.

- **Starters…** (paleta): componentes listos para añadir a la biblioteca y
  adaptar — entradas RTSP H.264/H.265 (CPU o NVIDIA), entrada de fichero,
  escalador, codificador H.264 (x264 o NVENC), grabador MP4 por segmentos,
  salidas SRT, RTMP y RTP/UDP, y un display que no frena la rama. Los que
  necesitan elementos que no hay en la máquina (NVIDIA sin GPU) lo indican.
- **Export to file / Import…**: un componente se descarga como
  `<id>.pipelab-component.json` junto con los componentes que contiene, y se
  importa en otra máquina (pregunta antes de reemplazar los que ya existan).

### Pipelines dinámicas y API de la pipeline
- **Slots**: "N instancias del componente X conectadas a `compositor.sink_%u`",
  con configuración inicial antes de arrancar y alta/baja/reinicio **en
  caliente** (desenlace seguro: estado NULL, liberar pads request, drenar con
  EOS las ramas consumidoras). Generan automáticamente `add_<item>()`,
  `remove_<item>(id)`, `restart_<item>(id)` y `list_<slots>()`.
- **Funciones propias** de la pipeline (nombre, parámetros tipados y una lista
  de acciones) que el software propietario llamará; se prueban desde la pestaña
  API con botones.

### Probes sin código (reglas)
Sobre cualquier enlace o elemento: **Cuando** (pasa un buffer, evento, *no
pasa nada durante N ms*, vuelven los datos, cada N ms, se pide cambiar una
propiedad, señal…) **Si** (keyframe, flags, tamaño, saltos de PTS, cada n,
tasa, campo de caps, variables, pad, aleatorio…) **Entonces** (pasar,
descartar, bloquear, **publicar un mensaje en el bus**, cambiar propiedades,
enviar eventos, pedir keyframe, variables, log, señales, **llamar a funciones**
de la API, añadir/quitar/reiniciar instancias). Plantillas: watchdog, cambio en
keyframe, descartar hasta keyframe, pérdida de paquetes, compuerta, alarma de
tasa, EOS tras N s. Los scripts Python siguen disponibles como vía de escape.

**Exportación**: componentes, slots, funciones y reglas se generan como
**código real en Rust (gstreamer-rs 0.25) y Python**: una librería con un
`build_<componente>()` por componente, el tipo de la pipeline con su
configuración (las instancias iniciales de cada slot), `start()`, `stop()`,
los métodos de la API, los de cada slot y un callback para los mensajes de
aplicación; cada regla se convierte en código explícito. Ejemplo con un slot
`inputs` de un componente `rtsp-input` y una función `set_layout`:

```python
p = StudioPipeline({"inputs": [{"location": "rtsp://cam1/stream"}]})
p.on_message(lambda name, fields, source: print(name, fields))  # p. ej. "branch-down"
p.start()
cam = p.add_input(location="rtsp://cam2/stream")       # -> "input1"
p.restart_input(cam); p.remove_input(cam); p.set_layout(columns=3)
```

```rust
let p = StudioPipeline::new(Config { inputs: vec![RtspInputParams { location: Some("rtsp://cam1/stream".into()), ..Default::default() }] })?;
p.connect_message(|m| println!("{} {:?}", m.name, m.field("element")));
p.start()?;
let cam = p.add_input(RtspInputParams { location: Some("rtsp://cam2/stream".into()), ..Default::default() })?;
p.remove_input(&cam)?;
```

El contrato detallado está en [docs/DYNAMIC.md](docs/DYNAMIC.md).

### Visualización de resultados
- Los sinks de pantalla (`autovideosink`, `xvimagesink`, `glimagesink`…) se
  sustituyen automáticamente por una **vista previa en el navegador**, y los de
  audio (`autoaudiosink`, `pulsesink`, `alsasink`…) por **audio escuchable**
  en el navegador con vúmetro. La sustitución no altera la negociación de la
  pipeline del usuario.
- **"Watch this link"**: inspecciona lo que pasa por **cualquier enlace** en
  ejecución; el vídeo crudo o codificado se decodifica aparte y se muestra, el
  audio se puede escuchar.
- **Outputs**: los ficheros generados (`filesink`, `splitmuxsink`,
  `multifilesink`, `hlssink2`…) se listan con reproductor integrado (vídeo,
  audio, imagen, **HLS**). También puedes subir ficheros de entrada. Las rutas
  relativas se resuelven dentro de `data/media`.

### Exportación
Desde el editor, **Export** genera:
- `gst-launch-1.0` (script de shell, con referencias por nombre y pads explícitos solo donde hacen falta);
- **Python** (PyGObject): clase embebible con `build()/start()/stop()`, pads request, `pad-added` para pads dinámicos, gestión del bus y SIGINT→EOS;
- **C**: programa completo (compilable con `gcc main.c $(pkg-config --cflags --libs gstreamer-1.0)`);
- **Rust** (gstreamer-rs);
- **JSON** de Pipelab (reimportable).

Los tests comprueban que la salida `gst-launch` la acepta `Gst.parse_launch`
y que el Python y el C generados compilan y se ejecutan hasta EOS; `make
test-rust` compila con cargo los escenarios dinámicos en Rust (slots,
watchdog, cambio en keyframe, funciones) y los ejecuta.

## Arquitectura

```
navegador (React + React Flow) ──HTTP/WebSocket──► web (nginx) ──► api (FastAPI + PyGObject)
                                                                    ├─ catálogo (introspección de todos los elementos)
                                                                    ├─ grafo: caps efectivas, comprobación de enlaces, reglas, fixes, layout
                                                                    ├─ export / import
                                                                    └─ runtime: un proceso worker por pipeline en ejecución
```

El contrato entre módulos (modelos, endpoints, eventos) está en
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

- `backend/` — Python 3.14, FastAPI, PyGObject sobre Arch Linux con repositorios
  **fijados a un snapshot** (`ARCH_SNAPSHOT` en el Dockerfile) para builds
  reproducibles. Para actualizar GStreamer basta con subir esa fecha.
- `frontend/` — React 18 + TypeScript + Vite, `@xyflow/react`, `zustand`.

## Desarrollo

```bash
make test-backend    # ruff + pytest (incluye pipelines reales y todas las plantillas)
make test-frontend   # eslint + tsc + vitest + build
make test-e2e        # Playwright/Chromium contra el stack real (web + api)
make test-rust       # compila y ejecuta las exportaciones Rust (cargo en Docker)
make test GPU=1      # todo, incluyendo los tests de elementos NVIDIA
make dev             # modo desarrollo con recarga en caliente (UI en :5173)
```

Los tests de backend usan el catálogo real del contenedor y ejecutan
pipelines de verdad: cada plantilla se valida, se arranca y se comprueba que
circulan datos por todos sus enlaces. Los e2e recorren la interfaz:
crear desde plantilla, ejecutar con preview, cambio en caliente de
`input-selector`, tap de un enlace, errores con pista, salidas reproducibles,
enlace incompatible con inserción del puente sugerido, exportación e
importación. La documentación OpenAPI está en `http://localhost:8080/api/docs`.

## Limitaciones conocidas

- Dentro de Docker no hay pantalla ni tarjeta de sonido: los sinks de
  pantalla/audio se previsualizan en el navegador (desactivable por nodo).
- Las propiedades de tipo objeto (p. ej. `playbin.video-sink`) no se pueden
  editar como texto, igual que en `gst-launch`.
- Las propiedades sin marca de mutabilidad se pueden *intentar* cambiar en
  caliente; si el elemento no las aplica, el valor leído lo indica.
- Para recibir streams de otras máquinas (RTP/RTSP/SRT) publica los puertos
  necesarios (ver `docker-compose.devices.yml`).
