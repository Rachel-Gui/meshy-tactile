#include <Arduino.h>
#include <Wire.h>
#include "driver/gpio.h"

// Standalone firmware for the reworked tactile PCB whose selected analog
// signal is wired to the Feather A2 header (ESP32 GPIO34).
//
// Serial commands at 1,000,000 baud:
//   'p', row, column  -> A5 5A row column value xor_checksum
//   'b'               -> A6 5B 60 sequence payload[96] xor_checksum
//   'd'               -> one ASCII diagnostic line
//   'w'               -> legacy 32 x 32 payload followed by '\n'

// ===== Firmware identity and tuning =====
static const char FIRMWARE_VERSION[] = "tactile-a2-v2";
static const uint32_t BAUDRATE = 1000000;
static const size_t UART_TX_BUFFER_SIZE = 4096;
static const uint16_t ROW_SETTLE_US = 200;
static const uint16_t COLUMN_SETTLE_US = 150;
static const uint8_t ADC_DISCARD_SAMPLES = 2;
static const uint8_t ADC_AVERAGE_SAMPLES = 8;

// ===== MCP4018 digital potentiometer =====
static const uint8_t MCP4018_ADDRESS = 0x2F;
static const int MCP4018_STEPS = 128;
static bool mcp4018SetPercent(float percent) {
  percent = constrain(percent, 0.0f, 1.0f);
  const uint8_t wiper =
      static_cast<uint8_t>(roundf(percent * (MCP4018_STEPS - 1)));
  Wire.beginTransmission(MCP4018_ADDRESS);
  Wire.write(wiper);
  return Wire.endTransmission() == 0;
}

// ===== Row selection: CD54HC154 =====
#define ROW_A0 GPIO_NUM_26
#define ROW_A1 GPIO_NUM_25
#define ROW_A2 GPIO_NUM_16
#define ROW_A3 GPIO_NUM_17
#define ROW_BANK_SELECT GPIO_NUM_12

// ===== Column selection: ADG732 =====
#define COLUMN_A0 GPIO_NUM_27
#define COLUMN_A1 GPIO_NUM_33
#define COLUMN_A2 GPIO_NUM_15
#define COLUMN_A3 GPIO_NUM_32
#define COLUMN_A4 GPIO_NUM_14

// The PCB rework routes the selected analog signal directly to Feather A2.
static const gpio_num_t ANALOG_INPUT = GPIO_NUM_34;

static const uint8_t SENSOR_COUNT = 96;
static const uint8_t LOGICAL_TO_PHYSICAL[12] = {
    0, 2, 4, 6, 1, 3, 5, 7, 9, 11, 13, 15,
};

static uint8_t batchSequence = 0;
static uint8_t batchPayload[SENSOR_COUNT];
static uint8_t legacyFrame[32 * 32];
static bool mcp4018Acknowledged = false;

static void configureOutput(gpio_num_t pin) {
  gpio_config_t config{};
  config.intr_type = GPIO_INTR_DISABLE;
  config.mode = GPIO_MODE_OUTPUT;
  config.pin_bit_mask = 1ULL << pin;
  config.pull_down_en = GPIO_PULLDOWN_DISABLE;
  config.pull_up_en = GPIO_PULLUP_DISABLE;
  gpio_config(&config);
}

static void setRowAddress(uint8_t rowWithinBank) {
  gpio_set_level(ROW_A0, (rowWithinBank >> 0) & 1);
  gpio_set_level(ROW_A1, (rowWithinBank >> 1) & 1);
  gpio_set_level(ROW_A2, (rowWithinBank >> 2) & 1);
  gpio_set_level(ROW_A3, (rowWithinBank >> 3) & 1);
}

static void setRowBank(uint8_t bank) {
  gpio_set_level(ROW_BANK_SELECT, bank ? 1 : 0);
}

static void setColumnAddress(uint8_t column) {
  gpio_set_level(COLUMN_A0, (column >> 0) & 1);
  gpio_set_level(COLUMN_A1, (column >> 1) & 1);
  gpio_set_level(COLUMN_A2, (column >> 2) & 1);
  gpio_set_level(COLUMN_A3, (column >> 3) & 1);
  gpio_set_level(COLUMN_A4, (column >> 4) & 1);
}

static void selectPoint(uint8_t row, uint8_t column) {
  setRowBank(row >= 16);
  setRowAddress(row & 0x0F);
  delayMicroseconds(ROW_SETTLE_US);
  setColumnAddress(column);
  delayMicroseconds(COLUMN_SETTLE_US);
}

static uint16_t readA2MillivoltsFiltered() {
  // The ESP32 ADC sample-and-hold can retain part of the preceding mux value.
  // Throw away the first conversions after every address change, then average
  // fresh conversions to suppress ADC noise without changing the wire format.
  for (uint8_t index = 0; index < ADC_DISCARD_SAMPLES; ++index) {
    (void)analogReadMilliVolts(static_cast<int>(ANALOG_INPUT));
  }

  uint32_t sum = 0;
  for (uint8_t index = 0; index < ADC_AVERAGE_SAMPLES; ++index) {
    sum += analogReadMilliVolts(static_cast<int>(ANALOG_INPUT));
  }
  return static_cast<uint16_t>(
      (sum + ADC_AVERAGE_SAMPLES / 2) / ADC_AVERAGE_SAMPLES
  );
}

static uint8_t millivoltsTo8Bit(uint16_t millivolts) {
  const uint32_t clamped = min<uint32_t>(millivolts, 3300UL);
  return static_cast<uint8_t>((clamped * 255UL + 1650UL) / 3300UL);
}

