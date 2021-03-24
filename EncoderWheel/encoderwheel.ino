#define SERVO_PIN 8

int PWLUT[16] = {2040, 1970, 1832, 1901, 1554, 1624, 1762, 1693, 1000, 1069, 1208, 1138, 1485, 1416, 1277, 1346};

int i = 0;
int incomingByte = 0;
bool valid1 = false;
byte index = 0;
int dt = 0;

// the setup function runs once when you press reset or power the board
void setup() {
  // initialize digital pin LED_BUILTIN as an output.
  pinMode(LED_BUILTIN, OUTPUT);
  pinMode(SERVO_PIN, OUTPUT); 
  digitalWrite(LED_BUILTIN, 0); 
  digitalWrite(SERVO_PIN, 0); 
  Serial.begin(9600); 
}

// the loop function runs over and over again forever
void loop() {
  if (Serial.available() > 0) {
          incomingByte = Serial.read();        
          dt = int(512 + 8.0*(float(incomingByte)));
          Serial.println(incomingByte);
          Serial.println(dt);
  }
  
  digitalWrite(LED_BUILTIN, HIGH);
  digitalWrite(8, HIGH);
  delayMicroseconds(dt);
  digitalWrite(8, LOW);
  digitalWrite(LED_BUILTIN, LOW);  
  delay(15);  
}
