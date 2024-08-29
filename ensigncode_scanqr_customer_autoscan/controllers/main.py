import requests
from odoo import http,_, api
import json
from werkzeug.wrappers import Response
from odoo.http import request
from odoo.exceptions import UserError
import odoo


class GetCustomerData(http.Controller):
    """controller for fetching customer data"""

    def validate_token(self, token):
        # Example: Validate token against stored tokens in a custom model
        token_model = request.env['auth.token'].sudo()
        valid_token = token_model.search([('token', '=', token)], limit=1)
        return bool(valid_token)

    @http.route('/api/getcustomer', type='json', auth="none",
                methods=['GET'])
    def get_customer(self, **kwargs):
        data = json.loads(request.httprequest.data)
        token = request.httprequest.headers.get('Authorization')
        if not token:
            return data.get('result', {'error': 'Authorization token is missing'})

        # Validate the token
        if not self.validate_token(token):
            return data.get('result', {'error':'Invalid authorization token'})

        pdata = data['customer']
        phone_number = pdata['phone']
        partner_model = request.env['res.partner'].sudo()
        parnter = partner_model.search(['|',('phone','=',phone_number),('mobile','=',phone_number)], limit=1)
        if pdata['country']:
            country_id = request.env['res.country'].search([('name','=',pdata['country'])])
        if parnter and parnter.name != phone_number:
            parnter.write({'name':pdata['name'] or '',
                           'city':pdata['city'] or '',
                           'street':pdata['address'] or '',
                           'country_id':country_id and country_id.id or False})
        if parnter:
            return data.get('result', {'customer':{'name':parnter.name,
                                                'phone':parnter.phone,
                                                'mobile':parnter.mobile,
                                                'address':parnter.street or '' + parnter.street2 or '',
                                                'city':parnter.city,
                                                'country':parnter.country_id and parnter.country_id.name or ''}})
        else:
            partner_id = partner_model.create({'phone':phone_number,'mobile':phone_number,'name':phone_number,})
            return data.get('result', {'message':'Customer is not found, Created new one with given number','customer':{
                'id':partner_id.id,
                'phone':partner_id.phone
            }})

    @http.route('/api/getauth', type='json', auth="none",
           methods=['GET'], csrf=False, save_session=False, cors="*")
    def get_auth(self, **kwargs):
        byte_string = request.httprequest.data
        data = json.loads(byte_string.decode('utf-8'))
        db_name = request.env.cr.dbname
        db = data.get('database', False)
        if not db:
            db = db_name
        registry = odoo.registry(db)
        username = data['username']
        password = data['password']
        user_id = request.session.authenticate(db, username, password)
        with registry.cursor() as cr:
            env = api.Environment(cr, user_id, request.context)
            token = env['auth.token'].sudo().with_context(from_api=True).generate_token()
        data = json.loads(request.httprequest.data)
        if token:
            return data.get('result', {'message':'Token Generated Sucessfully','Authorization':{
                    'token':token,
                }})
        else:
            return data.get('result', {'message':'Issue on the token generation'})
