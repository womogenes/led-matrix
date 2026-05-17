idf_component_register(SRCS "main.c"
                       PRIV_REQUIRES spi_flash esp_driver_gpio esp_http_server esp_wifi esp_netif esp_event nvs_flash protocol_examples_common
                       INCLUDE_DIRS "")
