import serial
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import numpy as np

import logging

# Configuración básica
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="estacion_tierra.log",   # Archivo donde se guardarán los eventos
    filemode="a"              # 'a' = append (agregar), 'w' = overwrite (sobrescribir)
)


# La estación de Tierra se encarga de comunicarse con el satélite.
estacion_tierra = 'COM3'      # Puerto de la estación de Tierra
BAUDRATE = 9600
com = serial.Serial(estacion_tierra, BAUDRATE, timeout=1)
time.sleep(2)


# VARIABLES GLOBALES - TEMPERATURA / HUMEDAD

temperaturas = []     # historial de temperaturas recibidas
humedades = []        # historial de humedades recibidas
medias_10 = []        # media móvil de 10 valores (o valor calculado por Arduino)
recibiendo = False    # indica si el hilo de recepción está iniciado
recepcion_activa = False  # indica si se deben almacenar nuevos datos (Parar/Reanudar)
modo_calculo = "tierra"   # "tierra" o "arduino"
temp = 0.0
hum = 0.0
limite_temp = 30.0      # Valor límite inicial
nuevo_periodo = 5000    # periodo inicial DHT (ms)
periodo_global = 5000   # periodo inicial (ms) GLOBAL (límite LoRa)


tiempos_TH = []       # tiempos (s) desde el inicio para cada medida de T/H
t0_TH = None          # tiempo de referencia (primera pulsación de "Iniciar")
VENTANA_TIEMPO = 30.0 # segundos visibles en el eje X para las gráficas de T/H


# VARIABLES GLOBALES - RADAR ULTRASÓNICO

angulos = []              # ángulos en radianes para la gráfica polar
distancias = []           # distancias correspondientes
historial_validas = []    # (tiempo, distancia) para ajuste dinámico de escala
max_escala = 30           # escala inicial del radar (cm)
ventana_puntos = 7        # número máximo de puntos visibles
margen_reduccion_dist = 50.0
tiempo_ventana_dist = 5.0
errores_distancia = 0
ultimo_cambio_escala_tiempo = time.time()
mensajes_sat = []    # mensajes que manda el sat de confirmación


# Buffers para el nuevo protocolo (T/H/media y ángulo de servo)
ultimo_angulo_deg = 90.0   # ángulo "frontal" por defecto
temp_buffer = None
hum_buffer = None
media_buffer = None

# =====================================================
# FUNCIONES AUXILIARES
# =====================================================
def actualizar_radiales(ax, max_escala):
    """Actualiza las divisiones radiales de la gráfica de radar."""
    num_divisiones = 6
    ticks = np.linspace(0, max_escala, num_divisiones + 1)
    ticks_visibles = ticks[::2]
    ax.set_yticks(ticks_visibles)
    ax.set_yticklabels([f"{int(t)}" for t in ticks_visibles], fontsize=9)

# =====================================================
# INTERFAZ GRÁFICA (Tkinter)
# =====================================================
root = tk.Tk()
root.title("Panel Satélite - Control de Temperatura/Humedad y Radar")

# Frames principales
frame_izq = ttk.Frame(root, padding=10)
frame_izq.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

frame_der = ttk.Frame(root, padding=10)
frame_der.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)


# -------------------------
# BOTONES CONTROL TEMP/HUM
# -------------------------
frame_botones = ttk.Frame(frame_izq, padding=10)
frame_botones.pack(side=tk.TOP, fill=tk.X)

def iniciar():
    """
    Inicia el hilo de recepción (si no lo está) y activa la recepción de datos.
    Ahora el hilo único recibe tanto datos de temperatura/humedad como del radar.
    """
    global recibiendo, recepcion_activa, t0_TH
    if not recibiendo:
        recibiendo = True
        recepcion_activa = True

        if t0_TH is None:
            t0_TH = time.time()
        
        hilo = threading.Thread(target=recepcion_datos, daemon=True)
        hilo.start()
        print("Recepción iniciada.")
        # Protocolo: 16:1:1|  -> Iniciar envío
        com.write(b'16:1:1|')
        print("Enviado: 16:1:1| (Iniciar envío)")
        logging.info("Recepción iniciada.")
        # Enviamos también el período inicial con el protocolo 16:1:4:<periodo>|
        mensaje = f"16:1:4:{nuevo_periodo}|"
        logging.info("Enviando periodo inicial: %s", mensaje)
        com.write(mensaje.encode('utf-8'))
        print(f"Enviado: {mensaje}")
    else:
        recepcion_activa = True
        print("Recepción ya estaba iniciada. Reanudando almacenamiento de datos.")

