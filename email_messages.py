START_SUBJECT = 'Script Started!'
START_BODY = '{}\n\nScript ver. {} started!'

INSUFFICIENT_SUBJECT = 'Error! Insufficient balance!'
INSUFFICIENT_BODY = '''{}

Please fund your wallet {} with ETH
Your current balance: {} ETH
Required: {} ETH (${})
'''

DAILY_REPORT_SUB = 'Daily Report'
DAILY_REPORT_BODY = '''{}

Status: Running
Start : {}
Uptime: {} days, {} hours, {} minutes
Script ver. {}

ETH balance: {} (${})
HEX balance: {}

Control1: {}
Control2: {}
'''

TOKENS_RECEIPT_SUB = '{} Tokens Received!'
TOKENS_RECEIPT_BODY = '''{}

{} {} received.
Tx hash: {}
'''

TX_SUCCESS_SUB = 'Transfer Success!'
TX_SUCCESS_BODY = '''{}

{} {} transferred from {}
to {}

Tx hash: {}
Tx Fee: {} ETH (${})
'''

TX_FAIL_SUB = 'Error! Transaction Failed!'
TX_FAIL_BODY = '''{}

Tx hash {}
Tx: {}
Receipt: {}
'''

DELAYED_TX_SUB = 'Delayed Transfer Success!'
DELAYED_TX_BODY = '''{}

{} {} transferred from {}
to {}

Tx hash: {}
'''
