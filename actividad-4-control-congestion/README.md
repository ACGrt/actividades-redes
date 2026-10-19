# Informe Actividad 4 - Control de congestión
## André Guinart Carranca

Link a github: https://github.com/ACGrt/actividades-redes

Extensión del TCP simplificado de la actividad 3: se agrega Go-Back-N sobre las clases
`SocketUDP` y `SlidingWindowCC`, y control de congestión de TCP Tahoe (slow start y
congestion avoidance) con la clase `CongestionControl`.

## Archivos

| Archivo | Contenido |
|---|---|
| `SocketTCP.py` | Clase `SocketTCP`: handshake, Stop & Wait, Go-Back-N con y sin control de congestión, cierre y modos debug |
| `CongestionControl.py` | Clase `CongestionControl`: estado, `cwnd` y `ssthresh` de TCP Tahoe |
| `cliente.py`, `server.py` | Cliente y servidor de prueba: envían y reciben un archivo |
| `clientTest.py`, `serverTest.py`, `test2n.py` | Tests de la actividad 3 |
| `experimento.py` | Comparación de Go-Back-N con y sin control de congestión |
| `CongestionControl_test.py`, `socketUDP.py`, `slidingWindowCC.py` | Material entregado del curso |

Ejecución:

    % python3 server.py localhost 8000 --gbn > recibido.txt
    % python3 cliente.py localhost 8000 --gbn < archivo.txt

| Flag | Efecto |
|---|---|
| `--gbn` | usa Go-Back-N (sin el flag, Stop & Wait) |
| `--no-cc` | Go-Back-N sin control de congestión (solo cliente) |
| `--debug` | modo debug de manejo de pérdidas |
| `--debug-cc` | modo debug del control de congestión (solo cliente) |

Los tests también aceptan `--gbn`.

## 1. Parte 1: clase `CongestionControl`

| Variable | Valor inicial | Rol |
|---|---|---|
| `current_state` | `"slow_start"` | `"slow_start"` o `"congestion_avoidance"` |
| `MSS` | el del constructor | tamaño máximo en bytes de los datos de un segmento |
| `cwnd` | `MSS` | ventana de congestión en bytes |
| `ssthresh` | `None` | se define en el primer timeout |
| `acks_in_cwnd` | `0` | ACKs recibidos en congestion avoidance desde que `cwnd` creció |

- `event_ack_received()`: en slow start suma 1 MSS por ACK, y si `ssthresh` está definido
  y `cwnd >= ssthresh` pasa a congestion avoidance. En congestion avoidance suma 1 MSS
  cada `get_MSS_in_cwnd()` ACKs.
- `event_timeout()`: en cualquier estado deja `ssthresh = cwnd // 2`, `cwnd = 1 MSS` y
  vuelve a slow start.
- `get_MSS_in_cwnd()` retorna `cwnd // MSS`. Los demás métodos retornan las variables o
  el estado.

**Decisión:** en congestion avoidance se cuentan los ACKs en `acks_in_cwnd` y, cuando
llegan tantos como `get_MSS_in_cwnd()`, se suma 1 MSS y se reinicia el contador. Así `cwnd`
siempre es un entero de bytes. Sumar la fracción como float acumula error de redondeo: la
ventana puede quedar en 9,999… MSS en vez de 10, y `get_MSS_in_cwnd()` entregaría un
segmento menos.

`CongestionControl_test.py` pasa los 5 tests con `MSS = 7` y con MSS de 1 a 100, 128,
512, 1000 y 1460.

## 2. Parte 2: Go-Back-N

### 2.1. Respuestas a las preguntas

**(1) ¿Por qué sirve usar como base el código de Stop & Wait? ¿Qué similitud tienen?**

**R:** Stop & Wait es Go-Back-N con una ventana de tamaño 1, así que la estructura del
`send` se mantien: armar los segmentos, enviar, esperar el ACK, avanzar y retransmitir en
timeout. Ambos usan un solo timer y el receptor acepta solo el segmento que espera. Lo que
cambia es que Go-Back-N envía hasta N segmentos sin esperar ACK, al hacer timeout reenvía
la ventana completa, y un ACK puede mover la ventana varios espacios.

