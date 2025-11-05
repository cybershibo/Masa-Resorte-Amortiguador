import serial
import serial.tools.list_ports
import matplotlib
# Intentar usar backend Qt5Agg para mejor rendimiento con GPU
# Si no está disponible, intentar QtAgg, luego TkAgg
backend_priority = ['Qt5Agg', 'QtAgg', 'TkAgg']
backend_set = False
for backend in backend_priority:
    try:
        matplotlib.use(backend)
        backend_set = True
        if backend.startswith('Qt'):
            print(f"Usando backend {backend} (aceleración GPU/hardware)")
        else:
            print(f"Usando backend {backend} (fallback)")
        break
    except Exception:
        continue

if not backend_set:
    # Usar el backend por defecto si todos fallan
    print("Usando backend por defecto de matplotlib")
import matplotlib.pyplot as plt
from collections import deque
import time
import csv
from datetime import datetime
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox

SERIAL_PORT = None  # Se seleccionará al inicio del programa
SERIAL_BAUD = 115200
READ_TIMEOUT = 1.0  # timeout de lectura en segundos
RECONNECT_DELAY = 2.0  # tiempo de espera antes de reconectar

ser = None
csv_file = None
csv_writer = None
session_start_time = datetime.now()
was_connected = False
disconnection_count = 0

def select_com_port():
    """Muestra una ventana para seleccionar el puerto COM."""
    global SERIAL_PORT
    
    # Obtener lista de puertos disponibles
    ports = serial.tools.list_ports.comports()
    available_ports = [port.device for port in ports]
    
    if not available_ports:
        root = tk.Tk()
        root.withdraw()  # Ocultar ventana principal
        messagebox.showerror(
            "Error", 
            "No se encontraron puertos COM disponibles.\n\n"
            "Por favor:\n"
            "1. Conecta tu microcontrolador\n"
            "2. Verifica que el driver esté instalado\n"
            "3. Reintenta"
        )
        root.destroy()
        return None
    
    # Crear ventana de selección
    root = tk.Tk()
    root.title("Seleccionar Puerto COM")
    root.geometry("450x280")
    root.resizable(False, False)
    
    # Centrar ventana
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f'{width}x{height}+{x}+{y}')
    
    # Siempre seleccionar el primer puerto disponible por defecto (no usar valor previo)
    selected_port = tk.StringVar(value=available_ports[0])
    
    # Frame principal
    main_frame = ttk.Frame(root, padding="20")
    main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    
    # Título
    title_label = ttk.Label(main_frame, text="Selecciona el Puerto COM (Obligatorio):", font=("Arial", 10, "bold"))
    title_label.grid(row=0, column=0, columnspan=2, pady=(0, 15), sticky=tk.W)
    
    # Información adicional
    info_label = ttk.Label(
        main_frame, 
        text="Debes seleccionar el puerto donde está conectado tu microcontrolador.\nSi cancelas, el programa se cerrará.",
        font=("Arial", 8)
    )
    info_label.grid(row=1, column=0, columnspan=2, pady=(0, 10), sticky=tk.W)
    
    # Lista de puertos
    port_frame = ttk.Frame(main_frame)
    port_frame.grid(row=2, column=0, columnspan=2, pady=(0, 15), sticky=(tk.W, tk.E))
    
    for i, port in enumerate(available_ports):
        # Obtener descripción del puerto si está disponible
        port_info = next((p for p in ports if p.device == port), None)
        port_description = ""
        if port_info:
            port_description = f" - {port_info.description}" if port_info.description else ""
        
        radio = ttk.Radiobutton(
            port_frame,
            text=f"{port}{port_description}",
            variable=selected_port,
            value=port
        )
        radio.grid(row=i, column=0, sticky=tk.W, pady=2)
    
    # Botones
    button_frame = ttk.Frame(main_frame)
    button_frame.grid(row=3, column=0, columnspan=2, pady=(10, 0))
    
    def on_ok():
        root.quit()
        root.destroy()
    
    def on_cancel():
        selected_port.set(None)
        root.quit()
        root.destroy()
    
    ok_button = ttk.Button(button_frame, text="Aceptar", command=on_ok, width=12)
    ok_button.grid(row=0, column=0, padx=5)
    
    cancel_button = ttk.Button(button_frame, text="Cancelar", command=on_cancel, width=12)
    cancel_button.grid(row=0, column=1, padx=5)
    
    # Hacer que Enter y Escape funcionen
    root.bind('<Return>', lambda e: on_ok())
    root.bind('<Escape>', lambda e: on_cancel())
    
    # Centrar en pantalla y mostrar
    root.focus()
    root.mainloop()
    
    port = selected_port.get()
    return port