def parar():
    """Pide al satélite que deje de enviar datos y detiene el almacenamiento (la gráfica puede seguir)."""
    global recepcion_activa
    recepcion_activa = False
    # Protocolo: 16:1:2|  -> Parar
    com.write(b'16:1:2|')
    print("Enviado: 16:1:2| (Parar; la gráfica seguirá avanzando sin datos cuando lleguen líneas vacías o errores)")
    logging.info("Recepción pausada por el usuario.")

def reanudar():
    """Pide al satélite que reanude el envío de datos y vuelve a almacenar medidas."""
    global recepcion_activa
    recepcion_activa = True
    # Protocolo: 16:1:3|  -> Reanudar medición
    com.write(b'16:1:3|')
    print("Enviado: 16:1:3| (Reanudar medición)")
    logging.info("Recepción reanudada por el usuario.")

def periodo():
    """Envía al satélite el nuevo periodo de envío de datos de temperatura/humedad."""
    global nuevo_periodo
    valor = periodo_entry.get()
    try:
        nuevo_periodo = int(valor)
        # Protocolo: 16:1:4:<periodo>|
        mensaje = f"16:1:4:{nuevo_periodo}|"
        com.write(mensaje.encode('utf-8'))
        print(f"Enviado: {mensaje}")
        logging.info("Nuevo periodo de envío de T/H: %s ms", nuevo_periodo)
    except ValueError:
        messagebox.showerror("Error", "Introduce un número entero válido para el periodo")

def periodo_global_func():
    """Envía al satélite el nuevo periodo GLOBAL de envío (limitador LoRa)."""
    global periodo_global
    valor = periodo_global_entry.get()
    try:
        periodo_global = int(valor)
        # Protocolo: 16:1:7:<periodo_global>|
        mensaje = f"16:1:7:{periodo_global}|"
        logging.info("Nuevo periodo GLOBAL de envío: %s ms", periodo_global)
        com.write(mensaje.encode('utf-8'))
        print(f"Enviado: {mensaje}")
    except ValueError:
        messagebox.showerror("Error", "Introduce un número entero válido para el periodo GLOBAL")


btn_iniciar = ttk.Button(frame_botones, text="Iniciar", command=iniciar)
btn_iniciar.pack(side=tk.LEFT, padx=5, pady=5)
btn_parar = ttk.Button(frame_botones, text="Parar", command=parar)
btn_parar.pack(side=tk.LEFT, padx=5, pady=5)
btn_reanudar = ttk.Button(frame_botones, text="Reanudar", command=reanudar)
btn_reanudar.pack(side=tk.LEFT, padx=5, pady=5)

ttk.Label(frame_botones, text="Modo de cálculo:").pack(side=tk.LEFT, padx=5)
modo_combo = ttk.Combobox(frame_botones, values=["Cálculo en Tierra (Python)", "Cálculo en Satélite (Arduino)"], state="readonly")
modo_combo.current(0)
modo_combo.pack(side=tk.LEFT)

def cambiar_modo(event):
    """Cambia el modo de cálculo de la media (tierra/arduino)."""
    global modo_calculo
    seleccion = modo_combo.get()
    if "Tierra" in seleccion:
        modo_calculo = "tierra"
        # Protocolo: 16:1:5|  -> Cambiar cálculo de media de temperatura a Python
        logging.info("Cambiando modo de cálculo de media a Tierra (Python)")
        com.write(b'16:1:5|')
        print("Enviado: 16:1:5| (Cálculo media en Python)")
    else:
        modo_calculo = "arduino"
        # Protocolo: 16:1:6|  -> Cambiar cálculo de media de temperatura a Satélite
        com.write(b'16:1:6|')
        print("Enviado: 16:1:6| (Cálculo media en Satélite)")
        logging.info("Cambiando modo de cálculo de media a Satélite (Arduino)")
    print(f"Modo de cálculo cambiado a: {modo_calculo}")

