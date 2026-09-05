# Informe Actividad 2 - DNS
Link a github: https://github.com/ACGrt/actividad-1-proxy

Resolver DNS iterativo implementado con sockets, sin usar `dnslib`: el parseo y la
construcción de mensajes se hacen a mano sobre los bytes del protocolo.

## Archivos

| Archivo | Contenido |
|---|---|
| `resolver.py` | Programa principal: sockets, función `resolver()`, modo debug |
| `DNS/parser.py` | `DNSParser`: pasa un mensaje DNS en bytes a un diccionario |
| `DNS/message.py` | `DNSMessage`: consultas sobre el mensaje ya parseado, y `build_query()` |
| `DNS/cache.py` | `DNSCache`: caché de los 3 dominios más frecuentes de las últimas 20 consultas |

Ejecución:

    % python3 resolver.py           # modo normal
    % python3 resolver.py --debug   # muestra las consultas internas

## 1. Tipo de socket

Usamos un socket **UDP** (`socket.SOCK_DGRAM`), no orientado a conexión, porque es
lo que define el protocolo DNS para consultas normales sobre el puerto 53.

Las razones concretas son:

- Una resolución DNS es un intercambio de un mensaje de ida y uno de vuelta. Un
  socket orientado a conexión gastaría un handshake de tres vías completo pra
  transportar un par de mensajes de unos cientos de bytes, más el cierre.
- Un resolver le habla a muchos servidores distintos en una sola
  resolución. Con TCP habría que abrir y cerrar una conexión por
  cada salto, lo que multiplica la latencia.
- La pérdida de mensajes se maneja en la capa de aplicación: el cliente
  simplemente reintenta la consulta.

Ambos sockets del programa son UDP: `sock_client`, asociado a `(IP_VM, 8000)` para
recibir consultas de los clientes, y `sock_server`, para consultar a los Name
Servers en el puerto 53.

## 2. Estructura de datos del parser

`DNSParser.parse()` devuelve un diccionario con:

| Campo | Contenido |
|---|---|
| `transaction_id`, `flags` | bytes crudos del header |
| `qdcount`, `ancount`, `nscount`, `arcount` | enteros |
| `qname` | nombre consultado, como texto (`'www.uchile.cl'`) |
| `question_section` | la sección Question en bytes, para reconstruir el mensaje |
| `answers`, `authority`, `additional` | listas de registros |

Cada registro de esas tres listas es a su vez un diccionario con `rr_name`,
`rr_type`, `rr_class`, `rr_ttl`, `rr_rdlength` y `rr_rdata`.

## 3. Funcionamiento del resolver

La función tiene la firma pedida:

    def resolver(mensaje_consulta: bytes, ip_addr=root_ip) -> bytes:

y sigue los pasos del enunciado:

- **a)** Envía la consulta a `ip_addr` (por defecto la raíz `198.41.0.4`) y espera
  la respuesta.
- **b)** Si la sección Answer trae un registro de tipo A, retorna **el mensaje
  completo en bytes**, no solo la IP, para que `dig` pueda interpretarlo. Como la
  consulta del cliente se reenvía sin modificar, el transaction ID de la respuesta
  ya coincide con el que el cliente espera.
- **c)** Si hay registros NS en Authority, es una delegación:
  - **c.i)** Si la sección Additional trae un registro A, se le manda la consulta
    original a esa primera dirección.
  - **c.ii)** Si no, se toma el nombre de un Name Server desde Authority y se
    resuelve su IP **usando recursivamente la propia función `resolver()`**,
    partiendo de nuevo desde la raíz. Para eso se construye una consulta nueva de
    tipo A por ese nombre con `build_query()`. Con la IP obtenida se vuelve al paso b).
- **d)** Cualquier otra respuesta se ignora y se devuelve tal cual al cliente.

Para el nombre del Name Server al que se consulta en c.i se usa el `rr_name` del
mismo registro A que aportó la IP, no el primer NS de Authority: el dueño del
registro A es por definición el servidor al que se le está preguntando, así que los
dos datos quedan consistentes por construcción.

## 4. Modo debug

Se activa con `--debug`. Muestra, para cada consulta interna, el dominio, el nombre
del Name Server e IP a la que se pregunta, e indica cuándo la respuesta salió del
caché:

    (debug) Consultando 'www.uchile.cl' a '.' con direccion IP '198.41.0.4'
    (debug) Consultando 'www.uchile.cl' a 'cl2-tld.d-zone.ca' con direccion IP '185.159.198.56'
    (debug) Consultando 'www.uchile.cl' a 'ns1.uchile.cl' con direccion IP '200.89.70.3'
    (debug)   200.89.70.3 responde: 200.89.76.36

    (debug) 'www.uchile.cl' servido desde el cache, sin salir a la red