def connect_serial():
    """Intenta conectar al puerto serie. Retorna True si tiene éxito."""
    global ser, SERIAL_PORT
    try:
        if ser is not None and ser.is_open:
            ser.close()
        
        # Verificar que se haya seleccionado un puerto
        if SERIAL_PORT is None:
            print("No se ha seleccionado ningún puerto COM.")
            return False
        
        # Verificar que el puerto exista antes de intentar conectar
        available_ports = [port.device for port in serial.tools.list_ports.comports()]
        if SERIAL_PORT not in available_ports:
            print(f"Puerto {SERIAL_PORT} no está disponible.")
            # No cambiar automáticamente el puerto, el usuario debe seleccionarlo nuevamente
            print("Por favor, reinicia el programa y selecciona un puerto disponible.")
            return False
        
        ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=READ_TIMEOUT)
        time.sleep(1)  # esperar a que se estabilice la conexión
        ser.reset_input_buffer()  # limpiar buffer de entrada
        print(f"Conectado a {SERIAL_PORT}")
        return True
    except serial.SerialException as e:
        print(f"Error al conectar: {e}. Reintentando en {RECONNECT_DELAY} segundos...")
        return False
    except Exception as e:
        print(f"Error inesperado al conectar: {e}")
        import traceback
        traceback.print_exc()
        return False

# Crear nombre del archivo CSV con formato: sesion-YYYYMMDD-HHMMSS.csv
timestamp_str = session_start_time.strftime("%Y%m%d-%H%M%S")
csv_filename = f"sesion-{timestamp_str}.csv"

# Abrir archivo CSV para escritura
try:
    csv_file = open(csv_filename, 'w', newline='', encoding='utf-8')
    csv_writer = csv.writer(csv_file)
    # Escribir encabezados
    csv_writer.writerow(['Timestamp', 'Sensor1_mm', 'Sensor2_mm', 'Estado'])
    csv_file.flush()  # Asegurar que se escriba el header
    print(f"Archivo CSV creado: {csv_filename}")
except Exception as e:
    print(f"Error al crear archivo CSV: {e}")
    csv_file = None
    csv_writer = None

# Función para registrar eventos en CSV
def log_to_csv(sensor1, sensor2, estado):
    """Registra una fila en el CSV con los datos proporcionados."""
    if csv_writer is not None:
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            csv_writer.writerow([timestamp, f"{sensor1:.1f}", f"{sensor2:.1f}", estado])
            csv_file.flush()  # Asegurar escritura inmediata
        except Exception as e:
            print(f"Error al escribir en CSV: {e}")

# Inicializar matplotlib PRIMERO para asegurar que la ventana se muestre
try:
    plt.ion()
    fig, ax = plt.subplots()
    fig.canvas.manager.set_window_title('Monitor de Sensores')
    
    # Habilitar renderizado acelerado por hardware (GPU) si está disponible
    try:
        fig.canvas.toolbar.configure(accelerated=True)
    except:
        pass
    
    # Configurar para mejor rendimiento en pantalla completa
    fig.set_facecolor('white')
    ax.set_facecolor('white')
    
    # Forzar actualización inicial de la ventana
    plt.show(block=False)
    plt.pause(0.1)  # Dar tiempo para que la ventana se renderice
    print("Ventana gráfica inicializada correctamente")
except Exception as e:
    print(f"ERROR CRÍTICO al inicializar matplotlib: {e}")
    sys.exit(1)

data1 = deque([0]*100, maxlen=100)
data2 = deque([0]*100, maxlen=100)

line1, = ax.plot(data1, label="Sensor 1")
line2, = ax.plot(data2, label="Sensor 2")

# Configurar eje Y centrado en 0
ax.set_ylim(-500, 500)  # Rango inicial centrado en 0
ax.set_ylabel("Distancia relativa (mm)")
ax.set_xlabel("Tiempo (muestras)")
ax.axhline(y=0, color='gray', linestyle='--', linewidth=0.8, alpha=0.5)  # Línea de referencia en 0
ax.legend(loc='lower right')
ax.grid(True, alpha=0.3, linestyle='--')  # Cuadrícula para facilitar lectura