modo_combo.bind("<<ComboboxSelected>>", cambiar_modo)

# -------------------------
# Límite de temperatura media
# -------------------------
frame_limite = ttk.Frame(frame_izq, padding=10)
frame_limite.pack(side=tk.TOP, fill=tk.X)
ttk.Label(frame_limite, text="Límite de temperatura media (°C):").pack(side=tk.LEFT)
limite_entry = ttk.Entry(frame_limite, width=5)
limite_entry.insert(0, str(limite_temp))
limite_entry.pack(side=tk.LEFT)

def actualizar_limite():
    """Actualiza el límite de temperatura media a partir del valor del cuadro de texto."""
    global limite_temp
    try:
        limite_temp = float(limite_entry.get())
        print(f"Límite actualizado a: {limite_temp} °C")
        logging.info("Límite de temperatura media actualizado a: %s °C", limite_temp)
    except ValueError:
        messagebox.showerror("Error", "Introduce un número válido")

ttk.Button(frame_limite, text="Actualizar", command=actualizar_limite).pack(side=tk.LEFT, padx=5)

# Control de los períodos de envío del sat
frame_periodo = ttk.Frame(frame_izq, padding=10)
frame_periodo.pack(side=tk.TOP, fill=tk.X)

# Periodo DHT
ttk.Label(frame_periodo, text="Periodo DHT (ms):").pack(side=tk.LEFT)
periodo_entry = ttk.Entry(frame_periodo, width=5)
periodo_entry.insert(0, str(nuevo_periodo))
periodo_entry.pack(side=tk.LEFT)
ttk.Button(frame_periodo, text="Actualizar", command=periodo).pack(side=tk.LEFT, padx=5)

# Periodo GLOBAL
ttk.Label(frame_periodo, text="Periodo GLOBAL (ms):").pack(side=tk.LEFT, padx=(20, 5))
periodo_global_entry = ttk.Entry(frame_periodo, width=5)
periodo_global_entry.insert(0, str(periodo_global))
periodo_global_entry.pack(side=tk.LEFT)
ttk.Button(frame_periodo, text="Actualizar global", command=periodo_global_func).pack(side=tk.LEFT, padx=5)


# =====================================================
# GRÁFICAS TEMPERATURA/HUMEDAD
# =====================================================
fig_temp, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(6, 8))
fig_temp.tight_layout(pad=3)
linea_temp, = ax1.plot([], [], 'y-', label="Temperatura")
linea_hum, = ax2.plot([], [], 'c-', label="Humedad")
linea_media, = ax3.plot([], [], 'r-', label="Media móvil 10 valores")

for ax in (ax1, ax2, ax3):
    ax.legend()

ax1.set_ylabel("°C")
ax2.set_ylabel("%")
ax3.set_ylabel("°C (Media)")
ax3.set_xlabel("Tiempo (s)")

canvas_temp = FigureCanvasTkAgg(fig_temp, master=frame_izq)
canvas_temp.get_tk_widget().pack(fill=tk.BOTH, expand=True)

# Mensajes del satélite
frame_mensajes_satelite = ttk.Frame(frame_der, padding=10)
frame_mensajes_satelite.pack(fill="both", expand=False)

ttk.Label(frame_mensajes_satelite, text="Mensajes de texto del satélite:").pack(anchor="w")

text_mensajes_satelite = tk.Text(frame_mensajes_satelite, height=6, state="disabled", wrap="word")
text_mensajes_satelite.pack(fill="both", expand=True)

# =====================================================
# GRÁFICA RADAR ULTRASÓNICO (polar)
# =====================================================
fig_radar = plt.Figure(figsize=(6, 6))
ax_radar = fig_radar.add_subplot(111, polar=True)
ax_radar.set_ylim(0, max_escala)
ax_radar.set_theta_zero_location("N")
ax_radar.set_theta_direction(-1)
ax_radar.set_thetamin(-90)
ax_radar.set_thetamax(90)
line_radar, = ax_radar.plot([], [], marker='', linestyle='-', linewidth=2)
ax_radar.set_title("Radar ultrasónico", pad=25)
text_label = ax_radar.text(0.5, 1.0, "", transform=ax_radar.transAxes,
                           ha='center', va='bottom', fontsize=12, color='gray')
