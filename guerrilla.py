import gevent

from gevent.server import StreamServer
from gevent import monkey
monkey.patch_socket()
from gevent import socket

import requests
import json
import struct
import string
from datetime import datetime
from datetime import timedelta


class Guerrilla():
  settings = {
    'GUERRILLA_STREAM':      'http://live.eliberadio.ro:8010/eliberadio-32.aac',
    'LAST_FM_API_URL':       'http://ws.audioscrobbler.com/2.0/',
    'LAST_FM_API_KEY':       'a13c587d66811a4c262c79f411eb5472',
    'LAST_FM_TRACK_INFO':    'track.getInfo',
    'LAST_FM_ARTIST_INFO':   'artist.getinfo',
    'STREAM_SERVER_IP':      '192.168.27.100',
    'STREAM_SERVER_PORT':    1060
  }

  def __init__(self):
    self.clients = []
    self.current_response = None
    self.current_size = None

    self.songs = requests.get(
      Guerrilla.settings['GUERRILLA_STREAM'],
      stream=True,
      headers={'Icy-MetaData': '1'}
    )

    self.start_time = datetime.now()

  def read_meta(self):
    icy_metaint_header = self.songs.headers['icy-metaint'] if 'icy-metaint' in self.songs.headers else None

    if icy_metaint_header is not None:
      icy_metaint_header = int(icy_metaint_header)

      self.songs.raw.read(icy_metaint_header)

      while True:
        current_time = datetime.now()
        
        if current_time - self.start_time > timedelta(hours=3):
          self.start_time = current_time
          
          self.songs = requests.get(
            Guerrilla.settings['GUERRILLA_STREAM'],
            stream=True,
            headers={'Icy-MetaData': '1'}
          )
          
          self.songs.raw.read(icy_metaint_header)

        length_byte = ord(self.songs.raw.read(1))

        if length_byte > 0:
          title = self.songs.raw.read(length_byte * 16)
          
          if title:
            title = self.decode_meta(title)

            details = [x.strip() for x in title.split('\'')[1].split(' - ')]
            
            print 'Details: ', details, '\n'

            if details[0] == 'Guerrilla':
              response = None
            else:
              artwork  = self.get_artwork(details)
              response = self.prepare_response(details, artwork)
            
            if response:
              self.current_response = json.dumps(response)
              print 'Length: ', len(self.current_response)
              self.current_size = struct.pack('!4s', str(len(self.current_response)))
              
              print self.current_size
              print 'Response: ', self.current_size, self.current_response, '\n'
            else:
              self.current_response = None
              print 'Length: 0'
              self.current_size = struct.pack('!4s', str(0))

            self.guerrilla_broadcast(self.current_size)
            if self.current_response:
              self.guerrilla_broadcast(self.current_response)

        self.songs.raw.read(icy_metaint_header)


  def decode_meta(self, title):
    return filter(lambda x: x in string.printable, title)

  def get_artwork(self, details):
    last_fm = {
      'artist':      None,
      'song':        None,
      'album':       None,
      'artistImage': None,
      'albumImage':  None
    }

    params = {
      'api_key': Guerrilla.settings['LAST_FM_API_KEY'],
      'format':  'json',
      'method':  Guerrilla.settings['LAST_FM_ARTIST_INFO'],
      'artist':  details[0],
    }

    artist = requests.get(Guerrilla.settings['LAST_FM_API_URL'], params=params).json()
    artist = artist['artist']

    if 'name' in artist:
      last_fm['artist'] = artist['name']

    if 'image' in artist:
      for img in artist['image']:
        if 'size' in img and img['size'] == 'mega':
          last_fm['artistImage'] = img['#text']

    params = {
      'api_key': Guerrilla.settings['LAST_FM_API_KEY'],
      'format':  'json',
      'method':  Guerrilla.settings['LAST_FM_TRACK_INFO'],
      'artist':  details[0],
      'track':   details[1],
      'autocorrect': 0
    }

    track = requests.get(Guerrilla.settings['LAST_FM_API_URL'], params=params).json()
    
    if 'track' in track and track['track']:
      track = track['track']

    if 'name' in track:
      last_fm['song'] = track['name']

    if 'album' in track and 'title' in track['album']:
      last_fm['album'] = track['album']['title']

    if 'album' in track and 'image' in track['album']:
      for img in track['album']['image']:
        if 'size' in img and img['size'] == 'extralarge':
          last_fm['albumImage'] = img['#text']

    return last_fm

  def prepare_response(self, metadata, artwork):
    response = {
      'artist':       artwork['artist'] or metadata[0],
      'song':         artwork['song'] or metadata[1],
      'album':        artwork['album'],
      'artistImage':  artwork['artistImage'],
      'albumImage':   artwork['albumImage']
    }

    return response

  def guerrilla_handle(self, sock, addr):
    print 'Client: ', addr, '\n'
    self.clients.append((sock, addr))
    
    sock.send(self.current_size)
    if self.current_response:
      sock.send(self.current_response)

  def guerrilla_broadcast(self, message):
    current_clients = []

    for client in self.clients:
      try:
        sock, addr = client
        print 'Brodcasting to: ', addr
        sock.send(message)
      except socket.error:
        print 'Removed: ', client
        current_clients.append(client)
      finally:
        pass

    self.clients = [item for item in self.clients if item not in current_clients]