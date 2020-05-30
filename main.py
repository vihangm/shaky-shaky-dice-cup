import json
import math
import random
import zlib

from flask import Flask, render_template
from flask_sockets import Sockets


app = Flask(__name__)
sockets = Sockets(app)


class Node:
    def __init__(self):
        self.prev = None
        self.next = None

    def insert_before(self, other):
        if other is None:
            self.prev = self
            self.next = self
            return

        self.prev = other.prev
        self.next = other

        other.prev.next = self
        other.prev = self

    def insert_after(self, other):
        if other is None:
            self.prev = self
            self.next = self
            return

        self.prev = other
        self.next = other.next

        other.next.prev = self
        other.next = self

    def remove(self):
        if self.prev is self or self.next is self:
            return

        self.next.prev = self.prev
        self.prev.next = self.next


class SortedDoublyLinkedList:
    def __init__(self):
        self.min_node = None
        self.length = 0

    def insert(self, node):
        self.length += 1
        if self.min_node is None or node < self.min_node:
            node.insert_before(self.min_node)
            self.min_node = node
            return

        curr_node = self.min_node
        while node > curr_node:
            curr_node = curr_node.next
            if curr_node is self.min_node:
                break

        node.insert_before(curr_node)

    def remove(self, node):
        self.length -= 1
        if self.length == 0:
            self.min_node = None
            return

        if node is self.min_node:
            self.min_node = node.next
        node.remove()


    def names(self):
        names = []
        node = self.min_node
        while node is not None:
            names.append(node.name)
            node = node.next
            if node is self.min_node:
                break
        return names


class Player(Node):
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.name_crc = zlib.crc32(name.encode())
        Node.__init__(self)

    def __hash__(self):
        return self.client(1)

    def __lt__(self, other):
        return self.name_crc < other.name_crc

    def __le__(self, other):
        return self.name_crc <= other.name_crc

    def __gt__(self, other):
        return self.name_crc > other.name_crc

    def __ge__(self, other):
        return self.name_crc >= other.name_crc

    def __eq__(self, other):
        return self.client == other.client

    def __ne__(self, other):
        return self.client != other.client


class GameState:
    def __init__(self):
        self.current_player = None
        self.last_person_to_roll_dice = ''
        self.last_person_to_peek_at_dice = ''
        self.dice_roll_count = 0

        self.current_dice = (3, 1)
        self.ordered_players = SortedDoublyLinkedList()
        self.players_by_name = dict()
        self.players_by_client = dict()


    def roll_die(self, client):
        print('roll_die')
        if self.current_player is None or self.current_player.client != client:
            return False

        self.dice_roll_count += 1
        self.current_dice = (random.randrange(6) + 1, random.randrange(6) + 1)
        self.last_person_to_roll_dice = self.current_player.name
        return True


    def pass_left(self, client):
        print('pass_left')
        if self.current_player is None or self.current_player.client != client:
            return False

        self.current_player = self.current_player.prev
        return True


    def pass_right(self, client):
        print('pass_right')
        if self.current_player is None or self.current_player.client != client:
            return False

        self.current_player = self.current_player.next
        return True


    def add_player(self, client, name):
        print('add_player')
        if client in self.players_by_client:
            print('Player already exists (client check)')
            return False

        if name in self.players_by_name:
            print('Player already exists (name check)')
            return False

        player = Player(client, name)
        self.players_by_name[name] = player
        self.players_by_client[client] = player

        self.ordered_players.insert(player)
        if self.current_player is None:
            self.current_player = player
        return True


    def remove_player(self, player):
        print('remove_player')
        del self.players_by_name[player.name]
        del self.players_by_client[player.client]

        if self.current_player is player:
            self.current_player = player.next
        self.ordered_players.remove(player)
        if self.ordered_players.length == 0:
            self.current_player = None
        return True


    def update_active_clients(self, curr_client, ws_clients):
        print('update_active_clients')
        state_changed = False
        for client in list(self.players_by_client.keys()):
            if client != curr_client and client not in ws_clients:
                self.remove_player(self.players_by_client[client])
                state_changed = True
        return state_changed


    def summarize_state_for_client(self, client, peek_dice=False, reveal_dice=False):
        print('summarize_state_for_client')
        if self.current_player is None or self.current_player.client != client:
            peek_dice = False
            reveal_dice = False

        summary = {
            'players': self.ordered_players.names(),
            'current_player': self.current_player.name if self.current_player is not None else '',
            'last_person_to_roll_dice': self.last_person_to_roll_dice,
            'last_person_to_peek_at_dice': self.last_person_to_peek_at_dice,
            'player_name_for_client': self.players_by_client[client].name if client in self.players_by_client else '',
            'dice_roll_count': self.dice_roll_count,
        }

        if peek_dice or reveal_dice:
            summary['dice'] = self.current_dice
            self.last_person_to_peek_at_dice = self.players_by_client[client].name

        if reveal_dice:
            self.last_person_to_peek_at_dice = 'Everyone!'

        return summary


gs = GameState()


@sockets.route('/play')
def game_socket(ws):
    while not ws.closed:
        message = ws.receive()
        if message is None:
            continue

        parsed = json.loads(message)
        state_changed = False
        if parsed['method'] == 'set_name':
            state_changed = gs.add_player(ws.handler.client_address, parsed['name'])

        elif parsed['method'] == 'peek_dice':
            summary = gs.summarize_state_for_client(ws.handler.client_address, peek_dice=True)
            ws.handler.active_client.ws.send(json.dumps(summary))
            if summary['dice'] is not None:
                state_changed = True

        elif parsed['method'] == 'reveal_dice':
            summary = gs.summarize_state_for_client(ws.handler.client_address, reveal_dice=True)
            for client in ws.handler.server.clients.values():
                client.ws.send(json.dumps(summary))

        elif parsed['method'] == 'roll_dice':
            state_changed = gs.roll_die(ws.handler.client_address)

        elif parsed['method'] == 'pass_left':
            state_changed = gs.pass_left(ws.handler.client_address)

        elif parsed['method'] == 'pass_right':
            state_changed = gs.pass_right(ws.handler.client_address)

        if gs.update_active_clients(ws.handler.client_address, ws.handler.server.clients):
            state_changed = True

        if state_changed:
            for client_addr, client in ws.handler.server.clients.items():
                client.ws.send(json.dumps(gs.summarize_state_for_client(client_addr)))

@app.route('/')
def index():
    return render_template('index.html')


if __name__ == '__main__':
    print("""
[WARNING] This cannot be run directly. Use gunicorn instead:
gunicorn -b 127.0.0.1:8080 -k flask_sockets.worker main:app
""")