actualizar_radiales(ax_radar, max_escala)

canvas_radar = FigureCanvasTkAgg(fig_radar, master=frame_der)
canvas_radar.get_tk_widget().pack(fill=tk.BOTH, expand=True)

def actualizar_mensajes_satelite():
    """Actualiza la lista visible de mensajes del satélite (máx 5 y máx 4 segundos)."""
    global mensajes_sat
    ahora = time.time()

    # Eliminamos los mensajes con más de 4 segundos de antigüedad
    mensajes_sat = [
        (txt, ts) for (txt, ts) in mensajes_sat
        if ahora - ts <= 4.0 
    ]

    # Mostramos solo los últimos 5 (como máximo)
    mensajes_visibles = mensajes_sat[-5:]

    text_mensajes_satelite.configure(state="normal")
    text_mensajes_satelite.delete("1.0", tk.END)
    for txt, ts in mensajes_visibles:
        text_mensajes_satelite.insert(tk.END, txt + "\n")
    text_mensajes_satelite.configure(state="disabled")


# -------------------------
# Control de ángulo del radar
# -------------------------
frame_angulo = ttk.Frame(frame_der, padding=10)
frame_angulo.pack(fill="x")
ttk.Label(frame_angulo, text="Ángulo (-90 a 90):").pack(side="left")
entry_angulo = ttk.Entry(frame_angulo, width=10)
entry_angulo.pack(side="left", padx=5)

def enviar_angulo():
    """Envía un comando ANG:<ángulo> a la estación de Tierra."""
    text_ang = entry_angulo.get().strip()
    if not text_ang:
        print("Introduce un ángulo.")
        return
    try:
        ang_esc = int(text_ang)
    except ValueError:
        print("El ángulo debe ser un número entero.")
        return
    if not (-90 <= ang_esc <= 90):
        print("El ángulo debe estar entre -90 y 90.")
        return

    comando = f"16:2:1:{ang_esc}|"
    com.write(comando.encode("ascii"))
    print("Ángulo enviado a estación (16:2:1):", ang_esc)
    logging.info("Ángulo enviado a estación: %s", ang_esc)
    entry_angulo.delete(0, tk.END)

btn_enviar = ttk.Button(frame_angulo, text="Enviar", command=enviar_angulo)
btn_enviar.pack(side="left", padx=5)


# Muestra en la interfaz los mensajes del satéllite
def append_mensaje_sat(texto):
    """Añade un mensaje de texto del satélite al cuadro de mensajes (desde cualquier hilo)."""
    def _inner():
        ahora = time.time()
        mensajes_sat.append((texto, ahora))
        # Actualizamos inmediatamente la zona de mensajes
        actualizar_mensajes_satelite()
    root.after(0, _inner)



