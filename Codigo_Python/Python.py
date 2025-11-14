import serial
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import numpy as np

# CONFIGURACIÓN DE PUERTO SERIE
device_tierra = 'COM5'   
BAUDRATE = 9600
ser_tierra = serial.Serial(device_tierra, BAUDRATE, timeout=1)
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
limite_temp = 30.0  # Valor límite inicial
nuevo_periodo = 5   # periodo inicial (segundos)

# VARIABLES GLOBALES - RADAR ULTRASÓNICO
angulos = []              # ángulos en radianes para la gráfica polar
distancias = []           # distancias correspondientes
historial_validas = []    # (tiempo, distancia) para ajuste dinámico de escala
max_escala = 30           # escala inicial del radar (cm)
ventana_puntos = 15       # número máximo de puntos visibles
margen_reduccion_dist = 50.0
tiempo_ventana_dist = 5.0
errores_distancia = 0
ultimo_cambio_escala_tiempo = time.time()

# FUNCIONES AUXILIARES
def actualizar_radiales(ax, max_escala):
    """Actualiza las divisiones radiales de la gráfica de radar."""
    num_divisiones = 6
    ticks = np.linspace(0, max_escala, num_divisiones + 1)
    ticks_visibles = ticks[::2]
    ax.set_yticks(ticks_visibles)
    ax.set_yticklabels([f"{int(t)}" for t in ticks_visibles], fontsize=9)

# INTERFAZ GRÁFICA (Tkinter)
root = tk.Tk()
root.title("Panel Satélite - Control de Temperatura/Humedad y Radar")

# Frames principales
frame_izq = ttk.Frame(root, padding=10)
frame_izq.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

frame_der = ttk.Frame(root, padding=10)
frame_der.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

# BOTONES CONTROL TEMP/HUM
frame_botones = ttk.Frame(frame_izq, padding=10)
frame_botones.pack(side=tk.TOP, fill=tk.X)

def iniciar():
    """
    Inicia el hilo de recepción (si no lo está) y activa la recepción de datos.
    Ahora el hilo único recibe tanto datos de temperatura/humedad como del radar.
    """
    global recibiendo, recepcion_activa
    if not recibiendo:
        recibiendo = True
        recepcion_activa = True
        hilo = threading.Thread(target=recepcion_datos, daemon=True)
        hilo.start()
        print("Recepción iniciada.")
        ser_tierra.write(b'Iniciar\n')
        print("Enviado: Iniciar")
    else:
        recepcion_activa = True
        print("Recepción ya estaba iniciada. Reanudando almacenamiento de datos.")

def parar():
    """Pide al satélite que deje de enviar datos y detiene el almacenamiento (la gráfica puede seguir)."""
    global recepcion_activa
    recepcion_activa = False
    ser_tierra.write(b'Parar\n')
    print("Enviado: Parar (la gráfica seguirá avanzando sin datos cuando lleguen líneas vacías o errores)")

def reanudar():
    """Pide al satélite que reanude el envío de datos y vuelve a almacenar medidas."""
    global recepcion_activa
    recepcion_activa = True
    ser_tierra.write(b'Reanudar\n')
    print("Enviado: Reanudar")

def periodo():
    """Envía al satélite el nuevo periodo de envío de datos de temperatura/humedad."""
    global nuevo_periodo
    valor = periodo_entry.get()
    try:
        nuevo_periodo = int(valor)
        mensaje = f"Periodo:{nuevo_periodo}\n"
        ser_tierra.write(mensaje.encode('utf-8'))
        print(f"Enviado: {mensaje.strip()}")
    except ValueError:
        messagebox.showerror("Error", "Introduce un número entero válido para el periodo")

btn_iniciar = ttk.Button(frame_botones, text="Iniciar", command=iniciar)
btn_iniciar.pack(side=tk.LEFT, padx=5, pady=5)
btn_parar = ttk.Button(frame_botones, text="Parar", command=parar)
btn_parar.pack(side=tk.LEFT, padx=5, pady=5)
btn_reanudar = ttk.Button(frame_botones, text="Reanudar", command=reanudar)
btn_reanudar.pack(side=tk.LEFT, padx=5, pady=5)

ttk.Label(frame_botones, text="Modo de cálculo:").pack(side=tk.LEFT, padx=5)
modo_combo = ttk.Combobox(frame_botones, values=["Cálculo en Tierra (Python)", "Cálculo en Satélite (Arduino)"])
modo_combo.current(0)
modo_combo.pack(side=tk.LEFT)

def cambiar_modo(event):
    """Cambia el modo de cálculo de la media (tierra/arduino)."""
    global modo_calculo
    seleccion = modo_combo.get()
    if "Tierra" in seleccion:
        modo_calculo = "tierra"
    else:
        modo_calculo = "arduino"
    print(f"Modo de cálculo cambiado a: {modo_calculo}")

modo_combo.bind("<<ComboboxSelected>>", cambiar_modo)

# Límite de temperatura media
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
    except ValueError:
        messagebox.showerror("Error", "Introduce un número válido")

ttk.Button(frame_limite, text="Actualizar", command=actualizar_limite).pack(side=tk.LEFT, padx=5)

# Periodo de envío (segundos)
frame_periodo = ttk.Frame(frame_izq, padding=10)
frame_periodo.pack(side=tk.TOP, fill=tk.X)
ttk.Label(frame_periodo, text="Periodo deseado (s):").pack(side=tk.LEFT)
periodo_entry = ttk.Entry(frame_periodo, width=5)
periodo_entry.insert(0, str(nuevo_periodo))
periodo_entry.pack(side=tk.LEFT)
ttk.Button(frame_periodo, text="Actualizar", command=periodo).pack(side=tk.LEFT, padx=5)

