import socket
from threading import Thread
from threading import Lock
import time

sock = socket.socket(
    socket.AF_INET,
    socket.SOCK_STREAM)

#Number of bytes for a message header. ex "PLYRMOVE"
MESSAGE_HEADER_LENGTH = 8

#server's IP/port. Change as needed, should be part of client UI to choose right port/IP.
sock.bind(("localhost", 53333))

mutex = Lock() #general mutex lock for player state changes (new inputs, changing connectionsList, etc)
#### Mutex locked variables
connectionList = []
clientThreads = []
gameStarted = False

#North, West, South, East movement vectors for each player
playerInputs = [[False, False, False, False],
                [False, False, False, False],
                [False, False, False, False],
                [False, False, False, False]]

# 10x10 grid (each tile is 80 pixels)
GRID_WIDTH = GRID_HEIGHT = 10

# itinital game state dict (X/Y)
# players start at the center of the grid
gameState = {'pos': [[4, 4],
                     [5, 4],
                     [4, 5],
                     [5, 5]]}

### end Mutex locked variables

#remove a client/thread (dont call from a thread when possible)
def removeConnection(index):
    #do not get mutex before calling
    try:
        if clientThreads[index] != None:
            with mutex:
                clientThreads[index] = None
                connectionList[index] = None
    except:
        print("Failed to join thread when removing connection.")

#handle all inputs from players, outputs will be handled in bulk via the broadcastGame() function
def handleConnection(connection, index):
    global gameStarted
    while True:
        with mutex:
            if gameStarted == False:
                #terminate connection
                connection.close()
                #end this thread
                return
        try:
            #general receive logic
            if connectionList[index] == None:
                #error, block thread.
                while 1:
                    pass

            data = connection.recv(MESSAGE_HEADER_LENGTH).decode()
            if data == "PLYRMOVE":
                #read <N/S/E/W><1/0>
                data = connection.recv(2).decode()
                with mutex:
                    # if recv PLYRMOVE data then move based on dir
                    for dirr in range(len(playerInputs[index])):
                        playerInputs[index][dirr] = False
                    if "N" in data:
                        playerInputs[index][0] = (data[1] == "1")
                    elif "S" in data:
                        playerInputs[index][1] = (data[1] == "1")
                    elif "W" in data:
                        playerInputs[index][2] = (data[1] == "1")
                    elif "E" in data:
                        playerInputs[index][3] = (data[1] == "1")
        except:
            #close socket on error #todo
            pass


#function to send the current game state to all players
def broadcastGameUpdates():
    with mutex:
        data = ("PLYRUPDT"+str(gameState["pos"][0][0]).zfill(2)+
                        str(gameState["pos"][0][1]).zfill(2)+
                        str(gameState["pos"][1][0]).zfill(2)+
                        str(gameState["pos"][1][1]).zfill(2)+
                        str(gameState["pos"][2][0]).zfill(2)+
                        str(gameState["pos"][2][1]).zfill(2)+
                        str(gameState["pos"][3][0]).zfill(2)+
                        str(gameState["pos"][3][1]).zfill(2))
    for conn in range(len(connectionList)):
        # format data ("PLYRUPDTXXYYXXYYXXYYXXYY")
        try:
            if connectionList[conn] != None:
                connectionList[conn].send(data.encode())
        except Exception as e:
            print(f"An unexpected error occurred during broadcast: {e}")
            #they left, close socket and join thread
            removeConnection(conn)

#Fill the connectionsList, and create threads for them
def getInitPlayers():
    #Start with no connections. Clients can reconnect on their own after a game
    connectionsList = []
    while True:
        #while true since we cannot check the len of connectionsList without mutex
        if len(connectionsList) == 4:
            #send everyone their player number. If it fails then they left, and we try again
            index = 1
            toRemove = []
            for connection in connectionsList:
                try:
                    #send player number
                    connection.send(("PLYRJOIN" + str(index)).encode())

                    #player should echo their player number
                    data = connection.recv(MESSAGE_HEADER_LENGTH + 1)
                    if data == b'':
                        toRemove.append(connection)
                except Exception as e:
                    print(f"An unexpected error occurred: {e}")
                    #sending failed, so remove that client.
                    toRemove.append(connection)

                index += 1
            for conn in toRemove:
                connectionsList.remove(conn)

            if len(connectionsList) == 4:
                #everyone is still ready
                break
        else:

            #get new client
            #buffer as many as we need
            sock.listen(4-len(connectionsList))
            connection, address = sock.accept()
            print("New Connection")

            #update list
            connectionsList.append(connection)

    #send startGame message (since all players have received their number)
    #   If players leave from this point, then we will just play with less players
    #update global list, and start threads
    global gameStarted
    global connectionList
    global clientThreads
    dropList = []
    with mutex:
        connectionList = connectionsList
        for conn in range(len(connectionList)):
            #send all clients the "GO" message. They should already have their player number
            try:
                connectionList[conn].send("GAMESTRT".encode())
            except:
                dropList.append(conn)
                #failed to send to client, we will just ignore them then. Remove socket/thread
                print("Failed to send game start to some players. removing them")

            t = Thread(target = handleConnection, args=(connectionList[conn], conn))
            t.start()
            clientThreads.append(t)
        gameStarted = True
    for i in dropList:
        removeConnection(i)

    return

def updatePositions(playerInputs, positions):
    with mutex:
        for player in range(len(positions)):
            if playerInputs[player][0]:
                #N
                positions[player][1] -= 1
                positions[player][1] %= GRID_HEIGHT
            elif playerInputs[player][1]:
                #S
                positions[player][1] += 1
                positions[player][1] %= GRID_HEIGHT
            elif playerInputs[player][2]:
                #W
                positions[player][0] -= 1
                positions[player][0] %= GRID_WIDTH
            elif playerInputs[player][3]:
                #E
                positions[player][0] += 1
                positions[player][0] %= GRID_WIDTH

def updateGameState():
    updatePositions(playerInputs, gameState['pos'])

def main():
    #loop so we can start new games afterwards
    global gameStarted
    while True:
        #start game
        getInitPlayers()


        #run game logic
        while gameStarted:
            #send new game state
            updateGameState()
            broadcastGameUpdates()
            time.sleep(0.5)

        #game end
        with mutex:
            gameStarted = False

        #make sure all threads close and sockets close
        for thread in range(len(clientThreads)):
            removeConnection(thread)

main()