// SATÉLITE
// Satélite <===> Estación de Tierra

#include <SoftwareSerial.h>
#include <DHT.h>
#include <Servo.h>

// Pines
#define DHTPIN   2
#define DHTTYPE  DHT11
#define TRIG_PIN 7
#define ECHO_PIN 8
#define SERVO_PIN 4
#define LED_PIN 13

SoftwareSerial mySerial(10, 11);  // RX, TX con Arduino Tierra
Servo servoMotor;
DHT dht(DHTPIN, DHTTYPE);

// Variables
const float MIN_CM = 3.0;
const float MAX_CM = 700.0;


const int   NUM_MEDIDAS = 3;      // si el codigo se va saturando se reduce el numero (pero menos medidas = menos precisión)

const unsigned long TIMEOUT_DIST = 30000;

const int PASO_SERVO = 2;
const unsigned long INTERVALO_SERVO = 20;
int angulo = 0;
int direccion = 1;

// Estas dos son globales y controlan el período de envío de TODOS los elementos
unsigned long periodoGlobalEnvio = 5000;   // ms. 0 = sin límite global
unsigned long ultimoEnvioGlobal  = 0;     // último envío de *cualquier* dato

unsigned long intervaloEnvio = 5000; // ms
unsigned long ultimoEnvio = 0;
unsigned long tUltimaMedicion = 0;
unsigned long tUltimoServo = 0;
const unsigned long INTERVALO_DIST = 600; // ms entre mediciones
bool calcularMediaEnSatelite = true;  // true = la media se calcula y envía desde el satélite

bool enviarDatos = true;
bool modoManual = false;
int anguloObjetivo = 0;
unsigned long inicioManual = 0;
const unsigned long TIEMPO_MANTENER_ANG = 4000;

// Para la media
float bufferTemps[10];
int indiceTemp = 0;
int numTemp = 0;
float mediaTemp = 0.0;


// ==========================================================
// Funciones

// 3 funciones para el checksum
uint8_t calcularChecksum(const String &s) {
  uint8_t sum = 0;
  for (unsigned int i = 0; i < s.length(); i++) {
    sum += (uint8_t)s[i];
  }
  return sum;
}

void enviarConChecksum(const String &payload) {
  uint8_t cs = calcularChecksum(payload);
  mySerial.print(payload);
  mySerial.print('*');
  if (cs < 0x10) {
    mySerial.print('0');
  }
  mySerial.print(cs, HEX);
  mySerial.print('|');
}

bool verificarYQuitarChecksum(String &frame) {
  int pos = frame.indexOf('*');

  if (pos < 0) {
    // No hay checksum → aceptar sin verificar
    return true;
  }

  String data = frame.substring(0, pos);
  String csStr = frame.substring(pos + 1);
  csStr.trim();

  if (csStr.length() == 0) return false;

  int csRecv = csStr.toInt();
  if (csRecv < 0 || csRecv > 255) return false;

  uint8_t csCalc = calcularChecksum(data);
  if (csCalc != (uint8_t)csRecv) {
    return false;  // checksum incorrecto
  }

  frame = data;  // dejamos solo los datos, sin "*CS"
  return true;
}


long medirPulso() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  return pulseIn(ECHO_PIN, HIGH, TIMEOUT_DIST);
}