# =====================================================
# HILO DE RECEPCIÓN ÚNICO (Tº/H y RADAR)
# =====================================================
def recepcion_datos():
    """
    Hilo que recibe continuamente datos desde la estación de Tierra.
    - Si la línea empieza por 'T:' se asume T:H:M: (temperatura/humedad/media).
    - Si la línea contiene 'ángulo,distancia' se interpreta como dato de radar.
    - Otros mensajes se muestran por consola.
    """
    global temp, hum, recibiendo, recepcion_activa
    global temperaturas, humedades, medias_10
    global angulos, distancias, max_escala, historial_validas
    global errores_distancia, ultimo_cambio_escala_tiempo
    global ultimo_angulo_deg, temp_buffer, hum_buffer, media_buffer
    global modo_calculo, limite_temp
    global tiempos_TH, t0_TH


    while recibiendo:
        try:
            # Leemos hasta el delimitador '|' del protocolo
            linea_bytes = com.read_until(b'|')
            if not linea_bytes:
                time.sleep(0.05)
                continue

            linea = linea_bytes.decode('utf-8', errors='ignore').strip()
            linea = linea.rstrip('|')

            if not linea:
                time.sleep(0.05)
                continue

            partes = linea.split(':')

            # Esperamos formato 16:grupo:codigo[:valor]
            if len(partes) < 3 or partes[0] != '16':
                print("Mensaje:", linea)
                continue

            grupo = partes[1]
            codigo = partes[2]
            valor = partes[3] if len(partes) > 3 else None
            
            # ------------------------------
            # Grupo 0: Mensajes de texto (16:0:lo_que_sea)
            # ------------------------------
            if grupo == '0':
                # Recuperamos todo lo que va después de "16:0:"
                if len(linea) > 5:
                    mensaje_texto = linea[5:]
                else:
                    mensaje_texto = ""

                # Si dentro del texto aparece otra cabecera "16:", cortamos ahí
                idx_proto = mensaje_texto.find("16:")
                if idx_proto != -1:
                    mensaje_texto = mensaje_texto[:idx_proto]

                mensaje_texto = mensaje_texto.strip()

                print("MENSAJE DE TEXTO DESDE SATÉLITE:", mensaje_texto)
                append_mensaje_sat(mensaje_texto)

                continue


            
            # ------------------------------
            # Grupo 1: Sensor humedad/temperatura (16:1:...)
            # ------------------------------
            if grupo == '1':
                # Errores de lectura/envío
                if codigo in ('-2', '-1'):
                    print("Error de T/H recibido:", linea)
                    if t0_TH is not None:
                        t_rel = time.time() - t0_TH
                    else:
                        t_rel = 0.0
                    tiempos_TH.append(t_rel)
                    temperaturas.append(np.nan if recepcion_activa else None)
                    humedades.append(np.nan if recepcion_activa else None)
                    while len(medias_10) < len(temperaturas):
                        medias_10.append(np.nan)
                    continue

                # 16:1:01:<temp>|
                if codigo == '01' and valor is not None:
                    try:
                        temp = float(valor)
                        temp_buffer = temp
                        logging.info('Temp %s',linea)
                    except ValueError:
                        print("Temperatura corrupta: %s", linea)
                        logging.warning("Humedad corrupta: %s", linea)
                    continue

                # 16:1:02:<hum>|
                if codigo == '02' and valor is not None:
                    try:
                        hum = float(valor)
                        hum_buffer = hum
                        logging.info('Hum %s',linea)

                    except ValueError:
                        print("Humedad corrupta: %s", linea)
                        logging.warning("Humedad corrupta:%s", linea)
                    continue

                # 16:1:03:<media>|
                if codigo == '03' and valor is not None:
                    try:
                        media_buffer = float(valor)
                        logging.info('Media %s',linea)

                    except ValueError:
                        print("Media corrupta: %s", linea)
                        logging.warning("Media corrupta: %s", linea)

                        media_buffer = None

                    # Solo generamos un "nuevo punto" cuando llega el 03 (paquete completo)
                    if temp_buffer is None or hum_buffer is None:
                        print("Faltan T/H para completar paquete:%s", linea)
                        logging.warning("Faltant T/H para copmletar paquete:%s", linea)
                        continue

                    if t0_TH is not None:
                        t_rel = time.time() - t0_TH
                    else:
                        t_rel = 0.0
                    tiempos_TH.append(t_rel)

                    if recepcion_activa:
                        temperaturas.append(temp_buffer)
                        humedades.append(hum_buffer)
                    else:
                        temperaturas.append(None)
                        humedades.append(None)

                    # Rellenar medias_10 con np.nan si es necesario
                    while len(medias_10) < len(temperaturas):
                        medias_10.append(np.nan)

                    # Cálculo de la media según el modo
                    if modo_calculo == "tierra":
                        logging.info('Calculo media en: %s',modo_calculo)
                        if len(temperaturas) >= 10:
                            ultimos = [t for t in temperaturas[-10:] if t is not None]
                            if len(ultimos) == 10:
                                medias_10[-1] = sum(ultimos) / 10
                    else:
                        if media_buffer is not None:
                            medias_10[-1] = media_buffer

                    # Alerta si tres últimas medias válidas > límite
                    if len(medias_10) >= 3:
                        ultimas_3 = medias_10[-3:]
                        if all((m is not None) and not np.isnan(m) and m > limite_temp for m in ultimas_3):
                            messagebox.showwarning("Alerta", f"¡Tres medias consecutivas > {limite_temp} °C!")
                            logging.warning("Alerta: Tres medias consecutivas > límite")
                            # CAMBIO 10: ahora se envía la alarma a la estación de Tierra
                            com.write(b'ALARMA\n')

                    continue  # siguiente iteración del bucle

                # Códigos no reconocidos del grupo 1
                print("Mensaje grupo 1 no reconocido:", linea)
                logging.warning("Mensaje grupo 1 no reconocido: %s", linea)
                continue

            # ------------------------------
            # Grupo 2: Servo (16:2:...)
            # ------------------------------
            if grupo == '2':
                # 16:2:-1|
                if codigo == '-1':
                    text_label.set_text("Ángulo N/A")
                    canvas_radar.draw()
                    continue

                # 16:2:0:<angulo>|
                if codigo == '0' and valor is not None:
                    try:
                        ultimo_angulo_deg = float(valor)
                        logging.info('Angulo servo %s',linea)
                    except ValueError:
                        print("Ángulo servo corrupto:", linea)
                        logging.warning("Ángulo servo corrupto: %s", linea)
                    continue

                # Otros códigos del grupo 2 (p.e. órdenes de mover / velocidad) no necesitan tratamiento aquí
                print("Mensaje grupo 2:", linea)
                continue

            # ------------------------------
            # Grupo 3: Distancia (16:3:...)
            # ------------------------------
            if grupo == '3':
                # Errores de distancia: 16:3:-1| o 16:3:-2|
                if codigo in ('-2', '-1'):
                    # Usamos el último ángulo conocido
                    angulo_rad = np.deg2rad(ultimo_angulo_deg - 90.0)
                    errores_distancia += 1
                    angulos.append(angulo_rad)
                    distancias.append(np.nan)

                    if len(angulos) > ventana_puntos:
                        angulos[:] = angulos[-ventana_puntos:]
                        distancias[:] = distancias[-ventana_puntos:]

                    line_radar.set_xdata(angulos)
                    line_radar.set_ydata(distancias)
                    text_label.set_text("Error distancia")
                    canvas_radar.draw()
                    continue

                # 16:3:0:<anguloServo>:<distancia>|
                if codigo == '0':
                    # Esperamos al menos 5 partes: 16, 3, 0, anguloServo, distancia
                    if len(partes) < 5:
                        print("Mensaje grupo 3 incompleto:", linea)
                        logging.warning("Mensaje grupo 3 incompleto: %s", linea)
                        continue

                    try:
                        angulo_servo = float(partes[3])     # 0..180
                        d = float(partes[4])                # distancia en cm
                        logging.info('Distancia radar %s',linea)
                    except ValueError:
                        # Texto no convertible a float: tratamos como dato corrupto
                        errores_distancia += 1
                        angulo_rad = np.deg2rad(ultimo_angulo_deg - 90.0)
                        angulos.append(angulo_rad)
                        distancias.append(np.nan)
                        if len(angulos) > ventana_puntos:
                            angulos[:] = angulos[-ventana_puntos:]
                            distancias[:] = distancias[-ventana_puntos:]
                        line_radar.set_xdata(angulos)
                        line_radar.set_ydata(distancias)
                        text_label.set_text("Dato corrupto")
                        canvas_radar.draw()
                        continue

                    # Actualizamos el último ángulo del servo recibido
                    ultimo_angulo_deg = angulo_servo
                    angulo_rad = np.deg2rad(angulo_servo - 90.0)

                    errores_distancia = 0
                    angulos.append(angulo_rad)
                    distancias.append(d)

                    if len(angulos) > ventana_puntos:
                        angulos[:] = angulos[-ventana_puntos:]
                        distancias[:] = distancias[-ventana_puntos:]

                    line_radar.set_xdata(angulos)
                    line_radar.set_ydata(distancias)

                    ahora = time.time()
                    historial_validas.append((ahora, d))
                    historial_validas = [
                        (t, val) for (t, val) in historial_validas
                        if ahora - t <= tiempo_ventana_dist
                    ]

                    # Ajuste dinámico de la escala radial
                    if historial_validas:
                        max_reciente = max(val for (t, val) in historial_validas)

                        if max_reciente > max_escala:
                            max_escala = int(max_reciente) + 1
                            ax_radar.set_ylim(0, max_escala)
                            actualizar_radiales(ax_radar, max_escala)
                            ultimo_cambio_escala_tiempo = ahora

                        elif (max_escala - max_reciente >= margen_reduccion_dist and
                              (ahora - ultimo_cambio_escala_tiempo >= tiempo_ventana_dist)):
                            max_escala = int(max_reciente) + 1
                            ax_radar.set_ylim(0, max_escala)
                            actualizar_radiales(ax_radar, max_escala)
                            ultimo_cambio_escala_tiempo = ahora

                    # Mostramos el ángulo ya centrado en [-90, 90]
                    text_label.set_text(
                        f"Ángulo: {angulo_servo-90:.0f}º    Distancia: {d:.1f} cm"
                    )
                    canvas_radar.draw()
                    continue

                # Códigos no reconocidos del grupo 3
                print("Mensaje grupo 3 no reconocido:", linea)
                logging.warning("Mensaje grupo 3 no reconocido: %s", linea)
                continue
            # ------------------------------
            # Otros grupos no previstos
            # ------------------------------
            print("Mensaje grupo no previsto:", linea)
            logging.warning("Mensaje grupo no previsto: %s", linea)

        except Exception as e:
            print("Error en recepción:", e)
            logging.error("Error en recepción")
            break

