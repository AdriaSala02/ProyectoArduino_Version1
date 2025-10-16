import serial
import threading
import time
import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as temperatura
import matplotlib.pyplot as humedad

# --- CONFIGURACIÓN DEL PUERTO SERIAL ---
device = 'COM7'
BAUDRATE = 9600
mySerial = serial.Serial(device, BAUDRATE, timeout=1)

# --- VARIABLES GLOBALES ---
x_data, y_data = [], []
x_data_h, y_data_h = [], []
j = 0
recibiendo = False  # Control del estado de recepción
temp = 0.0
hum = 0.0

# --- CONFIGURACIÓN DE LAS GRÁFICAS ---
temperatura.ion()
fig, ax = temperatura.subplots()
linea_grafica, = ax.plot([], [], 'y-')
ax.set_ylim(28, 30)
ax.set_xlim(0, 10)
ax.set_xlabel("Tiempo (iteraciones)")
ax.set_ylabel("Temperatura (°C)")

humedad.ion()
fig2, ah = humedad.subplots()
linea_grafica_h, = ah.plot([], [], 'y-')
ah.set_ylim(0, 100)
ah.set_xlim(0, 10)
ah.set_xlabel("Tiempo (iteraciones)")
ah.set_ylabel("Humedad (%)")

# --- FUNCIÓN DE RECEPCIÓN EN HILO ---
def recepcion():
    global j, temp, hum, recibiendo
    while recibiendo:
        try:
            if mySerial.in_waiting > 0:
                linea_serial = mySerial.readline().decode('utf-8', errors='ignore').strip()
                if linea_serial:
                    partes = linea_serial.split(':')

                    # Validación robusta del formato recibido
                    if len(partes) >= 4 and partes[0] == 'T' and partes[2] == 'H':
                        try:
                            temp = float(partes[1])
                            hum = float(partes[3])
                            x_data.append(j)
                            y_data.append(temp)
                            x_data_h.append(j)
                            y_data_h.append(hum)
                            j += 1
                            print(f"T: {temp:.2f}  H: {hum:.2f}")
                            mySerial.write(b'P')  # Parpadeo del LED receptor
                        except ValueError:
                            print("⚠️ Error al convertir datos:", linea_serial)
                    else:
                        print("⚠️ Formato inesperado:", linea_serial)
            time.sleep(0.1)
        except Exception as e:
            print("❌ Error en recepción:", e)
            break

# --- ACTUALIZACIÓN PERIÓDICA DE LAS GRÁFICAS ---
def actualizar_graficas():
    ax.set_title(f"Temperatura actual: {temp:.2f} °C")
    ah.set_title(f"Humedad actual: {hum:.2f} %")

    linea_grafica.set_data(x_data, y_data)
    linea_grafica_h.set_data(x_data_h, y_data_h)

    # --- Ajuste dinámico del eje X como en tu código original ---
    if j < 10:
        ax.set_xlim(0, j+1)
        ax.set_xticks(range(int(ax.get_xlim()[0]), int(ax.get_xlim()[1])+1, 1))
        ah.set_xlim(0, j+1)
        ah.set_xticks(range(int(ah.get_xlim()[0]), int(ah.get_xlim()[1])+1, 1))
    elif j < 95:
        ax.set_xlim(0, j+5)
        ax.set_xticks(range(int(ax.get_xlim()[0]), int(ax.get_xlim()[1])+1, 5))
        ah.set_xlim(0, j+5)
        ah.set_xticks(range(int(ah.get_xlim()[0]), int(ah.get_xlim()[1])+1, 5))
    elif j < 995:
        ax.set_xlim(0, j+10)
        ax.set_xticks(range(int(ax.get_xlim()[0]), int(ax.get_xlim()[1])+1, 10))
        ah.set_xlim(0, j+10)
        ah.set_xticks(range(int(ah.get_xlim()[0]), int(ah.get_xlim()[1])+1, 10))
    else:
        # Si j es muy grande, simplemente desplazamos la ventana
        ax.set_xlim(j-995, j+10)
        ah.set_xlim(j-995, j+10)

    fig.canvas.draw()
    fig2.canvas.draw()

    root.after(500, actualizar_graficas)

# --- FUNCIONES DE LOS BOTONES ---
def iniciar():
    global recibiendo
    if not recibiendo:
        recibiendo = True
        hilo = threading.Thread(target=recepcion, daemon=True)
        hilo.start()
        print("📡 Recepción iniciada.")

def parar():
    global recibiendo
    recibiendo = False
    mensaje = "Parar\n"
    mySerial.write(mensaje.encode('utf-8'))
    print("🛑 Enviado: Parar")

def reanudar():
    global recibiendo
    if not recibiendo:
        recibiendo = True
        hilo = threading.Thread(target=recepcion, daemon=True)
        hilo.start()
    mensaje = "Reanudar\n"
    mySerial.write(mensaje.encode('utf-8'))
    print("▶️ Enviado: Reanudar")

# --- INTERFAZ GRÁFICA ---
root = tk.Tk()
root.title("Panel Satélite - Control de Temperatura y Humedad")

frame = ttk.Frame(root, padding=20)
frame.pack()

btn_iniciar = ttk.Button(frame, text="Iniciar", command=iniciar)
btn_iniciar.grid(row=0, column=0, padx=10, pady=10)

btn_parar = ttk.Button(frame, text="Parar", command=parar)
btn_parar.grid(row=0, column=1, padx=10, pady=10)

btn_reanudar = ttk.Button(frame, text="Reanudar", command=reanudar)
btn_reanudar.grid(row=0, column=2, padx=10, pady=10)

# --- Actualización periódica de las gráficas ---
root.after(500, actualizar_graficas)

# --- Cierre seguro del programa ---
def cerrar():
    global recibiendo
    recibiendo = False
    mySerial.close()
    root.destroy()
    print("🔌 Conexión cerrada correctamente.")

root.protocol("WM_DELETE_WINDOW", cerrar)
root.mainloop()
