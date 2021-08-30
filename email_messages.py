START_SUBJECT = 'SCRIPT STARTED!'
START_BODY = '<strong>{}</strong>\n<h2>Script ver. <mark>{}</mark> started!</h2>'

INSUFFICIENT_SUBJECT = 'Error! Insufficient balance!'
INSUFFICIENT_BODY = '''<strong>{}</strong>
<h2>Please fund your wallet <mark>{}</mark> with ETH
Your current balance: <mark>{} ETH</mark>
Required: <mark>{} ETH (${})</mark></h2>
'''

DAILY_REPORT_SUB = 'DAILY REPORT'
DAILY_REPORT_BODY = '''<strong>{}</strong>
<h2>Status: Running
Script ver. <mark>{}</mark>

Control1: <mark>{}</mark>
Control2: <mark>{}</mark>

ETH balance: <mark>{} (${})</mark>
HEX balance: <mark>{}</mark></h2>
'''

TOKENS_RECEIPT_SUB = '{} TOKENS RECEIVED!'
TOKENS_RECEIPT_BODY = '''<strong>{}</strong>
<h2><mark>{}</mark> {} received.
Tx hash: <mark>{}</mark></h2>
'''

TX_SUCCESS_SUB = 'TRANSFER SUCCESS!'
TX_SUCCESS_BODY = '''<strong>{}</strong>
<h2><mark>{}</mark> {} transferred from <mark>{}</mark>
to <mark>{}</mark>

Tx hash: <mark>{}</mark>
Tx Fee: <mark>{}</mark> ETH ($<mark>{}</mark>)</h2>
'''

TX_FAIL_SUB = 'Error! Transaction Failed!'
TX_FAIL_BODY = '''<strong>{}</strong>
<h2>Tx hash <mark>{}</mark>
Tx: {tx}
Receipt: {receipt}</h2>
'''

DELAYED_TX_SUB = 'DELAYED TRANSFER SUCCESS!'
DELAYED_TX_BODY = '''<strong>{}</strong>
<h2><mark>{}</mark> {} transferred from <mark>{}</mark>
to <mark>{}</mark>

Tx hash: <mark>{}</mark></h2>
'''
