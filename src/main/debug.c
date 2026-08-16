#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>

#include "driver/gpio.h"
#include "driver/uart.h"
#include "driver/uart_vfs.h"
#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "sdkconfig.h"

typedef struct {
  char key;
  char name[32];
  gpio_num_t gpio;
  bool level;
} debug_pin_t;

#define MAX_DEBUG_PINS 16
#define COMMAND_LENGTH 96

static debug_pin_t debug_pins[MAX_DEBUG_PINS] = {
  {
    .key = 'j',
    .name = "anode SER (green)",
    .gpio = GPIO_NUM_27,
  },
  {
    .key = 'k',
    .name = "anode CLK (white)",
    .gpio = GPIO_NUM_25,
  },
  {
    .key = 'a',
    .name = "cathode SER (green)",
    .gpio = GPIO_NUM_33,
  },
  {
    .key = 's',
    .name = "cathode SRCLK (yellow)",
    .gpio = GPIO_NUM_32,
  },
  {
    .key = 'd',
    .name = "cathode RCLK (blue)",
    .gpio = GPIO_NUM_26,
  },
};

static size_t debug_pin_count = 5;

static void print_help(void) {
  printf("\nGPIO debug controls:\n");
  for (size_t i = 0; i < debug_pin_count; ++i) {
    printf("  %c  toggle %-27s GPIO %d\n",
           debug_pins[i].key,
           debug_pins[i].name,
           debug_pins[i].gpio);
  }
  printf("  r  reset every output LOW\n");
  printf("  ?  print this help\n");
  printf("\nRuntime configuration (prefix each command with ':'):\n");
  printf("  :map <key> <gpio> <name>\n");
  printf("  :unmap <key>\n");
  printf("  :list\n");
  printf("  :reset\n\n");
}

static void reset_outputs(void) {
  for (size_t i = 0; i < debug_pin_count; ++i) {
    debug_pins[i].level = false;
    ESP_ERROR_CHECK(gpio_set_level(debug_pins[i].gpio, 0));
  }
  printf("all debug outputs LOW\n");
}

static void configure_output(gpio_num_t gpio) {
  ESP_ERROR_CHECK(gpio_reset_pin(gpio));
  ESP_ERROR_CHECK(gpio_set_direction(gpio, GPIO_MODE_OUTPUT));
  ESP_ERROR_CHECK(gpio_set_level(gpio, 0));
}

static void configure_outputs(void) {
  for (size_t i = 0; i < debug_pin_count; ++i) {
    configure_output(debug_pins[i].gpio);
  }
  reset_outputs();
}

static void configure_console_uart(void) {
  const uart_port_t uart = (uart_port_t)CONFIG_ESP_CONSOLE_UART_NUM;

  if (!uart_is_driver_installed(uart)) {
    ESP_ERROR_CHECK(uart_driver_install(uart, 256, 0, 0, NULL, 0));
  }

  uart_vfs_dev_use_driver(uart);
  setvbuf(stdin, NULL, _IONBF, 0);
  setvbuf(stdout, NULL, _IONBF, 0);
}

static int find_key(char key) {
  for (size_t i = 0; i < debug_pin_count; ++i) {
    if (debug_pins[i].key == key) {
      return (int)i;
    }
  }
  return -1;
}

static bool gpio_is_available(int gpio, int current_index) {
  if (!GPIO_IS_VALID_OUTPUT_GPIO(gpio) || gpio == 1 || gpio == 3 ||
      (gpio >= 6 && gpio <= 11)) {
    return false;
  }

  for (size_t i = 0; i < debug_pin_count; ++i) {
    if ((int)i != current_index && debug_pins[i].gpio == gpio) {
      return false;
    }
  }
  return true;
}

static bool key_is_available(char key) {
  return key >= '!' && key <= '~' && strchr("r?:q", key) == NULL;
}

