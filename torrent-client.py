import bencodepy
import os
from urllib import request
from urllib import parse
import threading
import time
import hashlib
import struct
import socket
import bitstring
from random import choice
from string import digits
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters


def computeHash(info):
    return hashlib.sha1(info).digest()

def decodePeers(peers):
    peers = [peers[i:i + 6] for i in range(0, len(peers), 6)]
    return [(socket.inet_ntoa(p[:4]), struct.unpack('!H', (p[4:]))[0]) for p in peers]


def interested(bitfield, downloaded_pieces):
    for i in range(len(downloaded_pieces)):
        bit = bitfield[i] - downloaded_pieces[i]
        bitfield[i] = max(bit, 0)
    return sum(bitfield) > 0


def sendPieceNumb(peer_socket, index, length, begin=0):
    data = struct.pack('!BIII', 6, index, begin, length)
    data_s = struct.pack('!I', len(data)) + data
    peer_socket.sendall(data_s)


def connectTracker(dict_hash, peer_id):
    announce = torrent_dict[b'announce'].decode()
    if announce.startswith('http'):
        payload = {'info_hash': dict_hash, 'peer_id': peer_id,
                   'port': 6968, 'evented': 'started',
                   'uploaded': '0', 'downloaded': '0', 'left': str(full_length), 'compact': '1', 'numwant': '100'}

        full_url = f"{announce}?{parse.urlencode(payload)}"
        req = request.Request(full_url)
        req.method = "GET"
        if http_resp := request.urlopen(req):
            resp = http_resp.read()
            if b'failure reason' not in resp:
                answer_dict = bencodepy.decode(resp)
                return decodePeers(answer_dict[b'peers'])
            else:
                upd.message.reply_text("Error connecting to tracker")
        else:
            upd.message.reply_text("Can't connect to tracker")

    else:
        upd.message.reply_text("Can't connect to tracker")


def checkPartialTorrent():
    numb_pieces = len(pieces)
    piece_length = torrent_dict[b'info'][b'piece length']
    if os.path.exists(f"{saveDirectory}/{file}"):
        with open(f"{saveDirectory}/{file}", "r+b") as cur_file:
            for i in range(numb_pieces):
                cur_file.seek(i * piece_length)
                piece = cur_file.read(piece_length)
                if computeHash(piece) == pieces[i]:
                    downloaded_pieces[i] = 1


def sendRequest(bitfield, peer_socket, my_pieces):
    for i in range(len(bitfield)):
        if bitfield[i] == 1:
            try:
                pieces_lock.acquire()
                if downloaded_pieces[i] == 0:
                    downloaded_pieces[i] = 1
                    pieces_lock.release()
                    my_pieces[i] = b''
                    sendPieceNumb(peer_socket=peer_socket, index=i, length=16384)
                    break
                else:
                    pieces_lock.release()
            except:
                break


def writeBlockInFile(block, index, begin):
    new_bytes = len(block)
    begin = torrent_dict[b'info'][b'piece length'] * index
    with open(f"{saveDirectory}/{file}", "r+b") as cur_file:
        cur_file.seek(begin)
        cur_file.write(block)
    with lock:
        global downloaded_bytes
        downloaded_bytes += new_bytes


