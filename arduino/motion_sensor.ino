const int PIR_PIN = 2; // Pin connected to PIR output
const int LED_PIN = 3; // Optional LED for visual feedback

void setup() {
  pinMode(PIR_PIN, INPUT);
  pinMode(LED_PIN, OUTPUT);
  Serial.begin(9600);
}

void loop() {
  int motion = digitalRead(PIR_PIN);
  if (motion == HIGH) {
    Serial.println("ON");
    digitalWrite(LED_PIN, HIGH);
  } else {
    Serial.println("OFF");
    digitalWrite(LED_PIN, LOW);
  }
  delay(100); // Small delay for stability
}