**(2) ¿Qué ocurre con `recv`? ¿Cambia con el uso de `SocketUDP` y `SlidingWindowCC`?**

**R:** No necesita ninguna de las dos. El receptor nunca retransmite, así que no necesita
timers, y su ventana de recepción es de tamaño 1, así que no necesita una ventana
deslizante. Por eso `recv_using_go_back_n` tiene la misma estructura que el `recv` de
Stop & Wait; solo cambia el ACK (sección 2.3). Además, si el receptor enviara los ACK con
`SocketUDP.sendto`, cada envío arrancaría un timer que nadie detiene, por eso salen por el
socket normal.

### 2.2. `send`, `recv` y socket compartido

El código de la actividad 3 quedó en `send_using_stop_and_wait` y
`recv_using_stop_and_wait`. `send(message, mode)` y `recv(buff_size, mode)` eligen la
versión según `mode` (`"stop_and_wait"` por defecto, o `"go_back_n"`).

**Decisión:** `SocketUDP` crea el socket UDP y `SocketTCP` usa ese mismo socket
(`self.udp_socket = self.socketUDP.socket_udp`). El handshake, el cierre y Stop & Wait
siguen usando `settimeout`. `send_using_go_back_n` pone el socket en modo "no bloqueante",
que es lo que necesita `SocketUDP.recvfrom`, y al terminar restaura el timeout. Así la
conexión mantiene un solo puerto y no hubo que reescribir el handshake ni el cierre.

`settimeout(timeout)` cambia el timeout del socket y el de los timers de `SocketUDP`, y
`accept()` lo propaga al socket de la conexión.

### 2.3. Números de secuencia y ACKs

`SlidingWindowCC` numera por bytes, así que en Go-Back-N el ACK lleva `seq + len(data)`,
el siguiente byte esperado, y es acumulativp. El `seq_num` de ambos lados avanza en bytes y
queda sincronizado para el cierre.

### 2.4. Emisor y receptor

**Emisor:** como en Stop & Wait, el primer elemento de `data_list` es el largo del mensaje.
Un solo timer (índice 0) cubre toda la ventana; `SocketUDP.sendto` lo arranca solo si no
está corriendo.

- **Timeout:** se detiene el timer y se reenvía la ventana. Hay que detenerlo antes,
  puesto que un `Timer` que ya venció no puede volver a iniciarse y el `sendto` falla.
- **ACK válido:** la ventana se mueve hasta el segmento que confirma y se envían los que
  entran. El timer se reinicia al enviar; si no hay nada nuevo que enviar, sigue
  corriendo para los segmentos que quedan.
- **ACK duplicado, SYN o FIN:** se ignoran.
- **Dato duplicado del otro lado:** se reenvía su ACK, igual que en Stop & Wait.

Sin control de congestión la ventana es fija de 8 segmentos.

**Receptor:** acepta solo `seq == seq_num`. Un segmento fuera de orden (se perdió uno
anterior) o duplicado (se perdió su ACK) se descarta y se reenvía el último ACK.

**Decisión:** en `recv_close`, ante un dato duplicado se responde con `self.seq_num` (el
último ACK enviado) en vez de `seq + 1`. En Stop & Wait da lo mismo, pero en Go-Back-N
`seq + 1` no confirma ningún segmento y, si se perdía el último ACK, el emisor
retransmitía para siempre.

## 3. Parte 3: control de congestión

- `send_using_go_back_n` divide el mensaje en trozos de `MSS = 8` bytes, con o sin
  control de congestión.
- `congestion_control_on` es `True` por defecto y se cambia con
  `set_congestion_control_on()`.
- `congestion_controler = CongestionControl(8)` se crea al inicio de cada `send`, así cada
  envío parte en slow start.

**¿Qué valor tiene `window_size` al inicializar la ventana?** 1, porque `cwnd` parte en
1 MSS:

    [CC] start | slow_start | cwnd=8 B (1 MSS) | ssthresh=None | window_size=1

