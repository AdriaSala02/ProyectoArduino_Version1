// ===================================================
// === ARDUINO SATÉLITE ==============================
// === DHT11 + Ultrasonido + Servo Radar + Media T ===
// ===================================================

#include <SoftwareSerial.h>
#include <DHT.h>
#include <Servo.h>

// -------------------------
// CONFIGURACIÓN DE PINES
// -------------------------
#define DHTPIN   2
#define DHTTYPE  DHT11
#define TRIG_PIN 7
#define ECHO_PIN 8
#define SERVO_PIN 4
#define LED_PIN 13

// -------------------------
// VARIABLES DE CONTROL
// -------------------------
const float MIN_CM = 3.0;
const float MAX_CM = 700.0;

const int   NUM_MEDIDAS = 3;      // número de lecturas por medición 
const unsigned long TIMEOUT_DIST = 45000;  // tiempo máximo de espera eco ultrasónico (µs)

const int PASO_SERVO = 2;                 // grados por paso del servo
const unsigned long INTERVALO_SERVO = 20; // ms entre pasos de servo
int angulo = 0;                           // ángulo actual del servo (0-180)
int direccion = 1;                        // 1 = sube, -1 = baja

unsigned long intervaloEnvio = 3000;  // ms entre envíos DHT al suelo
unsigned long ultimoEnvio = 0;        // instante último envío DHT
unsigned long tUltimaMedicion = 0;    // instante última medición distancia
unsigned long tUltimoServo = 0;       // instante último paso servo
const unsigned long INTERVALO_DIST = 200; // ms entre mediciones de distancia

bool enviarDatos = true;          
bool modoManual = false;          
int anguloObjetivo = 0;            // ángulo al que se fija en modo manual (0-180)
unsigned long inicioManual = 0;    // instante en el que empezó el modo manual
const unsigned long TIEMPO_MANTENER_ANG = 2000; // ms que se mantiene el ángulo manual

// -------------------------
// OBJETOS
// -------------------------
DHT dht(DHTPIN, DHTTYPE);
SoftwareSerial mySerial(10, 11);  // RX, TX con Arduino Tierra
Servo servoMotor;

// -------------------------
// VARIABLES PARA LA MEDIA
// -------------------------
float bufferTemps[10];
int indiceTemp = 0;
int numTemp = 0;
float mediaTemp = 0.0;

// ===================================================
// FUNCIONES AUXILIARES
// ===================================================

// Dispara el sensor ultrasónico y mide el tiempo de eco
long medirPulso() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  return pulseIn(ECHO_PIN, HIGH, TIMEOUT_DIST);
}

// Calcula una distancia media (mediana) a partir de n lecturas válidas
float medirDistanciaMedia(int n) {
  float v[10]; // entran hasta 10 medidas
  int medidas_validas = 0;

  if (n > 10) {
    n = 10;
  }

  for (int i = 0; i < n; i++) {
    long duracion = medirPulso();

    if (duracion == 0) { // por si no ha habido eco
      continue;          // salta al siguiente valor y descarta el actual
    }
    float d = duracion * 0.0343 / 2.0;

    if ((d < MIN_CM) || (d > MAX_CM)) {
      continue;
    }

    v[medidas_validas] = d;
    medidas_validas++;

    delay(10);
  }

  if (medidas_validas == 0)
    return -1.0;                      // error: no se obtuvo ninguna medida válida

  // Ordenación con método burbuja para obtener la mediana
  for (int i = 0; i < medidas_validas - 1; i++) {
    for (int j = 0; j < medidas_validas - 1 - i; j++) {
      if (v[j] > v[j + 1]) {
        float dist_temporal = v[j];
        v[j] = v[j + 1];
        v[j + 1] = dist_temporal;
      }
    }
  }

  return v[medidas_validas / 2]; // valor central (mediana)
}

// Calcula la media de las últimas temperaturas almacenadas
float calcularMedia() {
  if (numTemp == 0) return 0.0;
  float suma = 0;
  for (int i = 0; i < numTemp; i++) suma += bufferTemps[i];
  return suma / numTemp;
}

// ===================================================
// SETUP
// ===================================================
void setup() {
  pinMode(LED_PIN, OUTPUT);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

  Serial.begin(9600);      // Debug local (opcional, hacia PC)
  mySerial.begin(9600);    // Comunicación con Tierra

  Serial.setTimeout(50);
  mySerial.setTimeout(50);

  dht.begin();

  servoMotor.attach(SERVO_PIN);
  servoMotor.write(angulo);

  Serial.println("Satélite listo. Transmisión activa.");
  tUltimaMedicion = millis();
  tUltimoServo = millis();
}

