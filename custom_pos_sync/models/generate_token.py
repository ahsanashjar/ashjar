from odoo import models, fields, api
import secrets,logging,json,requests
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Define the global URL
API_URL = "https://ashjar-rewards.applligentdemo.com/api/v1/odoo/update-leaf-history"


class AuthToken(models.Model):
    _name = 'auth.token'
    _description = 'Auth Token'
    _rec_name = 'user_id'

    token = fields.Char('Token', readonly=True)
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user.id)

    def generate_token(self):
        if self.env.context.get('from_api', False):
            return self.create({'token': secrets.token_hex(16)}).token
        else:
            return self.write({'token': secrets.token_hex(16)})


class ResPartner(models.Model):
    _inherit = 'res.partner'

    dob = fields.Date(string='Date of Birth')
    phonecode = fields.Char(string='Phone Code')
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ], string='Gender')


class PosOrder(models.Model):
    _inherit = 'pos.order'
    
    
    @api.model
    def action_pos_order_paid(self):
        leaf_data = []
        # Call the original method to ensure the base functionality is executed
        result = super(PosOrder, self).action_pos_order_paid()
        
        # Fetch the most recent loyalty rule
        latest_rule = self.env['loyalty.rule'].search([], order='id desc', limit=1)
        
        if latest_rule:
            _logger.info("Using Rule: Reward Points Per Unit Amount: %s, Minimum Amount: %s",
                         latest_rule.reward_point_amount, latest_rule.minimum_amount)
        
        # Iterate over each order being processed
        for order in self:
            order_number = order.name
            amount_paid = order.amount_paid
            partner_id = order.partner_id.id if order.partner_id else None
            
            # Calculate points earned based on the rule
            points_won = 0
            if latest_rule and amount_paid >= latest_rule.minimum_amount:
                points_won = amount_paid * latest_rule.reward_point_amount

            points_cost = sum(line.points_cost for line in order.lines if line.is_reward_line)
            
            leaf_data.append({
                'odoo_user_id': partner_id,
                'order_id': order_number,
                'add_points': points_won,
                'deduct_points': -points_cost
            })

            # Call the API with dynamically fetched stock data
            call_leaf_api = self.add_leaf_history_api(leaf_data)
            # Log details
            _logger.info("POS order has been validated!")
            _logger.info("Partner ID: %s", partner_id)
            _logger.info("POS Order Number: %s", order_number)
            _logger.info("POS Amount Paid: %s", amount_paid)
            _logger.info("POS Won Points: %s", points_won)
            _logger.info("POS Spent Points: %s", points_cost)
            _logger.info("POS Calling Leaf Api : %s", call_leaf_api)

        
        # Return the result of the original method
        return result
        
    def add_leaf_history_api(self, leaf_data_list):    
        url = API_URL
        for leaf_data in leaf_data_list:
            body = {
                "odoo_user_id": leaf_data['odoo_user_id'],
                "add_points": leaf_data['add_points'],
                "deduct_points": leaf_data['deduct_points'],
                "order_id": leaf_data['order_id']
            }
            headers = {
                "secret_key": "sk_e2a2d95a-34d4-4c58-8adf-21d7822f13f0"
            }
            response = requests.post(url, headers=headers, json=body)

            #response = requests.post(url, json=body)
            if response.status_code == 200:
                result = response.json()
                # Log or handle the successful response as needed
            else:
                raise UserError(f"Failed to Add Leaf History Data: {response.status_code} {response.text}")

        return result

