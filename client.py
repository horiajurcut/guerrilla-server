import socket

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

client.connect((' 192.168.27.100', 1060))

while True:
  message = client.recv(4096)

  if message:
    print message