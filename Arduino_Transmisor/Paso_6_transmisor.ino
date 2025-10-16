#include <SoftwareSerial.h>
#include <DHT.h>

#define DHTPIN 2
#define DHTTYPE DHT11

DHT dht(DHTPIN, DHTTYPE);
SoftwareSerial mySerial(10, 11); // RX, TX 
const int led1 = 13;  // LED en el pin 13 (Verde)

bool enviarDatos = true;          // Estado de transmisión (inicialmente activo)
unsigned long ultimoEnvio = 0;    // Control de tiempo para los envíos

void setup() {
  pinMode(led1, OUTPUT);
  digitalWrite(led1, LOW);

  mySerial.begin(9600);
  Serial.begin(9600);

  dht.begin();

  Serial.println("🚀 Satélite listo. Transmisión activa.");
}

void loop() {
  // -- - ESCUCHA ÓRDENES DEL RECEPTOR ---
  if (mySerial.available()) {
    String orden = mySerial.readStringUntil('\n');
    orden.trim();

    if (orden.equalsIgnoreCase("Parar")) {
      enviarDatos = false;
      digitalWrite(led1, LOW);
      Serial.println("🛑 Transmisión detenida (orden PARAR recibida).");
    } 
    else if (orden.equalsIgnoreCase("Reanudar")) {
      enviarDatos = true;
      Serial.println("▶️ Transmisión reanudada (orden REANUDAR recibida).");
    }
  }

  // --- ENVÍO DE DATOS SI ESTÁ ACTIVADO ---
  if (enviarDatos && millis() - ultimoEnvio >= 1000) {
    float h = dht.readHumidity();
    float t = dht.readTemperature();

    if (isnan(h) || isnan(t)) {
      Serial.println("⚠️ Error al leer el sensor DHT11");
    } else {
      digitalWrite(led1, HIGH);
      delay(500);
      // 💡 Mantenemos el mismo formato que ya usabas:
      // Ejemplo: T:25.5:H:60.2:
      mySerial.print("T:");
      mySerial.print(t);
      mySerial.print(":H:");
      mySerial.print(h);
      mySerial.print(":");
      digitalWrite(led1, LOW);
    }
    ultimoEnvio = millis();
  }
}
