import socket
from threading import Thread
from threading import Lock
import pygame
import textwrap

sock = socket.socket(
    socket.AF_INET,
    socket.SOCK_STREAM)

#Number of bytes for a message header. ex "PLYRMOVE"
MESSAGE_HEADER_LENGTH = 8


mutex = Lock() #general mutex lock for player state changes (new inputs, changing connectionsList, etc)
#### Mutex locked variables
playerNumber = -1
gameStarted = False

#init player positions
# players start at the center of the window
positions = [[4, 4],
             [5, 4],
             [4, 5],
             [5, 5]]
# list of wall positions
walls = [[0, 2],
         [1, 2],
         [1, 5],
         [1, 6],
         [1, 8],
         [2, 1],
         [2, 4],
         [2, 9],
         [3, 1],
         [3, 7],
         [4, 3],
         [4, 7],
         [5, 2],
         [5, 6],
         [5, 8],
         [6, 8],
         [7, 5],
         [7, 6],
         [8, 0],
         [8, 3],
         [8, 7],
         [9, 0],
         [9, 1],
         [9, 6]]
# list of goals positions, who they belong to, and how time is left on it
goals = []
currentScore = 0
### end Mutex locked variables

# may change this
maxScore = 20

clientInputs = [False, False, False, False]

#80x80 pixel rectangle
player_height = player_width = 80

# init pygame
pygame.init()

# 800x800 pixel game map
MAP_WIDTH = MAP_HEIGHT = 800
# 300 pixel wide sidebar
SIDEBAR_WIDTH = 300
# 80x80 pixel tile size
TILE_SIZE = 80
# 10x10 grid size
GRID_WIDTH = GRID_HEIGHT = 10

# map bg - black
BG_COLOR = (0, 0, 0)
# grid line color - gray
GRID_COLOR = (128, 128, 128)
# wall tile color - yellow
WALL_COLOR = (220, 220, 0)
# diagonal line color - black
DIAG_LINE_COLOR = (0, 0, 0)
# text color - white
TEXT_COLOR = (240, 240, 240)
# win text color - green
WIN_COLOR = (0, 255, 0)
# lose text color - red
LOSE_COLOR = (255, 0, 0)

PLAYER_COLORS = [
    # red
    (220, 0, 0),
    # green
    (0, 220, 0),
    # blue
    (0, 0, 220),
    # cyan
    (0, 220, 220)
]

# init text font
pygame.font.init()
font = pygame.font.SysFont("Comic Sans MS", 24)
font.set_bold(True)

win = pygame.display.set_mode((MAP_WIDTH + SIDEBAR_WIDTH, MAP_HEIGHT))
pygame.display.set_caption("Game")

