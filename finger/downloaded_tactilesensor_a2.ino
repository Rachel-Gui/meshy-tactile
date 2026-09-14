// Extend the user-supplied sketch with a true point-at-a-time serial command.
// Command:  'p', row (0..31), column (0..31)
// Response: A5 5A row column value xor_checksum
// Command:  'b' scans the 96-point cyclic layout in one hardware-side batch.
// Response: A6 5B count sequence payload[96] xor_checksum
// Command:  'd' prints one ASCII diagnostic line for the ADC/I2C readout path.

#define setup legacy_hardware_setup
#define loop legacy_full_frame_loop
#include "/Users/luojiahua/Downloads/tactilesensor.ino"
#undef setup
#undef loop

// This PCB is marked as reworked: the selected sensor's analog voltage was
// routed directly to the Feather's A2 header. On this Feather, A2 is GPIO34.
static const gpio_num_t REWORKED_ANALOG_INPUT = GPIO_NUM_34;

static bool readCommandByte(uint8_t &value, uint32_t timeoutMs = 100) {
  const uint32_t deadline = millis() + timeoutMs;
  while ((int32_t)(deadline - millis()) > 0) {
    if (Serial.available()) {
      value = (uint8_t)Serial.read();
      return true;
    }
    delay(1);
  }
  return false;
}

static uint8_t readReworkedAnalog8() {
  const uint32_t millivolts =
      ((uint32_t)analogReadMilliVolts((int)REWORKED_ANALOG_INPUT) +
       (uint32_t)analogReadMilliVolts((int)REWORKED_ANALOG_INPUT)) /
      2;
  return (uint8_t)constrain(
      (millivolts * 255UL + 1650UL) / 3300UL, 0UL, 255UL
  );
}

static uint8_t readOnePoint(uint8_t row, uint8_t column) {
  selectRowBank(row >= 16);
  setRowAddr(row & 0x0F);
  delayMicroseconds(ROW_SETTLE_US);
  setColAddr5(column);
  delayMicroseconds(COL_SETTLE_US);
  return readReworkedAnalog8();
}

static void sendPoint(uint8_t row, uint8_t column, uint8_t value) {
  uint8_t response[6] = {0xA5, 0x5A, row, column, value, 0};
  response[5] = response[0] ^ response[1] ^ response[2] ^ response[3] ^ response[4];
  Serial.write(response, sizeof(response));
}

static const uint8_t BATCH_POINT_COUNT = 96;
static const uint8_t LOGICAL_TO_PHYSICAL[12] = {
  0, 2, 4, 6, 1, 3, 5, 7, 9, 11, 13, 15
};
static uint8_t batchSequence = 0;
static uint8_t batchPayload[BATCH_POINT_COUNT];

static uint16_t readAdcDiagnostic(uint32_t spiHz, uint8_t spiMode) {
  SPI.beginTransaction(SPISettings(spiHz, MSBFIRST, spiMode));
  gpio_set_level(ADC_CS, 0);
  delayMicroseconds(2);
  const uint16_t value = SPI.transfer16(0x0000) & 0x0FFF;
  gpio_set_level(ADC_CS, 1);
  SPI.endTransaction();
  return value;
}

static void sendDiagnostics() {
  Wire.beginTransmission(MCP4018_ADDR);
  const uint8_t i2cStatus = Wire.endTransmission();
  static const uint32_t speeds[] = {100000, 500000, 1000000, 3000000};

  Serial.print("DIAG MCP4018=");
  Serial.print(i2cStatus == 0 ? "ACK" : "NACK");
  Serial.print(" SDATA_GPIO19_IDLE=");
  Serial.print(gpio_get_level(ADC_SDATA));
  Serial.print(" SDATA_A2_GPIO34_IDLE=");
  Serial.print(gpio_get_level(REWORKED_ANALOG_INPUT));
  Serial.print(" A2_RAW=");
  Serial.print(analogRead((int)REWORKED_ANALOG_INPUT));
  Serial.print(" A2_MV=");
  Serial.print(analogReadMilliVolts((int)REWORKED_ANALOG_INPUT));
  for (uint8_t speedIndex = 0; speedIndex < 4; ++speedIndex) {
    for (uint8_t mode = 0; mode < 4; ++mode) {
      uint16_t minimum = 0x0FFF;
      uint16_t maximum = 0;
      uint32_t total = 0;
      for (uint8_t sample = 0; sample < 8; ++sample) {
        const uint16_t value = readAdcDiagnostic(speeds[speedIndex], mode);
        minimum = min(minimum, value);
        maximum = max(maximum, value);
        total += value;
      }
      Serial.print(" F");
      Serial.print(speeds[speedIndex] / 1000);
      Serial.print("M");
      Serial.print(mode);
      Serial.print("=");
      Serial.print(minimum);
      Serial.print("/");
      Serial.print(total / 8);
      Serial.print("/");
      Serial.print(maximum);
    }
  }
  Serial.println();
  Serial.flush();
}

static void sendBatch96() {
  size_t index = 0;
  for (uint8_t logicalRow = 0; logicalRow < 12; ++logicalRow) {
    const uint8_t physicalRow = LOGICAL_TO_PHYSICAL[logicalRow];
    selectRowBank(physicalRow >= 16);
    setRowAddr(physicalRow & 0x0F);
    delayMicroseconds(ROW_SETTLE_US);
    for (uint8_t offset = 1; offset <= 8; ++offset) {
      const uint8_t logicalColumn = (logicalRow + offset) % 12;
      const uint8_t physicalColumn = LOGICAL_TO_PHYSICAL[logicalColumn];
      setColAddr5(physicalColumn);
      delayMicroseconds(COL_SETTLE_US);
      batchPayload[index++] = readReworkedAnalog8();
    }
  }

  const uint8_t header[4] = {0xA6, 0x5B, BATCH_POINT_COUNT, batchSequence++};
  uint8_t checksum = 0;
  for (size_t i = 0; i < sizeof(header); ++i) checksum ^= header[i];
  for (size_t i = 0; i < BATCH_POINT_COUNT; ++i) checksum ^= batchPayload[i];
  Serial.write(header, sizeof(header));
  Serial.write(batchPayload, BATCH_POINT_COUNT);
  Serial.write(checksum);
}

void setup() {
  legacy_hardware_setup();
  pinMode((int)REWORKED_ANALOG_INPUT, INPUT);
  analogReadResolution(12);
  analogSetPinAttenuation((int)REWORKED_ANALOG_INPUT, ADC_11db);
  (void)analogReadMilliVolts((int)REWORKED_ANALOG_INPUT);
}

void loop() {
  if (!Serial.available()) {
    delay(1);
    return;
  }

  const int command = Serial.read();
  if (command == 'p') {
    uint8_t row = 0;
    uint8_t column = 0;
    if (!readCommandByte(row) || !readCommandByte(column)) return;
    if (row >= 32 || column >= 32) return;
    sendPoint(row, column, readOnePoint(row, column));
  } else if (command == 'b') {
    sendBatch96();
  } else if (command == 'd') {
    sendDiagnostics();
  }
}
