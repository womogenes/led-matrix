compile:
	arduino-cli compile --fqbn esp32:esp32:esp32 ./

upload:
	arduino-cli upload -p /dev/ttyUSB0 --fqbn esp32:esp32:esp32 ./

monitor:
	arduino-cli monitor -p /dev/ttyUSB0 --fqbn esp32:esp32:esp32 --config baudrate=115200

flash:
	$(MAKE) compile ; $(MAKE) upload