**Eventos:**

- **Timeout:** `event_timeout()`, `window_size = get_MSS_in_cwnd()`,
  `update_window_size(window_size)` y se reenvía lo que queda en la ventana (1 segmento).
- **ACK nuevo:** `event_ack_received()` una vez por ACK (un ACK acumulativo cuenta como
  uno), se actualiza la ventana y se envían todos los elementos que entraron, por avance y
  por crecimiento.

**Caso borde:** si la ventana se achica después de enviar sus últimos elementos, puede
llegar un ACK que cae más allá de ella. En ese caso se mueve la ventana completa, como si
hubiera llegado el ACK de su último elemento, hasta que el ACK quede dentro.

## 4. Modo debug

Se mantienen los mensajes de la actividad 3 y se agregan:

| Mensaje | Significado |
|---|---|
| `send: timeout waiting for ACK of seq=N, resending the window` | se perdió un dato de la ventana o su ACK |
| `send: duplicate ACK seq=N ignored` | ACK que no confirma nada nuevo |
| `send: ACK seq=N past the window, moving the whole window` | caso borde de la ventana que se achica |
| `recv: out of order segment seq=N (expected M), ...` | se perdió un segmento anterior |
| `recv: duplicate segment seq=N (its ACK was lost), ...` | se perdió el ACK de ese dato |

`--debug-cc` escribe una línea por evento de control de congestión:

    [CC] <evento> | <estado> | cwnd=<bytes> B (<k> MSS) | ssthresh=<valor> | window_size=<k>

## 5. Pruebas

Las respuestas a las preguntas de la parte 2 están en la sección 2.1.

### 5.1. Integridad de los datos

    % sudo tc qdisc add dev lo root netem loss 20%
    % python3 server.py localhost 8000 --gbn --debug > recibido.txt
    % python3 cliente.py localhost 8000 --gbn --debug < archivo.txt
    % cmp archivo.txt recibido.txt && echo "idénticos"

| Prueba | Stop & Wait | Go-Back-N sin control | Go-Back-N con control |
|---|---|---|---|
| `test2n.py`, `serverTest.py` / `clientTest.py` | Passed | — | Passed |
| Archivo de 12585 B, sin pérdidas | idénticos | idénticos | idénticos |
| Archivo de 1500 B, `netem loss 20%` | idénticos | idénticos | idénticos |

**Pérdida de un dato** (`seq=87`). El receptor descarta los segmentos siguientes y
responde con el ACK 87; el emisor ignora esos ACK duplicados y reenvía la ventana al vencer
el timer:

    [servidor] recv: out of order segment seq=95 (expected 87), discarding it and resending ACK
    ...
    [cliente]  send: duplicate ACK seq=87 ignored
    [cliente]  send: timeout waiting for ACK of seq=87, resending the window

### 5.2. Control de congestión sin pérdidas

No hubo timeouts espontáneos. Sin timeouts `ssthresh` nunca se define, así que todo el
envío queda en slow start y cada ACK suma 1 MSS: con 100 B la ventana llega a 15 MSS, y
con 12585 B a 794 MSS.

### 5.3. Control de congestión con pérdidas

Con `netem loss 20%` y el archivo de 1500 B, la ventana se mantiene entre 1 y 6 MSS. Cada
línea muestra el estado después del evento.

    [CC] ACK seq=535 | congestion_avoidance | cwnd=48 B (6 MSS) | ssthresh=4 | window_size=6
    [CC] timeout | slow_start | cwnd=8 B (1 MSS) | ssthresh=24 | window_size=1
    [CC] ACK seq=543 | slow_start | cwnd=16 B (2 MSS) | ssthresh=24 | window_size=2
    [CC] timeout | slow_start | cwnd=8 B (1 MSS) | ssthresh=8 | window_size=1
    [CC] ACK seq=551 | congestion_avoidance | cwnd=16 B (2 MSS) | ssthresh=8 | window_size=2

