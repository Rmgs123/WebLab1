import pygame
import sys
import threading
import socket
import pickle
import time

# БАГИ: 1) если нажать готов и убрать корабль, то другой игрок начнет с вами играть
# а вы останетесь навсегда в меню расстановки кораблей 2) Если корабль потопить последним, его
# эффект будет рисоваться поверх текста "вы проиграли" (только у проигравшего), - нужно стопить эффект!


# Инициализация Pygame
pygame.init()

# Константы
WIDTH, HEIGHT = 900, 600  # Увеличена ширина для отображения списка кораблей
CELL_SIZE = 30
MARGIN = 50
FONT = pygame.font.SysFont('arial', 20)
SMALL_FONT = pygame.font.SysFont('arial', 16)

# Цвета
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BLUE = (64, 164, 223)
RED = (255, 0, 0)
GRAY = (200, 200, 200)
GREEN = (0, 255, 0)
YELLOW = (255, 255, 0)
TRANSPARENT_GREEN = (0, 255, 0, 100)
TRANSPARENT_RED = (255, 0, 0, 100)

# Сетевые настройки
TCP_PORT = 5005
UDP_PORT = 5006
BROADCAST_IP = '255.255.255.255'

class BattleshipGame:
    def __init__(self):
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Морской бой")
        self.clock = pygame.time.Clock()

        # Переменные игрока
        self.player_name = ''
        self.enemy_name = ''
        self.role = None  # 'host' или 'client'
        self.running = True
        self.connected = False

        # Игровые поля
        self.own_grid = [[0]*10 for _ in range(10)]  # Ваше поле
        self.enemy_grid = [[0]*10 for _ in range(10)]  # Поле противника (известная вам информация)

        # Корабли игрока
        self.all_ships_placed = False  # Добавлено в __init__
        self.ships_to_place = [3,1,1]  # Размеры кораблей для размещения [4, 3, 3, 2, 2, 2, 1, 1, 1, 1]
        self.placed_ships = []  # Список размещенных кораблей
        self.selected_ship_size = None  # Текущий выбранный размер корабля для размещения
        self.ship_orientation = 'horizontal'
        self.place_ships_phase = True
        self.ready = False
        self.enemy_ready = False
        self.both_ready = False  # Новая переменная для отслеживания готовности обоих игроков
        self.effect_playing = False

        # Сетевое соединение
        self.conn = None

        # Запуск игры
        self.main_menu()

    def main_menu(self):
        # Окно ввода имени (если имя еще не установлено)
        if not self.player_name:
            self.player_name = self.input_name()
            if not self.player_name:
                self.running = False
                return

        # Выбор режима игры
        self.select_role()

    def select_role(self):
        self.role = self.choose_role()
        if not self.role:
            self.running = False
            return

        # Установка соединения
        if self.role == 'host':
            self.start_host()
        else:
            self.join_game()

        if not self.connected:
            self.running = False
            return

        # Размещение кораблей
        self.place_ships()

        # Основной цикл игры
        self.game_loop()

    def input_name(self):
        name = ''
        input_active = True
        max_length = 20  # Maximum name length
        while input_active:
            self.clock.tick(60)
            self.screen.fill(WHITE)
            prompt = FONT.render('Введите ваше имя и нажмите Enter:', True, BLACK)
            name_text = FONT.render(name, True, BLACK)
            self.screen.blit(prompt, (WIDTH // 2 - prompt.get_width() // 2, HEIGHT // 2 - 30))
            self.screen.blit(name_text, (WIDTH // 2 - name_text.get_width() // 2, HEIGHT // 2))
            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    input_active = False
                    return None
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        input_active = False
                        break
                    elif event.key == pygame.K_BACKSPACE:
                        name = name[:-1]
                    elif len(name) < max_length:  # Check the length of the name
                        name += event.unicode
        return name.strip()

    def choose_role(self):
        role = None
        while role is None:
            self.clock.tick(60)
            self.screen.fill(WHITE)
            prompt = FONT.render('Выберите режим игры:', True, BLACK)
            host_button = pygame.Rect(WIDTH//2 - 100, HEIGHT//2 - 30, 200, 50)
            client_button = pygame.Rect(WIDTH//2 - 100, HEIGHT//2 + 30, 200, 50)
            pygame.draw.rect(self.screen, BLUE, host_button)
            pygame.draw.rect(self.screen, GREEN, client_button)
            host_text = FONT.render('Создать игру', True, WHITE)
            client_text = FONT.render('Присоединиться', True, WHITE)
            self.screen.blit(prompt, (WIDTH//2 - prompt.get_width()//2, HEIGHT//2 - 100))
            self.screen.blit(host_text, (host_button.centerx - host_text.get_width()//2, host_button.centery - host_text.get_height()//2))
            self.screen.blit(client_text, (client_button.centerx - client_text.get_width()//2, client_button.centery - client_text.get_height()//2))
            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return None
                if event.type == pygame.MOUSEBUTTONDOWN:
                    x, y = event.pos
                    if host_button.collidepoint(x, y):
                        return 'host'
                    elif client_button.collidepoint(x, y):
                        return 'client'
        return None

    def start_host(self):
        # Создаем сервер и начинаем рассылку UDP сообщений
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(('', TCP_PORT))
        self.server_socket.listen(1)

        self.broadcasting = True  # Добавляем флаг для управления потоками
        self.accepting_connections = True

        threading.Thread(target=self.accept_connection, daemon=True).start()
        threading.Thread(target=self.broadcast_game, daemon=True).start()

        # Ожидание подключения клиента
        waiting = True
        back_button = pygame.Rect(20, 20, 100, 40)  # Кнопка "Назад"

        while waiting:
            self.clock.tick(60)
            self.screen.fill(WHITE)
            prompt = FONT.render('Ожидание подключения игрока...', True, BLACK)
            self.screen.blit(prompt, (WIDTH // 2 - prompt.get_width() // 2, HEIGHT // 2))

            # Отображение кнопки "Назад"
            pygame.draw.rect(self.screen, GRAY, back_button)
            back_text = SMALL_FONT.render('Назад', True, WHITE)
            self.screen.blit(back_text, (
            back_button.centerx - back_text.get_width() // 2, back_button.centery - back_text.get_height() // 2))

            pygame.display.flip()

            if self.connected:
                waiting = False

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    waiting = False
                    return
                if event.type == pygame.MOUSEBUTTONDOWN:
                    x, y = event.pos
                    if back_button.collidepoint(x, y):
                        # Обработка нажатия кнопки "Назад"
                        self.broadcasting = False  # Останавливаем рассылку
                        self.accepting_connections = False  # Останавливаем принятие соединений

                        if self.server_socket:
                            self.server_socket.close()  # Закрываем серверный сокет

                        self.connected = False  # Сбрасываем состояние подключения
                        self.select_role()  # Возвращаемся к выбору роли
                        return

    def accept_connection(self):
        while self.accepting_connections:
            try:
                self.conn, addr = self.server_socket.accept()
                self.connected = True
                # Получаем имя противника
                data = self.conn.recv(1024)
                self.enemy_name = data.decode()
                # Отправляем свое имя
                self.conn.sendall(self.player_name.encode())
                print(f"Игрок {self.enemy_name} подключен.")
                break  # Выходим из цикла после подключения
            except Exception as e:
                if not self.accepting_connections:
                    break
                print(f"Ошибка при подключении: {e}")

    def broadcast_game(self):
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        message = f"BattleshipGame:{self.player_name}"
        while not self.connected and self.broadcasting:
            try:
                udp_socket.sendto(message.encode(), (BROADCAST_IP, UDP_PORT))
                time.sleep(1)
            except Exception as e:
                print(f"Ошибка при рассылке: {e}")
                break
        udp_socket.close()

    def join_game(self):
        # Очистка предыдущего состояния сети
        if self.conn:
            self.conn.close()
        self.conn = None
        self.connected = False

        # Сканируем сеть на наличие игр
        self.found_games = {}
        self.scanning = True
        threading.Thread(target=self.scan_for_games, daemon=True).start()

        selected_game = self.select_game()
        if not selected_game:
            # Если ничего не выбрано или нажата кнопка "Назад", возвращаемся в выбор роли
            self.scanning = False
            self.select_role()
            return

        # Устанавливаем соединение с выбранной игрой
        self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.conn.connect((selected_game['ip'], TCP_PORT))
            self.connected = True
            # Отправляем свое имя
            self.conn.sendall(self.player_name.encode())
            # Получаем имя противника
            data = self.conn.recv(1024)
            self.enemy_name = data.decode()
            print(f"Подключено к игроку {self.enemy_name}")
        except Exception as e:
            print(f"Не удалось подключиться к игре: {e}")
            self.show_message('Не удалось подключиться к игре.')

    def scan_for_games(self):
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        udp_socket.settimeout(2)
        udp_socket.bind(('', UDP_PORT))

        game_timeout = 1  # Seconds until a game is considered unavailable
        game_last_seen = {}  # Track last time each game was seen

        while self.scanning:
            current_time = time.time()

            try:
                data, addr = udp_socket.recvfrom(1024)
                message = data.decode()
                if message.startswith('BattleshipGame:'):
                    game_name = message.split(':')[1]
                    self.found_games[addr[0]] = {'name': game_name, 'ip': addr[0]}
                    game_last_seen[addr[0]] = current_time  # Update last seen time
            except socket.timeout:
                pass

            # Remove games that haven't broadcasted recently
            to_remove = [ip for ip, last_seen in game_last_seen.items() if current_time - last_seen > game_timeout]
            for ip in to_remove:
                if ip in self.found_games:
                    del self.found_games[ip]
                del game_last_seen[ip]

        udp_socket.close()

    def select_game(self):
        selected = None
        back_button = pygame.Rect(20, 20, 100, 40)
        while selected is None and self.running:
            self.clock.tick(60)
            self.screen.fill(WHITE)
            prompt = FONT.render('Выберите игру для подключения:', True, BLACK)
            self.screen.blit(prompt, (WIDTH//2 - prompt.get_width()//2, 50))

            # Кнопка "Назад"
            pygame.draw.rect(self.screen, GRAY, back_button)
            back_text = SMALL_FONT.render('Назад', True, WHITE)
            self.screen.blit(back_text, (back_button.centerx - back_text.get_width()//2, back_button.centery - back_text.get_height()//2))

            # Отображаем список найденных игр
            games = list(self.found_games.values())
            for idx, game in enumerate(games):
                game_button = pygame.Rect(WIDTH//2 - 150, 100 + idx * 60, 300, 50)
                pygame.draw.rect(self.screen, BLUE, game_button)
                game_text = FONT.render(f"{game['name']} ({game['ip']})", True, WHITE)
                self.screen.blit(game_text, (game_button.centerx - game_text.get_width()//2, game_button.centery - game_text.get_height()//2))
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
                        if game['button'].collidepoint(x, y):
                            self.scanning = False
                            return game

        return None

    def show_message(self, message):
        showing = True
        while showing:
            self.clock.tick(60)
            self.screen.fill(WHITE)
            prompt = FONT.render(message, True, BLACK)
            self.screen.blit(prompt, (WIDTH//2 - prompt.get_width()//2, HEIGHT//2))
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
        while placing and self.running:
            self.clock.tick(60)  # Необходимо для стабильной работы игры
            self.screen.fill(WHITE)
            self.draw_grid(self.own_grid, MARGIN, MARGIN)
            self.draw_ship_selection()
            prompt = FONT.render('Разместите свои корабли', True, BLACK)
            self.screen.blit(prompt, (WIDTH // 2 - prompt.get_width() // 2, 20))

            # Добавляем инструкцию по удалению кораблей
            instruction_text = SMALL_FONT.render('Удалить корабль: наведите на него и нажмите Delete', True, BLACK)
            self.screen.blit(instruction_text, (MARGIN, HEIGHT - 80))

            # Кнопка "Готово"
            ready_button = pygame.Rect(WIDTH - 150, HEIGHT - 60, 100, 40)
            ready_color = GREEN if self.all_ships_placed else GRAY
            pygame.draw.rect(self.screen, ready_color, ready_button)
            ready_text = SMALL_FONT.render('Готово', True, WHITE)
            self.screen.blit(ready_text, (
            ready_button.centerx - ready_text.get_width() // 2, ready_button.centery - ready_text.get_height() // 2))

            # Отображаем предварительный просмотр корабля
            mouse_pos = pygame.mouse.get_pos()
            grid_x = (mouse_pos[0] - MARGIN) // CELL_SIZE
            grid_y = (mouse_pos[1] - MARGIN) // CELL_SIZE

            # Проверяем, есть ли корабль под курсором
            ship_under_cursor = None
            if 0 <= grid_x < 10 and 0 <= grid_y < 10:
                ship_under_cursor = self.get_ship_at_position(grid_x, grid_y)

            if selected_ship and 0 <= grid_x < 10 and 0 <= grid_y < 10:
                can_place = self.can_place_ship(grid_x, grid_y, selected_ship, self.ship_orientation)
                color = GREEN if can_place else RED
                self.draw_ship_preview(grid_x, grid_y, selected_ship, self.ship_orientation, color)

            # Если мы нажали "Готово" и ждём противника, отображаем сообщение
            if self.ready and not self.both_ready:
                waiting_text = FONT.render('Ожидание готовности противника...', True, BLACK)
                self.screen.blit(waiting_text, (WIDTH // 2 - waiting_text.get_width() // 2, HEIGHT // 2))

            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    placing = False
                    return
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_r:
                        self.ship_orientation = 'vertical' if self.ship_orientation == 'horizontal' else 'horizontal'
                    if event.key == pygame.K_DELETE and ship_under_cursor:
                        # Удаляем корабль, если курсор над ним и нажата Delete
                        self.remove_ship(ship_under_cursor)
                        ship_under_cursor = None
                        self.all_ships_placed = False  # После удаления корабля, все корабли не размещены
                if event.type == pygame.MOUSEBUTTONDOWN:
                    x, y = event.pos
                    # Проверяем кнопки кораблей
                    for ship_button in self.ship_buttons:
                        if ship_button['rect'].collidepoint(x, y):
                            selected_ship = ship_button['size']
                    # Проверяем кнопку "Готово"
                    if ready_button.collidepoint(x, y) and self.all_ships_placed:
                        self.ready = True
                        self.send_data(('ready',))
                        # Мы готовы, ждём противника
                    # Размещение корабля на поле
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

            # Проверяем, готовы ли оба игрока
            if self.ready:
                if not hasattr(self, 'data_thread') or not self.data_thread.is_alive():
                    self.data_thread = threading.Thread(target=self.receive_data, daemon=True)
                    self.data_thread.start()

            if self.both_ready:
                placing = False  # Выходим из цикла размещения

        # Переходим к игре, если оба игрока готовы
        if self.both_ready:
            self.place_ships_phase = False
            return
        else:
            return

    def draw_ship_selection(self):
        # Отображаем доступные корабли для размещения
        self.ship_buttons = []
        start_x = WIDTH - 200
        start_y = MARGIN
        for idx, ship_size in enumerate(sorted(set(self.ships_to_place), reverse=True)):
            count = self.ships_to_place.count(ship_size)
            if count > 0:
                ship_rect = pygame.Rect(start_x, start_y + idx * 60, 150, 50)
                pygame.draw.rect(self.screen, BLUE, ship_rect)
                ship_text = SMALL_FONT.render(f'Корабль {ship_size} ({count})', True, WHITE)
                self.screen.blit(ship_text, (ship_rect.centerx - ship_text.get_width()//2, ship_rect.centery - ship_text.get_height()//2))
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
                    if self.own_grid[adj_y][adj_x] == 1 and (adj_x, adj_y) not in blocking_positions:
                        blocking_positions.append((adj_x, adj_y))
        return blocking_positions

    def place_ship(self, x, y, size, orientation):
        positions = []
        if orientation == 'horizontal':
            for i in range(size):
                self.own_grid[y][x + i] = 1
                positions.append((x + i, y))
        else:
            for i in range(size):
                self.own_grid[y + i][x] = 1
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
        # Set a flag to indicate an effect is being played
        self.effect_playing = True

        # Immediately mark the surrounding cells as gray
        self.mark_adjacent_cells(ship_positions, self.own_grid if offset_x == MARGIN else self.enemy_grid)
        pygame.display.flip()

        if animate:
            colors = [RED, YELLOW]  # Colors to alternate between
            for _ in range(6):  # Increase the loop to make the effect last longer
                for color in colors:
                    for (x, y) in ship_positions:
                        rect = pygame.Rect(offset_x + x * CELL_SIZE, offset_y + y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
                        pygame.draw.rect(self.screen, color, rect)  # Draw with the current color
                    pygame.display.flip()
                    pygame.time.delay(300)  # Delay to create a flashing effect

        # Reset the flag after the effect is complete
        self.effect_playing = False

    def mark_adjacent_cells(self, ship_positions, grid):
        for (x, y) in ship_positions:
            for adj_y in range(max(0, y - 1), min(10, y + 2)):
                for adj_x in range(max(0, x - 1), min(10, x + 2)):
                    if grid[adj_y][adj_x] == 0:  # Only mark cells that haven't been shot at
                        grid[adj_y][adj_x] = 3  # Mark as gray

    def check_ship_destroyed(self, grid, x, y):
        # Find the ship associated with the hit cell
        for ship in self.placed_ships:
            if (x, y) in ship['positions']:
                # Check if all positions of the ship have been hit
                if all(grid[pos_y][pos_x] == 2 for (pos_x, pos_y) in ship['positions']):
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
        threading.Thread(target=self.receive_data, daemon=True).start()
        self.turn = self.role == 'host'  # Хост начинает первым
        self.game_over = False
        while self.running:
            self.clock.tick(60)
            self.handle_events()
            self.draw()
            if self.game_over:
                self.show_game_over()
        pygame.quit()
        sys.exit()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            if event.type == pygame.MOUSEBUTTONDOWN and self.turn and not self.game_over:
                x, y = pygame.mouse.get_pos()
                grid_x = (x - MARGIN - 350) // CELL_SIZE
                grid_y = (y - MARGIN) // CELL_SIZE
                if 0 <= grid_x < 10 and 0 <= grid_y < 10:
                    if self.enemy_grid[grid_y][grid_x] == 0:
                        # Отправляем координаты хода противнику
                        self.send_data(('move', grid_x, grid_y))
                        self.turn = False

    def draw(self):
        if self.effect_playing:
            return  # Skip drawing if an effect is being played

        self.screen.fill(WHITE)
        # Draw own ships
        self.draw_grid(self.own_grid, MARGIN, MARGIN)
        # Draw enemy field
        self.draw_grid(self.enemy_grid, MARGIN + 350, MARGIN, hide_ships=True)
        # Display player names
        own_name_text = FONT.render(f"Вы: {self.player_name}", True, BLACK)
        enemy_name_text = FONT.render(f"Противник: {self.enemy_name}", True, BLACK)
        self.screen.blit(own_name_text, (MARGIN, MARGIN - 30))
        self.screen.blit(enemy_name_text, (MARGIN + 350, MARGIN - 30))
        # Display turn information
        if not self.game_over:
            text = "Ваш ход" if self.turn else "Ход противника"
        else:
            text = "Игра окончена"
        turn_text = FONT.render(text, True, BLACK)
        self.screen.blit(turn_text, (WIDTH // 2 - turn_text.get_width() // 2, HEIGHT - 30))
        pygame.display.flip()

    def draw_grid(self, grid, offset_x, offset_y, hide_ships=False):
        for y in range(10):
            for x in range(10):
                rect = pygame.Rect(offset_x + x * CELL_SIZE, offset_y + y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
                if grid[y][x] == 1 and not hide_ships:
                    pygame.draw.rect(self.screen, BLUE, rect)
                elif grid[y][x] == 2:
                    pygame.draw.rect(self.screen, RED, rect)
                elif grid[y][x] == 3:
                    pygame.draw.rect(self.screen, GRAY, rect)
                pygame.draw.rect(self.screen, BLACK, rect, 1)

    def send_data(self, data):
        try:
            self.conn.sendall(pickle.dumps(data))
        except Exception as e:
            print(f"Ошибка при отправке данных: {e}")
            self.running = False

    def receive_data(self):
        while self.running:
            try:
                data = self.conn.recv(4096)
                if data:
                    packet = pickle.loads(data)
                    self.handle_network_data(packet)
            except Exception as e:
                print(f"Ошибка при получении данных: {e}")
                self.running = False
                break

        # Close the connection when the thread ends
        if self.conn:
            self.conn.close()

    def handle_network_data(self, data):
        if data[0] == 'move':
            x, y = data[1], data[2]
            # Проверяем попадание по нашим кораблям
            if self.own_grid[y][x] == 1:
                self.own_grid[y][x] = 2  # Попадание
                self.send_data(('hit', x, y))

                # Check if a ship is destroyed on your grid
                destroyed_ship = self.check_ship_destroyed(self.own_grid, x, y)
                if destroyed_ship:
                    # Immediately mark adjacent cells and send the destroy message
                    self.mark_adjacent_cells(destroyed_ship, self.own_grid)
                    self.send_data(('destroyed', destroyed_ship))  # Notify opponent

                    # Show the destruction effect on your own grid
                    self.show_ship_destroy_effect(destroyed_ship, MARGIN, MARGIN)

                if self.check_defeat():
                    self.game_over = True
                    self.send_data(('defeat',))
            else:
                self.own_grid[y][x] = 3  # Мимо
                self.send_data(('miss', x, y))
                self.turn = True  # Switch turn to the opponent

        elif data[0] == 'hit':
            x, y = data[1], data[2]
            self.enemy_grid[y][x] = 2  # Отмечаем попадание

            # Check if a ship is destroyed on the enemy's grid
            destroyed_ship = self.check_ship_destroyed(self.enemy_grid, x, y)
            if destroyed_ship:
                # Immediately mark adjacent cells on enemy's grid
                self.mark_adjacent_cells(destroyed_ship, self.enemy_grid)
                # Show the destruction effect on the enemy's grid
                self.show_ship_destroy_effect(destroyed_ship, MARGIN + 350, MARGIN)

            # Allow player to continue their turn
            self.turn = True

        elif data[0] == 'destroyed':
            # Handle when opponent notifies of ship destruction
            destroyed_ship = data[1]
            # Immediately mark adjacent cells on the enemy's grid and show the effect
            self.mark_adjacent_cells(destroyed_ship, self.enemy_grid)
            self.show_ship_destroy_effect(destroyed_ship, MARGIN + 350, MARGIN, animate=False)

        elif data[0] == 'miss':
            x, y = data[1], data[2]
            self.enemy_grid[y][x] = 3  # Отмечаем промах
            self.turn = False  # Switch turn to the opponent

        elif data[0] == 'defeat':
            self.game_over = True

        elif data[0] == 'ready':
            self.enemy_ready = True
            # Проверяем, готовы ли оба игрока
            if self.ready and self.enemy_ready:
                self.both_ready = True

        else:
            print(f"Неизвестный тип данных: {data[0]}")

    def check_defeat(self):
        for row in self.own_grid:
            if 1 in row:
                return False
        return True

    def show_game_over(self):
        self.screen.fill(WHITE)
        if self.check_defeat():
            text = "Вы проиграли!"
        else:
            text = "Вы выиграли!"
        game_over_text = FONT.render(text, True, BLACK)
        self.screen.blit(game_over_text, (WIDTH//2 - game_over_text.get_width()//2, HEIGHT//2))
        pygame.display.flip()

        # Ждем несколько секунд и закрываем игру
        pygame.time.delay(5000)
        self.running = False

if __name__ == "__main__":
    BattleshipGame()