def unpackPiece(raw_data, my_pieces, peer_socket, bitfield):
    try:
        index, begin = struct.unpack('!II', raw_data[:8])
        block = raw_data[8:]
        my_pieces[index] += block
        prev_bytes = torrent_dict[b'info'][b'piece length'] * index
        global downloaded_bytes

        lock.acquire()

        if len(my_pieces[index]) == torrent_dict[b'info'][b'piece length'] or (
                (index == len(pieces) - 1 and prev_bytes + len(my_pieces[index]) == full_length)):
            lock.release()
            if computeHash(my_pieces[index]) == pieces[index]:
                writeBlockInFile(my_pieces[index], index, begin)
                if sum(downloaded_pieces) == len(pieces):
                    return True
                sendRequest(bitfield, peer_socket, my_pieces)
                return False
            else:
                with pieces_lock:
                    downloaded_pieces[index] = 0
                print("hash wasn't correct ")
                return True
        else:
            lock.release()

            if index == len(pieces) - 1 and prev_bytes + len(my_pieces[index]) + 16384 > full_length:
                last_piece_size = full_length - prev_bytes - len(my_pieces[index])
                if last_piece_size == 0: return False
                sendPieceNumb(peer_socket=peer_socket, index=index, length=last_piece_size,
                              begin=len(my_pieces[index]))
            else:
                sendPieceNumb(peer_socket=peer_socket, index=index, length=16384,
                              begin=len(my_pieces[index]))
            return False
    except:
        lock.release()
        return True


def processData(raw_data, bitfield, my_pieces, peer_socket):
    try:
        if struct.unpack('!B', raw_data[:1])[0] == 5:
            bitfield += map(lambda x: int(x), list(bitstring.BitArray(raw_data[1:]).bin))
            with pieces_lock:
                if interested(bitfield, downloaded_pieces):
                    data = struct.pack('!I', 1) + struct.pack('!B', 2)
                    peer_socket.sendall(data)
                else:
                    data = struct.pack('!I', 1) + struct.pack('!B', 3)
                    peer_socket.sendall(data)
                    return True

        if struct.unpack('!B', raw_data[:1])[0] == 4:
            piece_numb = struct.unpack('!I', raw_data[1:])[0]
            bitfield[piece_numb] = 1
            return False

        if struct.unpack('!B', raw_data[:1])[0] == 1:
            if bitfield:
                sendRequest(bitfield, peer_socket, my_pieces)
            return False

        if struct.unpack('!B', raw_data[:1])[0] == 0:
            return True

        if struct.unpack('!B', raw_data[:1])[0] == 7:
            return unpackPiece(raw_data[1:], my_pieces, peer_socket, bitfield)

        return False
    except:
        return True


def restoreInfo(my_pieces):
    for index, piece in my_pieces.items():
        if len(piece) < torrent_dict[b'info'][b'piece length']:
            try:
                pieces_lock.acquire()
                downloaded_pieces[index] = 0
            except:
                pass
            finally:
                pieces_lock.release()


def downloadData(peer_socket, peer):
    peer_socket.settimeout(5)
    bitfield = []
    my_pieces = {}

    try:
        while True:
            data = b''
            while len(data) < 4:
                new_data = peer_socket.recv(4 - len(data))
                if new_data == b'':
                    continue
                data += new_data
                peer_socket.settimeout(5)

            msg_length = struct.unpack('!I', data)[0]

            if msg_length == 0:
                continue
            data = b''
            while msg_length > 0:
                raw_data = peer_socket.recv(msg_length)
                if raw_data == b'':
                    break
                peer_socket.settimeout(5)
                data += raw_data
                msg_length -= len(raw_data)

            peer_socket.settimeout(None)
            if choked := processData(data, bitfield, my_pieces, peer_socket):
                if sum(downloaded_pieces) != len(pieces):
                    restoreInfo(my_pieces)

                break

    except (socket.timeout, OSError):
        restoreInfo(my_pieces)


def getHandshake(info_hash, id):
    protocol_name = b'BitTorrent protocol'
    data = struct.pack('!B', len(protocol_name))
    data += protocol_name
    data += struct.pack('!Q', 0)
    data += info_hash
    data += bytes(id, 'ascii')
    return data


def connectToPeer(peer):
    handshake = getHandshake(dict_hash, peerId)
    peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    global connected_peers
    try:
        peer_socket.connect(peer)
        peer_socket.sendall(handshake)
        peer_socket.settimeout(5)
        if interested := peer_socket.recv(len(handshake)):
            if dict_hash == struct.unpack('!20s', interested[28:48])[0]:
                with lock:
                    connected_peers.append(peer)

                peer_socket.settimeout(None)
                downloadData(peer_socket, peer)
            else:
                peer_socket.close()
    except (socket.timeout, OSError):
        text = f"Timeout of connecting to {str(peer)}"
        upd.message.reply_text(text)
    peer_socket.close()
    with lock:
        if peer in connected_peers:
            connected_peers.remove(peer)


