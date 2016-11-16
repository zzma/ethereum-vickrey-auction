import serpent
from ethereum import tester, utils, abi
import random

contract = '''
event Notice(x:str)
event Integer(x:int)

data bidders[2](address, commit, bid_price)
data bid_total
data num_bidders
data max_bidders
data bid_winners[2](address, win_pnot rice)
data has_completed
data bid_timer_start
data check_timer_start

macro MIN_BIDDERS: 2
macro MAX_BIDDERS: 2
macro MAX_BID: 1000
macro BID_DURATION: 10
macro CHECK_DURATION: 10
macro index_of_addr($addr):
    $match_index = -1
    $i = 0
    while $i < self.num_bidders:
        if self.bidders[$i].address == $addr:
            $match_index = $i
        $i += 1
    $match_index
macro return_money():
    $i = 0
    while $i < self.num_bidders:
        send(0, self.bidders[$i].address, MAX_BID)
        $i += 1

def init():
    self.num_bidders = 0
    self.bid_total = 0
    self.has_completed = 0

# accepts sha3(choice, nonce) from the player
def add_bidder(bidder_commitment):
    # prevent max callstack exception
    if self.test_callstack() != 1:
        return(-1)

    # don't add bidder if not enough money sent
    if msg.value < MAX_BID:
        send(0, msg.sender, msg.value)
        return(-1)

    # return difference if too much money is sent
    if msg.value > MAX_BID:
        send(0, msg.sender, msg.value - MAX_BID)

    self.bid_total += MAX_BID

    # add bidders if bid pool and time window are still open
    if self.num_bidders < MAX_BIDDERS:
        if not self.bid_timer_start:
            self.bid_timer_start = block.number
        if block.number - self.bid_timer_start < BID_DURATION:
            self.bidders[self.num_bidders].address = msg.sender
            self.bidders[self.num_bidders].commit = bidder_commitment
            self.num_bidders = self.num_bidders + 1
            return(0)
        else:
            return(-1)
    else:
        return(-1)

# verify that the user's bid matches commitment
def check_bids(bid, nonce):
    # prevent max callstack exception
    if self.test_callstack() != 1:
        return(-1)

    # prevent money leakage
    if msg.value > 0:
        send(0, msg.sender, msg.value)
    if bid < 0 or bid > MAX_BID:
        return(-1)

    # search the array
    in = index_of_addr(msg.sender)
    if in == -1:
        log(type=Notice, text("Unable to find commitment for address"))
        return(-1)

    # make sure bid window is closed and check window is open
    if block.number - self.bid_timer_start > BID_DURATION-1:
        # start bid check window
        if not self.check_timer_start:
            self.check_timer_start = block.number
            # send back money if not enough for auction
        if self.num_bidders < MIN_BIDDERS:
            log(type=Notice, text("Not enough bidders to proceed with auction"))
            return_money()
            return(-1)
        if block.number - self.check_timer_start < CHECK_DURATION:
            if sha3([bid, nonce], items=2) == self.bidders[in].commit:
                log(type=Notice, text("Commit matches!"))
                self.bidders[in].bid_price = bid
                return(0)
            else:
                log(type=Notice, text("Commit doesn't match!"))
                return(-1)
        else:
            return(-1)
    else:
        log(type=Notice, text("Not within bid checking time window"))
        return(-1)

# calculate winning prices and receive refund
def finish_auction():
    # prevent max callstack exception
    if self.test_callstack() != 1:
        return(-1)

    # prevent money leakage
    if msg.value > 0:
        send(0, msg.sender, msg.value)

    # make sure an auction happened at all
    if self.num_bidders < MIN_BIDDERS:
        log(type=Notice, text("No auction occurred"))
        return(-1)

    # make sure both bidders have confirmed bid
    if self.bidders[0].bid_price and not self.bidders[1].bid_price:
        send(0, self.bidders[0].address, MAX_BID)
        return(-1)
    if self.bidders[1].bid_price and not self.bidders[0].bid_price:
        send(0, self.bidders[1].address, MAX_BID)
        return(-1)
    if not self.bidders[0].bid_price and not self.bidders[1].bid_price:
        return(-1)

    # make sure check window has closed and no one has won yet
    if not self.has_completed and block.number - self.check_timer_start > CHECK_DURATION - 1:
        # bids are tied, everyone gets money back, no winner
        if self.bidders[0].bid_price == self.bidders[1].bid_price:
            return_money()
        # winner pays other persons price, loser gets money back
        if self.bidders[0].bid_price > self.bidders[1].bid_price:
            send(0, self.bidders[0].address, MAX_BID - self.bidders[1].bid_price)
            send(0, self.bidders[1].address, MAX_BID)
        if self.bidders[1].bid_price > self.bidders[0].bid_price:
            send(0, self.bidders[0].address, MAX_BID)
            send(0, self.bidders[1].address, MAX_BID - self.bidders[0].bid_price)

        self.has_completed = 1
        return(0)
    else:
        return(-1)

def test_callstack():
    return(1)
'''

s = tester.state()
c = s.abi_contract(contract)

tobytearr = lambda n, L: [] if L == 0 else tobytearr(n / 256, L - 1)+[n % 256]

print("Welcome to the Vickrey auction.")

# Set up bidders
bidder_1_address = tester.a0
bidder_2_address = tester.a1
bidder_1_key = tester.k0
bidder_2_key = tester.k1

# Generate random bids for each bidder
bidder_1_bid = random.randint(0,1000)
bidder_2_bid = random.randint(0,1000)
bidder_1_bid_bytes = ''.join(map(chr, tobytearr(bidder_1_bid, 32)))
bidder_2_bid_bytes = ''.join(map(chr, tobytearr(bidder_2_bid, 32)))

# Make commitment with nonce
bidder_1_nonce = ''.join(map(chr, tobytearr(random.randint(0,2**256-1), 32)))
bidder_2_nonce = ''.join(map(chr, tobytearr(random.randint(0,2**256-1), 32)))
bidder_1_commitment = utils.sha3(''.join([bidder_1_bid_bytes, bidder_1_nonce]))
bidder_2_commitment = utils.sha3(''.join([bidder_2_bid_bytes, bidder_2_nonce]))

# Send commitment and max bid
o = c.add_bidder(bidder_1_commitment, sender=bidder_1_key, value=1000)
print("Bidder 1 (secret bid {}) Added: {}").format(bidder_1_bid,o)
o = c.add_bidder(bidder_2_commitment, sender=bidder_2_key, value=1000)
print("Bidder 2 (secret bid {}) Added: {}").format(bidder_2_bid,o)

# 10 blocks of time are allowed for bidders to enter - after which we block new commitments
s.mine(11)

# Gather message + commitments
o = c.check_bids(bidder_1_bid, bidder_1_nonce, sender=bidder_1_key)
print("Bidder 1 Checked: {}").format(o)
o = c.check_bids(bidder_2_bid, bidder_2_nonce, sender=bidder_2_key)
print("Bidder 2 Checked: {}").format(o)

# Wait some time - at least 10 blocks - after which we block commitment checks
s.mine(11)

print 'Bidder 1 balance before auction close: %d' % (s.block.get_balance(bidder_1_address))
print 'Bidder 2 balance before auction close: %d' % (s.block.get_balance(bidder_2_address))
# calculate winning prices and receive refund
o = c.finish_auction()
print("Auction finished: {}").format(o)
print 'Bidder 1 balance after auction close: %d' % (s.block.get_balance(bidder_1_address))
print 'Bidder 2 balance after auction close: %d' % (s.block.get_balance(bidder_2_address))
