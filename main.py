import json
import os
import time
from datetime import datetime, timezone

import yagmail
from dotenv import load_dotenv
from loguru import logger
from web3 import Web3, HTTPProvider

load_dotenv()

TOKEN = 'HEX'
DECIMAL = 10 ** 8

MIN_AMOUNT_TO_SEND = 100
BONUS_GAS = 10000
BONUS_GAS_PRICE = Web3.toWei(2, 'gwei')
TRANSFER_STARTED = False

GMAIL_USERNAME = os.getenv('GMAIL_USERNAME')
GMAIL_PASSWORD = os.getenv('GMAIL_PASSWORD')
MAIL_RECIPIENT = os.getenv('MAIL_RECIPIENT')
ENDPOINT_URL = os.getenv('ENDPOINT_URL')

yag = yagmail.SMTP(GMAIL_USERNAME, GMAIL_PASSWORD)

REPORTED_TODAY = False
REPORT_HOUR = 4

logger.add('app.log', format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")

ADDRESS_FROM = Web3.toChecksumAddress(os.getenv('ADDRESS_FROM'))
ADDRESS_TO = Web3.toChecksumAddress(os.getenv('ADDRESS_TO'))
PRIVATE_KEY = os.getenv('PRIVATE_KEY')
CHAIN_ID = int(os.getenv('CHAIN_ID'))

CONTRACT_ADDRESS = Web3.toChecksumAddress(os.getenv('CONTRACT_ADDRESS'))
ABI = json.loads(os.getenv('ABI'))

web3 = Web3(HTTPProvider(ENDPOINT_URL))
contract = web3.eth.contract(address=CONTRACT_ADDRESS, abi=ABI)


def wait_until_balance_funded(estimated_max_fee):
    logger.warning('Waiting until balance funded')
    balance = _get_eth_balance()
    last = _get_eth_balance(formatted=True, balance=balance)
    logger.warning(f'Current balance: {last} ETH')
    yag.send(to=MAIL_RECIPIENT, subject=f'Error! Insufficient balance.',
             contents=f'Please fund your wallet {ADDRESS_FROM} with ETH,\nYour current balance: {last} ETH\nRequired: {estimated_max_fee} ETH')
    current = balance
    while not balance < current:
        time.sleep(20)
        current = _get_eth_balance()
    logger.info('Balance Funded')
    logger.info(f'Current ETH: {web3.fromWei(current, "ether")}')


def calc_transfer_fee(gas_limit, gas_price):
    return format(gas_limit * Web3.fromWei(gas_price, 'ether'), '.6f')


@logger.catch
def transfer_tokens(amount: int) -> bool:
    logger.info('Transferring tokens')
    global BONUS_GAS_PRICE, TRANSFER_STARTED

    transfer = contract.functions.transfer(ADDRESS_TO, amount)
    gas_limit = transfer.estimateGas({'from': ADDRESS_FROM}) + BONUS_GAS
    gas_price = web3.eth.gas_price + BONUS_GAS_PRICE
    estimated_max_fee = calc_transfer_fee(gas_limit, gas_price)

    logger.info(f'Gas limit: {gas_limit}, Gas price, gwei: {Web3.fromWei(gas_price, "gwei")}')
    logger.info(f'Estimated max fee: {estimated_max_fee} ETH')

    transaction = transfer.buildTransaction(
        {'chainId': CHAIN_ID, 'gas': gas_limit, 'gasPrice': gas_price,
         'nonce': web3.eth.getTransactionCount(ADDRESS_FROM)})
    signed_txn = web3.eth.account.signTransaction(transaction, PRIVATE_KEY)

    try:
        txn_hash = web3.eth.sendRawTransaction(signed_txn.rawTransaction)
        logger.info(Web3.toHex(txn_hash))
        receipt = web3.eth.wait_for_transaction_receipt(txn_hash, timeout=60)
        tx = web3.eth.get_transaction(txn_hash)
        logger.info(f'Tx: {tx}')
        logger.info(f'Receipt: {receipt}')
        if receipt.status == 1:
            logger.info('Transaction Success!')
            tx_fee = calc_transfer_fee(receipt.gasUsed, receipt.effectiveGasPrice)
            yag.send(to=MAIL_RECIPIENT, subject=f'TRANSFER SUCCESS!',
                     contents=f'{amount / DECIMAL} {TOKEN} transferred from {ADDRESS_FROM} to {ADDRESS_TO}\nTx hash: {Web3.toHex(txn_hash)}\nTx Fee: {tx_fee} ETH')
            TRANSFER_STARTED = False
            BONUS_GAS_PRICE = Web3.toWei(2, 'gwei')
            check_tokens_to_send()
            return True

        logger.error('Transaction Failed!')
        yag.send(to=MAIL_RECIPIENT, subject=f'Error! Transaction Failed!.',
                 contents=f'Details: tx hash {Web3.toHex(txn_hash)}\nTx: {tx}\nReceipt: {receipt}')
    except ValueError as e:
        logger.warning(e)
        if 'insufficient' in e.args[0]['message']:
            wait_until_balance_funded(estimated_max_fee)
            return False
    except Exception as e:
        logger.warning(e)
        TRANSFER_STARTED = True
    BONUS_GAS_PRICE += Web3.toWei(2, 'gwei')
    return False


def check_tokens_to_send():
    logger.info('Checking tokens balance')
    token_balance = _get_token_balance()
    logger.info(f'Tokens balance: {token_balance / DECIMAL}')
    while (token_balance / DECIMAL >= MIN_AMOUNT_TO_SEND) and not transfer_tokens(token_balance):
        time.sleep(10)
        token_balance = _get_token_balance()

    global TRANSFER_STARTED, BONUS_GAS_PRICE
    if TRANSFER_STARTED:
        TRANSFER_STARTED = False
        BONUS_GAS_PRICE = Web3.toWei(2, 'gwei')
        logger.info('DELAYED TRANSFER SUCCESS!')
        yag.send(to=MAIL_RECIPIENT, subject=f'DELAYED TRANSFER SUCCESS!',
                 contents=f'All {TOKEN} tokens transferred from {ADDRESS_FROM} to {ADDRESS_TO}')
        check_tokens_to_send()


def event_loop(event_filter, poll_interval):
    logger.info('In event monitoring loop:')
    while True:
        for transfer in event_filter.get_new_entries():
            if transfer.args.to == ADDRESS_FROM:
                logger.info(f'New Transfer Event: {transfer}')
                logger.info(f'{TOKEN} received: {transfer.args.value / DECIMAL}')
                yag.send(to=MAIL_RECIPIENT, subject=f'{TOKEN} tokens received!',
                         contents=f'{transfer.args.value / DECIMAL} {TOKEN} received.\nTx hash: {Web3.toHex(transfer.transactionHash)}')
                check_tokens_to_send()
        time.sleep(poll_interval)

        hour = datetime.now(timezone.utc).hour
        global REPORTED_TODAY
        if not REPORTED_TODAY and hour == REPORT_HOUR:
            daily_report()
            REPORTED_TODAY = True
        if REPORTED_TODAY and hour > REPORT_HOUR:
            REPORTED_TODAY = False


def _get_eth_balance(formatted=False, balance=None):
    balance = web3.eth.getBalance(ADDRESS_FROM) if balance is None else balance
    return format(web3.fromWei(balance, "ether"), '.5f') if formatted else balance


def _get_token_balance(decimal=False):
    balance = contract.functions.balanceOf(ADDRESS_FROM).call()
    return balance if not decimal else balance / DECIMAL


def daily_report():
    logger.info('Daily report sending')
    eth_balance = _get_eth_balance(formatted=True)
    token_balance = _get_token_balance(decimal=True)
    yag.send(to=MAIL_RECIPIENT, subject=f'DAILY REPORT',
             contents=f'Status: Running\nETH balance: {eth_balance}\n{TOKEN} balance: {token_balance}')


def main():
    logger.info(f'Started')
    yag.send(to=MAIL_RECIPIENT, subject=f'SCRIPT STARTED!',
             contents=f'The script is running now')
    event_filter = contract.events.Transfer.createFilter(fromBlock='latest')
    check_tokens_to_send()
    event_loop(event_filter, 5)


if __name__ == '__main__':
    main()
