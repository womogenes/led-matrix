SHELL := /bin/bash

IDF_PATH ?= $(HOME)/esp/esp-idf
IDF_TOOLS_PATH ?= $(HOME)/.espressif
PORT ?= /dev/ttyUSB0
BAUD ?= 115200

IDF_PYTHON ?= $(firstword $(wildcard $(IDF_TOOLS_PATH)/python_env/idf*_env/bin/python))
XTENSA_BIN ?= $(firstword $(wildcard $(IDF_TOOLS_PATH)/tools/xtensa-esp-elf/*/xtensa-esp-elf/bin))
ESP_ROM_ELF_DIR ?= $(firstword $(wildcard $(IDF_TOOLS_PATH)/tools/esp-rom-elfs/*))

PROGRAM_GOALS := $(filter %.c,$(MAKECMDGOALS))

ifneq ($(words $(PROGRAM_GOALS)),0)
ifneq ($(words $(PROGRAM_GOALS)),1)
$(error Pass exactly one C program, for example: make flash main/debug.c)
endif
PROGRAM := $(firstword $(PROGRAM_GOALS))
else
PROGRAM ?= main/main.c
endif

ifeq ($(wildcard $(PROGRAM)),)
$(error Program does not exist: $(PROGRAM))
endif

PROGRAM_NAME := $(basename $(notdir $(PROGRAM)))
BUILD_DIR ?= build/$(PROGRAM_NAME)
PYTHON_ENV := $(patsubst %/bin/python,%,$(IDF_PYTHON))

IDF_ENV := env \
	IDF_PATH="$(IDF_PATH)" \
	IDF_TOOLS_PATH="$(IDF_TOOLS_PATH)" \
	IDF_PYTHON_ENV_PATH="$(PYTHON_ENV)" \
	ESP_ROM_ELF_DIR="$(ESP_ROM_ELF_DIR)" \
	LED_MATRIX_PROGRAM="$(abspath $(PROGRAM))" \
	PATH="$(dir $(IDF_PYTHON)):$(XTENSA_BIN):/usr/local/sbin:/usr/local/bin:/usr/bin:/bin"
IDF := $(IDF_ENV) "$(IDF_PYTHON)" "$(IDF_PATH)/tools/idf.py"

.DEFAULT_GOAL := help
.PHONY: help build flash monitor clean

help:
	@printf '%s\n' \
		'Usage:' \
		'  make flash main/debug.c   Build and flash a specific program' \
		'  make flash                Build and flash main/main.c' \
		'  make build main/debug.c   Build without flashing' \
		'  make monitor main/debug.c Open its serial monitor' \
		'  make clean main/debug.c   Remove its generated build directory' \
		'' \
		'Override the serial device with PORT=/dev/ttyUSB1 if needed.'

build:
	@test -x "$(IDF_PYTHON)" || { echo "ESP-IDF Python environment not found under $(IDF_TOOLS_PATH)/python_env" >&2; exit 1; }
	@test -x "$(IDF_PATH)/tools/idf.py" || { echo "ESP-IDF not found at $(IDF_PATH)" >&2; exit 1; }
	@test -x "$(XTENSA_BIN)/xtensa-esp32-elf-gcc" || { echo "ESP32 compiler not found under $(IDF_TOOLS_PATH)/tools" >&2; exit 1; }
	$(IDF) -B "$(BUILD_DIR)" reconfigure build

flash: build
	$(IDF) -B "$(BUILD_DIR)" -p "$(PORT)" -b "$(BAUD)" flash

monitor:
	$(IDF) -B "$(BUILD_DIR)" -p "$(PORT)" monitor

clean:
	$(IDF) -B "$(BUILD_DIR)" fullclean

ifneq ($(PROGRAM_GOALS),)
.PHONY: $(PROGRAM_GOALS)
$(PROGRAM_GOALS):
	@:
endif
