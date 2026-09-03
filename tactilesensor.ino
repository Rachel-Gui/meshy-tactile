
#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>
#include "driver/gpio.h"

// ===== Tunable parameters =====
#define BAUDRATE            1000000
#define UART_TX_BUF         4096
#define WAIT_CMD            1
#define COL_SETTLE_US       75
#define ROW_SETTLE_US       150
#define GUARD_BEFORE_ADC_US 0
#define ADC_DISCARD_FIRST   0
#define ADC_AVG2            0
#define USE_COL_EN_BLANK    0   // If /EN is wired, set to 1 and use together with linear addressing

// ===== MCP4018 =====
static const uint8_t MCP4018_ADDR  = 0x2F;
static const int     MCP4018_STEPS = 128;
static inline bool mcp4018_set_percent(float pct){
  if (pct < 0) pct = 0; if (pct > 1) pct = 1;
  uint8_t w = (uint8_t)roundf(pct * (MCP4018_STEPS - 1));
  Wire.beginTransmission(MCP4018_ADDR);
  Wire.write(w);
  return Wire.endTransmission() == 0;
}

// ===== Rows (CD54HC154) =====
#define ROW_A0 GPIO_NUM_26
#define ROW_A1 GPIO_NUM_25
#define ROW_A2 GPIO_NUM_16
#define ROW_A3 GPIO_NUM_17
#define ROW_BANK_SEL GPIO_NUM_12 // LOW:1..16, HIGH:17..32

// ===== Columns (ADG732) =====
#define COL_A0 GPIO_NUM_27
#define COL_A1 GPIO_NUM_33
#define COL_A2 GPIO_NUM_15
#define COL_A3 GPIO_NUM_32
#define COL_A4 GPIO_NUM_14
static const int COL_EN = -1;  // If /EN is not wired, keep as -1

// ===== External ADC (AD7466, U1) =====
// U1 pin 1: /CS, pin 2: SDATA, pin 3: SCLK
#define ADC_CS    GPIO_NUM_4
#define ADC_SDATA GPIO_NUM_19
#define ADC_SCLK  GPIO_NUM_5
static const uint32_t ADC_SPI_HZ = 3000000;

// ===== Buffer =====
static uint8_t frame[32*32]; // 1024B

static inline void cfgOut(gpio_num_t pin){
  gpio_config_t c{};
  c.intr_type=GPIO_INTR_DISABLE; c.mode=GPIO_MODE_OUTPUT;
  c.pin_bit_mask=(1ULL<<pin); c.pull_down_en=GPIO_PULLDOWN_DISABLE; c.pull_up_en=GPIO_PULLUP_DISABLE;
  gpio_config(&c);
}

static inline void setRowAddr(uint8_t r0_15){
  gpio_set_level(ROW_A0, (r0_15>>0)&1);
  gpio_set_level(ROW_A1, (r0_15>>1)&1);
  gpio_set_level(ROW_A2, (r0_15>>2)&1);
  gpio_set_level(ROW_A3, (r0_15>>3)&1);
}
static inline void selectRowBank(uint8_t bank){ gpio_set_level(ROW_BANK_SEL, bank?1:0); }

static inline void setColAddr5(uint8_t v5){
  // Linear binary: A0 = LSB, A4 = MSB
  gpio_set_level(COL_A0, (v5>>0)&1);
  gpio_set_level(COL_A1, (v5>>1)&1);
  gpio_set_level(COL_A2, (v5>>2)&1);
  gpio_set_level(COL_A3, (v5>>3)&1);
  gpio_set_level(COL_A4, (v5>>4)&1);
}

static inline void colsEnable(bool en){
  if (COL_EN>=0) gpio_set_level((gpio_num_t)COL_EN, en?0:1); // /EN active low
}

static inline uint16_t readAD7466Raw(){
  SPI.beginTransaction(SPISettings(ADC_SPI_HZ, MSBFIRST, SPI_MODE0));
  gpio_set_level(ADC_CS, 0);
  delayMicroseconds(1);
  uint16_t word = SPI.transfer16(0x0000);
  gpio_set_level(ADC_CS, 1);
  SPI.endTransaction();

  // AD7466 frame: four leading zeros followed by the 12-bit result.
  return word & 0x0FFF;
}

static inline uint8_t readPixel8(){
  if (GUARD_BEFORE_ADC_US) delayMicroseconds(GUARD_BEFORE_ADC_US);
#if ADC_DISCARD_FIRST
  (void)readAD7466Raw();
#endif
#if ADC_AVG2
  uint16_t a = readAD7466Raw();
  uint16_t b = readAD7466Raw();
  uint16_t m = (a + b) >> 1;
  return (uint8_t)(m >> 4);
#else
  uint16_t a = readAD7466Raw();
  return (uint8_t)(a >> 4);
#endif
}

static inline void wait_command_if_needed(){
#if WAIT_CMD
  while (true){
    if (Serial.available()){
      int ch = Serial.read();
      if (ch == 'w') break;
    }
    delay(1);
  }
#endif
}

void setup(){
  Serial.setTxBufferSize(UART_TX_BUF);
  Serial.begin(BAUDRATE);

  Wire.begin(23,22);
  Wire.setClock(400000);
  (void)mcp4018_set_percent(0.96f); //0.999f // 0.9999 12/8

  cfgOut(ROW_A0); cfgOut(ROW_A1); cfgOut(ROW_A2); cfgOut(ROW_A3); cfgOut(ROW_BANK_SEL);
  cfgOut(COL_A0); cfgOut(COL_A1); cfgOut(COL_A2); cfgOut(COL_A3); cfgOut(COL_A4);
  if (COL_EN>=0) cfgOut((gpio_num_t)COL_EN);

  cfgOut(ADC_CS);
  gpio_set_level(ADC_CS, 1);
  SPI.begin((int)ADC_SCLK, (int)ADC_SDATA, -1, (int)ADC_CS);

  gpio_set_level(ROW_BANK_SEL, 0);
  if (COL_EN>=0) gpio_set_level((gpio_num_t)COL_EN, 1);
  setRowAddr(0); setColAddr5(0);

  (void)readAD7466Raw();
}

void loop(){
  wait_command_if_needed();

  size_t idx=0;

  for (uint8_t r=0; r<32; ++r){
    selectRowBank(r>=16);
    setRowAddr(r & 0x0F);

#if USE_COL_EN_BLANK
    if (COL_EN>=0) colsEnable(false);
#endif
    delayMicroseconds(ROW_SETTLE_US);
#if USE_COL_EN_BLANK
    if (COL_EN>=0) colsEnable(true);
#endif

    for (uint8_t c=0; c<32; ++c){
#if USE_COL_EN_BLANK
      if (COL_EN>=0){
        colsEnable(false);
        setColAddr5(c);               // ★ Linear addressing
        delayMicroseconds(8);
        colsEnable(true);
      } else {
        setColAddr5(c);
      }
#else
      setColAddr5(c);                 // ★ Linear addressing
#endif
      delayMicroseconds(COL_SETTLE_US);
      frame[idx++] = readPixel8();
    }
  }

  Serial.write(frame, sizeof(frame));
  Serial.write('\n'); // optional
}
