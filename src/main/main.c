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

#include "driver/gpio.h"

// serial and clock pins for cathodes (columns)
const int SER_CAT = 25;
const int CLK_CAT = 26;

// serial and clock pins for anodes (rows)
const int SER_AN = 27;
const int CLK_AN = 14;

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

void pulseRow() {
  gpio_set_level(CLK_AN, 0);
  gpio_set_level(CLK_AN, 1);
}

void pulseCol() {
  gpio_set_level(CLK_CAT, 0);
  gpio_set_level(CLK_CAT, 1);
}

void displayImage(int arr[8]) {
  // Put 0 into first row, 1 for the next 7
  for (int row = 0; row < 8; row++) {
    // Shift in the column
    for (int col = 0; col < 8; col++) {
      gpio_set_level(SER_CAT, arr[row] & (1 << col) ? 1 : 0);
      pulseCol();
    }
    pulseCol();

    gpio_set_level(SER_AN, row == 7 ? 0 : 1);
    pulseRow();

    vTaskDelay(pdMS_TO_TICKS(1));
  }
}

void configure_pin(int pin) {
  gpio_reset_pin(pin);
  gpio_set_direction(pin, GPIO_MODE_OUTPUT);
}

void app_main(void) {
  printf("Hello world!\n");

  // Reset the pins
  configure_pin(SER_CAT);
  configure_pin(CLK_CAT);
  configure_pin(SER_AN);
  configure_pin(CLK_AN);

  // Draw images forever!
  while (true) {
    displayImage(image);
  }
}
