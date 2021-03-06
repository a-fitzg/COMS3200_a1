import socket
import sys
import threading
import math
import time

PACKET_SIZE_RAW = 1500
PACKET_SIZE = 1472
PACKET_MAX_PAYLOAD_SIZE = 1464
RUSHB_VERSION = 2
CHECKSUM_WINDOW_SIZE = 2

ENC_N = 249
ENC_D = 15
ENC_E = 11

# Enum for packets from client - reserved for future use
CLIENT_UNSEEN = 0
CLIENT_ACK = 1
CLIENT_NAK = 2

thread_exit_flag = False


class RUSHBPacket:
    """
    Packet class for RUSHB packets.

    The constructor for this class can only be used to initialise a RUSHB
    packet from an incoming bytearray. If we want to create our own RUSHB
    packet, this class must be initialised with no arguments.
    """
    def __init__(self, packet_in=None):
        # RUSHB header variables
        self.seq_number = None
        self.ack_number = None
        self.checksum = None
        self.rushb_version = None

        # Flags
        self.f_ack = None
        self.f_nak = None
        self.f_get = None
        self.f_dat = None
        self.f_fin = None
        self.f_chk = None
        self.f_enc = None

        self.payload = None

        self.sent_time = None

        if packet_in is not None:
            self._decode_packet(packet_in)

    def _decode_packet(self, packet_in):
        # PRIVATE - Parse incoming packet
        self.seq_number = int.from_bytes(packet_in[0:2], "big")
        self.ack_number = int.from_bytes(packet_in[2:4], "big")
        self.checksum = int.from_bytes(packet_in[4:6], "big")
        row4 = int.from_bytes(packet_in[6:8], "big")

        # Bit masking for flags
        self.f_ack = not not (row4 & (1 << 15))
        self.f_nak = not not (row4 & (1 << 14))
        self.f_get = not not (row4 & (1 << 13))
        self.f_dat = not not (row4 & (1 << 12))
        self.f_fin = not not (row4 & (1 << 11))
        self.f_chk = not not (row4 & (1 << 10))
        self.f_enc = not not (row4 & (1 << 9))

        self.rushb_version = row4 & 0b111

        # The rest of the packet is data payload
        self.payload = packet_in[8:]

    def get_packet_bytes(self):
        # Return this packet as an encoded bytearray so we can send over a network connection
        seq_number = self.seq_number if self.seq_number is not None else 0
        ack_number = self.ack_number if self.ack_number is not None else 0
        checksum = self.checksum if self.checksum is not None else 0

        f_ack = self.f_ack if self.f_ack is not None else 0
        f_nak = self.f_nak if self.f_nak is not None else 0
        f_get = self.f_get if self.f_get is not None else 0
        f_dat = self.f_dat if self.f_dat is not None else 0
        f_fin = self.f_fin if self.f_fin is not None else 0
        f_chk = self.f_chk if self.f_chk is not None else 0
        f_enc = self.f_enc if self.f_enc is not None else 0

        rushb_version = self.rushb_version if self.rushb_version is not None else RUSHB_VERSION
        payload = self.payload if self.payload is not None else bytearray(PACKET_MAX_PAYLOAD_SIZE)

        special_row = (f_ack << 15) | (f_nak << 14) | (f_get << 13) | (f_dat << 12) | \
                      (f_fin << 11) | (f_chk << 10) | (f_enc << 9) | \
                      (rushb_version & 0b111)

        packet = bytearray()
        packet.extend(int.to_bytes(seq_number, 2, "big"))
        packet.extend(int.to_bytes(ack_number, 2, "big"))
        packet.extend(int.to_bytes(checksum, 2, "big"))
        packet.extend(int.to_bytes(special_row, 2, "big"))
        packet.extend(payload)

        return packet

    @staticmethod
    def _carry_add(a, b):
        sum_out = a + b
        return (sum_out & 0xFFFF) + (sum_out >> 16)

    def calculate_checksum(self):
        # Calculate if the checksum of this packet is valid or not
        payload = self.payload.rstrip(b'\0x00')
        num_windows = math.ceil(len(payload) / CHECKSUM_WINDOW_SIZE)
        cs_sum = 0
        for i in range(num_windows):
            start_window_index = i * CHECKSUM_WINDOW_SIZE
            stop_window_index = (i + 1) * CHECKSUM_WINDOW_SIZE
            cs_sum = self._carry_add(cs_sum, int.from_bytes(payload[start_window_index:stop_window_index], "little"))

        return ~cs_sum & 0xFFFF

    def get_decrypted_payload(self, n, d):
        message = bytearray()
        for i in self.payload:
            if i == 0:
                break
            value = (int(i) ** d) % n
            message.extend(int.to_bytes(value, 1, "big"))
        return message

    def get_encrypted_payload(self, n, e):
        encrypted = bytearray()
        for i in self.payload:
            if i == 0:
                break
            value = (int(i) ** e) % n
            encrypted.extend(int.to_bytes(value, 1, "big"))
        return encrypted

    def is_valid_checksum(self):
        return True if self.checksum == self.calculate_checksum() else False

    def get_seq_number(self):
        return self.seq_number

    def set_seq_number(self, seq_number):
        self.seq_number = seq_number

    def get_ack_number(self):
        return self.ack_number

    def set_ack_number(self, ack_number):
        self.ack_number = ack_number

    def get_checksum(self):
        return self.checksum

    def set_checksum(self, checksum):
        self.checksum = checksum

    def get_rushb_version(self):
        return self.rushb_version

    def set_rushb_version(self, rushb_version):
        self.rushb_version = rushb_version

    def get_f_ack(self):
        return self.f_ack

    def set_f_ack(self, f_ack):
        self.f_ack = f_ack

    def get_f_nak(self):
        return self.f_nak

    def set_f_nak(self, f_nak):
        self.f_nak = f_nak

    def get_f_get(self):
        return self.f_get

    def set_f_get(self, f_get):
        self.f_get = f_get

    def get_f_dat(self):
        return self.f_dat

    def set_f_dat(self, f_dat):
        self.f_dat = f_dat

    def get_f_fin(self):
        return self.f_fin

    def set_f_fin(self, f_fin):
        self.f_fin = f_fin

    def get_f_chk(self):
        return self.f_chk

    def set_f_chk(self, f_chk):
        self.f_chk = f_chk

    def get_f_enc(self):
        return self.f_enc

    def set_f_enc(self, f_enc):
        self.f_enc = f_enc

    def get_payload(self):
        return self.payload

    def set_payload(self, payload):
        self.payload = payload

    def get_sent_time(self):
        return self.sent_time

    def set_sent_time(self, sent_time):
        self.sent_time = sent_time


