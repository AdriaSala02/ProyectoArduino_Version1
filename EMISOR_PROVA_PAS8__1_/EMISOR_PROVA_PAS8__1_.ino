a#include <SoftwareSerial.h>
#include <DHT.h>
#define DHTPIN 2
#define DHTTYPE DHT11

DHT dht(DHTPIN, DHTTYPE);
SoftwareSerial mySerial(10, 11); // RX, TX 
const int led1 = 13;  // LED en el pin 13 (Verde)


void setup() {

   pinMode(led1, OUTPUT);  // IMPORTANTE: definir el LED como salida
   digitalWrite(led1, LOW); // Lo dejamos apagado al inicio

   mySerial.begin(9600);
   Serial.begin(9600);
   // Inicialización del sensor
   dht.begin();
}

void loop() {
   delay(3000);
   float h = dht.readHumidity();
   float t = dht.readTemperature();
   if (isnan(h) || isnan(t))
      Serial.println("Error al leer el sensor DHT11");
   else {
      digitalWrite(led1, HIGH);
      mySerial.print("T:");
      mySerial.print(t);
      mySerial.print("H:");
      mySerial.print(h);
      
      delay(500);             // opcional, para verlo encenderse brevemente
      digitalWrite(led1, LOW);

   }

}