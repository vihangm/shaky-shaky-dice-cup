import json
import random
import zlib

from flask import Flask, render_template
from flask_sockets import Sockets


app = Flask(__name__)
sockets = Sockets(app)


class Player:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.name_crc = zlib.crc32(name.encode())

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
        self.current_player_idx = 0
        self.last_person_to_roll_dice = ''
        self.last_person_to_peek_at_dice = ''
        self.dice_roll_count = 0

        self.current_dice = (3, 1)
        self.ordered_players = list()
        self.players_by_name = dict()
        self.players_by_client = dict()


    def roll_die(self, client):
        print('roll_die')
        if self.ordered_players[self.current_player_idx].client != client:
            return False

        self.dice_roll_count += 1
        self.current_dice = (random.randrange(6) + 1, random.randrange(6) + 1)
        self.last_person_to_roll_dice = self.players_by_client[client].name
        return True


    def pass_left(self, client):
        print('pass_left')
        if self.ordered_players[self.current_player_idx].client != client:
            return False

        self.current_player_idx -= 1
        if self.current_player_idx < 0:
            self.current_player_idx += len(self.ordered_players)
        return True


    def pass_right(self, client):
        print('pass_right')
        if self.ordered_players[self.current_player_idx].client != client:
            return False

        self.current_player_idx += 1
        if self.current_player_idx >= len(self.ordered_players):
            self.current_player_idx -= len(self.ordered_players)
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

        self.ordered_players.append(player)
        # sorting would need us to track current player
        # self.ordered_players.sort()
        return True


    def remove_player(self, player):
        print('remove_player')
        if player not in self.ordered_players:
            print('No such player')
            return False

        del self.players_by_name[player.name]
        del self.players_by_client[player.client]

        self.ordered_players.remove(player)
        if self.current_player_idx > len(self.ordered_players):
            self.current_player_idx = 0
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
        if self.ordered_players[self.current_player_idx].client != client:
            peek_dice = False
            reveal_dice = False

        current_player = ''
        if self.current_player_idx < len(self.ordered_players):
            current_player = self.ordered_players[self.current_player_idx].name

        client_name = ''
        if client in self.players_by_client:
            client_name = self.players_by_client[client].name

        summary = {
            'players': [player.name for player in self.ordered_players],
            'current_player': current_player,
            'last_person_to_roll_dice': self.last_person_to_roll_dice,
            'last_person_to_peek_at_dice': self.last_person_to_peek_at_dice,
            'player_name_for_client': client_name,
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
