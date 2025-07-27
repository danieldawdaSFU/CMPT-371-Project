import socket
from threading import Thread
from threading import Lock
import pygame

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
walls = [[0, 0], [0, 9], [9, 0], [9, 9]] # TODO: make an actual map
# list of goals positions, who they belong to, and how time is left on it
goals = []
### end Mutex locked variables

clientInputs = [False, False, False, False]

#80x80 pixel rectangle
player_height = player_width = 80

# init pygame
pygame.init()

# 800x800 pixel game map
MAP_WIDTH = MAP_HEIGHT = 800
# 80x80 pixel tile size
TILE_SIZE = 80

# map bg - black
BG_COLOR = (0, 0, 0)
# grid line color - gray
GRID_COLOR = (128, 128, 128)

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

win = pygame.display.set_mode((MAP_WIDTH, MAP_HEIGHT))
pygame.display.set_caption("Game")

#connect to server, blocks till game starts
def connect(address, port):
    global gameStarted
    sock.connect((address, port))
    #we will receive a player number first.
    #then we will receive a game start message
    while not gameStarted:
        data = sock.recv(MESSAGE_HEADER_LENGTH)
        if data == b"GAMESTRT":
            gameStarted = True
        elif data == b"PLYRJOIN":
            #updated player number

            #receive 1 byte for player number
            playerNumber = sock.recv(1).decode()

            #send player number back as confirmation that we are active
            sock.send(data)
    print("I am player", playerNumber)

    return playerNumber

# Checks all the list of entities given an x y coordinate to see if there is something there that player can't move into (ex. a player or wall)
def checkForNoCollision(x, y):
    if not [x, y] in positions:
        if not [x, y] in walls:
            return True
    return False

# TODO: check for collision on players or walls before sending move packet
def send_move(dir, down):
    # construct message ("PLYRMOVE <N/S/E/W direction> + <1/0>")
    if down:
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
    # constantly check for game updates
    while True:
        # data will be "POSXXXYYYXXXYYYXXXYYYXXXYYY"
        try:
            data = sock.recv(MESSAGE_HEADER_LENGTH).decode()
        except:
            #Failed to get update. Dissconnect.
            #todo
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
                goals = []

                # receive goal positions and info
                # Format is ("GOALUPDTNGXXYYPNTLXXYYPNTL...")
                # where NG = number of goals, XX = x pos of the ith goal, YY = y pos of the ith goal, PN = player number the goal belongs to, TL = time left on goal
                numOfGoals = int(sock.recv(2))
                for i in range(numOfGoals):
                    x_pos = int(sock.recv(2))
                    y_pos = int(sock.recv(2))
                    player_num = int(sock.recv(2))
                    time_left = int(sock.recv(2))
                    
                    goals.append([x_pos, y_pos, player_num, time_left])
        updateDisplay()

def draw_grid(window):
    window.fill(BG_COLOR)

    # drawing vertical grid lines from left to right, every 50 pixels
    for x in range(0, MAP_WIDTH, TILE_SIZE):
        pygame.draw.line(window, GRID_COLOR, (x, 0), (x, MAP_HEIGHT))

    # drawing horizontal grid lined from top to bottom, every 50 pixels
    for y in range(0, MAP_HEIGHT, TILE_SIZE):
        pygame.draw.line(window, GRID_COLOR, (0, y), (MAP_WIDTH, y))

def updateDisplay():
    draw_grid(win)

    # TODO: draw goals

    # draw all players
    for i in range(4):
        try:
            with mutex:
                x, y = positions[i]

            # Draw the player's rect
            pygame.draw.rect(win, PLAYER_COLORS[i], (x*TILE_SIZE, y*TILE_SIZE, player_width, player_height))
            # Render the player's ID as a text rect
            playerID = font.render((f"P{i + 1}"), True, (255, 255, 255))
            # Center the text rect in the player's rect
            playerID_rect = playerID.get_rect(center=(x*TILE_SIZE + TILE_SIZE // 2, y*TILE_SIZE + TILE_SIZE // 2))
            # Draw the player's ID onto the game window
            win.blit(playerID, playerID_rect)

        except Exception as e:
            print(f"Error drawing player {i}: {e}")

    pygame.display.update()

#in match, play the game
def main():
    global playerNumber
    #connect, wait until game starts
    playerNumber = connect("localhost", 53333)
    print("Game Started. My player number is:", playerNumber)
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