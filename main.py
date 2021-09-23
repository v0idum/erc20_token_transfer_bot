import json
import os
import time

import yagmail
from dotenv import load_dotenv
from loguru import logger
from web3 import Web3, HTTPProvider

from email_messages import *
from utils import eth_to_usd, now, current_hour, current_datetime, crop_key, FORMAT

load_dotenv()

VERSION = '2021-09-23'
START_TIME = current_datetime()

TOKEN = 'HEX'
DECIMAL = 10 ** 8

MIN_AMOUNT_TO_SEND = 100
BONUS_GAS = 10000
BONUS_GAS_PRICE = Web3.toWei(2, 'gwei')

TRANSFER_STARTED = False
global DELAYED_TX_TOKENS, TX_HASH

GMAIL_USERNAME = os.getenv('GMAIL_USERNAME')
GMAIL_PASSWORD = os.getenv('GMAIL_PASSWORD')
MAIL_RECIPIENT = os.getenv('MAIL_RECIPIENT')
ENDPOINT_URL = os.getenv('ENDPOINT_URL')

yag = yagmail.SMTP(GMAIL_USERNAME, GMAIL_PASSWORD)

REPORTED_TODAY = False
REPORT_HOUR = 12

logger.add('app.log', format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")

with open('intro.txt', 'r+') as f:
    data = []
    for line in f:
        data.append(line.strip())
    f.seek(0)
    f.write('0000000000000\n' * 2)
    f.truncate()

global WEB3, PRIVATE_KEY, ADDRESS_FROM, ADDRESS_TO, CONTRACT
CHAIN_ID = int(os.getenv('CHAIN_ID'))
ABI = json.loads(os.getenv('ABI'))


def wait_until_balance_funded(estimated_max_fee):
    logger.warning('Waiting until balance funded')
    balance = _get_eth_balance()
    last = _get_eth_balance(formatted=True, balance=balance)
    logger.warning(f'Current balance: {last} ETH')
    yag.send(to=MAIL_RECIPIENT, subject=INSUFFICIENT_SUBJECT,
             contents=INSUFFICIENT_BODY.format(now(), ADDRESS_FROM, last,
                                               estimated_max_fee, eth_to_usd(estimated_max_fee)))
    current = balance
    while not balance < current:
        time.sleep(20)
        current = _get_eth_balance()
    logger.info('Balance Funded')
    logger.info(f'Current ETH: {Web3.fromWei(current, "ether")}')


def calc_transfer_fee(gas_limit, gas_price):
    return format(gas_limit * Web3.fromWei(gas_price, 'ether'), '.6f')


@logger.catch
def transfer_tokens(amount: int) -> bool:
    logger.info('Transferring tokens')
    global BONUS_GAS_PRICE, TRANSFER_STARTED, TX_HASH

    transfer = CONTRACT.functions.transfer(ADDRESS_TO, amount)
    gas_limit = transfer.estimateGas({'from': ADDRESS_FROM}) + BONUS_GAS
    gas_price = WEB3.eth.gas_price + BONUS_GAS_PRICE
    estimated_max_fee = calc_transfer_fee(gas_limit, gas_price)

    logger.info(f'Gas limit: {gas_limit}, Gas price, gwei: {Web3.fromWei(gas_price, "gwei")}')
    logger.info(f'Estimated max fee: {estimated_max_fee} ETH')

    transaction = transfer.buildTransaction(
        {'chainId': CHAIN_ID, 'gas': gas_limit, 'gasPrice': gas_price,
         'nonce': WEB3.eth.getTransactionCount(ADDRESS_FROM)})
    signed_txn = WEB3.eth.account.signTransaction(transaction, PRIVATE_KEY)

    try:
        tx_hash = WEB3.eth.sendRawTransaction(signed_txn.rawTransaction)
        TX_HASH = Web3.toHex(tx_hash)
        logger.info(TX_HASH)
        receipt = WEB3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        tx = WEB3.eth.get_transaction(tx_hash)
        logger.info(f'Tx: {tx}')
        logger.info(f'Receipt: {receipt}')
        if receipt.status == 1:
            logger.info('Transaction Success!')
            tx_fee = calc_transfer_fee(receipt.gasUsed, receipt.effectiveGasPrice)
            yag.send(to=MAIL_RECIPIENT, subject=TX_SUCCESS_SUB,
                     contents=TX_SUCCESS_BODY.format(now(), amount / DECIMAL, TOKEN, ADDRESS_FROM, ADDRESS_TO,
                                                     TX_HASH, tx_fee, eth_to_usd(tx_fee)))
            TRANSFER_STARTED = False
            BONUS_GAS_PRICE = Web3.toWei(2, 'gwei')
            check_tokens_to_send()
            return True

        logger.error('Transaction Failed!')
        yag.send(to=MAIL_RECIPIENT, subject=TX_FAIL_SUB,
                 contents=TX_FAIL_BODY.format(now(), TX_HASH, tx, receipt))
    except ValueError as e:
        logger.warning(e)
        if 'insufficient' in e.args[0]['message']:
            wait_until_balance_funded(estimated_max_fee)
            return False
    except Exception as e:
        logger.warning(e)
        TRANSFER_STARTED = True
        global DELAYED_TX_TOKENS
        DELAYED_TX_TOKENS = amount / DECIMAL

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
        logger.info(DELAYED_TX_SUB)
        yag.send(to=MAIL_RECIPIENT, subject=DELAYED_TX_SUB,
                 contents=DELAYED_TX_BODY.format(now(), DELAYED_TX_TOKENS, TOKEN,
                                                 ADDRESS_FROM, ADDRESS_TO, TX_HASH))
        check_tokens_to_send()


def event_loop(event_filter, poll_interval):
    logger.info('In event monitoring loop:')
    while True:
        for transfer in event_filter.get_new_entries():
            if transfer.args.to == ADDRESS_FROM:
                logger.info(f'New Transfer Event: {transfer}')
                logger.info(f'{TOKEN} received: {transfer.args.value / DECIMAL}')
                yag.send(to=MAIL_RECIPIENT, subject=TOKENS_RECEIPT_SUB.format(TOKEN),
                         contents=TOKENS_RECEIPT_BODY.format(now(), transfer.args.value / DECIMAL, TOKEN,
                                                             Web3.toHex(transfer.transactionHash)))
                check_tokens_to_send()
        time.sleep(poll_interval)

        hour = current_hour()
        global REPORTED_TODAY
        if not REPORTED_TODAY and hour == REPORT_HOUR:
            daily_report()
            REPORTED_TODAY = True
        if REPORTED_TODAY and hour > REPORT_HOUR:
            REPORTED_TODAY = False


def _get_eth_balance(formatted=False, balance=None):
    balance = WEB3.eth.getBalance(ADDRESS_FROM) if balance is None else balance
    return format(WEB3.fromWei(balance, "ether"), '.5f') if formatted else balance


def _get_token_balance(decimal=False):
    balance = CONTRACT.functions.balanceOf(ADDRESS_FROM).call()
    return balance if not decimal else balance / DECIMAL


def daily_report():
    logger.info('Daily report sending')
    uptime = current_datetime() - START_TIME
    days = uptime.days
    hours = uptime.seconds // 3600
    minutes = uptime.seconds % 3600 // 60
    eth_balance = _get_eth_balance(formatted=True)
    token_balance = _get_token_balance(decimal=True)
    yag.send(to=MAIL_RECIPIENT, subject=DAILY_REPORT_SUB,
             contents=DAILY_REPORT_BODY.format(now(), START_TIME.strftime(FORMAT), days, hours, minutes, VERSION,
                                               eth_balance,
                                               eth_to_usd(eth_balance), token_balance, crop_key(data[0]),
                                               crop_key(data[1])))


def main():
    global WEB3, PRIVATE_KEY, ADDRESS_FROM, ADDRESS_TO, CONTRACT
    WEB3 = Web3(HTTPProvider(ENDPOINT_URL))

    PRIVATE_KEY = data[0]
    ADDRESS_FROM = Web3.toChecksumAddress(WEB3.eth.account.from_key(PRIVATE_KEY).address)
    ADDRESS_TO = Web3.toChecksumAddress(data[1])

    CONTRACT_ADDRESS = Web3.toChecksumAddress(os.getenv('CONTRACT_ADDRESS'))
    CONTRACT = WEB3.eth.contract(address=CONTRACT_ADDRESS, abi=ABI)

    event_filter = CONTRACT.events.Transfer.createFilter(fromBlock='latest')
    check_tokens_to_send()
    event_loop(event_filter, 5)


if __name__ == '__main__':
    logger.info(f'Started ver. {VERSION}')
    yag.send(to=MAIL_RECIPIENT, subject=START_SUBJECT,
             contents=START_BODY.format(now(), VERSION))
    while True:
        try:
            main()
        except Exception as ex:
            logger.error(f'Exception in main() {ex}')
            time.sleep(5)