# Variables para almacenar los valores más recientes
current_d1 = 0.0
current_d2 = 0.0

# Crear textbox para mostrar valores actuales
# Posicionado en la esquina superior derecha de la gráfica
textbox = ax.text(0.98, 0.98, 'Inicializando...', transform=ax.transAxes,
                  verticalalignment='top', horizontalalignment='right',
                  bbox=dict(boxstyle='round', facecolor='white', alpha=0.8),
                  fontsize=11, family='monospace')

# Optimización: Habilitar blitting para actualizar solo las partes que cambian
# Esto mejora significativamente el rendimiento en pantalla completa
bg = None
use_blitting = False
try:
    # Configurar blitting para actualización eficiente
    fig.canvas.draw()
    bg = fig.canvas.copy_from_bbox(ax.bbox)
    use_blitting = True
    print("Blitting habilitado para renderizado optimizado")
except Exception as e:
    use_blitting = False
    print(f"Blitting no disponible: {e}")

# Variables para control de frecuencia de actualización
last_graph_update = time.time()
GRAPH_UPDATE_INTERVAL = 1.0 / 60.0  # Actualizar a máximo 60 FPS
needs_update = False

# Actualizar ventana inicial (ya se hizo draw() en el try anterior si use_blitting es True)
if not use_blitting:
    plt.draw()
plt.pause(0.1)

# Permitir al usuario seleccionar el puerto COM
selected_port = select_com_port()

if selected_port is None:
    print("No se seleccionó ningún puerto. Cerrando programa...")
    sys.exit(0)

SERIAL_PORT = selected_port
print(f"Puerto seleccionado: {SERIAL_PORT}")

last_update_time = time.time()
consecutive_errors = 0
MAX_CONSECUTIVE_ERRORS = 10

# Actualizar textbox con el puerto seleccionado
textbox.set_text(f'Puerto: {SERIAL_PORT}\nConectando...')
if use_blitting:
    fig.canvas.draw()
    bg = fig.canvas.copy_from_bbox(ax.bbox)
else:
    plt.draw()
plt.pause(0.1)

# Conectar inicialmente DESPUÉS de que la ventana esté lista
print(f"Intentando conectar a {SERIAL_PORT}...")
if not connect_serial():
    print("No se pudo conectar inicialmente. El programa seguirá intentando...")
    if csv_writer is not None:
        log_to_csv(0, 0, "Sin conexion inicial")
    textbox.set_text(f'Puerto: {SERIAL_PORT}\nSin conexión - Reintentando...')
    if use_blitting:
        fig.canvas.draw()
        bg = fig.canvas.copy_from_bbox(ax.bbox)
    else:
        plt.draw()
    plt.pause(0.1)