def download():
    if sum(downloaded_pieces) == len(pieces):
        return
    upd.message.reply_text("\tConnecting to tracker")
    peers_ips = connectTracker(dict_hash, peerId)
    if len(peers_ips) > 0:
        upd.message.reply_text("\tConnecting to peers")
        global thread_i
        while True:
            try:
                lock.acquire()
                if thread_i < len(peers_ips) and len(connected_peers) < 10 and downloaded_bytes != full_length:
                    lock.release()
                    peer = peers_ips[thread_i]
                    text = f'Trying connect to {str(peer)}'
                    upd.message.reply_text(text)
                    threading.Thread(target=connectToPeer, args=(peer,), daemon=True).start()
                    thread_i += 1
                else:
                    lock.release()
                    if downloaded_bytes == full_length or thread_i == len(peers_ips):
                        upd.bot.send_document(document=open(file, 'rb'))
                        break
                time.sleep(5)
            except:
                upd.message.reply_text("Downloading stopped")
                break


def infoLogging():
    while True:
        time.sleep(logging_time)
        percent = (downloaded_bytes / full_length) * 100
        percent = min(percent, 100)
        text = '\n' + "\tDownloaded: " + str(int(downloaded_bytes / 1000)) + "KB" + "\tPeers: " + str(len(connected_peers)) + " " + str(connected_peers) + "\t" + str(round(percent, 2)) + "% was downloaded" + "\n"
        upd.message.reply_text(text)

def downloading(torrent_file, update, log_time):
    global logging_time
    logging_time = log_time
    global saveDirectory
    saveDirectory = os.getcwd()
    global torrent_dict
    global upd
    upd = update

    torrent_dict = bencodepy.decode_from_file(torrent_file)
    text = (
        f"Name: {str(torrent_dict[b'info'][b'name'])}"
        + "\nLength: "
        + str(torrent_dict[b'info'][b'length'])
        + "\nURL: "
        + str(torrent_dict[b'announce'])
    )
    update.message.reply_text(text)
    global dict_hash
    dict_hash = computeHash(bencodepy.encode(torrent_dict[b'info']))
    global peerId
    peerId = ''.join(choice(digits) for _ in range(20))
    global hashes
    hashes = torrent_dict[b'info'][b'pieces']

    global files
    global file
    files = []
    file = ()

    file = str(torrent_dict[b'info'][b'name'], 'utf-8')
    if not os.path.exists(f"{saveDirectory}/{file}"):
        open(f"{saveDirectory}/{file}", "w+b")

    global pieces
    pieces = [hashes[i:i + 20] for i in range(0, len(hashes), 20)]
    global downloaded_pieces
    downloaded_pieces = [0] * len(pieces)
    checkPartialTorrent()
    print(sum(downloaded_pieces), " / ", len(downloaded_pieces), " was downloaded")
    global full_length
    full_length = 0
    if b'length' in torrent_dict[b'info'].keys():
        full_length = torrent_dict[b'info'][b'length']
    else:
        for file in torrent_dict[b'info'][b'files']:
            full_length += file[b'length']
    global downloaded_bytes
    global lock
    global connected_peers
    global pieces_lock
    global thread_i
    downloaded_bytes = sum(downloaded_pieces) * torrent_dict[b'info'][b'piece length']
    connected_peers = []
    lock = threading.Lock()
    pieces_lock = threading.Lock()
    thread_i = 0
    threading.Thread(target=infoLogging, args=(), daemon=False).start()
    threading.Thread(target=download, daemon=False).start()

    return(file)
