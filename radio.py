import gevent

from gevent.server import StreamServer
from gevent import monkey
monkey.patch_socket()

from guerrilla import Guerrilla

if __name__ == '__main__':
  radio = Guerrilla()

  guerrilla_server = StreamServer((Guerrilla.settings['STREAM_SERVER_IP'], Guerrilla.settings['STREAM_SERVER_PORT']), radio.guerrilla_handle)
  guerrilla_server.start()

  radio.read_meta()