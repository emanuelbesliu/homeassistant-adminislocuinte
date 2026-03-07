"""Constants for the Adminis Locuințe integration.

Copyright (c) 2026 Emanuel Besliu
Licensed under the MIT License
"""

DOMAIN = "adminislocuinte"
CONF_APARTMENT_ID = "apartment_id"

# API endpoints
BASE_URL = "https://adminislocuinte.ro"
LOGIN_URL = f"{BASE_URL}/contul-meu/autentificare/"
DASHBOARD_URL = f"{BASE_URL}/i/"
API_PENDING_PAYMENTS = f"{BASE_URL}/api/pending-payments/{{location_id}}/"
API_PAYMENTS_HISTORY = f"{BASE_URL}/api/payments-history/{{location_id}}/"
API_COUNTERS = f"{BASE_URL}/api/counters/{{location_id}}/"
API_RECEIPT = f"{BASE_URL}/api/receipt/{{location_id}}/"
API_RECEIPT_MONTH = f"{BASE_URL}/api/receipt/{{location_id}}/{{month}}-{{year}}/"
API_PAYMENT_INFO = f"{BASE_URL}/api/payment-info/"

# Update interval - 4 times per day (every 6 hours)
DEFAULT_SCAN_INTERVAL = 21600  # 6 hours in seconds
