import random

import pygame
import threading
import socket
import pickle
import time

import sys
import os

def resource_path(relative_path):
    """ Get absolute path to resource, works for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# Initializing Pygame
pygame.init()

# Constants
WIDTH, HEIGHT = 900, 600
CELL_SIZE = 30
MARGIN = 50
FONT = pygame.font.SysFont('arial', 24)
BIG_FONT = pygame.font.SysFont('Comic Sans', 50)
SMALL_FONT = pygame.font.SysFont('arial', 20)

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BLUE = (64, 164, 223)
RED = (255, 0, 0)
GRAY = (200, 200, 200)
GREEN = (0, 255, 0)
YELLOW = (255, 255, 0)
TRANSPARENT_GREEN = (0, 255, 0, 100)
TRANSPARENT_RED = (255, 0, 0, 100)

# Network settings
TCP_PORT = 5005
UDP_PORT = 5006
BROADCAST_IP = '255.255.255.255'


class BattleshipGame:
    def __init__(self):
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Battleship")
        self.clock = pygame.time.Clock()

        # Player variables
        self.player_name = ''
        self.enemy_name = ''
        self.role = None  # 'host' or 'client'
        self.running = True
        self.connected = False

        # Player's fields
        self.own_grid = [[0] * 10 for _ in range(10)]  # Your field
        self.enemy_grid = [[0] * 10 for _ in range(10)]  # Enemy's field (known information)
        self.fire = ['fire.png']

        # Player's ships
        self.ships = ['Pi',
                      'solo.png',  # Single ship textures
                      'front.png',  # Front of ship textures
                      'middle.png',  # Middle of ship textures
                      'back.png']  # Back of ship textures
        self.index_ships = [[1],
                            [2],
                            [3],
                            [4]]

        self.index_defeat = 100  # A value exceeding this indicates a hit on the ship
        self.all_ships_placed = False
        self.ships_to_place = [4, 3, 3, 2, 2, 2, 1, 1, 1,
                               1]  # Ship sizes to place; default - [4, 3, 3, 2, 2, 2, 1, 1, 1, 1]
        self.placed_ships = []  # List of placed ships
        self.selected_ship_size = None  # Currently selected ship size for placement
        self.ship_orientation = 'horizontal'
        self.menu_phase = True
        self.place_ships_phase = False
        self.game_phase = False
        self.ready = False
        self.enemy_ready = False
        self.both_ready = False  # New variable to track readiness of both players
        self.effect_playing = False
        self.stop_animations = False
        self.safe_turn = False  # Temporary fix for safe turn (without bugs)
        self.turn = True
        self.game_over = False

        # Network connection
        self.conn = None
        self.scan_thread = None
        self.server_socket = None
        self.broadcasting = False
        self.accepting_connections = False
        self.scanning = False
        self.found_games = {}
        self.game_last_seen = {}

    def main_menu(self):
        # Name input window (if name is not set yet)
        if not self.player_name:
            self.player_name = self.input_name()

            if not self.player_name:
                self.running = False
                return

        # Select game mode
        self.select_role()

    def select_role(self):
        self.role = self.choose_role()

        if not self.role:
            return

        # Establish connection
        if self.role == 'host':
            self.start_host()
        else:
            self.join_game()

        if not self.connected:
            return

        self.turn = self.role == 'host'  # Host starts first

        self.menu_phase = False
        self.place_ships_phase = True

    def input_name(self):
        name = ''
        input_active = True
        max_length = 16  # Maximum name length

        while input_active:
            self.clock.tick(60)
            self.screen.fill(WHITE)
            prompt = FONT.render('Enter your name and press Enter:', True, BLACK)
            name_text = FONT.render(name, True, BLACK)

            self.screen.blit(prompt, (WIDTH // 2 - prompt.get_width() // 2, HEIGHT // 2 - 50))
            self.screen.blit(name_text, (WIDTH // 2 - name_text.get_width() // 2, HEIGHT // 2))

            name_game = BIG_FONT.render('Battleship Game', True, BLACK)

            self.screen.blit(name_game, (WIDTH // 2 - name_game.get_width() // 2, 50))
            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    return None
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        input_active = False
                        break
                    elif event.key == pygame.K_BACKSPACE:
                        name = name[:-1]
                    elif len(name) < max_length:
                        name += event.unicode
        return name.strip()

    def choose_role(self):
        role = None

        while role is None and self.running:
            self.clock.tick(60)

            host_button = pygame.Rect(WIDTH // 2 - 100, HEIGHT // 2 - 40, 200, 50)
            client_button = pygame.Rect(WIDTH // 2 - 100, HEIGHT // 2 + 20, 200, 50)
            return_button = pygame.Rect(WIDTH // 2 - 100, HEIGHT - 100, 200, 50)

            self.draw_menu(host_button, client_button, return_button)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    break
                if event.type == pygame.MOUSEBUTTONDOWN:
                    x, y = event.pos

                    if host_button.collidepoint(x, y):
                        role = 'host'
                    elif client_button.collidepoint(x, y):
                        role = 'client'
                    elif return_button.collidepoint(x, y):
                        self.player_name = ''
                        return None

        return role

    def draw_menu(self, host_button, client_button, return_button):
        self.screen.fill(WHITE)
        prompt = FONT.render('Choose game mode:', True, BLACK)

        pygame.draw.rect(self.screen, BLUE, host_button)
        pygame.draw.rect(self.screen, GREEN, client_button)
        pygame.draw.rect(self.screen, GRAY, return_button)

        host_text = FONT.render('Create game', True, WHITE)
        client_text = FONT.render('Join game', True, WHITE)
        return_text = FONT.render('Back', True, WHITE)

        self.screen.blit(prompt, (WIDTH // 2 - prompt.get_width() // 2, HEIGHT // 2 - 100))
        self.screen.blit(host_text, (host_button.centerx - host_text.get_width() // 2,
                                     host_button.centery - host_text.get_height() // 2))
        self.screen.blit(client_text, (client_button.centerx - client_text.get_width() // 2,
                                       client_button.centery - client_text.get_height() // 2))
        self.screen.blit(return_text, (return_button.centerx - return_text.get_width() // 2,
                                       return_button.centery - return_text.get_height() // 2))

        pygame.display.flip()

    def start_host(self):
        # Create server and start broadcasting
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('', TCP_PORT))
        self.server_socket.listen(1)

        self.broadcasting = True
        self.accepting_connections = True

        threading.Thread(target=self.accept_connection, daemon=True).start()
        threading.Thread(target=self.broadcast_game, daemon=True).start()

        # Waiting for client to connect
        waiting = True
        back_button = pygame.Rect(WIDTH // 2 - 50, HEIGHT // 2 + 220, 100, 40)  # "Back" button

        while waiting and self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    waiting = False
                    return
                if event.type == pygame.MOUSEBUTTONDOWN:
                    x, y = event.pos

                    if back_button.collidepoint(x, y):
                        # Handling the "Back" button press
                        self.broadcasting = False  # Stop broadcasting
                        self.accepting_connections = False  # Stop accepting connections

                        if self.server_socket:
                            self.server_socket.close()  # Close server socket

                        self.connected = False  # Reset connection state

                        return

            self.clock.tick(60)

            self.screen.fill(WHITE)
            prompt = FONT.render('Waiting for player to connect...', True, BLACK)
            self.screen.blit(prompt, (WIDTH // 2 - prompt.get_width() // 2, HEIGHT // 2 - 40))

            # Displaying "Back" button
            pygame.draw.rect(self.screen, GRAY, back_button)
            back_text = SMALL_FONT.render('Back', True, WHITE)
            self.screen.blit(back_text, (
                back_button.centerx - back_text.get_width() // 2, back_button.centery - back_text.get_height() // 2))

            pygame.display.flip()

            if self.connected:
                waiting = False

    def accept_connection(self):
        while self.accepting_connections:
            try:
                self.conn, addr = self.server_socket.accept()
                self.connected = True
                # Receiving enemy's name
                data = self.conn.recv(1024)
                self.enemy_name = data.decode()
                # Sending your name
                self.conn.sendall(self.player_name.encode())

                break  # Exit loop after connection
            except Exception as e:
                if not self.accepting_connections:
                    break

    def broadcast_game(self):
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        message = f"BattleshipGame:{self.player_name}"

        while not self.connected and self.broadcasting:
            try:
                udp_socket.sendto(message.encode(), (BROADCAST_IP, UDP_PORT))
                time.sleep(1)
            except Exception as e:
                break
        udp_socket.close()

    def join_game(self):
        # Clear previous game listings
        self.found_games = {}
        self.scanning = True

        # Start scanning for games in a separate thread
        if not hasattr(self, 'scan_thread') or self.scan_thread is None or not self.scan_thread.is_alive():
            self.scan_thread = threading.Thread(target=self.scan_for_games, daemon=True)
            self.scan_thread.start()

        selected_game = self.select_game()
        if not selected_game:
            # If nothing is selected or "Back" is clicked, return to role selection
            self.scanning = False
            return

        # Establish connection to selected game
        self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        retries = 3

        while retries > 0 and not self.connected:
            try:
                self.conn.connect((selected_game['ip'], TCP_PORT))
                self.connected = True
                self.conn.sendall(self.player_name.encode())
                data = self.conn.recv(1024)
                self.enemy_name = data.decode()
            except Exception as e:
                retries -= 1
                time.sleep(2)

    def scan_for_games(self):
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        udp_socket.settimeout(2)
        udp_socket.bind(('', UDP_PORT))

        game_timeout = 2  # Seconds until a game is considered unavailable
        self.game_last_seen = {}  # Track last time each game was seen

        while self.scanning:
            current_time = time.time()

            try:
                data, addr = udp_socket.recvfrom(1024)
                message = data.decode()

                if message.startswith('BattleshipGame:'):
                    game_name = message.split(':')[1]
                    self.found_games[addr[0]] = {'name': game_name, 'ip': addr[0]}
                    self.game_last_seen[addr[0]] = current_time  # Update last seen time
            except socket.timeout:
                pass

            # Remove games that haven't broadcasted recently
            to_remove = [ip for ip, last_seen in self.game_last_seen.items() if current_time - last_seen > game_timeout]

            for ip in to_remove:
                if ip in self.found_games:
                    del self.found_games[ip]
                del self.game_last_seen[ip]

        udp_socket.close()

    def select_game(self):
        selected = None
        back_button = pygame.Rect(WIDTH // 2 - 50, HEIGHT // 2 + 220, 100, 40)  # "Back" button

        while selected is None and self.running:
            self.clock.tick(60)
            self.screen.fill(WHITE)
            prompt = FONT.render('Select a game to join:', True, BLACK)
            self.screen.blit(prompt, (WIDTH // 2 - prompt.get_width() // 2, 50))

            # "Back" button
            pygame.draw.rect(self.screen, GRAY, back_button)
            back_text = SMALL_FONT.render('Back', True, WHITE)
            self.screen.blit(back_text, (
                back_button.centerx - back_text.get_width() // 2, back_button.centery - back_text.get_height() // 2))

            # Display list of found games
            games = list(self.found_games.values())

            for idx, game in enumerate(games):
                game_button = pygame.Rect(WIDTH // 2 - 250, 100 + idx * 60, 500, 50)
                pygame.draw.rect(self.screen, BLUE, game_button)
                game_text = FONT.render(f"{game['name']} ({game['ip']})", True, WHITE)
                self.screen.blit(game_text, (
                    game_button.centerx - game_text.get_width() // 2,
                    game_button.centery - game_text.get_height() // 2))

                game['button'] = game_button

            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    self.scanning = False
                    return None
                if event.type == pygame.MOUSEBUTTONDOWN:
                    x, y = event.pos

                    if back_button.collidepoint(x, y):
                        self.scanning = False
                        return None
                    for game in games:
                        if game['button'].collidepoint(x, y) and time.time() - self.game_last_seen[game['ip']] < 3:
                            self.scanning = False
                            return game

        return None

    def show_message(self, message):
        showing = True

        while showing:
            self.clock.tick(60)
            self.screen.fill(WHITE)
            prompt = FONT.render(message, True, BLACK)
            self.screen.blit(prompt, (WIDTH // 2 - prompt.get_width() // 2, HEIGHT // 2))
            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    showing = False
                    return
                if event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN:
                    showing = False
                    return

    def place_ships(self):
        placing = True
        selected_ship = None
        self.all_ships_placed = False
        self.ready = False
        threading.Thread(target=self.receive_data, daemon=True).start()

        ready_button = pygame.Rect(WIDTH - 150, HEIGHT - 60, 100, 40)
        while placing and self.running and self.place_ships_phase:
            self.clock.tick(60)

            mouse_pos = pygame.mouse.get_pos()
            grid_x = (mouse_pos[0] - MARGIN) // CELL_SIZE
            grid_y = (mouse_pos[1] - MARGIN) // CELL_SIZE

            self.draw_place_ships(selected_ship, ready_button, grid_x, grid_y)

            ship_under_cursor = None
            if 0 <= grid_x < 10 and 0 <= grid_y < 10:
                ship_under_cursor = self.get_ship_at_position(grid_x, grid_y)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    self.send_data(('disconnect',))
                    placing = False
                    return
                if event.type == pygame.KEYDOWN and not self.ready:
                    if event.key == pygame.K_r:
                        self.ship_orientation = 'vertical' if self.ship_orientation == 'horizontal' else 'horizontal'
                    if event.key == pygame.K_DELETE and ship_under_cursor:
                        # Remove ship if the cursor is over it and Delete is pressed
                        self.remove_ship(ship_under_cursor)
                        ship_under_cursor = None
                        self.all_ships_placed = False  # After removing a ship, all ships are not placed
                if event.type == pygame.MOUSEBUTTONDOWN:
                    x, y = event.pos
                    # Check ship buttons
                    for ship_button in self.ship_buttons:
                        if ship_button['rect'].collidepoint(x, y):
                            selected_ship = ship_button['size']
                    # Check "Ready" button
                    if ready_button.collidepoint(x, y) and self.all_ships_placed:
                        self.ready = True
                        self.send_data(('ready',))
                        # We are ready, waiting for the enemy

                    # Place ship on the field
                    grid_x = (x - MARGIN) // CELL_SIZE
                    grid_y = (y - MARGIN) // CELL_SIZE

                    if selected_ship and 0 <= grid_x < 10 and 0 <= grid_y < 10:
                        if self.can_place_ship(grid_x, grid_y, selected_ship, self.ship_orientation):
                            self.place_ship(grid_x, grid_y, selected_ship, self.ship_orientation)
                            self.ships_to_place.remove(selected_ship)
                            selected_ship = None
                            if not self.ships_to_place:
                                self.all_ships_placed = True
                if not self.running:
                    break

            # Check if both players are ready
            if self.ready:
                if self.enemy_ready:
                    self.both_ready = True

            if self.both_ready:
                placing = False  # Exit the ship placement loop

        self.place_ships_phase = False

        if self.both_ready:
            self.game_phase = True
        else:
            self.menu_phase = True

    def draw_place_ships(self, selected_ship, ready_button, grid_x, grid_y):
        self.screen.fill(WHITE)
        self.draw_grid(self.own_grid, MARGIN, MARGIN)
        self.draw_ship_selection()

        prompt = FONT.render('Place your ships', True, BLACK)
        self.screen.blit(prompt, (WIDTH // 2 - 400, 10))

        prompt = FONT.render('Ship list:', True, BLACK)
        self.screen.blit(prompt, (WIDTH // 2 + 110, 10))

        # Adding instructions for ship deletion
        instruction_text1 = SMALL_FONT.render('Hints:', True, BLACK)
        self.screen.blit(instruction_text1, (MARGIN, HEIGHT - 200))

        instruction_text2 = SMALL_FONT.render('1) To rotate a ship - press R', True, BLACK)
        self.screen.blit(instruction_text2, (MARGIN, HEIGHT - 175))

        instruction_text3 = SMALL_FONT.render('2) To delete a ship - hover over it and press Delete', True, BLACK)
        self.screen.blit(instruction_text3, (MARGIN, HEIGHT - 150))

        instruction_text4 = SMALL_FONT.render(
            '3) After clicking "Ready", you will not be able to change ship placement ', True, BLACK)
        self.screen.blit(instruction_text4, (MARGIN, HEIGHT - 125))

        name_player = SMALL_FONT.render(
            f'Your name: {self.player_name}', True, BLACK)
        self.screen.blit(name_player, (MARGIN, HEIGHT - 75))

        enemy_player = SMALL_FONT.render(
            f'Enemy name: {self.enemy_name}', True, BLACK)
        self.screen.blit(enemy_player, (MARGIN, HEIGHT - 50))

        # "Ready" button - moved out to avoid bug

        if not self.ready:
            ready_color = GREEN if self.all_ships_placed else GRAY
            pygame.draw.rect(self.screen, ready_color, ready_button)
            ready_text = SMALL_FONT.render('Ready', True, WHITE)
            self.screen.blit(ready_text, (
                ready_button.centerx - ready_text.get_width() // 2,
                ready_button.centery - ready_text.get_height() // 2))

        if selected_ship and 0 <= grid_x < 10 and 0 <= grid_y < 10:
            can_place = self.can_place_ship(grid_x, grid_y, selected_ship, self.ship_orientation)
            color = GREEN if can_place else RED
            self.draw_ship_preview(grid_x, grid_y, selected_ship, self.ship_orientation, color)

        # If we clicked "Ready" and are waiting for the enemy, show message
        if self.ready and not self.both_ready:
            waiting_text = FONT.render('Waiting for the enemy to be ready...', True, BLACK)
            self.screen.blit(waiting_text, (WIDTH // 2 + 5, HEIGHT // 2 - 120))

        pygame.display.flip()

    def draw_ship_selection(self):
        # Display available ships for placement
        self.ship_buttons = []
        selection_colors = [(139, 0, 0), (255, 69, 0), (255, 215, 0), (0, 100, 0), (0, 139, 139)]
        start_x = WIDTH - 370
        start_y = MARGIN

        for idx, ship_size in enumerate(sorted(set(self.ships_to_place), reverse=True)):
            count = self.ships_to_place.count(ship_size)
            if count > 0:
                ship_rect = pygame.Rect(start_x, start_y + idx * 60, 150, 50)
                pygame.draw.rect(self.screen, selection_colors[(idx % len(selection_colors))], ship_rect)
                ship_text = SMALL_FONT.render(f'Ship {ship_size} ({count})', True, WHITE)
                self.screen.blit(ship_text, (
                    ship_rect.centerx - ship_text.get_width() // 2, ship_rect.centery - ship_text.get_height() // 2))
                self.ship_buttons.append({'rect': ship_rect, 'size': ship_size})

    def can_place_ship(self, x, y, size, orientation):
        # Check for placement out of bounds
        if (orientation == 'horizontal' and x + size > 10) or (orientation == 'vertical' and y + size > 10):
            return False

        # Check for overlap and adjacent cells
        for i in range(size):
            current_x = x + i if orientation == 'horizontal' else x
            current_y = y if orientation == 'horizontal' else y + i

            # Check the cell itself
            if self.own_grid[current_y][current_x] != 0:
                return False

            # Check surrounding cells (including diagonals)
            for adj_y in range(max(0, current_y - 1), min(10, current_y + 2)):
                for adj_x in range(max(0, current_x - 1), min(10, current_x + 2)):
                    if self.own_grid[adj_y][adj_x] != 0:
                        return False

        return True

    def find_blocking_ship(self, x, y, size, orientation):
        blocking_positions = []
        for i in range(size):
            current_x = x + i if orientation == 'horizontal' else x
            current_y = y if orientation == 'horizontal' else y + i

            # Check surrounding cells for ships
            for adj_y in range(max(0, current_y - 1), min(10, current_y + 2)):
                for adj_x in range(max(0, current_x - 1), min(10, current_x + 2)):
                    if self.own_grid[adj_y][adj_x] != 0 and (adj_x, adj_y) not in blocking_positions:
                        blocking_positions.append((adj_x, adj_y))
        return blocking_positions

    def place_ship(self, x, y, size, orientation):
        positions = []
        if orientation == 'horizontal':
            for i in range(size):
                if i == 0:
                    self.own_grid[y][x + i] = self.index_ships[1][random.randint(0, len(self.index_ships[1]) - 1)]

                    if size == 1:
                        self.own_grid[y][x + i] = self.index_ships[0][random.randint(0, len(self.index_ships[0]) - 1)]
                elif i == size - 1:
                    self.own_grid[y][x + i] = self.index_ships[3][random.randint(0, len(self.index_ships[3]) - 1)]
                else:
                    self.own_grid[y][x + i] = self.index_ships[2][random.randint(0, len(self.index_ships[2]) - 1)]
                positions.append((x + i, y))
        else:
            for i in range(size):
                if i == 0:
                    self.own_grid[y + i][x] = self.index_ships[1][random.randint(0, len(self.index_ships[1]) - 1)]

                    if size == 1:
                        self.own_grid[y + i][x] = self.index_ships[0][random.randint(0, len(self.index_ships[0]) - 1)]
                elif i == size - 1:
                    self.own_grid[y + i][x] = self.index_ships[3][random.randint(0, len(self.index_ships[3]) - 1)]
                else:
                    self.own_grid[y + i][x] = self.index_ships[2][random.randint(0, len(self.index_ships[2]) - 1)]

                self.own_grid[y + i][x] = -1 * self.own_grid[y + i][x]
                positions.append((x, y + i))
        self.placed_ships.append({'positions': positions, 'size': size, 'orientation': orientation})

    def draw_ship_preview(self, x, y, size, orientation, color):
        blocking_positions = self.find_blocking_ship(x, y, size, orientation)

        # Highlight the blocking ships in purple
        for bx, by in blocking_positions:
            rect = pygame.Rect(MARGIN + bx * CELL_SIZE, MARGIN + by * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            pygame.draw.rect(self.screen, (128, 0, 128), rect, 2)  # Purple color

        # Highlight the ship being placed
        for i in range(size):
            current_x = x + i if orientation == 'horizontal' else x
            current_y = y if orientation == 'horizontal' else y + i
            rect = pygame.Rect(MARGIN + current_x * CELL_SIZE, MARGIN + current_y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            pygame.draw.rect(self.screen, color, rect, 2)

    def show_ship_destroy_effect(self, ship_positions, offset_x, offset_y, animate=True):
        # Check if animations should be stopped
        if self.stop_animations:
            return

        # Set a flag to indicate an effect is being played
        self.effect_playing = True

        # Immediately mark the surrounding cells as gray
        self.mark_adjacent_cells(ship_positions, self.own_grid if offset_x == MARGIN else self.enemy_grid,
                                 True if offset_x == MARGIN else False)
        pygame.display.flip()

        if animate:
            colors = [YELLOW, RED]  # Colors to alternate between
            for _ in range(4):  # Increase the loop to make the effect last longer
                # Check if animations should be stopped (additional)
                if self.stop_animations:
                    return
                for color in colors:
                    for (x, y) in ship_positions:
                        rect = pygame.Rect(offset_x + x * CELL_SIZE, offset_y + y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
                        pygame.draw.rect(self.screen, color, rect)  # Draw with the current color

                    pygame.display.flip()
                    pygame.time.delay(200)  # Delay to create a flashing effect

        # Reset the flag after the effect is complete
        self.effect_playing = False

    def mark_adjacent_cells(self, ship_positions, grid, flag_own=False):
        for (x, y) in ship_positions:
            for adj_y in range(max(0, y - 1), min(10, y + 2)):
                for adj_x in range(max(0, x - 1), min(10, x + 2)):
                    if grid[adj_y][adj_x] == 0:  # Only mark cells that haven't been shot at
                        grid[adj_y][adj_x] = 3  # Mark as gray

                        if flag_own:
                            grid[adj_y][adj_x] = len(self.ships) + self.index_defeat + 1

    def check_ship_destroyed(self, grid, x, y):
        # Find the ship associated with the hit cell
        for ship in self.placed_ships:
            if (x, y) in ship['positions']:
                # Check if all positions of the ship have been hit
                if all(abs(grid[pos_y][pos_x]) > self.index_defeat for (pos_x, pos_y) in ship['positions']):
                    return ship['positions']
        return None

    def get_ship_at_position(self, x, y):
        for ship in self.placed_ships:
            if (x, y) in ship['positions']:
                return ship
        return None

    def remove_ship(self, ship):
        for x, y in ship['positions']:
            self.own_grid[y][x] = 0
        self.placed_ships.remove(ship)
        self.ships_to_place.append(ship['size'])
        self.ready = False

    def game_loop(self):
        self.game_over = False

        while self.running:
            self.clock.tick(60)
            if not self.connected:
                self.game_over = True
                self.send_data(('disconnect',))
            if self.game_over:
                break
            self.handle_events()
            self.draw()

        if not self.running:
            return
        else:
            self.game_phase = False

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                self.send_data(('disconnect',))
                break
            if event.type == pygame.MOUSEBUTTONDOWN and self.turn and self.safe_turn and not self.game_over:
                x, y = pygame.mouse.get_pos()
                grid_x = (x - MARGIN - 350) // CELL_SIZE
                grid_y = (y - MARGIN) // CELL_SIZE

                if 0 <= grid_x < 10 and 0 <= grid_y < 10:
                    if self.enemy_grid[grid_y][grid_x] == 0:
                        # Send move coordinates to the opponent
                        self.send_data(('move', grid_x, grid_y))
                        self.clock.tick(10)

    def draw(self):
        if self.effect_playing:
            return  # Skip drawing if an effect is being played

        self.screen.fill(WHITE)
        # Draw own ships
        self.draw_grid(self.own_grid, MARGIN, MARGIN)
        # Draw enemy field
        self.draw_grid(self.enemy_grid, MARGIN + 350, MARGIN, hide_ships=True)
        # Display player names
        own_name_text = FONT.render(f"You: {self.player_name}", True, BLACK)
        enemy_name_text = FONT.render(f"Enemy: {self.enemy_name}", True, BLACK)
        self.screen.blit(own_name_text, (MARGIN, MARGIN - 30))
        self.screen.blit(enemy_name_text, (MARGIN + 350, MARGIN - 30))
        # Display turn information

        if self.turn:
            self.safe_turn = True
            text = "Your turn"
        else:
            self.safe_turn = False
            text = "..."

        turn_text = FONT.render(text, True, BLACK)
        self.screen.blit(turn_text, (WIDTH // 2 - turn_text.get_width() // 2, HEIGHT - 40))
        pygame.display.flip()

    def draw_grid(self, grid, offset_x, offset_y, hide_ships=False):
        # Fill the field with blue color (water color)
        pygame.draw.rect(self.screen, BLUE, (offset_x, offset_y, CELL_SIZE * 10, CELL_SIZE * 10))

        for y in range(10):
            for x in range(10):
                mark_text = SMALL_FONT.render(chr(x + ord('A')), True, BLACK)
                self.screen.blit(mark_text, (offset_x + x * CELL_SIZE + CELL_SIZE // 2 - mark_text.get_width() // 2,
                                             offset_y - mark_text.get_height() - 5 + CELL_SIZE * 11))

                rect = pygame.Rect(offset_x + x * CELL_SIZE, offset_y + y * CELL_SIZE, CELL_SIZE, CELL_SIZE)

                if hide_ships:
                    if grid[y][x] == 2:
                        pygame.draw.rect(self.screen, RED, rect)
                    elif grid[y][x] == 3:
                        pygame.draw.rect(self.screen, GRAY, rect)
                else:
                    if grid[y][x] == len(self.ships) + self.index_defeat + 1:
                        pygame.draw.rect(self.screen, GRAY, rect)
                    elif grid[y][x] != 0:
                        self.draw_ship(grid, x, y, offset_x + x * CELL_SIZE, offset_y + y * CELL_SIZE)

                pygame.draw.rect(self.screen, BLACK, rect, 1)

            mark_text = SMALL_FONT.render(str(y + 1), True, BLACK)
            self.screen.blit(mark_text, (offset_x - mark_text.get_width() - 5,
                                         offset_y + y * CELL_SIZE + CELL_SIZE // 2 - mark_text.get_height() // 2))

    def draw_ship(self, grid, x, y, offset_x, offset_y):
        value = grid[y][x]
        index1 = (abs(value) % self.index_defeat) % len(self.ships)

        image = pygame.image.load(resource_path(self.ships[index1]))
        image = pygame.transform.scale(image, (CELL_SIZE, CELL_SIZE))

        if value < 0:
            image = pygame.transform.rotate(image, 270)

        self.screen.blit(image, (offset_x, offset_y))

        if abs(value) >= self.index_defeat:
            image = pygame.image.load(resource_path(self.fire[0]))
            image = pygame.transform.scale(image, (CELL_SIZE, CELL_SIZE))

        self.screen.blit(image, (offset_x, offset_y))

    def send_data(self, data):
        try:
            self.conn.sendall(pickle.dumps(data))
        except Exception as e:
            pass

    def receive_data(self):
        while self.running and self.connected and not self.menu_phase:
            try:
                data = self.conn.recv(4096)
                if not data:
                    break
                packet = pickle.loads(data)
                self.handle_network_data(packet)
            except socket.error as e:
                break
            except Exception as e:
                break

        # Close the connection when the thread ends
        if self.conn and not self.menu_phase:
            try:
                self.conn.shutdown(socket.SHUT_RDWR)  # Shutdown the socket before closing
                self.conn.close()
            except Exception as e:
                pass
            self.conn = None
            self.connected = False
        return

    def handle_network_data(self, data):
        if data[0] == 'move':
            x, y = data[1], data[2]

            # Check if it hit our ships
            if self.own_grid[y][x] != 0:
                self.own_grid[y][x] += self.index_defeat if self.own_grid[y][x] > 0 else -self.index_defeat  # Hit
                self.send_data(('hit', x, y))

                # Check if a ship is destroyed on your grid
                destroyed_ship = self.check_ship_destroyed(self.own_grid, x, y)
                if destroyed_ship:
                    # Immediately mark adjacent cells and send the destroy message
                    self.mark_adjacent_cells(destroyed_ship, self.own_grid, True)
                    self.send_data(('destroyed', destroyed_ship))  # Notify opponent

                    # Show the destruction effect on your own grid
                    self.show_ship_destroy_effect(destroyed_ship, MARGIN, MARGIN)

                if self.check_defeat():
                    self.game_over = True
                    self.send_data(('defeat',))

                self.turn = False
            else:
                self.own_grid[y][x] = len(self.ships) + self.index_defeat + 1  # Miss
                self.send_data(('miss', x, y))
                self.turn = True  # Switch turn to the opponent

        elif data[0] == 'hit':
            x, y = data[1], data[2]
            self.enemy_grid[y][x] = 2  # Mark hit
            self.turn = True

        elif data[0] == 'destroyed':
            # Handle when opponent notifies of ship destruction
            destroyed_ship = data[1]
            # Immediately mark adjacent cells on the enemy's grid and show the effect
            self.mark_adjacent_cells(destroyed_ship, self.enemy_grid)
            self.turn = True

        elif data[0] == 'miss':
            x, y = data[1], data[2]
            self.enemy_grid[y][x] = 3  # Mark miss
            self.turn = False  # Switch turn to the opponent

        elif data[0] == 'defeat':
            self.stop_animations = True  # Stop all animations
            self.game_over = True

        elif data[0] == 'ready':
            self.enemy_ready = True
            # Check if both players are ready
            if self.ready and self.enemy_ready:
                self.both_ready = True
        elif data[0] == 'disconnect':
            self.reset_game(True, False)
        else:
            pass

    def check_defeat(self):
        for row in self.own_grid:
            for col in row:
                if col != 0 and abs(col) < self.index_defeat:
                    return False
        return True

    def show_game_over(self):
        end_game_flag = True
        disconnect = True

        self.stop_animations = True  # Stop all ongoing animations
        self.screen.fill(WHITE)

        if self.check_defeat():
            text = "You lost!"
        else:
            text = "You won!"

        game_over_text = FONT.render(text, True, BLACK)
        continue_button = pygame.Rect(WIDTH // 2 - 100, HEIGHT // 2 - 40, 200, 50)
        return_button = pygame.Rect(WIDTH // 2 - 100, HEIGHT // 2 + 20, 200, 50)

        continue_text = FONT.render('Continue playing', True, WHITE)
        return_text = FONT.render('Return to menu', True, WHITE)

        while end_game_flag and self.game_over:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    self.send_data(('disconnect',))
                    return None
                if event.type == pygame.MOUSEBUTTONDOWN:
                    x, y = event.pos

                    if continue_button.collidepoint(x, y):
                        disconnect = False
                        end_game_flag = False
                    elif return_button.collidepoint(x, y):
                        end_game_flag = False

            self.screen.fill(WHITE)

            self.screen.blit(game_over_text, (WIDTH // 2 - game_over_text.get_width() // 2, HEIGHT // 4))

            pygame.draw.rect(self.screen, GREEN, continue_button)
            pygame.draw.rect(self.screen, RED, return_button)

            self.screen.blit(continue_text, (continue_button.centerx - continue_text.get_width() // 2,
                                             continue_button.centery - continue_text.get_height() // 2))
            self.screen.blit(return_text, (return_button.centerx - return_text.get_width() // 2,
                                           return_button.centery - return_text.get_height() // 2))
            pygame.display.flip()

        self.reset_game(disconnect)

    def reset_game(self, disconnect=True, send_disconnect=True):
        # Reset player states
        self.own_grid = [[0] * 10 for _ in range(10)]
        self.enemy_grid = [[0] * 10 for _ in range(10)]
        self.all_ships_placed = False
        self.ships_to_place = [4, 3, 3, 2, 2, 2, 1, 1, 1,
                               1]  # Ship sizes to place; default - [4, 3, 3, 2, 2, 2, 1, 1, 1, 1]
        self.placed_ships = []
        self.selected_ship_size = None
        self.ship_orientation = 'horizontal'
        self.game_last_seen = {}
        self.found_games = {}

        self.ready = False
        self.enemy_ready = False
        self.both_ready = False
        self.effect_playing = False
        self.stop_animations = False
        self.menu_phase = False
        self.place_ships_phase = False
        self.game_phase = False
        self.game_over = False
        self.safe_turn = False  # Temporary fix for safe turn (without bugs)

        if disconnect:
            if send_disconnect:
                self.send_data(('disconnect',))
            self.enemy_name = ''
            # Reset network-related states
            self.scanning = False
            self.broadcasting = False
            self.accepting_connections = False
            self.conn = None
            self.connected = False
            self.server_socket = None

            self.scan_thread = None  # Reset thread reference

            # Clear role to allow for a new selection
            self.role = None

            self.menu_phase = True
            self.place_ships_phase = False
            self.game_phase = False
            self.game_over = False

        else:
            self.place_ships_phase = True

            if self.turn:
                self.turn = False
            else:
                self.turn = True


if __name__ == "__main__":
    main_game = BattleshipGame()

    while main_game.running:
        if main_game.menu_phase:
            main_game.main_menu()
        elif main_game.place_ships_phase:
            main_game.place_ships()
        elif main_game.game_phase:
            main_game.game_loop()
        elif main_game.game_over:
            main_game.show_game_over()

        for main_event in pygame.event.get():
            if main_event.type == pygame.QUIT:
                main_game.running = False
                break