# =====================================================
# ACTUALIZACIÓN PERIÓDICA DE LAS GRÁFICAS T/H
# =====================================================
def actualizar_graficas():
    """Actualiza las gráficas de temperatura, humedad y media en la interfaz."""
    # Tiempo transcurrido desde la primera pulsación de "Iniciar"
    if t0_TH is not None:
        tiempo_actual = time.time() - t0_TH
    else:
        tiempo_actual = 0.0

    # Aseguramos que todas las series tienen la misma longitud
    n = min(len(tiempos_TH), len(temperaturas), len(humedades), len(medias_10))
    if n > 0:
        x_vals = tiempos_TH[:n]
        y_temp = temperaturas[:n]
        y_hum = humedades[:n]
        y_media = medias_10[:n]

        linea_temp.set_data(x_vals, y_temp)
        linea_hum.set_data(x_vals, y_hum)
        linea_media.set_data(x_vals, y_media)
    else:
        # Si aún no hay datos, vaciamos las curvas
        linea_temp.set_data([], [])
        linea_hum.set_data([], [])
        linea_media.set_data([], [])
        x_vals = []

    # Ventana deslizante fija de VENTANA_TIEMPO segundos
    if t0_TH is not None:
        t_max_ventana = max(VENTANA_TIEMPO, tiempo_actual)
        t_min_ventana = max(0.0, t_max_ventana - VENTANA_TIEMPO)
    else:
        t_min_ventana = 0.0
        t_max_ventana = VENTANA_TIEMPO

    for ax in (ax1, ax2, ax3):
        ax.set_xlim(t_min_ventana, t_max_ventana)
        ax.relim()
        ax.autoscale_view(scalex=False, scaley=True)

    # Actualizar títulos con valores actuales
    ax1.set_title(f"Temperatura actual: {temp:.2f} °C")
    ax2.set_title(f"Humedad actual: {hum:.2f} %")
    if len(medias_10) > 0 and not np.isnan(medias_10[-1]):
        ax3.set_title(f"Media actual: {medias_10[-1]:.2f} °C")
    else:
        ax3.set_title("Media actual: N/A")

    canvas_temp.draw()
    root.after(500, actualizar_graficas)




# =====================================================
# INICIO DE LA APLICACIÓN
# =====================================================

# esto soluciona los bugs de valores nulos o fantasmas iniciales
def arrancar_recepcion_al_inicio():

    #Arranca el hilo de recepción nada más abrir la GUI,
    #de modo que se reciban radar, servo y mensajes 16:0 aunque aún no
    #se hayan pedido datos de T/H.
    global recibiendo, recepcion_activa, t0_TH

    if not recibiendo:
        recibiendo = True
        recepcion_activa = True
        if t0_TH is None:
            t0_TH = time.time()
        hilo = threading.Thread(target=recepcion_datos, daemon=True)
        hilo.start()
        print("Recepción global arrancada al inicio.")
        logging.info("Recepción global arrancada al inicio.")
        
root.after(100, arrancar_recepcion_al_inicio)        
root.after(500, actualizar_graficas)
root.after(200, actualizar_mensajes_satelite)  # refresca mensajes del cada 200 ms
root.mainloop()
