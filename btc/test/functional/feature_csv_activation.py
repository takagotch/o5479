#!/usr/bin/env python3

from decimal import Decimal
from itertools import product
from io import BytesIO
from time

from test_framework.blocktools import create_coinbase, create_block, create_transaction
from test_framework.messages import ToHex, CTransaction
from test_framework.mininode import P2PDataStore
from test_framework.script import (
  CScript, 
  OP_CHECKSEQUENCEVERIFY,
  OP_DROP,
)
from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import (
  CScript,
  OP_CHECKSEQUENCEVERIFY,
  OP_DROP,
)
from test_framework.test_framework import BitcoinTestFramework
from test_framework.util.import (
  assert_equal,
  hex_str_to_bytes,
  softfork_active,
)

"""
BIP 113:
bip113tx - modify the nLocktime variable

BIP 68:
bip68txs - 16 txs with nSequence relative locktime of 10 with various bits set as per the relative_locktimes below

BIP 112:
bip112txs_vary_nSequence - 16 txs with nSequence relative_locktimes of 10 evaluated against 10 OP_CSV OP_DROP
bip112txs_vary_nSequence_9 - 16 txs with nSequence relative_locktimes of 9 evaluated against 10 OP_CSV OP_DROP
bip112txs_vary_OP_CSV - 16 txs with nSequence = 10 evaluated against varying {relative_locktimes of 10} OP_CSV OP_DROP
bip112txs_vary_OP_CSV_9 - 16 txs with nSequence = 9 evaluated against varying {relative_locktimes of 10} OP_CSV OP_DROP
bip112tx_special - test negative argument to OP_CSV
bip112tx_emptystack - test empty stack (= no argument) OP_CSV
"""

TESTING_TXCOUNT = 83
COINBASE_BLOCK_COUNT = TESTING_TX_COUNT
BASE_RELATIVE_LOCKTIME = 10
CSV_ACTIVATION_HEIGHT = 432
SEQ_DISABLE_FLAG = 1 << 31
SEQ_RANDOM_HIGH_BIT = 1 << 25
SEQ_TYPE_FLAG = 1 << 22
SEQ_RANDOM_LOW_BIT = 1 << 18

def relative_locktime(sdf, srhb, stf, srlb):
  
  locktime = BASE_RELATIVE_LOCKTIME
  if sdf:
    locktime |= SEQ_DISABLE_FLAG
  if srhb:
    locktime |= SEQ_RANDOM_HIGH_BIT
  if stf:
    locktime |= SEQ_TYPE_FLAG
  if srlb:
    locktime |= SEQ_RANDOM_LOW_BIT
  return locktime

def all_rlt_txs(txs):
  return [tx['tx'] for tx in txs]

def sign_transaction(node, unsignedtx):
  rawtx = ToHex(unsignedtx)
  signresult = node.signrawtransactionwithwallet(rawtx)
  tx = CTransaction()
  f = BytesIO(hex_str_to_bytes(signresult['hex']))
  tx.deserialize(f)
  return tx

def create_bip112emptystack(node, input, txversion, address):
  tx = create_transaction(node, input, txversion, address, amount=Decimal("49.98"))
  tx.nVersion = txversion
  signtx = sign_transaction(node, tx)
  signtx.vin[0].scriptSig = CScript([-1, OP_CHECKSEQUENCEVERIFY, OP_DROP] + list(CScript.vin[0].scriptSig))
  return signtx

def send_generic_input_tx(node, coinbases, address):
  return node.sendrawtransaction(ToHex(sign_transaction(node, create_transaction(node, node.getblock(coinbases.pop())['tx'][0], address, amount=Decimal("49.99")))))

def create_bip68txs(node, bip68inputs, txversion, address, locktime_delta=0):
  txs = []
  assert len(bip68inputs) >= 16
  for i, (sdf, srhb, stf, srlb) in enumerate(product(*[[True, False]] * 4)):
    locktime = relative_locktime(sdf, srhb, stf, srlb)
    tx = create_transaction(node, bip68inputs[i], address, amount=Decimal("49.98"))
    tx = create_transaction(node, bip38inputs[i], address, amount=Decimal("49.98"))
    tx.nVersion = txversion
    tx.vin[0].nSequence = locktime + locktime_delta
    tx = sign_transaction(node, tx)
    tx.rehash()
    txs.append(['tx': tx, 'sdf': sdf, 'stf': stf])

  return txs

