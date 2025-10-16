// **ARDUINO RECEPTOR/CONTROLADOR (Conectado a la PC - COM4)**
// Este sketch recibe los datos del Arduino Emisor (DHT) a través de SoftwareSerial
// y los reenvía a Python. También recibe el comando 'P' de Python para parpadear el LED.

#include <SoftwareSerial.h>

// --- CONFIGURACIÓN DE PINES Y VELOCIDADES ---
#define LED_PIN 13              // Pin del LED integrado
#define BLINK_DURATION_MS 100   // Duración del pulso de encendido (en milisegundos)
#define BAUDRATE 9600           // Velocidad de comunicación

// Configuración de la comunicación con el Arduino Emisor (el del sensor):
// Conecta el TX del Emisor al Pin 10 (RX) del Receptor.
SoftwareSerial EmisorSerial(10, 11); 

// --- VARIABLES DE ESTADO ---
// Usamos int para representar booleanos (1 = True, 0 = False) en estilo C
int isBlinking = 0; 
unsigned long lastBlinkTime = 0;

void setup() {
    // 1. Inicializar Serial Hardware (para comunicarse con Python/PC)
    Serial.begin(BAUDRATE);      
    
    // 2. Inicializar Serial Software (para comunicarse con el Arduino Emisor)
    EmisorSerial.begin(BAUDRATE); 
    
    pinMode(LED_PIN, OUTPUT);
    digitalWrite(LED_PIN, LOW);
}

void loop() {
    // 1. LÓGICA DE PUENTE: De Arduino Emisor (SoftSerial) a Python (HardSerial)
    // MIENTRAS haya datos disponibles en la línea del Emisor:
    while (EmisorSerial.available()) {
        char data = EmisorSerial.read();
        Serial.write(data); // Reenvía el byte directamente al puerto COM4
    }

    // 2. CONTROL DEL LED: Si hay datos esperando de Python (un comando)
    if (Serial.available() > 0) {
        char command = Serial.read(); 
        
        // Si el comando es 'P' (Parpadeo)
        if (command == 'P') { 
            isBlinking = 1; /* Activar la bandera de parpadeo */
            lastBlinkTime = millis();
            digitalWrite(LED_PIN, HIGH); /* Encender el LED inmediatamente */
        }
    }

    // 3. LÓGICA DE TIEMPO: Apagar el LED después del pulso rápido
    if (isBlinking == 1) {
        // Comprobar si ha pasado el tiempo de la duración del parpadeo
        if ((millis() - lastBlinkTime) >= BLINK_DURATION_MS) {
            digitalWrite(LED_PIN, LOW); /* Apagar el LED */
            isBlinking = 0; /* Finalizar el ciclo de parpadeo */
        }
    }
}
