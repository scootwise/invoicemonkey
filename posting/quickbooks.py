import requests
from auth.quickbooks import QuickBooksAuth
from config.settings import QB_ENVIRONMENT
from datetime import datetime

class QuickBooksPoster:
    def __init__(self, user):
        self.user = user
        self.auth = QuickBooksAuth()
        
        if QB_ENVIRONMENT == 'sandbox':
            self.base_url = "https://sandbox-quickbooks.api.intuit.com/v3/company"
        else:
            self.base_url = "https://quickbooks.api.intuit.com/v3/company"
    
    def post_bill(self, invoice_data: dict) -> dict:
        try:
            if self.user.is_token_expired():
                tokens = self.auth.refresh_access_token(self.user.qb_refresh_token_enc)
                access_enc, refresh_enc = self.auth.encrypt_tokens(
                    tokens['access_token'], tokens['refresh_token']
                )
                
                from models.database import Session
                session = Session()
                user = session.query(type(self.user)).filter_by(id=self.user.id).first()
                user.qb_access_token_enc = access_enc
                user.qb_refresh_token_enc = refresh_enc
                user.qb_token_updated_at = datetime.utcnow()
                user.qb_expires_in = tokens['expires_in']
                session.commit()
                
                self.user = user
            
            access_token = self.auth.decrypt_access_token(self.user.qb_access_token_enc)
            bill = self._build_bill(invoice_data)
            
            url = f"{self.base_url}/{self.user.qb_realm_id}/bill"
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            resp = requests.post(url, headers=headers, json=bill)
            
            if resp.status_code == 200:
                result = resp.json()
                return {
                    'status': 'posted',
                    'qb_bill_id': result['Bill']['Id'],
                    'message': 'Successfully posted to QuickBooks'
                }
            else:
                return {
                    'status': 'error',
                    'qb_bill_id': None,
                    'message': f"QB API error {resp.status_code}: {resp.text}"
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'qb_bill_id': None,
                'message': str(e)
            }
    
    def _build_bill(self, invoice_data: dict) -> dict:
        lines = []
        for item in invoice_data.get('line_items', []):
            lines.append({
                "Description": item.get('description', 'Invoice line item'),
                "Amount": item.get('amount', 0),
                "DetailType": "AccountBasedExpenseLineDetail",
                "AccountBasedExpenseLineDetail": {
                    "AccountRef": {"value": "63"}
                }
            })
        
        if not lines:
            lines.append({
                "Description": "Invoice total",
                "Amount": invoice_data.get('total', 0),
                "DetailType": "AccountBasedExpenseLineDetail",
                "AccountBasedExpenseLineDetail": {
                    "AccountRef": {"value": "63"}
                }
            })
        
        return {
            "VendorRef": {"value": invoice_data.get('vendor_id', '46')},
            "APAccountRef": {"value": "33"},
            "TxnDate": invoice_data.get('invoice_date', datetime.now().strftime("%Y-%m-%d")),
            "DueDate": invoice_data.get('due_date', datetime.now().strftime("%Y-%m-%d")),
            "TotalAmt": invoice_data.get('total', 0),
            "Line": lines
        }
