/*
  esp-idf yay!
*/

#include <stdio.h>
#include <inttypes.h>
#include <string.h>
#include <stdbool.h>
#include <stdint.h>
#include "sdkconfig.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_event.h"
#include "esp_http_server.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "esp_system.h"
#include "esp_rom_sys.h"
#include "esp_task_wdt.h"
#include "protocol_examples_common.h"

#include "driver/gpio.h"
#include "soc/gpio_struct.h"

#define DISPLAY_CORE 1
#define ROW_HOLD_US 1000

static const char *TAG = "led_matrix";

// serial and clock pins for cathodes (columns)
static const int SER_CAT = 25;
static const int CLK_CAT = 26;

// serial and clock pins for anodes (rows)
static const int SER_AN = 27;
static const int CLK_AN = 14;

static uint8_t active_frame[8] = {
  0b00000000,
  0b01000010,
  0b10100101,
  0b11111111,
  0b10000001,
  0b10100101,
  0b10000001,
  0b01111110,
};
static uint8_t pending_frame[8];
static bool pending_frame_ready = false;
static portMUX_TYPE frame_lock = portMUX_INITIALIZER_UNLOCKED;

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

void display_image(uint8_t arr[8]) {
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

  taskENTER_CRITICAL(&frame_lock);
  if (pending_frame_ready) {
    memcpy(active_frame, pending_frame, sizeof(active_frame));
    pending_frame_ready = false;
  }
  taskEXIT_CRITICAL(&frame_lock);
}

void configure_pin(int pin) {
  gpio_reset_pin(pin);
  gpio_set_direction(pin, GPIO_MODE_OUTPUT);
}

void display_task() {
  // Remove watchdog
  esp_task_wdt_delete(xTaskGetIdleTaskHandleForCore(DISPLAY_CORE));

  while (true) display_image(active_frame);
}

static esp_err_t frame_ws_handler(httpd_req_t *req) {
  // Runs on every websocket command
  if (req->method == HTTP_GET) {
    ESP_LOGI(TAG, "WebSocket client connected");
    return ESP_OK;
  }

  uint8_t frame[8];
  httpd_ws_frame_t pkt = {0};
  esp_err_t ret = httpd_ws_recv_frame(req, &pkt, 0);
  if (ret != ESP_OK) return ret;

  if (pkt.type != HTTPD_WS_TYPE_BINARY || pkt.len != sizeof(frame)) {
    ESP_LOGW(TAG, "Rejected WebSocket frame: type=%d len=%d", pkt.type, pkt.len);
    return ESP_FAIL;
  }

  // Write the 8 bytes to `frame`
  pkt.payload = frame;
  ret = httpd_ws_recv_frame(req, &pkt, sizeof(frame));
  if (ret != ESP_OK) return ret;

  // Swap frames with lock
  taskENTER_CRITICAL(&frame_lock);
  memcpy(pending_frame, frame, sizeof(pending_frame));
  pending_frame_ready = true;
  taskEXIT_CRITICAL(&frame_lock);

  return ESP_OK;
}

static httpd_handle_t start_webserver(void) {
  httpd_handle_t server = NULL;
  esp_netif_ip_info_t ip_info;
  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  config.core_id = 0;

  static const httpd_uri_t frame_ws = {
    .uri = "/frame",
    .method = HTTP_GET,
    .handler = frame_ws_handler,
    .is_websocket = true,
  };

  ESP_ERROR_CHECK(httpd_start(&server, &config));
  ESP_ERROR_CHECK(httpd_register_uri_handler(server, &frame_ws));
  ESP_ERROR_CHECK(esp_netif_get_ip_info(get_example_netif(), &ip_info));
  ESP_LOGI(TAG, "WebSocket endpoint ready at ws://" IPSTR "/frame", IP2STR(&ip_info.ip));

  return server;
}

void app_main(void) {
  // Fetch credentials + check wifi connection
  ESP_ERROR_CHECK(nvs_flash_init());
  ESP_ERROR_CHECK(esp_netif_init());
  ESP_ERROR_CHECK(esp_event_loop_create_default());
  ESP_ERROR_CHECK(example_connect());
  start_webserver();

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
