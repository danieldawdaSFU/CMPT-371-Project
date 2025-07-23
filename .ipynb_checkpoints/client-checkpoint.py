import socket
sock = socket.socket(
    socket.AF_INET,
    socket.SOCK_STREAM)

MESSAGE_HEADER_LENGTH = 1

playerNumber = -1
gameStarted = False

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
            print(str(playerNumber))
            #send player number back as confirmation that we are active
            sock.send(data)

    return playerNumber

#in match, play the game
def main():
    global playerNumber
    #connect, wait until game starts
    playerNumber = connect("127.0.0.1", 53333)
    print("Game Started. My player number is:", playerNumber)
    #game is now started

    #make thread for sending inputs (mutex needed for verifying legal inputs)
    #make thread to receive game state updates (mutex needed)

    while gameStarted:
        pass

    #game is over, terminate threads (with mutex)
    
    #reconnect for a new game, if desired


main()