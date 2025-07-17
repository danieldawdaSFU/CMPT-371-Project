import socket
from threading import Thread
import pygame 
import time

sock = socket.socket(
    socket.AF_INET,
    socket.SOCK_STREAM)

MESSAGE_HEADER_LENGTH = 1

playerNumber = -1
gameStarted = False

positions = [[100, 100],
             [200, 100],
             [100, 200],
             [200, 200]]

player_height = 15
player_width = 15

# init pygame   
pygame.init() 

win = pygame.display.set_mode((800, 800)) 
pygame.display.set_caption("Game")

#connect to server, blocks till game starts
def connect(address, port):
    global gameStarted
    sock.connect((address, port))
    #we will receive a player number first.
    #then we will receive a game start message
    while not gameStarted:
        data = sock.recv(8)
        if data == b"GAMESTRT":
            gameStarted = True
        elif data == b"PLYRJOIN":
            #updated player number
            playerNumber = sock.recv(1).decode()
            #send player number back as confirmation that we are active
            sock.send(data)

    return playerNumber

# def init_game():
#     # init pygame   
#     pygame.init() 

#     # game window
#     global win 
#     win = pygame.display.set_mode((1000, 800)) 
#     pygame.display.set_caption("Game")

def send_move(dir):
    # construct message ("MOV <direction>")
    msg = "MOV" + dir
    sock.send(msg.encode())

def send_stop(dir):
    # construct message ("STOP <direction>")
    msg = "STOP" + dir
    sock.send(msg.encode())

def inputs():
    # always check inputs
    while True: 
        pygame.time.delay(1) 
        
        for event in pygame.event.get(): 
            # if quit then close game
            if event.type == pygame.QUIT: 
                pygame.quit()

        # get keydown and send data
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                send_move("up")
            if event.key == pygame.K_DOWN:
                send_move("down")    
            if event.key == pygame.K_LEFT:
                send_move("left") 
            if event.key == pygame.K_RIGHT:
                send_move("right") 

        # get keyup and send data
        if event.type == pygame.KEYUP:
            if event.key == pygame.K_UP:
                send_stop("up")
            if event.key == pygame.K_DOWN:
                send_stop("down")
            if event.key == pygame.K_LEFT:
                send_stop("left")
            if event.key == pygame.K_RIGHT:
                send_stop("right")

        UpdateDisplay()
            
def recvGameUpdates():
    # constantly check for game updates
    while True:
        # data will be "POSXXXYYYXXXYYYXXXYYYXXXYYY"
        data = sock.recv(32).decode()
        if data[:3] == "POS":
            
            for i in range(4):
                x_vals = 3 + (i * 6)
                y_vals = 6 + (i * 6)

                #update player posititons
                positions[i][0] = int(data[x_vals:x_vals+3])
                positions[i][1] = int(data[y_vals:y_vals+3])

def UpdateDisplay():

    pygame.time.delay(10) 
    win.fill((0, 0, 0)) 
    # draw all players 
    for i in range(4):
        try:
            x, y = positions[i]
            pygame.draw.rect(win, (255, 0, 0), (x, y, player_width, player_height))
        except Exception as e:
            print(f"Error drawing player {i}: {e}")
    
    pygame.display.update() 
            
                              
#in match, play the game
def main():
    global playerNumber
    #connect, wait until game starts
    playerNumber = connect("127.0.0.1", 53333)
    print("Game Started. My player number is:", playerNumber)
    #game is now started
    # init_game()
    #make thread to receive game state updates (mutex needed)
    Thread(target = recvGameUpdates, args=()).start()
    #make thread for sending inputs (mutex needed for verifying legal inputs)
    inputs()

    while gameStarted:
        pass

    #game is over, terminate threads (with mutex)
    
    #reconnect for a new game, if desired


main()