def draw_waiting_screen():
    win.fill(BG_COLOR)

    waiting_text = font.render("Waiting for players...", True, TEXT_COLOR)
    waiting_rect = waiting_text.get_rect(center=((MAP_WIDTH + SIDEBAR_WIDTH) // 2, MAP_HEIGHT // 2 - 100))
    win.blit(waiting_text, waiting_rect)

    pygame.display.update()

def draw_game_win():
    global currentScore

    win.fill(BG_COLOR)

    win_text = font.render("You Win!", True, WIN_COLOR)
    win_rect = win_text.get_rect(center=((MAP_WIDTH + SIDEBAR_WIDTH) // 2, MAP_HEIGHT // 2 - 100))
    win.blit(win_text, win_rect)

    score_text = font.render((f"Team Score: {currentScore} / 20"), True, TEXT_COLOR)
    score_rect = score_text.get_rect(center=((MAP_WIDTH + SIDEBAR_WIDTH) // 2, MAP_HEIGHT // 2 - 50))
    win.blit(score_text, score_rect)

    pygame.display.update()

def draw_game_over():
    global currentScore

    win.fill(BG_COLOR)

    lose_text = font.render("You Lose!", True, LOSE_COLOR)
    lose_rect = lose_text.get_rect(center=((MAP_WIDTH + SIDEBAR_WIDTH) // 2, MAP_HEIGHT // 2 - 100))
    win.blit(lose_text, lose_rect)

    score_text = font.render((f"Team Score: {currentScore} / 20"), True, TEXT_COLOR)
    score_rect = score_text.get_rect(center=((MAP_WIDTH + SIDEBAR_WIDTH) // 2, MAP_HEIGHT // 2 - 50))
    win.blit(score_text, score_rect)

    pygame.display.update()

#connect to server, blocks till game starts
def connect(address, port):
    global gameStarted, playerNumber
    sock.connect((address, port))

    draw_waiting_screen()

    #we will receive a player number first.
    #then we will receive a game start message
    while not gameStarted:
        data = sock.recv(MESSAGE_HEADER_LENGTH)
        if data == b"GAMESTRT":
            gameStarted = True
        elif data == b"PLYRJOIN":
            #updated player number

            #receive 1 byte for player number
            playerNumber = int(sock.recv(1))

            #send player number back as confirmation that we are active
            sock.send(data)

            print(f"You are player {int(playerNumber)}.")

    return playerNumber

# Checks all the list of entities given an x y coordinate to see if there is something there that player can't move into (ex. a player or wall)
def checkForNoCollision(x, y):
    if not [x, y] in positions:
        if not [x, y] in walls:
            return True
    return False

# Sends packet telling server that player is moving either to N, E, S, or W direction 1 tile, if there's no collision (ex. with players or walls)
def send_move(dir, down):
    newPos = [coord for coord in positions[playerNumber - 1]]

    # Calculate the coords of where the player is moving to
    if down:
        if dir == "N":
            newPos[1] -= 1
            newPos[1] %= GRID_HEIGHT
        elif dir == "S":
            newPos[1] += 1
            newPos[1] %= GRID_HEIGHT
        elif dir == "W":
            newPos[0] -= 1
            newPos[0] %= GRID_WIDTH
        elif dir == "E":
            newPos[0] += 1
            newPos[0] %= GRID_WIDTH

    # construct message ("PLYRMOVE <N/S/E/W direction> + <1/0>")
    if down:
        # Check if there's something in the tile the player is moving to
        if checkForNoCollision(newPos[0], newPos[1]):
            msg = "PLYRMOVE" + dir + "1"
            sock.send(msg.encode())
    else:
        msg = "PLYRMOVE" + dir + "0"
        sock.send(msg.encode())

def inputHandler():
    # always check inputs
    while True:
        #dont bombard the server with messages
        pygame.time.delay(1)

        for event in pygame.event.get():
            # if quit then close game
            if event.type == pygame.QUIT:
                pygame.quit()
        with mutex:
            if gameStarted == False:
                #game ended
                return

        # get keydown and send data
        with mutex:
            if event.type == pygame.KEYDOWN:
                eventNum = -1
                if event.key == pygame.K_UP and clientInputs[0] == False:
                    eventNum = 0
                    send_move("N", True)
                    clientInputs[0] = True
                elif event.key == pygame.K_DOWN and clientInputs[1] == False:
                    eventNum = 1
                    send_move("S", True)
                    clientInputs[1] = True
                elif event.key == pygame.K_LEFT and clientInputs[2] == False:
                    eventNum = 2
                    send_move("W", True)
                    clientInputs[2] = True
                elif event.key == pygame.K_RIGHT and clientInputs[3] == False:
                    eventNum = 3
                    send_move("E", True)
                    clientInputs[3] = True
                if (event.key == pygame.K_UP or event.key == pygame.K_DOWN or
                   event.key == pygame.K_LEFT or event.key == pygame.K_RIGHT):
                    # for i in range(len(clientInputs)):
                    #     clientInputs[i] = False
                    #     if i == eventNum:
                    #         clientInputs[i] = True
                    pass

            # get keyup and send data
            if event.type == pygame.KEYUP:
                if event.key == pygame.K_UP and clientInputs[0] == True:
                    send_move("N", False)
                    clientInputs[0] = False
                if event.key == pygame.K_DOWN and clientInputs[1] == True:
                    send_move("S", False)
                    clientInputs[1] = False
                if event.key == pygame.K_LEFT and clientInputs[2] == True:
                    send_move("W", False)
                    clientInputs[2] = False
                if event.key == pygame.K_RIGHT and clientInputs[3] == True:
                    send_move("E", False)
                    clientInputs[3] = False

def recvGameUpdates():
    global goals, currentScore
    # constantly check for game updates
    while True:
        # data will be "POSXXXYYYXXXYYYXXXYYYXXXYYY"
        try:
            data = sock.recv(MESSAGE_HEADER_LENGTH).decode()
        except:
            #Failed to get update. Dissconnect.
            # TODO
            pass
        if data == "PLYRUPDT":
            #receive each players position
            # Format is PLYRUPDTXXYYXXYYXXYYXXYY
            #ie. 2 chars for each players x/y position, and 4 players
            for i in range(4):
                data = sock.recv(2).decode()
                x_pos = int(data)
                data = sock.recv(2).decode()
                y_pos = int(data)

                #update player posititons
                with mutex:
                    positions[i][0] = x_pos
                    positions[i][1] = y_pos
        elif data == "GOALUPDT":
            with mutex:
                # clear all goals so that only current info from server is kept
                goals = []

                # receive goal positions and info
                # Format is ("GOALUPDTNGCSXXYYPNTLXXYYPNTL...")
                # where NG = number of goals, CS = current score (number of goals reached), XX = x pos of the ith goal, YY = y pos of the ith goal, PN = player number the goal belongs to, TL = time left on goal
                numGoals = int(sock.recv(2))
                currentScore = int(sock.recv(2))

                # clear the goals array to get rid of tiles that were already reached
                goals.clear()

                for i in range(numGoals):
                    x_pos = int(sock.recv(2))
                    y_pos = int(sock.recv(2))
                    player_num = int(sock.recv(2))
                    time_left = int(sock.recv(2))

                    goals.append([x_pos, y_pos, player_num, time_left])
        elif data == "GAMEWINN":
            print("Game Won")
            draw_game_win()
            break
        elif data == "GAMEOVER":
            print("Game Lost")
            draw_game_over()
            break

        updateDisplay()

def draw_grid():
    win.fill(BG_COLOR)

    # drawing vertical grid lines from left to right, every 50 pixels
    for x in range(0, MAP_WIDTH, TILE_SIZE):
        pygame.draw.line(win, GRID_COLOR, (x, 0), (x, MAP_HEIGHT), 3)

    # drawing horizontal grid lined from top to bottom, every 50 pixels
    for y in range(0, MAP_HEIGHT, TILE_SIZE):
        pygame.draw.line(win, GRID_COLOR, (0, y), (MAP_WIDTH, y), 3)

def draw_walls():
    for wall in walls:
        pygame.draw.rect(win, WALL_COLOR, (wall[0] * TILE_SIZE, wall[1] * TILE_SIZE, TILE_SIZE, TILE_SIZE))
        # draw a diagonal line from top-right to bot-left
        pygame.draw.line(win, DIAG_LINE_COLOR, (wall[0] * TILE_SIZE + TILE_SIZE, wall[1] * TILE_SIZE), (wall[0] * TILE_SIZE, wall[1] * TILE_SIZE + TILE_SIZE), 5)
        # draw a diagonal line from top-left to bot-right
        pygame.draw.line(win, DIAG_LINE_COLOR, (wall[0] * TILE_SIZE, wall[1] * TILE_SIZE), (wall[0] * TILE_SIZE + TILE_SIZE, wall[1] * TILE_SIZE + TILE_SIZE), 5)

def draw_goal_tiles():
    for goal in goals:
        pygame.draw.rect(win, PLAYER_COLORS[goal[2]], (goal[0] * TILE_SIZE, goal[1] * TILE_SIZE, TILE_SIZE, TILE_SIZE))

        # Draw the countdown timer in the center of a goal tile
        time_text = font.render(str(goal[3]), True, TEXT_COLOR)
        time_rect = time_text.get_rect(center=(goal[0] * TILE_SIZE + TILE_SIZE // 2, goal[1] * TILE_SIZE + TILE_SIZE // 2))
        win.blit(time_text, time_rect)

def draw_sidebar():
    global currentScore, playerNumber

    # draw the sidebar background
    sidebar_rect = pygame.Rect(MAP_WIDTH, 0, SIDEBAR_WIDTH, MAP_HEIGHT)
    pygame.draw.rect(win, (40, 40, 40), sidebar_rect)

    score_text = font.render((f"Team Score: {currentScore} / {maxScore}"), True, TEXT_COLOR)
    score_rect = score_text.get_rect(center=(MAP_WIDTH + SIDEBAR_WIDTH // 2, 100))
    win.blit(score_text, score_rect)

    playerID_text = font.render((f"Player Number: {playerNumber}"), True, TEXT_COLOR)
    playerID_rect = playerID_text.get_rect(center=(MAP_WIDTH + SIDEBAR_WIDTH // 2, 200))
    win.blit(playerID_text, playerID_rect)

def draw_players():
    for i in range(4):
        try:
            with mutex:
                x, y = positions[i]

            # Draw the player's rect
            pygame.draw.rect(win, PLAYER_COLORS[i], (x * TILE_SIZE, y * TILE_SIZE, player_width, player_height))
            # Draw a border around the player's tile
            pygame.draw.rect(win, TEXT_COLOR, (x * TILE_SIZE, y * TILE_SIZE, player_width, player_height), 2)
            # Render the player's ID as a text rect
            playerID_text = font.render((f"P{i + 1}"), True, TEXT_COLOR)
            # Center the text rect in the player's rect
            playerID_rect = playerID_text.get_rect(center=(x * TILE_SIZE + TILE_SIZE // 2, y * TILE_SIZE + TILE_SIZE // 2))
            # Draw the player's ID onto the game window
            win.blit(playerID_text, playerID_rect)

        except Exception as e:
            print(f"Error drawing player {i}: {e}")

def updateDisplay():
    draw_grid()
    draw_goal_tiles()
    draw_walls()
    draw_sidebar()
    draw_players()

    pygame.display.update()

#in match, play the game
def main():
    global playerNumber
    #connect, wait until game starts
    playerNumber = connect("localhost", 53333)
    #game is now started
    # init_game()
    #make thread to receive game state updates/drawing it (mutex needed)
    Thread(target = recvGameUpdates, args=()).start()
    #make thread for sending inputs (mutex needed for verifying legal inputs)
    inputHandler()

    while gameStarted:
        pass

    #game is over, terminate threads (with mutex)

    #reconnect for a new game, if desired


main()