float medirDistanciaMedia(int n) {
  float v[10]; // entran hasta 10 medidas
  int medidas_validas = 0;
 
  if (n > 10) {
    n = 10;
  }

  for (int i = 0; i < n; i++) {
    long duracion = medirPulso();

    if (duracion == 0) { // por si no ha habido eco
      continue;   // continue = salta al siguiente valor y descarta el actual
    }
    float d = duracion * 0.0343 / 2.0;

    //PARA DEBUG SI HAY ERROR EN LA MEDIDCIÓN DE DISTANCIA
    /*
    Serial.print("Pulso = ");
    Serial.print(duracion);
    Serial.print(" us, d = ");
    Serial.print(d);
    Serial.println(" cm");
    */

    if ((d < MIN_CM) || (d > MAX_CM)) {
      Serial.println(" -> fuera de rango");
      continue;
    }

    v[medidas_validas] = d;
    medidas_validas++;

    delayMicroseconds(300);
  }

  if (medidas_validas == 0)
    return -1.0;                      // ATENCIÓN CON ESTE ERROR !!!!!!!!!!!!

  // Ordenación con método burbuja
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


float calcularMedia() {
  if (numTemp == 0) return 0.0;
  float suma = 0;
  for (int i = 0; i < numTemp; i++) suma += bufferTemps[i];
  return suma / numTemp;
}

// Devuelve true si ya ha pasado el periodo global entre envíos.
// Si periodoGlobalEnvio == 0, no hay límite global.
bool puedeEnviarGlobal() {
  if (periodoGlobalEnvio == 0) {
    return true;
  }
  unsigned long ahora = millis();
  if (ahora - ultimoEnvioGlobal >= periodoGlobalEnvio) {
    ultimoEnvioGlobal = ahora;  // actualizamos el último envío global
    return true;
  }
  return false;
}


// decodifica el código del tipo 16:1:3:20 en 4 campos separados por ":".
void decodificarComando(const String &com_sat, int &c1, int &c2, int &c3, long &c4){
  String cas0 = "";
  String cas1 = "";
  String cas2 = "";
  String cas3 = "";
  String cas4 = "";

  int casilla = 0;

  for (unsigned int i = 0; i < com_sat.length(); i++) {
    char ch = com_sat[i];

    if (ch == ':') {
      casilla ++;
    } else {
      if (casilla == 0) {
        cas0 += ch;      
      } else if (casilla ==1) {
        cas1 += ch;
      } else if (casilla == 2) {
          cas2 += ch;
      } else if (casilla == 3) {
        cas3 += ch;
      } else if (casilla == 4) {
        cas4 += ch;
      }
    }
  }

  cas0.trim();
  cas1.trim();
  cas2.trim();
  cas3.trim();
  cas4.trim();
                                                  // OJO CON LOS -1!!!!!!!!!!
  c1 = (cas1.length() > 0) ? cas1.toInt() : -1;   // si casi no está vacía, se convierte a un entero. si esta vacia, a -1.
  c2 = (cas2.length() > 0) ? cas2.toInt() : -1;
  c3 = (cas3.length() > 0) ? cas3.toInt() : -1;
  c4 = (cas4.length() > 0) ? cas4.toInt() : 0;
}

void enviarMensajeTexto(const String &msg) {
  String frame = "16:0:";   // frame incluye todo el contenido de comunicación
  frame += msg;
  enviarConChecksum;
}


void setup() {

  pinMode(LED_PIN, OUTPUT);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

  Serial.begin(9600);      // Radar
  mySerial.begin(9600);    // Comunicación con Tierra


  Serial.setTimeout(50);
  mySerial.setTimeout(50);

  dht.begin();

  servoMotor.attach(SERVO_PIN);
  servoMotor.write(angulo);

  Serial.println("Satelite listo. Transmisión activa.");
  enviarMensajeTexto("Satélite iniciado. Transmitiendo datos.");
  tUltimaMedicion = millis();
  tUltimoServo = millis();
}

void loop() {
  unsigned long ahora = millis();
  static String ultimo_comando = "";
    while (mySerial.available()) {             // ojo con este if!!!!!!!!!!!!!
    String com_sat = mySerial.readStringUntil('|');
    com_sat.trim();
    if (com_sat.length() == 0) {
      continue;
    }

    if (!verificarYQuitarChecksum(com_sat)) {
      enviarMensajeTexto("Satélite: checksum incorrecto. Comando ignorado");
      continue;
    }

    if (com_sat == ultimo_comando) {
      continue;   // ignorar comandos duplicados
    }
    ultimo_comando = com_sat;

    if (com_sat.length() > 0) {
      int c1, c2, c3;
      long c4;
      decodificarComando(com_sat, c1, c2, c3, c4);

      // c1 = grupo, c2 = código, c3 = valor (según el protocolo 16:grupo:codigo:valor)

      // ======================================================
      // Sensor humedad / temperatura (16:1:...)
      // ======================================================
      if (c1 == 1) {
        // 16:1:1|  o 16:1:3|  --> iniciar / reanudar envío
        if (c2 == 1 || c2 == 3) {
          enviarDatos = true;
          enviarMensajeTexto("Satélite: envío de datos T/H activado");
        }

        // 16:1:2|  --> parar envío
        else if (c2 == 2) {
          enviarDatos = false;
          digitalWrite(LED_PIN, LOW);
          enviarMensajeTexto("Satélite: envío de datos T/H detenido");
        }

        // 16:1:4:<periodo>|  --> cambiar periodo de envío (ms)
        else if (c2 == 4) {
          if (c3 >= 500 && c3 <= 5000) {
            intervaloEnvio = (unsigned long)c3;
            String msg = "Satélite: periodo de envío = ";
            msg += intervaloEnvio;
            msg += " ms";
            enviarMensajeTexto(msg);
          } else {
            enviarMensajeTexto("Satélite: periodo de envío fuera de rango (500-5000 ms)");
          }
        }

        // 16:1:5|  --> media en Python (Tierra)
        else if (c2 == 5) {
          calcularMediaEnSatelite = false;
          enviarMensajeTexto("Satélite: media de temperatura calculada en Tierra (Python)");
        }

        // 16:1:6|  --> media en Satélite
        else if (c2 == 6) {
          calcularMediaEnSatelite = true;
          enviarMensajeTexto("Satélite: media de temperatura calculada en el propio satélite");
        }

        // 16:1:7:<periodoGlobal>|  --> cambiar periodo GLOBAL de envío (ms)
        else if (c2 == 7) {
          // c3 es el periodo global en ms. Si es 0, quitamos el límite global.
          if (c3 == 0 || (c3 >= 500 && c3 <= 10000)) {
            periodoGlobalEnvio = (unsigned long)c3;

            String msg = "Satélite: periodo GLOBAL de envío = ";
            msg += periodoGlobalEnvio;
            msg += " ms.";
            enviarMensajeTexto(msg);
          } else {
            enviarMensajeTexto("Satélite: periodo GLOBAL fuera de rango (500-10000 ms o 0 para desactivar)");
          }
        }
      }

      // ======================================================
      // Grupo 2: Servo (16:2:...)
      // ======================================================
      else if (c1 == 2) {
        // 16:2:1:<angulo>|  -> mover al ángulo deseado manualmente
        if (c2 == 1) {
          int nuevoAngulo = (int)c3;  // ángulo en rango [-90,90] desde Tierra

          if (nuevoAngulo >= -90 && nuevoAngulo <= 90) {
            int nuevoAnguloServo = nuevoAngulo + 90;

            anguloObjetivo = nuevoAnguloServo;
            angulo = anguloObjetivo;
            servoMotor.write(anguloObjetivo);

            modoManual = true;
            inicioManual = ahora;

            // Confirmación numérica a Tierra: 16:2:0:<anguloServo>|
            mySerial.print("16:2:0:");
            mySerial.print(nuevoAnguloServo);
            mySerial.print("|");
            enviarConChecksum(frame);

            // Mensaje de texto 16:0:... para Python
            String msg = "Satélite: servo movido a ";
            msg += nuevoAngulo;
            msg += " grados";
            enviarMensajeTexto(msg);
          } else {
            // Ángulo fuera de rango: 16:2:-1| + mensaje 16:0:...
            mySerial.print("16:2:-1|");
            enviarMensajeTexto("Satélite: ángulo de servo fuera de rango (-90 a 90)");
          }
        }
      }
    }
  }

  // === LECTURA Y ENVÍO DHT (protocolo 16:1:xx) ===
  if (enviarDatos && (ahora - ultimoEnvio >= intervaloEnvio) && puedeEnviarGlobal()) {

    float h = dht.readHumidity();
    float t = dht.readTemperature();

    if (isnan(h) || isnan(t)) {
      // DEBUG con tiempo transcurrido
      Serial.print('[');
      Serial.print(millis());
      Serial.print(" ms] DHT ERROR: lectura NaN");
      Serial.println();
      
      // 16:1:-1| Error con la lectura del sensor de temperatura y humedad
      mySerial.print("16:1:-1|");
    } else {
      // Actualizamos media solo si se calcula en el satélite
      if (calcularMediaEnSatelite) {
        bufferTemps[indiceTemp] = t;
        indiceTemp = (indiceTemp + 1) % 10;
        if (numTemp < 10) numTemp++;
        mediaTemp = calcularMedia();
      }

      digitalWrite(LED_PIN, HIGH);

      // 16:1:01| dato Temperatura (envío regular)
      mySerial.print("16:1:01:");
      mySerial.print(t, 2);
      mySerial.print("|");
      enviarConChecksum(frame);

      // 16:1:02| dato Humedad (envío regular)
      mySerial.print("16:1:02:");
      mySerial.print(h, 2);
      mySerial.print("|");
      enviarConChecksum(frame);

      // 16:1:03| dato media temperatura (solo si la calcula el satélite)
      if (calcularMediaEnSatelite) {
        mySerial.print("16:1:03:");
        mySerial.print(mediaTemp, 2);
        mySerial.print("|");
        enviarConChecksum(frame);
      }

      digitalWrite(LED_PIN, LOW);
    }
    ultimoEnvio = ahora;
  }

  // CONTROL MANUAL DE SERVO
  if (Serial.available() > 0) {
    int nuevoAngulo = Serial.parseInt();  // parseInt = leer un entero

    if (nuevoAngulo >= -90 && nuevoAngulo <= 90) {
      int nuevoAnguloServo = nuevoAngulo + 90;

      anguloObjetivo = nuevoAnguloServo;
      angulo = anguloObjetivo;
      servoMotor.write(anguloObjetivo);

      modoManual = true;
      inicioManual = millis();

      if (Serial.available() > 0) {       // este if también cambiado !!!!!!!!!!!
        Serial.read();
      }

      mySerial.print("Comando recibido. Angulo: ");
      mySerial.print(nuevoAngulo);
      mySerial.print(" --> ");
      mySerial.println(nuevoAnguloServo);
    }
  }

  // MEDICIÓN DE DISTANCIA (protocolo 16:3:x)
  if (ahora - tUltimaMedicion >= INTERVALO_DIST) {
  tUltimaMedicion = ahora;
  float distancia = medirDistanciaMedia(NUM_MEDIDAS); // número de lecturas que hacen media

  if (distancia < 0) {
    // 16:3:-2| Error lectura distancia
    mySerial.print("16:3:-2|");
    enviarConChecksum(frame);
  } else {
    // 16:3:0:<angulo>:<distancia>| Envío regular de distancia
    mySerial.print("16:3:0:");
    mySerial.print(angulo);
    mySerial.print(":");
    mySerial.print(distancia, 1);
    mySerial.print("|");
    enviarConChecksum(frame);

    Serial.println(distancia); // debug para comprobar si funciona el sensor
  }
}


  // MOVIMIENTO AUTOMÁTICO SERVO
  while ((unsigned long)(ahora - tUltimoServo) >= INTERVALO_SERVO) {    // con while en lugar de if se supone que va mejor
    tUltimoServo += INTERVALO_SERVO;

    if (modoManual) {
      // mantenemos el ángulo objetivo mientras dura el modo manual
      unsigned long ahoraServo = millis();    // control del tiempo más preciso
      servoMotor.write(anguloObjetivo);

      if (ahoraServo - inicioManual >= TIEMPO_MANTENER_ANG) {
        modoManual = false;
      }
    } 
    else {
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