La raíz es el único servidor al que nadie nos derivó, así que su nombre `'.'` sale
de una constante; para todos los demás, el nombre se conoce en el paso anterior, al
leer las secciones Authority y Additional de la delegación.

## 5. Caché

El caché guarda los 3 dominios más repetidos dentro de las últimas 20 consultas
recibidas desde clientes. Son **dos estructuras** con roles distintos:

- `history`: lista de a lo más 20 nombres de dominio, **con repeticiones**, en
  orden de llegada. Cuando entra uno nuevo y ya hay 20, sale el más antiguo.
- `cache`: diccionario de a lo más 3 entradas, de dominio a la respuesta DNS
  completa en bytes.

Una observacion sobre el diseño:

- **Empates.** Cuando varios dominios tienen la misma cantidad de apariciones, el
  orden lo define `sorted`, que es estable, así que gana el que apareció primero en
  la ventana. Consecuencia: si el tráfico es de
  puros dominios distintos, el caché queda vacío, lo que asumo, es correcto, porque no hay
  nada popular.


## 6. Limitaciones del paso d)

Ignorar "cualquier otra respuesta" es simple, pero deja fuera varios casos:

- **CNAME.** Es la limitación más importante y se ve en el experimento 1. Si la
  sección Answer trae solo registros CNAME y ningún A, el resolver no sigue la
  cadena. Peor: si además vienen registros NS en Authority, el código los
  interpreta como una delegación aunque no lo sean.
- **Solo tipo A.** Las consultas AAAA, MX, TXT o NS no se resuelven, aunque el
  parser sí sepa leerlas, pero por indicaciones en EOL solo trabajamos con tipo A,
  así que en este caso no es un problema.
- **Sin reintentos ni timeout.** Si un Name Server no contesta, la espera es
  indefinida.
- **Sin validación.** No se revisa el código de respuesta (RCODE) ni se comprueba
  que el transaction ID de la respuesta coincida con el de la consulta.

## 7. Pruebas de funcionalidad

| Comando | Resultado |
|---|---|
| `dig -p8000 @IP_VM eol.uchile.cl` | `NOERROR`, 1 CNAME a `oeol-c.uchile.cl` y **11 direcciones** `146.83.63.X` |
| `dig -p8000 @IP_VM eol.uchile.cl` (2ª vez) | mismas 11 direcciones, respondido por el **caché** |
| `dig -p8000 @IP_VM www.uchile.cl` | `200.89.76.36` |
| `dig -p8000 @IP_VM cc4303.bachmann.cl` | `104.248.65.245` |

Las 11 direcciones de `eol.uchile.cl` observadas fueron: 146.83.63.**31, 40, 64,
65, 68, 69, 71, 72, 73, 74, 77**. La segunda consulta devuelve exactamente el mismo
conjunto porque el caché entrega el mismo mensaje guardado, con el transaction ID
reemplazado.

Vale notar que `eol.uchile.cl` **sí** resuelve pese a ser un CNAME: el servidor
autoritativo de `uchile.cl` resuelve la cadena por su cuenta y devuelve el CNAME
junto con los registros A en la misma sección Answer. Como hay registros A, el paso
b) se cumple. El experimento 1 muestra el caso en que esto no ocurre.

La resolución de `cc4303.bachmann.cl` es la que ejercita el paso **c.ii**: el
servidor de `.cl` delega en `ns1.digitalocean.com` sin incluir su IP en Additional,
así que el resolver resuelve ese nombre desde la raíz antes de poder continuar.

## 8. Experimentos

### 8.1. `www.webofscience.com`

**No resuelve, y además deja al resolver dando vueltas indefinidamente.**

El servidor autoritativo responde así:

    ;; ANSWER SECTION:
    www.webofscience.com.    60  IN  CNAME  www-us.webofscience.com.
    www-us.webofscience.com. 60  IN  CNAME  www-us.webofscience.com.cdn.cloudflare.net.

    ;; AUTHORITY SECTION:
    webofscience.com.  172800  IN  NS  ns-1010.awsdns-62.net.
    ;; (Additional vacía)