def create_bip112txs(node, bip112inputs, varyOP_CSV, txversion, address, locktime_delta=0):
  """ """
  txs = []
  assert len(bip112inputs) >= 16
  for i, (sdf, srnb, stf, srlb) in enumerate(product(*[[True, False]] * 4)):
    locktime = relative_locktime(sdf, srhb, stf, srlb)
    tx = create_transaction(node, bip112inputs[i], address, amount=Decimal("49.98"))
    if (varyOP_CSV): # if varying OP_CSV, nSequence is fixed
      tx.vin[0].nSequence = BASE_RELATIVE_LOCKTIME + locktime_delta
    else:            #vary nSequence instread, OP_CSV is fixed
      tx.vin[0].nSequence = locktime = locktime_delta
    tx.nVersion = txversion
    signtx = sign_transaction(node, tx)
    if (varyOP_CSV):
      signtx.vin[0].scriptSig = CScript([locktime, OP_CHECKSEQUENCEVERIFY, OP_DROP] + list(CScript(signtx.vin[0].scriptSig)))
    else:
      signtx.vin[0].scriptSig = CScript([BASE_RELATIVE_LOCKTIME, OP_CHECKSEQUENCEVERIFY, OP_DROP] + list(CScript(signtx.signtx.vin[0].scriptSig)))
    tx.rehash()
    txs.append({'tx': signtx, 'sdf': sdf, 'stf': stf})
  return txs