static void map_pin(char key, int gpio, const char *name) {
  if (key >= 'A' && key <= 'Z') {
    key += 'a' - 'A';
  }

  const int index = find_key(key);
  if (!key_is_available(key)) {
    printf("ERR key '%c' is reserved or invalid\n", key);
    return;
  }
  if (!gpio_is_available(gpio, index)) {
    printf("ERR GPIO %d is unavailable, unsafe, or already mapped\n", gpio);
    return;
  }
  if (index < 0 && debug_pin_count == MAX_DEBUG_PINS) {
    printf("ERR mapping table is full\n");
    return;
  }

  debug_pin_t *pin =
    index < 0 ? &debug_pins[debug_pin_count++] : &debug_pins[index];
  if (index >= 0) {
    ESP_ERROR_CHECK(gpio_set_level(pin->gpio, 0));
    ESP_ERROR_CHECK(gpio_reset_pin(pin->gpio));
  }

  pin->key = key;
  pin->gpio = (gpio_num_t)gpio;
  pin->level = false;
  snprintf(pin->name, sizeof(pin->name), "%s", name);
  configure_output(pin->gpio);
  printf("OK mapped %c to GPIO %d (%s)\n", pin->key, pin->gpio, pin->name);
}

static void unmap_pin(char key) {
  if (key >= 'A' && key <= 'Z') {
    key += 'a' - 'A';
  }

  const int index = find_key(key);
  if (index < 0) {
    printf("ERR key '%c' is not mapped\n", key);
    return;
  }

  ESP_ERROR_CHECK(gpio_set_level(debug_pins[index].gpio, 0));
  ESP_ERROR_CHECK(gpio_reset_pin(debug_pins[index].gpio));
  memmove(&debug_pins[index],
          &debug_pins[index + 1],
          (debug_pin_count - (size_t)index - 1) * sizeof(debug_pins[0]));
  --debug_pin_count;
  printf("OK unmapped %c\n", key);
}

static void process_command(char *command) {
  char key;
  int gpio;
  char name[sizeof(debug_pins[0].name)];

  if (sscanf(command, "map %c %d %31[^\r\n]", &key, &gpio, name) == 3) {
    map_pin(key, gpio, name);
  } else if (sscanf(command, "unmap %c", &key) == 1) {
    unmap_pin(key);
  } else if (strcmp(command, "list") == 0 || strcmp(command, "help") == 0) {
    print_help();
  } else if (strcmp(command, "reset") == 0) {
    reset_outputs();
  } else {
    printf("ERR unknown command; use :help\n");
  }
}

static void read_command(void) {
  char command[COMMAND_LENGTH];
  size_t length = 0;
  bool overflow = false;

  while (true) {
    const int input = getchar();
    if (input < 0) {
      continue;
    }
    if (input == '\r') {
      continue;
    }
    if (input == '\n') {
      break;
    }
    if (length + 1 < sizeof(command)) {
      command[length++] = (char)input;
    } else {
      overflow = true;
    }
  }

  if (overflow) {
    printf("ERR command is too long\n");
    return;
  }
  command[length] = '\0';
  process_command(command);
}

static bool toggle_pin_for_key(char key) {
  const int index = find_key(key);
  if (index < 0) {
    return false;
  }

  debug_pin_t *pin = &debug_pins[index];
  pin->level = !pin->level;
  ESP_ERROR_CHECK(gpio_set_level(pin->gpio, pin->level));
  printf(
    "%s (GPIO %d) -> %s\n", pin->name, pin->gpio, pin->level ? "HIGH" : "LOW");
  return true;
}

void app_main(void) {
  configure_console_uart();
  configure_outputs();
  print_help();

  while (true) {
    const int input = getchar();
    if (input < 0) {
      continue;
    }

    char key = (char)input;
    if (key >= 'A' && key <= 'Z') {
      key += 'a' - 'A';
    }

    if (key == ':') {
      read_command();
    } else if (key == 'r') {
      reset_outputs();
    } else if (key == '?') {
      print_help();
    } else {
      toggle_pin_for_key(key);
    }
  }
}