while True:
    try:
        # Verificar conexión y reconectar si es necesario
        if ser is None or not ser.is_open:
            if was_connected:
                # Se perdió la conexión después de estar conectado
                was_connected = False
                disconnection_count += 1
                if csv_writer is not None:
                    log_to_csv(current_d1, current_d2, f"Desconexion microcontrolador #{disconnection_count}")
            if not connect_serial():
                # Mostrar estado de conexión en textbox
                textbox.set_text(f'Sensor 1: {current_d1:.1f} mm\n'
                               f'Sensor 2: {current_d2:.1f} mm\n'
                               f'[Sin conexión - Reintentando...]')
                # Actualización gráfica optimizada
                if use_blitting:
                    try:
                        fig.canvas.restore_region(bg)
                        ax.draw_artist(textbox)
                        fig.canvas.blit(ax.bbox)
                    except:
                        fig.canvas.draw()
                        bg = fig.canvas.copy_from_bbox(ax.bbox)
                else:
                    plt.draw()
                time.sleep(RECONNECT_DELAY)
                plt.pause(0.05)  # mantener la gráfica viva
                continue
            else:
                # Reconexión exitosa
                was_connected = True
                if csv_writer is not None:
                    log_to_csv(current_d1, current_d2, f"Reconexion microcontrolador exitosa")

        # Intentar leer línea con timeout
        try:
            line = ser.readline().decode(errors='ignore').strip()
        except serial.SerialTimeoutException:
            # Timeout normal, continuar sin actualizar datos
            consecutive_errors = 0
            # Mantener textbox actualizado
            textbox.set_text(f'Sensor 1: {current_d1:.1f} mm\n'
                           f'Sensor 2: {current_d2:.1f} mm\n'
                           f'[Timeout]')
            if csv_writer is not None:
                log_to_csv(current_d1, current_d2, "Timeout lectura")
            # Actualización gráfica optimizada
            current_time = time.time()
            if current_time - last_graph_update >= GRAPH_UPDATE_INTERVAL:
                if use_blitting:
                    try:
                        fig.canvas.restore_region(bg)
                        ax.draw_artist(textbox)
                        fig.canvas.blit(ax.bbox)
                    except:
                        fig.canvas.draw()
                        bg = fig.canvas.copy_from_bbox(ax.bbox)
                else:
                    plt.draw()
                last_graph_update = current_time
            plt.pause(0.01)
            continue
        except serial.SerialException:
            # Error de conexión, cerrar y marcar para reconectar
            print("Conexión perdida. Intentando reconectar...")
            if was_connected:
                was_connected = False
                disconnection_count += 1
                if csv_writer is not None:
                    log_to_csv(current_d1, current_d2, f"Error conexion - Desconexion microcontrolador #{disconnection_count}")
            if ser is not None:
                try:
                    ser.close()
                except:
                    pass
            ser = None
            consecutive_errors = 0
            # Mostrar estado de desconexión en textbox
            textbox.set_text(f'Sensor 1: {current_d1:.1f} mm\n'
                           f'Sensor 2: {current_d2:.1f} mm\n'
                           f'[Desconectado - Reconectando...]')
            # Actualización gráfica optimizada
            if use_blitting:
                try:
                    fig.canvas.restore_region(bg)
                    ax.draw_artist(textbox)
                    fig.canvas.blit(ax.bbox)
                except:
                    fig.canvas.draw()
                    bg = fig.canvas.copy_from_bbox(ax.bbox)
            else:
                plt.draw()
            plt.pause(0.05)
            continue

        if not line:
            consecutive_errors += 1
            if consecutive_errors > MAX_CONSECUTIVE_ERRORS:
                print("Muchas líneas vacías. Verificando conexión...")
                consecutive_errors = 0
            # Actualizar textbox incluso sin nuevos datos
            textbox.set_text(f'Sensor 1: {current_d1:.1f} mm\n'
                           f'Sensor 2: {current_d2:.1f} mm\n'
                           f'[Sin datos nuevos]')
            # Actualización gráfica optimizada (solo si ha pasado suficiente tiempo)
            current_time = time.time()
            if current_time - last_graph_update >= GRAPH_UPDATE_INTERVAL:
                if use_blitting:
                    try:
                        fig.canvas.restore_region(bg)
                        ax.draw_artist(textbox)
                        fig.canvas.blit(ax.bbox)
                    except:
                        fig.canvas.draw()
                        bg = fig.canvas.copy_from_bbox(ax.bbox)
                else:
                    plt.draw()
                last_graph_update = current_time
            plt.pause(0.01)
            continue

        # Resetear contador de errores si recibimos datos
        consecutive_errors = 0

        # Parsear datos
        parts = line.split(',')
        if len(parts) == 2:
            try:
                d1_raw = float(parts[0])
                d2_raw = float(parts[1])

                # Guardar valores originales para CSV antes de corrección
                d1_original = d1_raw
                d2_original = d2_raw

                # Ignorar valores nulos o erróneos
                # Si hay valores inválidos, usar el último valor válido si existe
                if d1_raw == 0 or d1_raw > 8200:
                    d1 = data1[-1] if len(data1) > 0 else 0
                else:
                    d1 = d1_raw
                    
                if d2_raw == 0 or d2_raw > 8200:
                    d2 = data2[-1] if len(data2) > 0 else 0
                else:
                    d2 = d2_raw

                # Guardar valores actuales (corregidos para gráfica)
                current_d1 = d1
                current_d2 = d2

                data1.append(d1)
                data2.append(d2)

                line1.set_ydata(data1)
                line2.set_ydata(data2)

                # Actualizar límites del eje Y centrado en 0
                ylim_changed = False
                if len(data1) > 0 and len(data2) > 0:
                    # Calcular rango de datos
                    data_min = min(min(data1), min(data2))
                    data_max = max(max(data1), max(data2))
                    
                    # Calcular el rango máximo (absoluto) para mantener el 0 centrado
                    max_range = max(abs(data_min), abs(data_max)) + 50  # Margen de 50
                    
                    # Asegurar un mínimo razonable para el rango
                    max_range = max(max_range, 100)  # Mínimo de ±100 mm
                    
                    # Limitar el rango máximo para evitar escalas excesivas
                    max_range = min(max_range, 1000)  # Máximo de ±1000 mm
                    
                    old_ylim = ax.get_ylim()
                    new_ylim = (-max_range, max_range)
                    
                    if abs(old_ylim[0] - new_ylim[0]) > 10 or abs(old_ylim[1] - new_ylim[1]) > 10:
                        ax.set_ylim(new_ylim)
                        ylim_changed = True

                # Actualizar textbox con valores actuales
                textbox.set_text(f'Sensor 1: {current_d1:.1f} mm\n'
                               f'Sensor 2: {current_d2:.1f} mm')

                # Marcar como conectado si no lo estaba antes
                if not was_connected:
                    was_connected = True
                    if csv_writer is not None:
                        log_to_csv(d1_original, d2_original, "Reconexion microcontrolador exitosa")

                # Registrar datos en CSV usando valores originales
                if csv_writer is not None:
                    estado = "Normal"
                    # Detectar posibles problemas con sensores (valores cero o fuera de rango)
                    if d1_original == 0 or d1_original > 8200:
                        estado = "Sensor1_invalido"
                    if d2_original == 0 or d2_original > 8200:
                        if estado == "Sensor1_invalido":
                            estado = "Ambos_sensores_invalidos"
                        else:
                            estado = "Sensor2_invalido"
                    log_to_csv(d1_original, d2_original, estado)

                last_update_time = time.time()
                needs_update = True
                
                # Actualización gráfica optimizada con blitting
                current_time = time.time()
                if current_time - last_graph_update >= GRAPH_UPDATE_INTERVAL or ylim_changed:
                    if use_blitting and not ylim_changed:
                        # Usar blitting para actualización rápida (solo las líneas)
                        try:
                            fig.canvas.restore_region(bg)
                            ax.draw_artist(line1)
                            ax.draw_artist(line2)
                            ax.draw_artist(textbox)
                            fig.canvas.blit(ax.bbox)
                        except:
                            # Si falla el blitting, hacer redibujado completo
                            fig.canvas.draw()
                            bg = fig.canvas.copy_from_bbox(ax.bbox)
                    else:
                        # Redibujado completo (necesario cuando cambian los límites)
                        fig.canvas.draw()
                        if use_blitting:
                            bg = fig.canvas.copy_from_bbox(ax.bbox)
                    last_graph_update = current_time
                    needs_update = False
            except (ValueError, IndexError) as e:
                # Error al parsear, ignorar esta línea
                pass

        # Pausa mínima para mantener la gráfica viva
        plt.pause(0.001)  # Reducido de 0.01 para mejor rendimiento
        
    except KeyboardInterrupt:
        print("Finalizado por el usuario")
        break
    except Exception as e:
        print(f"Error inesperado: {e}")
        consecutive_errors += 1
        if consecutive_errors > MAX_CONSECUTIVE_ERRORS:
            print("Muchos errores consecutivos. Verificando conexión...")
            if ser is not None:
                try:
                    ser.close()
                except:
                    pass
            ser = None
            consecutive_errors = 0
        # Actualización gráfica optimizada incluso con errores
        current_time = time.time()
        if current_time - last_graph_update >= GRAPH_UPDATE_INTERVAL:
            if use_blitting:
                try:
                    fig.canvas.restore_region(bg)
                    ax.draw_artist(textbox)
                    fig.canvas.blit(ax.bbox)
                except:
                    fig.canvas.draw()
                    bg = fig.canvas.copy_from_bbox(ax.bbox)
            else:
                plt.draw()
            last_graph_update = current_time
        plt.pause(0.05)  # mantener la gráfica viva incluso con errores

# Cerrar conexión al finalizar
if ser is not None and ser.is_open:
    ser.close()

# Cerrar archivo CSV
if csv_file is not None:
    try:
        # Registrar fin de sesión
        if csv_writer is not None:
            csv_writer.writerow(['', '', '', 'Fin de sesion'])
        csv_file.close()
        print(f"Archivo CSV guardado: {csv_filename}")
    except Exception as e:
        print(f"Error al cerrar archivo CSV: {e}")
