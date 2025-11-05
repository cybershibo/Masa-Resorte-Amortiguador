#include <Arduino.h>
#include "Adafruit_VL53L0X.h"

#define XSHUT1 PA0
#define XSHUT2 PA1

Adafruit_VL53L0X lox1 = Adafruit_VL53L0X();
Adafruit_VL53L0X lox2 = Adafruit_VL53L0X();

bool sensor1_ok = false;
bool sensor2_ok = false;

// Variables para calibración inicial (estado de reposo)
const int CALIBRATION_SAMPLES = 5;  // Número de muestras para calcular el promedio inicial
const int SMOOTH_WINDOW = 5; // Tamaño de la ventana de suavizado
int16_t offset_d1 = 0;  // Offset del sensor 1 (promedio inicial)
int16_t offset_d2 = 0;  // Offset del sensor 2 (promedio inicial)
bool calibration_complete = false;  // Flag para indicar si la calibración está completa

void setup() {
  Serial.begin(115200);
  // Esperar solo un tiempo limitado por si el puerto no está conectado
  // pero no bloquear indefinidamente
  unsigned long startTime = millis();
  while (!Serial && (millis() - startTime < 3000)) {
    delay(5);
  }

  pinMode(XSHUT1, OUTPUT);
  pinMode(XSHUT2, OUTPUT);

  // Apagar ambos sensores primero
  digitalWrite(XSHUT1, LOW);
  digitalWrite(XSHUT2, LOW);
  delay(5);

  // --- Inicializar Sensor 1 ---
  digitalWrite(XSHUT1, HIGH);
  delay(10);
  if (lox1.begin(0x30)) {
    sensor1_ok = true;
    lox1.startRangeContinuous();
    Serial.println(F("Sensor 1 listo"));
  } else {
    Serial.println(F("Error al iniciar Sensor 1"));
  }

  // --- Inicializar Sensor 2 ---
  digitalWrite(XSHUT2, HIGH);
  delay(10);
  if (lox2.begin(0x31)) {
    sensor2_ok = true;
    lox2.startRangeContinuous();
    Serial.println(F("Sensor 2 listo"));
  } else {
    Serial.println(F("Error al iniciar Sensor 2 (no conectado)"));
  }

  if (!sensor1_ok && !sensor2_ok) {
    Serial.println(F("Ningún sensor detectado, deteniendo programa."));
    while (1);
  }

  // Esperar un poco para que los sensores se estabilicen
  delay(100);
  Serial.println(F("Iniciando calibración (estado de reposo)..."));
  Serial.println(F("Mantén el sistema en reposo durante la calibración."));
}

void loop() {
  uint16_t d1_raw = 0, d2_raw = 0;
  bool data_ready = false;

  // Leer Sensor 1
  if (sensor1_ok && lox1.isRangeComplete()) {
    d1_raw = lox1.readRange();
    if (d1_raw > 8200 || d1_raw == 65535) {
      d1_raw = 0;
    } else {
      data_ready = true;
    }
  }

  // Leer Sensor 2
  if (sensor2_ok && lox2.isRangeComplete()) {
    d2_raw = lox2.readRange();
    if (d2_raw > 8200 || d2_raw == 65535) {
      d2_raw = 0;
    } else {
      data_ready = true;
    }
  }

  // Fase de calibración: calcular promedio inicial
  if (!calibration_complete && (sensor1_ok || sensor2_ok) && data_ready) {
    static uint32_t cal_sum_d1 = 0;
    static uint32_t cal_sum_d2 = 0;
    static int cal_count_d1 = 0;  // Contador de muestras válidas para sensor 1
    static int cal_count_d2 = 0;  // Contador de muestras válidas para sensor 2

    // Acumular solo muestras válidas y contar por separado
    if (sensor1_ok && d1_raw > 0) {
      cal_sum_d1 += d1_raw;
      cal_count_d1++;
    }
    if (sensor2_ok && d2_raw > 0) {
      cal_sum_d2 += d2_raw;
      cal_count_d2++;
    }

    // Mostrar progreso cada 10 muestras válidas
    int total_samples = (cal_count_d1 > cal_count_d2) ? cal_count_d1 : cal_count_d2;
    if (total_samples > 0 && total_samples % 10 == 0) {
      Serial.print(F("Calibrando... "));
      Serial.print(total_samples);
      Serial.print(F("/"));
      Serial.println(CALIBRATION_SAMPLES);
    }

    // Completar calibración cuando tengamos suficientes muestras válidas
    if (cal_count_d1 >= CALIBRATION_SAMPLES || cal_count_d2 >= CALIBRATION_SAMPLES) {
      if (sensor1_ok && cal_count_d1 > 0) {
        offset_d1 = cal_sum_d1 / cal_count_d1;
      }
      if (sensor2_ok && cal_count_d2 > 0) {
        offset_d2 = cal_sum_d2 / cal_count_d2;
      }
      
      calibration_complete = true;
      Serial.print(F("Calibración completa. Offset Sensor 1: "));
      Serial.print(offset_d1);
      Serial.print(F(" mm, Offset Sensor 2: "));
      Serial.print(offset_d2);
      Serial.println(F(" mm"));
      Serial.println(F("Iniciando mediciones relativas al estado de reposo..."));
      
      // Limpiar buffers de suavizado para empezar limpio
      delay(100);
    }
    
    delay(25);
    return;
  }

  // Fase de medición: enviar datos relativos al estado de reposo
  if (calibration_complete && (sensor1_ok || sensor2_ok) && Serial) {
    
    static uint16_t d1_buffer[SMOOTH_WINDOW] = {0};
    static uint16_t d2_buffer[SMOOTH_WINDOW] = {0};
    static int buffer_index = 0;
    static bool buffer_filled = false;

    // Calcular valores relativos al estado de reposo
    int16_t d1_relative = 0;
    int16_t d2_relative = 0;
    
    if (sensor1_ok && d1_raw > 0) {
      d1_relative = (int16_t)d1_raw - offset_d1;
    }
    if (sensor2_ok && d2_raw > 0) {
      d2_relative = (int16_t)d2_raw - offset_d2;
    }

    // Insertar nuevos datos en el buffer circular (usar valores absolutos para el buffer)
    d1_buffer[buffer_index] = d1_raw;
    d2_buffer[buffer_index] = d2_raw;

    buffer_index++;
    if (buffer_index >= SMOOTH_WINDOW) {
      buffer_index = 0;
      buffer_filled = true;
    }

    // Calcular el promedio suavizado
    uint32_t sum_d1 = 0, sum_d2 = 0;
    int N = buffer_filled ? SMOOTH_WINDOW : buffer_index;
    if (N > 0) {
      for (int i = 0; i < N; i++) {
        sum_d1 += d1_buffer[i];
        sum_d2 += d2_buffer[i];
      }
      uint16_t d1_smooth = sum_d1 / N;
      uint16_t d2_smooth = sum_d2 / N;
      
      // Calcular valores relativos del promedio suavizado
      int16_t d1_final = (int16_t)d1_smooth - offset_d1;
      int16_t d2_final = (int16_t)d2_smooth - offset_d2;
      
      // Enviar valores relativos (pueden ser negativos si están más cerca que el estado de reposo)
      Serial.print(d1_final);
      Serial.print(",");
      Serial.println(-d2_final);
      
      // Forzar envío inmediato para evitar pérdida de datos
      Serial.flush();
    }
  }

  delay(25); // evita saturación del bus y del puerto serie
}
