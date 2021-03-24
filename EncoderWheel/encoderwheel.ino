#define SERVO_PIN 8

int PWLUT[16] = {2040, 1970, 1832, 1901, 1554, 1624, 1762, 1693, 1000, 1069, 1208, 1138, 1485, 1416, 1277, 1346};

int i = 0;
byte incomingByte = 0;
bool valid1 = false;
byte index = 0;

// the setup function runs once when you press reset or power the board
void setup() {
  // initialize digital pin LED_BUILTIN as an output.
  pinMode(LED_BUILTIN, OUTPUT);
  pinMode(SERVO_PIN, OUTPUT); 
  digitalWrite(LED_BUILTIN, 0); 
  digitalWrite(SERVO_PIN, 0); 
  i = 0;
  Serial.begin(9600); 
}

// the loop function runs over and over again forever
void loop() {
  if (Serial.available() > 0) {
          incomingByte = Serial.read();        
          if ((incomingByte & 0b11110000) == 0b10100000){
            index = incomingByte & 0b00001111;
            digitalWrite(LED_BUILTIN, index % 2);
            digitalWrite(8, HIGH);
            delayMicroseconds(PWLUT[index]);
            digitalWrite(8, LOW);
            delay(5);
          };
          if ((incomingByte) == 0b01011111){
            index = incomingByte & 0b00001111;
            digitalWrite(LED_BUILTIN, 0);
            Serial.print("EncoderWheel\r\n");
          }; 
  }
  delay(5);  
}