El resolver lo interpreta de la siguiente forma: la sección Answer no tiene ningún
registro A, así que el paso b) no aplica. Pasa al paso c), ve registros NS en
Authority y concluye que es una delegación. Pero **no lo es**: esos NS son los name
servers de la propia zona. Como Additional viene vacía, entra al paso c.ii, resuelve
`ns-1010.awsdns-62.net`, obtiene la IP del mismo servidor que acaba de responder,
le hace la misma consulta, recibe la misma respuesta, y vuelve a empezar. El ciclo
no termina nunca.

La causa de fondo es que el resolver no maneja **CNAME**. Un CNAME es un alias: la
respuesta está diciendo "el nombre que buscas es en realidad este otro". El
enunciado asume que las respuestas o traen un A o son delegaciones, y este caso no
es ninguna de las dos.

**Cómo lo arreglaría.** Agregando un caso entre b) y c): si la sección Answer trae
registros CNAME pero ningún A, se toma el nombre destino del último CNAME de la
cadena y se reinicia la resolución con ese nombre desde la raíz, construyendo una
consulta nueva igual que en el paso c.ii. Al obtener la respuesta final se
concatenan los CNAME recorridos con los registros A encontrados.

Tal vez el resolver debería tener un límite de iteraciones o
detectar que está repitiendo la misma consulta al mismo servidor, para que un
dominio problemático falle rápido en vez de bloquear el servicio para todos los
demás.

### 8.2. `www.cc4303.bachmann.cl`

El resolver responde **NXDOMAIN**, con el SOA de `bachmann.cl` en la sección
Authority:

    ;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN
    ;; AUTHORITY SECTION:
    bachmann.cl.  1800  IN  SOA  ns1.digitalocean.com. hostmaster.bachmann.cl. ...

`dig @1.1.1.1 www.cc4303.bachmann.cl` devuelve exactamente lo mismo: `NXDOMAIN`.

Era lo esperable. `cc4303.bachmann.cl` sí existe y resuelve a `104.248.65.245`,
pero eso **no implica** que exista `www.cc4303.bachmann.cl`y que un nodo exista no crea automáticamente sus hijos. El prefijo `www` es una convención histórica, no una regla del protocolo, y solo funciona si el administrador de la zona creó explícitamente ese registro. En
`bachmann.cl` existe el registro para `cc4303` pero no para `www.cc4303`, y el
servidor autoritativo lo informa con NXDOMAIN, que significa "este nombre no existe
en el árbol", distinto de NOERROR con Answer vacía, que significaría "el nombre
existe pero no tiene registros de este tipo".

Este caso también muestra que el paso d) funciona bien: la respuesta no trae A ni
NS en Authority (trae un SOA), así que el resolver no intenta seguir ninguna
delegación y devuelve el mensaje tal cual.

### 8.3. ¿Son siempre los mismos Name Servers?

Repitiendo la misma consulta varias veces y observando el modo debug, la cadena
fue estable. Seis resoluciones consecutivas de `cc4303.bachmann.cl` recorrieron
siempre la misma secuencia:

    . -> cl2-tld.d-zone.ca -> . -> l.gtld-servers.net -> kim.ns.cloudflare.com -> ns1.digitalocean.com

Consultando directamente a la raíz cinco veces por el mismo dominio, el primer
registro A de Additional fue siempre `l.gtld-servers.net (192.41.162.30)`.

Donde sí cambian los Name Servers es al consultar dominios de **TLD distintos**,
lo cual es esperable porque cada TLD tiene su propio conjunto de servidores:

| Dominio consultado a la raíz | Primer A de Additional |
|---|---|
| `www.example.com` | `l.gtld-servers.net` (192.41.162.30) |
| `www.github.com` | `l.gtld-servers.net` (192.41.162.30) |
| `ns-1010.awsdns-62.net` | `m.gtld-servers.net` (192.55.83.30) |
| `www.python.org` | `a2.org.afilias-nst.info` (199.249.112.1) |

Que la cadena sea estable se explica por dos cosas. Primero, el resolver es
determinista: siempre toma **el primer** registro A de la sección Additional, nunca
elige al azar entre los trece que ofrece la raíz. Segundo, en nuestras mediciones
los servidores devolvieron los registros en un orden constante para una misma
consulta.

Por último, con el caché activo la pregunta cambia de sentido: a partir de la
segunda consulta al mismo dominio no se consulta **ningún** Name Server, porque la
respuesta se sirve localmente.