El timeout en congestion avoidance deja `ssthresh = 48 // 2 = 24`. El siguiente ACK sigue
en slow start porque `16 < 24`. El timeout en slow start deja `ssthresh = 8`, y el ACK
siguiente pasa a congestion avoidance porque `16 >= 8`.

    [CC] ACK seq=343 | congestion_avoidance | cwnd=16 B (2 MSS) | ssthresh=4 | window_size=2
    [CC] ACK seq=351 | congestion_avoidance | cwnd=16 B (2 MSS) | ssthresh=4 | window_size=2
    [CC] ACK seq=359 | congestion_avoidance | cwnd=24 B (3 MSS) | ssthresh=4 | window_size=3
    [CC] ACK seq=367 | congestion_avoidance | cwnd=24 B (3 MSS) | ssthresh=4 | window_size=3
    [CC] ACK seq=375 | congestion_avoidance | cwnd=24 B (3 MSS) | ssthresh=4 | window_size=3
    [CC] ACK seq=383 | congestion_avoidance | cwnd=32 B (4 MSS) | ssthresh=4 | window_size=4

En congestion avoidance `cwnd` sube 1 MSS cada 2 ACKs con 2 MSS y cada 3 ACKs con 3 MSS.

**Caso borde de la ventana que se achica.** Tras el timeout de `seq=951` la ventana queda
en 1 segmento, pero el receptor ya tenía el 951 y el 959. Ante el 951 reenviado responde
con el ACK 967, que cae más allá de la ventana:

    [cliente]  send: timeout waiting for ACK of seq=951, resending the window
    [servidor] recv: duplicate segment seq=951 (its ACK was lost), resending ACK
    [cliente]  send: ACK seq=967 past the window, moving the whole window

### 5.4. Comparación con y sin control de congestión

    % sudo tc qdisc add dev lo root netem loss 20%
    % python3 experimento.py archivo.txt 5

`experimento.py` usa un timeout de 0,5 s y envía el archivo 5 veces con control de
congestión y 5 sin él, midiendo el tiempo de `send` y `number_of_sent_segments` (segmentos
de datos enviados, incluidas las retransmisiones). El enunciado pregunta por un archivo de
más de 1000 B y luego pide uno de 100 B; se usó uno de 1500 B (189 segmentos sin
retransmisiones).

| Repetición | Tiempo con control (s) | Segmentos con control | Tiempo sin control (s) | Segmentos sin control |
|---|---|---|---|---|
| 1 | 25.54 | 307 | 31.55 | 674 |
| 2 | 32.55 | 329 | 26.04 | 598 |
| 3 | 26.04 | 310 | 27.54 | 623 |
| 4 | 27.04 | 313 | 28.54 | 637 |
| 5 | 36.05 | 339 | 26.04 | 605 |
| Promedio | 29.44 | 319.6 | 27.94 | 627.4 |

Los 10 envíos llegaron íntegros.

**¿Cómo se comparan?** Con control de congestión se envía cerca de la mitad de los
segmentos. Sin control, cada timeout reenvía la ventana completa de 8 segmentos; con
control, la ventana queda en 1 segmento y se reenvía solo ese.

**¿Cuál toma menos tiempo?** Sin control, por poco (27,94 s contra 29,44 s), pero la
diferencia es menor que la variación entre repeticiones. En ambos casos el tiempo lo ponen
las esperas de 0,5 s de los timeouts: sin pérdidas el mismo archivo se envía en 0,01 a
0,02 s.

## 6. Limitaciones

- **Timeout con `cwnd = 1 MSS`.** Deja `ssthresh = 4 B`, menos de un MSS, así que el
  siguiente ACK pasa directo a congestion avoidance. Es lo que resulta de
  `ssthresh = cwnd/2` y lo que esperan los tests.
- **Cierre con mucha pérdida.** Viene de la actividad 3: si se pierden los 4 FIN de
  `close()`, el cliente asume que la contraparte cerró y `recv_close()` queda esperando
  el FIN sin límite. Los datos ya llegaron completos en ese caso.
- **Sin límite de `cwnd`.** Sin pérdidas la ventana crece mientras haya datos que enviar.
