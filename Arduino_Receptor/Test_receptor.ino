#include <SoftwareSerial.h>

// --- CONFIGURACIÓN DE PINES Y VELOCIDADES ---
#define LED_PIN 13              // Pin del LED integrado
#define BLINK_DURATION_MS 100   // Duración del pulso de encendido (en milisegundos)
#define BAUDRATE 9600           // Velocidad de comunicación

// Comunicación con el Arduino Emisor (el del sensor):
SoftwareSerial EmisorSerial(10, 11); // RX, TX

// --- VARIABLES DE ESTADO ---
int isBlinking = 0;
unsigned long lastBlinkTime = 0;

void setup() {
    Serial.begin(BAUDRATE);       // Comunicación con Python/PC
    EmisorSerial.begin(BAUDRATE); // Comunicación con Arduino Emisor (Satélite)
    pinMode(LED_PIN, OUTPUT);
    digitalWrite(LED_PIN, LOW);

    Serial.println("Receptor listo. Esperando comandos desde Python...");
}

void loop() {
   // DATOS DEL EMISOR → PYTHON
   if (EmisorSerial.available()) {
   Serial.println("La transmision de informacion es la esperada");
}
else
 Serial.println("La conexion entre ambos arduinos no es la esperada, es posbile que se deba a un error de conexion de pines o un error interno en las conexiones");
}