class ServerThread(threading.Thread):

    def __init__(self, first_packet_raw, server_socket, client_address):
        threading.Thread.__init__(self)
        self.first_packet_raw = first_packet_raw
        self.server_socket = server_socket
        self.client_address = client_address
        self.server_packets = list()
        self.client_packets = list()
        self.received_packets = list()
        self.sent_packets = list()

    def run(self):
        # Got here because we need to start communication with this client
        first_packet = RUSHBPacket(self.first_packet_raw)

        sequence_number = 1

        # Is this communication going to be encrypted / checksum'd?
        is_encrypting = False
        is_checking = False

        # Is this communication finished?
        is_finished = False

        # List of packets we need to send
        packets_to_send = list()

        if first_packet.f_enc is True:
            # Client has requested encryption
            is_encrypting = True
            # Decrypt the payload
            first_packet.set_payload(first_packet.get_decrypted_payload(ENC_N, ENC_D))

        if first_packet.f_chk is True:
            # Client has requested checksum
            is_checking = True
            first_packet_valid_chk = first_packet.is_valid_checksum()
            if first_packet_valid_chk:
                # We have a valid first packet
                self.received_packets.append(first_packet)
            else:
                while not first_packet_valid_chk:
                    # That was not a valid checksum. Ignore that packet and wait for a valid one
                    while len(self.received_packets) == 0:
                        # Just keep waiting until we get another packet in
                        pass
                    if self.received_packets[0].is_valid_checksum():
                        first_packet = self.received_packets[0]
                        first_packet_valid_chk = True
                        self.received_packets.append(first_packet)
                        break
                    time.sleep(0.001)

        if first_packet.f_get is True:
            # Client sent a GET request, we need to get them the file
            # First, find the file.
            file_data = None
            try:
                requested_file = open(first_packet.payload.decode("utf-8").rstrip('\0x00'), "r")
                file_data = requested_file.read()
                requested_file.close()
            except (IOError, UnicodeEncodeError, UnicodeDecodeError) as error:
                # Requested file doesn't exist, OR error in encoding
                # CLOSE CONNECTION
                is_finished = True

            # Now work out how we're going to send the message over.
            if not is_finished:
                # How many packets do we need to send the data across?
                num_packets = int(math.ceil(len(file_data) / PACKET_MAX_PAYLOAD_SIZE))

                for i in range(num_packets):
                    # Construct our packet(s) containing the message
                    packet_to_send = RUSHBPacket()
                    packet_to_send.set_seq_number(sequence_number)
                    packet_to_send.set_f_dat(True)

                    window_start_index = i * PACKET_MAX_PAYLOAD_SIZE
                    window_stop_index = (i + 1) * PACKET_MAX_PAYLOAD_SIZE

                    payload = bytearray(file_data[window_start_index:window_stop_index], "ascii")
                    if len(payload) < PACKET_MAX_PAYLOAD_SIZE:
                        # Pad byte array with null bytes
                        payload.extend(bytearray(PACKET_MAX_PAYLOAD_SIZE - len(payload)))
                    packet_to_send.set_payload(payload)

                    if is_checking:
                        packet_to_send.set_f_chk(True)
                        packet_to_send.set_checksum(packet_to_send.calculate_checksum())

                    if is_encrypting:
                        packet_to_send.set_f_enc(True)
                        packet_to_send.set_payload(packet_to_send.get_encrypted_payload(ENC_N, ENC_E))

                    packets_to_send.append(packet_to_send)

                    sequence_number += 1

                # We have all the packets we need to send the file over

                for packet in packets_to_send:
                    # Send over each file one at a time, wait for an ACK, then send the next
                    self.server_socket.sendto(packet.get_packet_bytes(), self.client_address)
                    packet.set_sent_time(time.time())

                    this_seq_num = packet.get_seq_number()

                    # Now wait for that packet's ACK
                    packet_acked = False
                    while not packet_acked:
                        # See if the packet's been ACK'ed
                        for rec_packet in self.received_packets:
                            if rec_packet.get_f_ack() and (rec_packet.get_ack_number() == this_seq_num):
                                # We got an ACK for this packet
                                if is_checking and (rec_packet.get_f_chk() is False):
                                    # Technically, this needs to be set if we're checking, so we have to ignore
                                    continue
                                if is_encrypting and (rec_packet.get_f_enc() is False):
                                    # This must be set if we're encrypting, so we must ignore this packet
                                    continue
                                packet_acked = True
                                break

                        # See if the packet's been NAK'ed
                        for rec_packet in self.received_packets:
                            if rec_packet.get_f_nak() and (rec_packet.get_ack_number() == this_seq_num):
                                if is_checking and (rec_packet.get_f_chk() is False):
                                    # Technically, this needs to be set if we're checking, so we have to ignore
                                    continue
                                if is_encrypting and (rec_packet.get_f_enc() is False):
                                    # Technically, this needs to be set if we're encrypting, so we have to ignore
                                    continue
                                # We got a NAK for this packet, we need to re-send it
                                self.server_socket.sendto(packet.get_packet_bytes(), self.client_address)
                                packet.set_sent_time(time.time())
                                self.received_packets.remove(rec_packet)
                                break

                        # Otherwise, we haven't heard back from them yet. We'll check on them 4 seconds after it was
                        # sent to send it again
                        if time.time() > (packet.get_sent_time() + 4):
                            # We've now waited 4 seconds for this packet to be ACK'ed, so we'll just send it again
                            self.server_socket.sendto(packet.get_packet_bytes(), self.client_address)
                            packet.set_sent_time(time.time())

                        time.sleep(0.001)

        # Now it's time to close connection
        # First, we send a FIN packet to the client
        fin_packet = RUSHBPacket()
        fin_packet.set_seq_number(sequence_number)
        sequence_number += 1
        if is_checking:
            fin_packet.set_f_chk(True)
            fin_packet.set_checksum(65535)
        if is_encrypting:
            fin_packet.set_f_enc(True)
        fin_packet.set_rushb_version(RUSHB_VERSION)

        fin_packet.set_f_fin(True)

        self.server_socket.sendto(fin_packet.get_packet_bytes(), self.client_address)

        # Sent that off, we need to wait for a FIN/ACK packet from the client
        fin_acknowledged = False
        fin_ack_num_client = 0
        while not fin_acknowledged:
            for packet in self.received_packets:
                if packet.get_f_ack() and packet.get_f_fin():
                    if is_checking and (packet.get_f_chk() is False):
                        # We must ignore this packet, it's not following the rules!
                        continue
                    if is_encrypting and (packet.get_f_enc() is False):
                        # Ignore, this packet is not following the rules
                        continue
                    # We are finally free!
                    fin_acknowledged = True
                    fin_ack_num_client = packet.get_seq_number()
            time.sleep(0.01)

        # Send off final FIN/ACK packet
        fin_ack_packet = RUSHBPacket()
        fin_ack_packet.set_seq_number(sequence_number)
        fin_ack_packet.set_ack_number(fin_ack_num_client)
        sequence_number += 1
        fin_ack_packet.set_rushb_version(RUSHB_VERSION)
        if is_checking:
            fin_ack_packet.set_f_chk(True)
            fin_ack_packet.set_checksum(65535)
        if is_encrypting:
            fin_ack_packet.set_f_enc(True)
        fin_ack_packet.set_f_fin(True)
        fin_ack_packet.set_f_ack(True)
        self.server_socket.sendto(fin_ack_packet.get_packet_bytes(), self.client_address)
        # Farewell connection
        return

    def incoming_packet(self, packet_bytes):
        self.received_packets.append(RUSHBPacket(packet_bytes))


def main(argv):
    # Socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # Bind
    server_socket.bind(('', 0))
    port = server_socket.getsockname()[1]

    server_threads = dict()
    active_clients = list()

    # Print port to stdout
    print(port)
    sys.stdout.flush()

    # "Listen" forever
    while 1:
        # According to the spec, the max length of the data section (payload +
        # data payload) is 1472 bytes. Spec says max 1500 bytes, but we will
        # only read 1472 of those, as the operating system deals with the
        # IP and UDP headers before it reaches the program
        client_message, client_address = server_socket.recvfrom(PACKET_SIZE)

        if client_address in active_clients:
            # Incoming message for existing client
            server_threads[client_address].incoming_packet(client_message)
            pass
        else:
            # Incoming packet from new client, establish new connection
            active_clients.append(client_address)

            server_thread = ServerThread(client_message, server_socket, client_address)
            server_threads[client_address] = server_thread
            server_thread.start()


if __name__ == "__main__":
    main(sys.argv)