# GRÁFICAS TEMPERATURA/HUMEDAD
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
ax3.set_xlabel("Iteraciones")

canvas_temp = FigureCanvasTkAgg(fig_temp, master=frame_izq)
canvas_temp.get_tk_widget().pack(fill=tk.BOTH, expand=True)

# GRÁFICA RADAR ULTRASÓNICO (polar)
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

# Control de ángulo del radar
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

    comando = f"ANG:{ang_esc}\n"
    ser_tierra.write(comando.encode("ascii"))
    print("Ángulo enviado a estación:", ang_esc)
    entry_angulo.delete(0, tk.END)

btn_enviar = ttk.Button(frame_angulo, text="Enviar", command=enviar_angulo)
btn_enviar.pack(side="left", padx=5)

# HILO DE RECEPCIÓN ÚNICO (Tº/H y RADAR)
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

    while recibiendo:
        try:
            linea = ser_tierra.readline().decode('utf-8', errors='ignore').strip()
            if not linea:
                time.sleep(0.05)
                continue

            # Datos de temperatura/humedad
            if linea.startswith('T:'):
                partes = linea.split(':')
                if len(partes) >= 4 and partes[0] == 'T' and partes[2] == 'H':
                    try:
                        temp = float(partes[1])
                        hum = float(partes[3])
                    except ValueError:
                        print("Línea T/H corrupta:", linea)
                        continue

                    temperaturas.append(temp if recepcion_activa else None)
                    humedades.append(hum if recepcion_activa else None)

                    while len(medias_10) < len(temperaturas):
                        medias_10.append(np.nan)

                    if modo_calculo == "tierra" and len(temperaturas) >= 10:
                        ultimos = [t for t in temperaturas[-10:] if t is not None]
                        if len(ultimos) == 10:
                            medias_10[-1] = sum(ultimos) / 10

                    if len(medias_10) >= 3:
                        ultimas_3 = medias_10[-3:]
                        if all((m is not None) and not np.isnan(m) and m > limite_temp for m in ultimas_3):
                            messagebox.showwarning("Alerta", f"¡Tres medias consecutivas > {limite_temp} °C!")
                          
                            ser_tierra.write(b'ALARMA\n')
                else:
                    print("Línea T/H con formato inesperado:", linea)
                continue 
            # Datos de radar (ángulo,distancia)
            partes = linea.split(',')
            if len(partes) == 2:
                ang_str, dist_str = partes[0].strip(), partes[1].strip()

                try:
                    angulo_deg = float(ang_str)
                except ValueError:
                    errores_distancia += 1
                    text_label.set_text("Ángulo corrupto")
                    canvas_radar.draw()
                    continue

                angulo_rad = np.deg2rad(angulo_deg - 90)

                try:
                    d = float(dist_str)
                    errores_distancia = 0
                    angulos.append(angulo_rad)
                    distancias.append(d)
                    if len(angulos) > ventana_puntos:
                        angulos = angulos[-ventana_puntos:]
                        distancias = distancias[-ventana_puntos:]

                    line_radar.set_xdata(angulos)
                    line_radar.set_ydata(distancias)

                    ahora = time.time()
                    historial_validas.append((ahora, d))
                    historial_validas = [(t, val) for (t, val) in historial_validas if ahora - t <= tiempo_ventana_dist]

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

                    text_label.set_text(f"Ángulo: {angulo_deg-90:.0f}º    Distancia: {d:.1f} cm")
                    canvas_radar.draw()

                except ValueError:
                    errores_distancia += 1
                    angulos.append(angulo_rad)
                    distancias.append(np.nan)
                    if len(angulos) > ventana_puntos:
                        angulos = angulos[-ventana_puntos:]
                        distancias = distancias[-ventana_puntos:]
                    line_radar.set_xdata(angulos)
                    line_radar.set_ydata(distancias)
                    text_label.set_text("Dato corrupto")
                    canvas_radar.draw()

            else:
                print("Mensaje:", linea)

        except Exception as e:
            print("Error en recepción:", e)
            break

# ACTUALIZACIÓN PERIÓDICA DE LAS GRÁFICAS T/H
def actualizar_graficas():
    """Actualiza las gráficas de temperatura, humedad y media en la interfaz."""
    x_vals = list(range(len(temperaturas)))

    linea_temp.set_data(x_vals, temperaturas)
    linea_hum.set_data(x_vals, humedades)
    linea_media.set_data(x_vals, medias_10)

    for ax in (ax1, ax2, ax3):
        ax.set_xlim(0, max(len(x_vals), 10))  
        ax.relim()
        ax.autoscale_view(scalex=False, scaley=True)

    ax1.set_title(f"Temperatura actual: {temp:.2f} °C")
    ax2.set_title(f"Humedad actual: {hum:.2f} %")
    if len(medias_10) > 0 and not np.isnan(medias_10[-1]):
        ax3.set_title(f"Media actual: {medias_10[-1]:.2f} °C")
    else:
        ax3.set_title("Media actual: N/A")

    canvas_temp.draw()
    root.after(500, actualizar_graficas)

# INICIO DE LA APLICACIÓN
root.after(500, actualizar_graficas)
root.mainloop()
