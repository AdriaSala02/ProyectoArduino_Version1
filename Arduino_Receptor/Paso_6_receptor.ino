

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

    Serial.println("🛰️ Receptor listo. Esperando comandos desde Python...");
}

void loop() {
    // 1️⃣ DATOS DEL EMISOR → PYTHON
    while (EmisorSerial.available()) {
        char data = EmisorSerial.read();
        Serial.write(data); // Reenvía byte a la PC
    }

    // 2️⃣ COMANDOS DESDE PYTHON
    if (Serial.available() > 0) {
        // Leemos el mensaje completo si es una palabra
        String comando = Serial.readStringUntil('\n');
        comando.trim();

        // Caso 1: Parpadeo rápido (comando 'P')
        if (comando == "P") {
            isBlinking = 1;
            lastBlinkTime = millis();
            digitalWrite(LED_PIN, HIGH);
        }

        // Caso 2: Comando textual "Parar" → reenviar al Emisor
        else if (comando.equalsIgnoreCase("Parar")) {
            EmisorSerial.println("Parar");
            Serial.println("🛑 Orden 'Parar' enviada al satélite.");
        }

        // Caso 3: Comando textual "Reanudar" → reenviar al Emisor
        else if (comando.equalsIgnoreCase("Reanudar")) {
            EmisorSerial.println("Reanudar");
            Serial.println("▶️ Orden 'Reanudar' enviada al satélite.");
        }
    }

    // 3️⃣ LÓGICA DE PARPADEO
    if (isBlinking == 1) {
        if ((millis() - lastBlinkTime) >= BLINK_DURATION_MS) {
            digitalWrite(LED_PIN, LOW);
            isBlinking = 0;
        }
    }
}