static uint8_t readSelectedPoint8() {
  return millivoltsTo8Bit(readA2MillivoltsFiltered());
}

static uint8_t readOnePoint(uint8_t row, uint8_t column) {
  selectPoint(row, column);
  return readSelectedPoint8();
}

static bool readCommandByte(uint8_t &value, uint32_t timeoutMs = 100) {
  const uint32_t deadline = millis() + timeoutMs;
  while (static_cast<int32_t>(deadline - millis()) > 0) {
    if (Serial.available()) {
      value = static_cast<uint8_t>(Serial.read());
      return true;
    }
    delay(1);
  }
  return false;
}

static void sendPoint(uint8_t row, uint8_t column) {
  const uint8_t value = readOnePoint(row, column);
  uint8_t response[6] = {0xA5, 0x5A, row, column, value, 0};
  response[5] =
      response[0] ^ response[1] ^ response[2] ^ response[3] ^ response[4];
  Serial.write(response, sizeof(response));
}

static void sampleBatch96() {
  size_t index = 0;
  for (uint8_t logicalRow = 0; logicalRow < 12; ++logicalRow) {
    const uint8_t physicalRow = LOGICAL_TO_PHYSICAL[logicalRow];
    for (uint8_t offset = 1; offset <= 8; ++offset) {
      const uint8_t logicalColumn = (logicalRow + offset) % 12;
      const uint8_t physicalColumn = LOGICAL_TO_PHYSICAL[logicalColumn];
      batchPayload[index++] = readOnePoint(physicalRow, physicalColumn);
    }
  }
}

static void sendBatch96() {
  sampleBatch96();
  const uint8_t header[4] = {
      0xA6, 0x5B, SENSOR_COUNT, batchSequence++,
  };
  uint8_t checksum = 0;
  for (const uint8_t value : header) checksum ^= value;
  for (const uint8_t value : batchPayload) checksum ^= value;

  Serial.write(header, sizeof(header));
  Serial.write(batchPayload, sizeof(batchPayload));
  Serial.write(checksum);
}

static void sendLegacyFrame() {
  size_t index = 0;
  for (uint8_t row = 0; row < 32; ++row) {
    for (uint8_t column = 0; column < 32; ++column) {
      legacyFrame[index++] = readOnePoint(row, column);
    }
  }
  Serial.write(legacyFrame, sizeof(legacyFrame));
  Serial.write('\n');
}

static void sendDiagnostics() {
  const uint8_t sampleCount = 32;
  uint16_t minimumMv = UINT16_MAX;
  uint16_t maximumMv = 0;
  uint32_t totalMv = 0;

  for (uint8_t index = 0; index < sampleCount; ++index) {
    const uint16_t millivolts =
        analogReadMilliVolts(static_cast<int>(ANALOG_INPUT));
    minimumMv = min(minimumMv, millivolts);
    maximumMv = max(maximumMv, millivolts);
    totalMv += millivolts;
  }

  const uint16_t averageMv =
      static_cast<uint16_t>((totalMv + sampleCount / 2) / sampleCount);
  Wire.beginTransmission(MCP4018_ADDRESS);
  const uint8_t currentI2cStatus = Wire.endTransmission();

  Serial.print("DIAG FW=");
  Serial.print(FIRMWARE_VERSION);
  Serial.print(" SOURCE=A2_GPIO34");
  Serial.print(" MCP4018=");
  Serial.print(currentI2cStatus == 0 && mcp4018Acknowledged ? "ACK" : "NACK");
  Serial.print(" A2_MV=");
  Serial.print(minimumMv);
  Serial.print('/');
  Serial.print(averageMv);
  Serial.print('/');
  Serial.print(maximumMv);
  Serial.print(" ADC8=");
  Serial.print(millivoltsTo8Bit(averageMv));
  Serial.print(" ROW_SETTLE_US=");
  Serial.print(ROW_SETTLE_US);
  Serial.print(" COLUMN_SETTLE_US=");
  Serial.print(COLUMN_SETTLE_US);
  Serial.print(" DISCARD=");
  Serial.print(ADC_DISCARD_SAMPLES);
  Serial.print(" AVERAGE=");
  Serial.println(ADC_AVERAGE_SAMPLES);
  Serial.flush();
}

void setup() {
  Serial.setTxBufferSize(UART_TX_BUFFER_SIZE);
  Serial.begin(BAUDRATE);

  Wire.begin(23, 22);
  Wire.setClock(400000);
  mcp4018Acknowledged = mcp4018SetPercent(0.96f);

  configureOutput(ROW_A0);
  configureOutput(ROW_A1);
  configureOutput(ROW_A2);
  configureOutput(ROW_A3);
  configureOutput(ROW_BANK_SELECT);
  configureOutput(COLUMN_A0);
  configureOutput(COLUMN_A1);
  configureOutput(COLUMN_A2);
  configureOutput(COLUMN_A3);
  configureOutput(COLUMN_A4);

  setRowBank(0);
  setRowAddress(0);
  setColumnAddress(0);

  pinMode(static_cast<int>(ANALOG_INPUT), INPUT);
  analogReadResolution(12);
  analogSetPinAttenuation(static_cast<int>(ANALOG_INPUT), ADC_11db);
  delay(10);
  (void)readA2MillivoltsFiltered();
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
    if (row < 32 && column < 32) sendPoint(row, column);
  } else if (command == 'b') {
    sendBatch96();
  } else if (command == 'd') {
    sendDiagnostics();
  } else if (command == 'w') {
    sendLegacyFrame();
  }
}
