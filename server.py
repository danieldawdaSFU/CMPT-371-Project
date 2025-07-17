import socket
from threading import Thread
from threading import Lock
from game import updatePositions
import time

sock = socket.socket(
    socket.AF_INET,
    socket.SOCK_STREAM)

#server's IP/port. Change as needed, should be part of client UI to choose right port/IP.
sock.bind(("127.0.0.1", 53333))

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
# itinital game state dict
gameState = {'pos': [[100, 100],
                    [200, 100],
                    [100, 200],
                    [200, 200]]}

### end Mutex locked variables



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
                pass
            except:
                #close socket on error
                pass
        

#function to send the current game state to all players
def broadcastGameUpdates():
    while True:
        for conn in connectionList:
            # format data ("POSXXXYYYXXXYYYXXXYYYXXXYYY")
            data = ("POS"+str(gameState["pos"][0][0]).zfill(3)+
                            str(gameState["pos"][0][1]).zfill(3)+
                            str(gameState["pos"][1][0]).zfill(3)+
                            str(gameState["pos"][1][1]).zfill(3)+
                            str(gameState["pos"][2][0]).zfill(3)+
                            str(gameState["pos"][2][1]).zfill(3)+
                            str(gameState["pos"][3][0]).zfill(3)+
                            str(gameState["pos"][3][1]).zfill(3))
            conn.send(data.encode())
            time.sleep(0.01)

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
                    data = connection.recv(9)
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
    with mutex:
        connectionList = connectionsList
        for conn in connectionList:
            #send all clients the "GO" message. They should already have their player number
            conn.send("GAMESTRT".encode())

            t = Thread(target = handleConnection, args=(connection, len(connectionsList)-1))
            t.start()
            clientThreads.append(t)
        gameStarted = True
        

        
    return

def initInputs():
        
        # launch a thread for each clients movement
        for conn in connectionList:
            Thread(target = inputs, args=(conn,)).start()

def inputs(conn):

    idx = connectionList.index(conn)
    while True:
        data = conn.recv(32).decode()
        with mutex:
            # if recv MOV data then mov based on dir
            if "MOV" in data:
                # print("START")
                if "up" in data:
                    playerInputs[idx][0] = True
                elif "left" in data:
                    playerInputs[idx][1] = True
                elif "down" in data:
                    playerInputs[idx][2] = True
                elif "right" in data:
                    playerInputs[idx][3] = True
                
            elif "STOP" in data:
                # print("STOP")
                if "up" in data:
                    playerInputs[idx][0] = False
                elif "left" in data:
                    playerInputs[idx][1] = False
                elif "down" in data:
                    playerInputs[idx][2] = False
                elif "right" in data:
                    playerInputs[idx][3] = False

                
                # print(playerInputs)

def updateGameState():

    while True:
        gameState['pos'] = updatePositions(playerInputs, gameState['pos'])
        time.sleep(0.005)




def main():
    #loop so we can start new games afterwards
    global gameStarted
    while True:
        #start game
        getInitPlayers()
        
        #new inputs come from threads, mutex game logic
        initInputs()
        
        #run game logic
        Thread(target = updateGameState, args=()).start()

        #send new game state
        broadcastGameUpdates()
        
        #game end
        with mutex:
            gameStarted = False

        #make sure all threads close
        for thread in clientThreads:
            thread.join()

main()