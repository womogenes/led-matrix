if(DEFINED ENV{LED_MATRIX_PROGRAM})
    set(LED_MATRIX_PROGRAM "$ENV{LED_MATRIX_PROGRAM}")
else()
    set(LED_MATRIX_PROGRAM "${CMAKE_CURRENT_SOURCE_DIR}/main.c")
endif()

if(NOT EXISTS "${LED_MATRIX_PROGRAM}")
    message(FATAL_ERROR "LED matrix program does not exist: ${LED_MATRIX_PROGRAM}")
endif()

idf_component_register(SRCS "${LED_MATRIX_PROGRAM}"
                       PRIV_REQUIRES spi_flash esp_driver_gpio esp_driver_uart esp_http_server esp_wifi esp_netif esp_event nvs_flash protocol_examples_common
                       INCLUDE_DIRS "")
