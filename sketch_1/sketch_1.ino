const int SER_CAT = 25;
const int CLK_CAT = 26;

const int SER_AN = 27;
const int CLK_AN = 14;

int counter = 0;

int image[8] = {
  0b00000000,
  0b01000010,
  0b10100101,
  0b11111111,
  0b10000001,
  0b10100101,
  0b10000001,
  0b01111110,
};

void setup() {
  pinMode(CLK_CAT, OUTPUT);
  pinMode(SER_CAT, OUTPUT);

  pinMode(CLK_AN, OUTPUT);
  pinMode(SER_AN, OUTPUT);
}

void pulseRow() {
  digitalWrite(CLK_AN, LOW);
  digitalWrite(CLK_AN, HIGH);
}

void pulseCol() {
  digitalWrite(CLK_CAT, LOW);
  digitalWrite(CLK_CAT, HIGH);
}

void displayImage(int arr[8]) {
  // Put 0 into first row, 1 for the next 7
  for (int row = 0; row < 8; row++) {
    // Shift in the column
    for (int col = 0; col < 8; col++) {
      digitalWrite(SER_CAT, arr[row] & (1 << col) ? HIGH : LOW);
      pulseCol();
    }
    pulseCol();

    digitalWrite(SER_AN, row == 7 ? LOW : HIGH);
    pulseRow();

    delay(2);
  }
}

void loop() {
  displayImage(image);

  // digitalWrite(SER_AN, (counter % 8) < 4 ? HIGH : LOW);
  // digitalWrite(SER_CAT, (counter % 8) < 4 ? HIGH : LOW);

  // digitalWrite(CLK_AN, 1);
  // digitalWrite(CLK_AN, 0);

  // digitalWrite(CLK_CAT, 1);
  // digitalWrite(CLK_CAT, 0);

  // counter++;
  // delay(250);
}
