// ================================================
// === ARDUINO ESTACIÓN DE TIERRA ================
// === Puente entre Satélite y PC (Python) =======
// ================================================

#include <SoftwareSerial.h>

#define LED_PIN     13   // LED de actividad (verde)
#define LED_ERROR    8   // LED rojo de error 
#define BAUDRATE  9600

SoftwareSerial SatSerial(10, 11);  // RX, TX con Satélite

void setup() {
  Serial.begin(BAUDRATE);

  SatSerial.begin(BAUDRATE);

  pinMode(LED_PIN, OUTPUT);
  pinMode(LED_ERROR, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  digitalWrite(LED_ERROR, LOW);

  Serial.setTimeout(50);
  SatSerial.setTimeout(50);

  Serial.println("Receptor (Tierra) listo. Esperando comandos desde Python...");
}

void loop() {
  // =================================================
  // DATOS DESDE SATÉLITE → PC
  // =================================================
  while (SatSerial.available()) {
    char c = SatSerial.read();
    Serial.write(c);
  }

  // =================================================
  // COMANDOS DESDE PYTHON → SATÉLITE
  // =================================================
  if (Serial.available()) {
    String comando = Serial.readStringUntil('\n');
    comando.trim();

    if (comando.length() == 0) {
      return;
    }

    if (comando.equalsIgnoreCase("Parar")) {
      SatSerial.println("Parar");
      digitalWrite(LED_PIN, LOW);
    }
    else if (comando.equalsIgnoreCase("Reanudar")) {
      SatSerial.println("Reanudar");
      digitalWrite(LED_PIN, HIGH);
    }
    else if (comando.startsWith("Periodo:")) {
      SatSerial.println(comando);
    }
    else if (comando.equalsIgnoreCase("Iniciar"))
    {
      SatSerial.println("Iniciar");
      digitalWrite(LED_PIN,HIGH);
    }
    else if (comando.startsWith("ANG:")) {
      SatSerial.println(comando);
    }
    else {
      SatSerial.println(comando);
    }
  }
}
