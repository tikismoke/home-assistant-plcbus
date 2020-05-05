import serial
myser= serial.Serial('/dev/ttyUSB0',9600)
frame="0205D1001D000003"
message_bytes = bytes.fromhex(frame)
myser.write(message_bytes)