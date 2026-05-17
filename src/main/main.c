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
#include "soc/gpio_struct.h"

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

void pulse_row() {
  GPIO.out_w1tc = 1UL << (CLK_AN);   // clear CLK_CAT
  GPIO.out_w1ts = 1UL << (CLK_AN);   // set CLK_CAT
}

void pulse_col() {
  GPIO.out_w1tc = 1UL << (CLK_CAT);   // clear CLK_CAT
  GPIO.out_w1ts = 1UL << (CLK_CAT);   // set CLK_CAT
}

void display_image(int arr[8]) {
  // Put 0 into first row, 1 for the next 7
  for (int row = 0; row < 8; row++) {
    // Shift in the column
    for (int col = 0; col < 8; col++) {
      gpio_set_level(SER_CAT, arr[row] & (1 << col) ? 1 : 0);
      pulse_col();
    }
    pulse_col();

    gpio_set_level(SER_AN, row == 7 ? 0 : 1);
    pulse_row();

    vTaskDelay(1);
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
    display_image(image);
  }
}
