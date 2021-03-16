import socketserver
import socket
from copy import deepcopy
import threading
from threading import Thread, Lock
from dpwa.messaging import send_message, recv_message
from queue import Queue
import time
MESSAGE_TYPE_FETCH_PARAMETERS = 1



TCP_SOCKET_BUFFER_SIZE = 8 * 1024 * 1024

rx_have_state=False
rx_lock = Lock()

rx_state=None
rx_payload=None

class Myserver(socketserver.BaseRequestHandler):
    
    def handle(self):
        global rx_have_state
        global rx_lock  
        global rx_state
        global rx_payload

        client_sock=self.request 
        while True:  
            try:
                # 相应模型数据请求
                message_type, _, _ = recv_message(client_sock)
                assert message_type == MESSAGE_TYPE_FETCH_PARAMETERS

                # print(message_type)
                # print('handle',rx_have_state)
                # print('lock',rx_lock)
                # time.sleep(10)
                # send the result
                if not rx_have_state:
                    send_message(client_sock, MESSAGE_TYPE_FETCH_PARAMETERS)
                else:
                    with rx_lock:
                        send_message(client_sock, MESSAGE_TYPE_FETCH_PARAMETERS, rx_state, rx_payload)


            except (BrokenPipeError, ConnectionResetError):
                print("Other end had a timeout, socket closed")
                client_sock.close()
                break

            except Exception as e:
                print("Error handling request (closing socket, client will retry)", e)
                client_sock.close()
                break        


class RxThread(Thread):
    def __init__(self, bind_host, bind_port):
        super(RxThread, self).__init__()


        self.bind_host = bind_host
        self.bind_port = bind_port
        self.server=None
        



    def set_current_state(self, state, payload):  #payload表示训练的网络参数
        # We're using a lock because we cannot update the state and payload
        # While it is sent to a remote peer
        global rx_have_state
        global rx_lock  
        global rx_state
        global rx_payload
        # print('set_current_state ... ',rx_have_state)
        with rx_lock:
            #deepcopy完全真正意义上的复制
            rx_state = deepcopy(state)
            rx_payload = deepcopy(payload)
            rx_have_state = True
        # print('state is finished...',rx_have_state)

        # time.sleep(5)

    def run(self):
        print("RxThread: run()")
        # input('输入回车继续')
        try:
            # while True:
                # server = socketserver.ThreadingTCPServer((self.bind_host,self.bind_port),Myserver)
            self.server=socketserver.ThreadingTCPServer((self.bind_host,self.bind_port),Myserver)
            print ("socket server start.....")
            # time.sleep(2)
            self.server.serve_forever()
            print('sever has been shutdowned')
        except Exception as e:
               print('===>Rxthead exception:',self.bind_host,self.bind_port)
               print(str(e))

        

    def shutdown(self):
        # TODO(guyz): Implement using eventfd...
        # raise NotImplementedError
        self.server.shutdown()


def _create_tcp_socket():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, TCP_SOCKET_BUFFER_SIZE)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, TCP_SOCKET_BUFFER_SIZE)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    return sock


class TxThread(Thread):
    def __init__(self, peerhost,peerport):   # socket_timeout_ms):
        super(TxThread, self).__init__()
        self.peerhost=peerhost
        self.peerport=peerport
        self.sock=None
        self._queue = Queue(1)
        self.peer_payload = None
        self.peer_message = None


    def run(self):
        print("TxThread: run()")

        self.sock=_create_tcp_socket()
        time.sleep(1)
        self.sock.connect((self.peerhost, self.peerport))
        while True:
            witem = self._queue.get(block=True)   #如果队列中没有值可以返回，就会被阻塞在这里
            if not witem:
                print("Exiting TxThread...")
                break

            # Wait until we succefully fetch from a peer,
            # or until we don't have any peers to fetch from
            done = False
            while not done:

                try:
                    # Send a fetch parameters request
                    # LOGGER.debug("TxThread: Sending message fd=%d", peer.sock.fileno())
                    send_message(self.sock, MESSAGE_TYPE_FETCH_PARAMETERS)  #MESSAGE_TYPE_FETCH_PARAMETERS=1
                    message_type, self.peer_message, self.peer_payload = recv_message(self.sock)
                    assert message_type == MESSAGE_TYPE_FETCH_PARAMETERS


                    #根据是否返回有意义的payload来结束通信
                    done = self.peer_payload is not None

                except socket.timeout:
                    # print("TxThread: peer %s timeout, restarting connection...", peer.name)
                    print('timeout')
                    self.sock.close()
                    self.sock = None
      

                except:
                    print('error connecting',self.peerport)
                    raise ZeroDivisionError('error connecting')
                    # print("Error connecting with peer %s.", peer.name)


            self._queue.task_done()

        print("TxThread: exiting...")
        self._queue.task_done()

    def fetch_send(self):
        """Initiate an async fetch_parameters request.

        Selects a random peer and fetch its latest parameters.
        """

        self._queue.put(True)

    def fetch_wait(self):
        """Waits for the fetch_parameters request to complete."""
        self._queue.join()
        return self.peer_message, self.peer_payload

    def shutdown(self):
        self._queue.put(False)
        print('shutdown join ... ')
        # self.join()
        print('-----------------------')
        self._queue.join()
        print('-----------------------')
        # print('shutdown join ... ')
        # self.join()
