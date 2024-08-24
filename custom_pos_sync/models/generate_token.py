from odoo import models, fields, api
import secrets

class AuthToken(models.Model):
    _name = 'auth.token'
    _description = 'Auth Token'
    _rec_name = 'user_id'

    token = fields.Char('Token', readonly=True)
    user_id = fields.Many2one('res.users', string = 'User', default = lambda self: self.env.user.id)

    def generate_token(self):
        if self.env.context.get('from_api',False):
            return self.create({'token':secrets.token_hex(16)}).token
        else:
            return self.write({'token':secrets.token_hex(16)})




class ResPartner(models.Model):
    _inherit = 'res.partner'

    dob = fields.Date(string='Date of Birth')
    phonecode = fields.Char(string='Phone Code')
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ], string='Gender')