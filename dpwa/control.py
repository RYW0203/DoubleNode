from dpwa.conn import RxThread, TxThread



class DpwaControl:
    def __init__(self, name,myPort,peerPort):  #, config_file):
        self.name = name
        # The clock is used to keep track of the model's age in terms of
        # training samples trained so far (increase by 1 in update_send())
        self.clock = 0
        self.fetching = False

        #from .conn import RxThread, TxThread
        host='localhost'
  
        self.rx = RxThread(host, myPort)
        self.tx = TxThread(host,peerPort)

        # input()
        self.rx.start()
        self.tx.start()


    def update_send(self, parameters, loss): #parameters为训练网络的参数
        """Initiate an update to the cluster.

        Performs 2 things:
        1. Updates the local server with the latest parameters, so other peers could fetch them
        2. Initiate a fetch parameters request to a random peer.
        """
        # Increase the clock value
        self.clock += 1

        # Serve the new parameters
        state = {'clock': self.clock, 'loss': loss}
        # 在rx线程中保存此时的loss和模型参数等
        self.rx.set_current_state(state, parameters)

        self.fetching = True
        self.tx.fetch_send()



    def update_wait(self, loss):
        """Waits for the cluster update to finish.

        Waiting for the fetch parameters request to complete (blocking)
        """
        if not self.fetching:
            return None, 0

        peer_state, peer_parameters = self.tx.fetch_wait()
        self.fetching = False
        # There may be no peers listening
        if peer_parameters is None:
            return None, 0

        peer_clock = peer_state['clock']
        peer_loss = peer_state['loss']


        factor = 0.5 # self.interpolation(self.clock, peer_clock, loss, peer_loss)



        # Update local clock
        new_clock = factor * peer_clock + (1 - factor) * self.clock

        # LOGGER.debug("update_wait(): (clock=%f, peer_clock=%f), (loss=%s, peer_loss=%f) => factor=%f, new_clock=%f",
        #              self.clock, peer_clock, loss, peer_loss, factor, new_clock)

        self.clock = new_clock
        return peer_parameters, factor

    def shutdown(self):
        self.rx.shutdown()
        self.tx.shutdown()
