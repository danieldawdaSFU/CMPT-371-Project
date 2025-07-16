import socket
from threading import Thread
from threading import Lock

sock = socket.socket(
    socket.AF_INET,
    socket.SOCK_STREAM)

#server's IP/port. Change as needed, should be part of client UI to choose right port/IP.
sock.bind(("", 53333))

mutex = Lock() #general mutex lock for player state changes (new inputs, changing connectionsList, etc)
#### Mutex locked variables
connectionList = []
clientThreads = []
gameStarted = False

#North, West, South, East movement vectors for each player
playerInputs = [[False, False, False, False]*4]
gameState = []

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
    pass
    #todo

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



def main():
    #loop so we can start new games afterwards
    global gameStarted
    while True:
        #start game
        getInitPlayers()
        
        #new inputs come from threads, mutex game logic
        
        #run game logic

        #send new game state
        broadcastGameUpdates()
        
        #game end
        with mutex:
            gameStarted = False

        #make sure all threads close
        for thread in clientThreads:
            thread.join()

main()