import serial
import matplotlib.pyplot as plt
from collections import deque
import time
import csv
from datetime import datetime
import os

SERIAL_PORT = 'COM4'
SERIAL_BAUD = 115200
READ_TIMEOUT = 1.0  # timeout de lectura en segundos
RECONNECT_DELAY = 2.0  # tiempo de espera antes de reconectar

ser = None
csv_file = None
csv_writer = None
session_start_time = datetime.now()
was_connected = False
disconnection_count = 0

def connect_serial():
    """Intenta conectar al puerto serie. Retorna True si tiene éxito."""
    global ser
    try:
        if ser is not None and ser.is_open:
            ser.close()
        ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=READ_TIMEOUT)
        time.sleep(2)  # esperar a que se estabilice la conexión
        ser.reset_input_buffer()  # limpiar buffer de entrada
        print(f"Conectado a {SERIAL_PORT}")
        return True
    except serial.SerialException as e:
        print(f"Error al conectar: {e}. Reintentando en {RECONNECT_DELAY} segundos...")
        return False
    except Exception as e:
        print(f"Error inesperado al conectar: {e}")
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

# Conectar inicialmente
if not connect_serial():
    print("No se pudo conectar inicialmente. El programa seguirá intentando...")
    if csv_writer is not None:
        log_to_csv(0, 0, "Sin conexion inicial")

plt.ion()
fig, ax = plt.subplots()

data1 = deque([0]*100, maxlen=100)
data2 = deque([0]*100, maxlen=100)

line1, = ax.plot(data1, label="Sensor 1")
line2, = ax.plot(data2, label="Sensor 2")

ax.set_ylim(0, 2000)
ax.set_ylabel("Distancia (mm)")
ax.set_xlabel("Tiempo (muestras)")
ax.legend(loc='lower right')

# Variables para almacenar los valores más recientes
current_d1 = 0.0
current_d2 = 0.0

# Crear textbox para mostrar valores actuales
# Posicionado en la esquina superior derecha de la gráfica
textbox = ax.text(0.98, 0.98, '', transform=ax.transAxes,
                  verticalalignment='top', horizontalalignment='right',
                  bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8),
                  fontsize=11, family='monospace')

last_update_time = time.time()
consecutive_errors = 0
MAX_CONSECUTIVE_ERRORS = 10

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
                time.sleep(RECONNECT_DELAY)
                plt.pause(0.1)  # mantener la gráfica viva
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
            plt.pause(0.1)
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

                # Actualizar límites del eje Y solo si hay datos válidos
                if len(data1) > 0 and len(data2) > 0:
                    ymin = min(min(data1), min(data2)) - 50
                    ymax = max(max(data1), max(data2)) + 50
                    ax.set_ylim(max(ymin, 0), min(ymax, 2000))

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
            except (ValueError, IndexError) as e:
                # Error al parsear, ignorar esta línea
                pass

        plt.pause(0.01)
        
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
        plt.pause(0.1)  # mantener la gráfica viva incluso con errores

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
