/*
  esp-idf yay!
*/

#include <stdio.h>
#include <inttypes.h>
#include "sdkconfig.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_chip_info.h"
#include "esp_flash.h"
#include "esp_system.h"
#include "esp_rom_sys.h"
#include "esp_task_wdt.h"

#include "driver/gpio.h"
#include "soc/gpio_struct.h"

#define DISPLAY_CORE 1
#define ROW_HOLD_US 100

// serial and clock pins for cathodes (columns)
static const int SER_CAT = 25;
static const int CLK_CAT = 26;

// serial and clock pins for anodes (rows)
static const int SER_AN = 27;
static const int CLK_AN = 14;

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

static inline void digital_write(int pin, int value) {
  if (value) {
    GPIO.out_w1ts = 1UL << pin;
  } else {
    GPIO.out_w1tc = 1UL << pin;
  }
}

void pulse_row() {
  digital_write(CLK_AN, 0);
  digital_write(CLK_AN, 1);
}

void pulse_col() {
  digital_write(CLK_CAT, 0);
  digital_write(CLK_CAT, 1);
}

void display_image(int arr[8]) {
  // Put 0 into first row, 1 for the next 7
  for (int row = 0; row < 8; row++) {
    // Shift in the column
    for (int col = 0; col < 8; col++) {
      digital_write(SER_CAT, (arr[row] & (1 << col)));
      pulse_col();
    }
    pulse_col();

    // Loop over active row
    digital_write(SER_AN, (row == 7) ? 0 : 1);
    pulse_row();

    esp_rom_delay_us(ROW_HOLD_US);
  }
}

void configure_pin(int pin) {
  gpio_reset_pin(pin);
  gpio_set_direction(pin, GPIO_MODE_OUTPUT);
}

void display_task() {
  // Remove watchdog
  esp_task_wdt_delete(xTaskGetIdleTaskHandleForCore(DISPLAY_CORE));

  while (true) display_image(image);
}

void app_main(void) {
  // Reset the pins
  configure_pin(SER_CAT);
  configure_pin(CLK_CAT);
  configure_pin(SER_AN);
  configure_pin(CLK_AN);

  // Display task on dedicated core 1
  xTaskCreatePinnedToCore(
      display_task,
      "display",
      4096,                     // bytes allocated to task size
      NULL,
      configMAX_PRIORITIES - 1, // priority
      NULL,
      DISPLAY_CORE              // core ID
  );
}