// ===================================================
// LOOP PRINCIPAL
// ===================================================
void loop() {
  unsigned long ahora = millis();

  // =================================================
  // COMANDOS DESDE TIERRA (Arduino Tierra → mySerial)
  // =================================================
  if (mySerial.available()) {
    String orden = mySerial.readStringUntil('\n');
    orden.trim();

    if (orden.equalsIgnoreCase("Parar")) {
      enviarDatos = false;
      digitalWrite(LED_PIN, LOW);
    }
    else if (orden.equalsIgnoreCase("Reanudar")) {
      enviarDatos = true;
    }
    else if (orden.startsWith("Periodo:")) {
      unsigned long nuevo = orden.substring(8).toInt();
      if (nuevo >= 100 && nuevo <= 5000) intervaloEnvio = nuevo;
    }
    else if (orden.startsWith("ANG:")) {
      int nuevoAngulo = orden.substring(4).toInt();   // valor en grados -90..90

      if (nuevoAngulo >= -90 && nuevoAngulo <= 90) {
        int nuevoAnguloServo = nuevoAngulo + 90;      // convertir a rango 0..180

        anguloObjetivo = nuevoAnguloServo;
        angulo = anguloObjetivo;
        servoMotor.write(anguloObjetivo);

        modoManual = true;
        inicioManual = ahora;

        mySerial.print("Comando recibido. Angulo: ");
        mySerial.print(nuevoAngulo);
        mySerial.print(" --> ");
        mySerial.println(nuevoAnguloServo);
      } else {
        mySerial.println("Error: ANG fuera de rango (-90 a 90)");
      }
    }
  }

  // =================================================
  // LECTURA Y ENVÍO DHT (Temperatura / Humedad)
  // =================================================
  if (enviarDatos && (ahora - ultimoEnvio >= intervaloEnvio)) {
    float h = dht.readHumidity();
    float t = dht.readTemperature();

    if (!isnan(h) && !isnan(t)) {
      bufferTemps[indiceTemp] = t;
      indiceTemp = (indiceTemp + 1) % 10;
      if (numTemp < 10) numTemp++;
        mediaTemp = calcularMedia();

      digitalWrite(LED_PIN, HIGH);
      mySerial.print("T:");
      mySerial.print(t, 2);
      mySerial.print(":H:");
      mySerial.print(h, 2);
      mySerial.print(":M:");
      mySerial.print(mediaTemp, 2);
      mySerial.println(":");
      digitalWrite(LED_PIN, LOW);
    }
    ultimoEnvio = ahora;
  }

  // =================================================
  // CONTROL MANUAL DEL SERVO
  // =================================================

  // =================================================
  // MEDICIÓN DE DISTANCIA (ultrasonidos)
  // =================================================
  if (ahora - tUltimaMedicion >= INTERVALO_DIST) {
    tUltimaMedicion = ahora;
    float distancia = medirDistanciaMedia(NUM_MEDIDAS); // número de lecturas que hacen media

    if (distancia < 0) {
      mySerial.print(angulo);
      // CAMBIO 3: usar println en lugar de '\n' manual para simplificar
      mySerial.println(",Error medida distancia");
    }
    else {
      mySerial.print(angulo);
      mySerial.print(",");
      mySerial.println(distancia, 1);
    }
  }

  // =================================================
  // MOVIMIENTO AUTOMÁTICO SERVO (modo radar)
  // =================================================
  
  while ((unsigned long)(ahora - tUltimoServo) >= INTERVALO_SERVO) {
    tUltimoServo += INTERVALO_SERVO;

    if (modoManual) {
      // Mantenemos el ángulo objetivo mientras dura el modo manual
      servoMotor.write(anguloObjetivo);

      if (ahora - inicioManual >= TIEMPO_MANTENER_ANG) {
        modoManual = false;
      }
    } else {
      angulo += direccion * PASO_SERVO;

      if (angulo >= 180) {
        angulo = 180;
        direccion = -1;
      } else if (angulo <= 0) {
        angulo = 0;
        direccion = 1;
      }

      servoMotor.write(angulo);
    }
  }
}