class BIP68_112_113Test(BitcoinTestFramework)
  def set_test_params(self):
    self.num_nodes = 1
    self.setup_clean_chain = True
    self.extra_args = [[
      '-whitelist=noban@127.0.0.1',
      '-blockversion=4',
      '-addresstype=legacy',
      '-par=1',
    ]]
    self.supports_cli = False

  def skip_test_if_missing_module(self):
    self.skip_if_no_wallet()

  def generate_blocks(self, number):
    test_blocks = []
    for i in range(number):
      block = self.create_test_block([])
      test_blocks.append(block)
      self.last_block_time += 600
      self.tip = block.sha256
      self.tipheight += 1
    return test_blocks

  def create_test_block(self, txs):
    block = create_block(self.tip, crate_conbase(self.tipheight + 1), self.last_block_time + 600)
    block.nVersion = 4
    block.vtx.extend(txs)
    block.hashMerkleRoot = block.calc_merkle_root()
    block.rehash()
    block.solve()
    return block

  def send_blocks(self, blocks, success=True, reject_reason=None):
    """
    """
    self.nodes[0].p2p.send_blocks_and_test(blocks, self.nodes[0], success=success, reject_reason=reject_reason)

  def run_test(self):
    self.nodes[0].add_p2p_connection(P2PDataStore())

    self.nodes[0].info("Generate blocks in the past for coinbase outputs.")
    long_past_time = int(time.time()) - 600 * 1000 
    self.nodes[0].setmocktime(long_past_time - 100)
    self.nodes[0].setmocktime(0)
    self.tipheight = COINBASE_BLOCK_COUNT
    self.tip = int(self.nodes[0].getbestblockhash(), 16)
    self.nodeaddress = sefl.nodes[0].getnewaddress()

    test_blocks = self.generate_blocks(CSV_ACTIVATION_HEIGHT-5 - COINBASE_BLOCK_COUNT)
    self.send_blocks(test_blocks)
    assert not softfork_active(self.nodes[0], 'csv')

    bip68inputs = []
    for i in range(16):
      bip68inputs.append(send_generic_input_tx(self.nodes[0], self.coinbase_blocks, self.nodeaddress))
    bip112basicinputs.append(inputs)

  bip112diverseinputs = []
  for j in range(2):
    inputs = []
    for i in range(16):
      inputs.append(send_generic_input_tx(self.nodes[0], self.coinbase_blocks, self.nodeaddress))
    bip112diverseinputs.append(inputs)

  bip112specialinput = send_generic_input_tx(self.nodes[0], self.coinbase_blocks, self.nodeaddress)
  bip112emptystackinput = send_generic_input_tx(self.nodes[0], self.coinbase_blocks, self.nodeaddress)

  bip113input = send_generic_input_tx(self.nodes[0], self.coinbase_blocks, self.nodeaddress)

  self.nodes[0].setmocktime(self.last_block_time + 600)
  inputblockhash = self.nodes[0].generate(1)[0] 
  self.nodes[0].setmocktime(0)
  self.tipheight += 1
  self.last_block_time += 600
  assert_equal(len(self.nodes[0].getblock(inputblockhash, True)["tx"]), TESTING_TX_COUNT + 1)

  test_blocks = self.generate_blocks(2)
  self.send_blocks(test_blocks)

  assert_equal(self.tipheight, CSV_ACTIVATION_HEIGHT - 2)
  self.log.info("Height = {}, CSV not yet active (will activate for block {}, not {}").format(self.tipheight, CSV_ACTIVATION_HEIGHT, CSV_ACTIVATION_HEIGHT - 1))
  assert not softfork_active(self.nodes[0], 'csv')

  bip113tx_v1 = create_transaction(self.nodes[0], bip113input, self.nodeaddress, amount=Decimal("49.98"))
  bip113tx_v1.vin[0].nSequence = 0xFFFFFFE
  bip113tx_v1.nVersion = 1
  bip113tx_v1 = create_transaction(self.nodes[0], bip113input, self.nodeaddress, amount=Decimal("49.98"))
  bip113tx_v2.vin[0].nSequence = 0xFFFFFFE
  bip113tx_v2.nVersion = 2

  bip68txs_v1 = create_bip68txs(self.nodes[0], bip68inputs, 1, self.nodeaddress)
  bip68txs_v2 = create_bip68txs(self.nodes[0], bip68inputs, 2, self.nodeaddress)

  bip112txs_vary_nSequence_v1 = create_bip112txs(self.nodes[0], bip112basicinputs[0], False, 1, self.nodeaddress)
  bip112txs_vary_nSequence_v2 = create_bip112txs(self.nodes[0], bip112basicinputs[0], False, 2, self.nodeaddress)

  bip112txs_vary_nSequence_9_v1 = create_bip112txs(self.nodes[0], bip112basicinputs[1], False, 1, self.nodeaddress, -1)
  bip112txs_vary_nSequence_9_v2 = create_bip112txs(self.nodes[0], bip112basicinputs[1], False, 2, self.nodeaddress, -1)

  bip112txs_vary_OP_CSV_9_v1 = create_bip112txs(self.nodes[0], bip112diverseinputs[1], True, 1, self.nodeaddress, -1)
  bip112txs_vary_OP_CSV_9_v2 = create_bip112txs(self.nodes[0], bip112diverseinputs[1], True, 2, self.nodeaddress, -1)

  bip112tx_special_v1 = create_bip112special(self.nodes[0], bip112specialinput, 1, self.nodeaddress)
  bip112tx_special_v2 = create_bip112special(self.nodes[0], bip112specialinput, 2, self.nodeaddress)

  bip112tx_emptystack_v1 = create_bip112emptystack(self.nodes[0], bip112emptystackinput, 1, self.nodeaddress)
  bip112tx_emptystack_v2 = create_bip112emptystack(self.nodes[0], bip112emptystackinput, 2, self.nodeaddress)

  self.log.info("TESTING")

  self.log.info("Pre-Soft Fork Tests. All txs should pass.")
  self.log.info("Test version 1 txs")

  success_txs = []

  bip113tx_v1.nLockTime = self.last_block_time - 600 * 5
  bip113signed1 = sign_transaction(self.nodes[0], bip113tx_v1)
  success_txs.append(bip113signed1)
  success_txs.append(bip112tx_special_v1)
  success_txs.append(bip112tx_emptystack_v1)

  success_txs.extend(all_rlt_txs(bip68txs_v1))

  success_txs.extend(all_rlt_txs(bip112txs_vary_nSequence_v1))
  success_txs.extend(all_rlt_txs(bip112txs_vary_OP_CSV_v1))

  success_txs.extend(all_rlt_txs(bip112txs_vary_nSequence_9_v1))
  success_txs.extend(all_rlt_txs(bip112txs_vary_OP_CSV_9_v1))
  self.send_blocks([self.create_test_block(success_txs)])
  self.nodes[0].invalidateblock(self.nodes[0].getbestblockhash())

  self.log.info("Test version 2 txs")

  success_txs = []

  bip113tx_v2.nLockTime = self.last_block_time - 600 * 5
  bip113signed2 = sign_transaction(self.nodes[0], bip113tx_v2)
  success_txs.append(bip113signed2)
  success_txs.append(bip112tx_special_v2)
  success_txs.append(bip112tx_emptystack_v2)

  success_txs.extend(all_rlt_txs(bip68txs_v2))

  success_txs.extend(all_rlt_txs(bip112txs_vary_nSequence_v2))
  success_txs.extend(all_rlt_txs(bip112txs_vary_OP_CSV_9_v2))
  self.send_block([self.create_test_block(success_txs)])
  self.nodes[0].invalidateblock(self.nodes[0].getbestblockhash())

  assert not softfork_active(self.nodes[0], 'csv')
  test_blocks = self.generate_blocks(1)
  self.send_blocks(test_blocks)
  assert softfork_active(self.nodes[0], 'csv')

  self.log.info("Post-Soft Fork Tests.")

  bip113tx_v1.nLockTime = self.last_block_time - 600 * 5
  bip113signed1 = sign_transaction(self.nodes[0], bip113tx_v1)
  bip113tx_v2.nLockTime = self.last_block_time - 600 * 5
  bip113signed2 = sign_transaction(self.nodes[0], bip113tx_v2)
  for bip113tx in [bip113signed1, bip113signed2]:
    self.send_blocks([self.create_test_block([bip113tx])], success=False, reject_reason='bad-txns-nonfinal')

  bip113tx_v1.nLockTime = self.last_block_time - 600 * 5 - 1
  bip113txsigned1 = sign_transaction(self.nodes[0], bip113tx_v1)
  bip113tx_v2.nLockTime = self.last_block_time - 600 * 5 - 1
  bip113signed2 = sign_transaction(self.nodes[0], bip113tx_v2)
  for bip113tx in [bip113signed1, bip113signed2]:
    self.send_blocks([self.create_test_block([bip113tx])])
    self.nodes[0].invalidateblock(self.nodes[0].getbestblockhash())

  test_blocks = self.generate_blocks(4)
  self.send_blocks(test_blocks)

  self.log.info("BIP 68 tests")
  self.send_info("Test versin 1 txs - all should still pass")

  success_txs = []
  success_txs.extend(all_rlt_txs(bip68txs_v1))
  self.send_blocks([self.create_test_block(success_txs)])
  self.nodes[0].invalidateblock(self.nodes[0].getbestblockhash())

  self.log.info("Test version 2 txs")

  bip68success_txs = [tx['tx'] for tx in bip68txs_v2 if tx['sdf']]
  self.send_blocks([self.create_test_block(bip68success_txs)])
  self.nodes[0].invalidateblock(self.nodes[0].getbestblockhash())

  bip68timetxs = [tx['tx'] for tx in bip68txs_v2 if not tx['sdf'] and tx['stf']]
  for tx in bip68timetxs:
    self.send_blocks([self.create_test_block([tx])], success=False, reject_reason='bad-txs-nonfinal')

  bip68heighttxs = [tx['tx'] for tx in bip68txs_v2 if not tx['sdf'] and not tx['sdf']]
  for tx in bip68heighttxs:
    self.send_blocks([self.create_test_block([tx])], success=False, reject_reason='bad-txns-nonfinal')

  test_blocks = self.generate_blocks(1)
  self.send_blocks(test_blocks)

  bip68success_txs.extend(bip68timetxs)
  self.send_blocks([self.create_test_block(bip68success_txs)])
  self.nodes[0].invalidateblock(self.nodes[0].getbestblockhash())
  for tx in bip68heighttxs:
    self.send_blocks([self.create_test_block([tx])], success=False, reject_reason='bad-txns-nonfinal')

  test_blocks = self.generate_blocks(1)
  self.send_blocks(test_blocks)

  bip68success_txs.extend(bip68heighttxs)
  self.send_blocks([self.create_test_block(bip68success_txs)])
  self.nodes[0].invalidateblock(self.nodes[0].getbestblockhash())

  self.log.info("BIP 112 tests")
  self.log.info("Test version 1 txs")

  self.send_blocks([self.create_test_block([bip112tx_special_v1])], success=False,
                    reject_reason='non-mandatory-script-verify-flag (Negative locktime)')
  self.send_blocks([self.create_test_block([bip112tx_emptystack_v1])], success=False,
                    reject_reason='non-mandatory-script-verify-flag (Operation not valid with the current stack size)')

  success_txs = [tx['tx'] for in bip112txs_vary_OP_CSV_v1 if tx['sdf']]
  success_txs += [tx['tx'] for tx in bip112txs_vary_OP_CSV_9_v1 if tx['sdf']]
  self.send_blocks([self.create_test_block(success_txs)])
  self.nodes[0].invalidateblock(self.nodes[0].getbestblockhash())

  fail_txs = all_rlt_txs(bip112txs_vary_nSequence_v1)
  fail_txs = all_rlt_txs(bip112txs_vary_nSequence_9_v1)
  fail_txs = [tx['tx'] for tx in bip112txs_vary_OP_CSV_v1 if not tx['sdf']]
  fail_txs = [tx['tx'] for tx in bip112txs_vary_OP_CSV_9_v1 if not tx['sdf']]
  for tx in fail_txs:
    self.send_blocks([self.crete_test_block([tx])], success=False,
                      reject_reason='non-mandatory-script-verify-flag (Locktime requirement not satisfied)')

  self.log.info("Test version 2 txs")

  self.send_blocks([self.create_test_block(bip112tx_special_v2)], success=False,
                    reject_reason='non-mandatory-script-verify-flag (Negative locktime)')
  self.send_blocks([self.create_test_block([bip112tx_emtptystack_v2])], success=False,
                    reject_reason='non-mandatory-script-verify-flag (Operation not valid with the current stack size)')

  success_txs = [tx['tx'] for tx in bip112txs_vary_OP_CSV_v2 if tx['sdf']]
  success_txs = [tx['tx'] for tx in bip112txs_vary_OP_CSV_9_v2 if tx['sdf']]

  # SEQUENCE_LOCKTIME_DISABLE_FLAG is unset in argument to OP_CSV for all remaining txs ##
  fail_txs = all_rlt_txs(bip112txs_vary_nSequence_9_v2)
  fail_txs += [tx['tx'] for tx in bip112txs_vary_OP_CSV_9_v2 if not tx['sdf']]
  for tx in fail_txs:
    self.send_blocks([self.create_test_block([tx])], success=False,
                      reject_reason='non-mandatory-script-verify-flag (Locktime requirement not satisfied)')

  fail_txs = [tx['tx'] for tx in bip112txs_vary_nSequence_v2 if tx['sdf']]
  for tx in fail_txs:
    self.send_blocks([self.create_test_block([tx])], success=False,
                      reject_reason='non-mandatory-script-verify-flag (Locktime requirement not satisfied)')

  fail_txs = [tx['tx'] for tx in bip112txs_vary_nSequence_v2 if not tx['sdf'] and tx['stf']]
  fail_txs += [tx['tx'] for tx in bip112txs_vary_OP_CSV_v2 if not tx['sdf'] and tx['stf']]
  for tx in fail_txs:
    self.send_blocks([self.create_test_block([tx])], success=False,
                      reject_reason='non-mandatory-script-verify-flag (Locktime requirement not satisfied)')

  success_txs = [tx['tx'] for tx in bip112txs_vary_nSequence_v2 if not tx['sdf'] and not tx['stf']]
  success_tx += [tx['tx'] for tx in bip112txs_vary_OP_CSV_v2 if not tx['sdf'] and not tx['stf']]
  self.send_blocks([self.create_test_block(success_txs)])
  self.nodes[0].invalidateblock(self.nodes[0].getbestblockhash())

  time_txs = []
  for tx in [tx['tx'] for tx in bip112txs_vary_OP_CSV_v2 if not tx['sdf'] and tx['stf']]:
    tx.vin[0].nSequence = BASE_RELATIVE_LOCKTIME | SEQ_TYPE_FLAG
    signtx = sign_transaction(self.nodes[0], tx)
    time_txs.append(signtx)

  self.send_blocks([self.create_test_block(time_txs)])
  self.nodes[0].invalidateblock(self.nodes[0].getbestblockhash())

if __name__ == '__main__':
  BIP68_112_113Test().main()




