import requests
from odoo import http, _, api
import json
from werkzeug.wrappers import Response
from odoo.http import request
from odoo.exceptions import UserError
import odoo
from datetime import datetime


class RegisterCustomerData(http.Controller):
    """controller for fetching customer data"""

    def validate_token(self, token):
        # Example: Validate token against stored tokens in a custom model
        token_model = request.env['auth.token'].sudo()
        valid_token = token_model.search([('token', '=', token)], limit=1)
        return bool(valid_token)

    @http.route('/api/registercustomer', type='json', auth="none",methods=['POST'])
    def register_customer(self, **kwargs):
        data = json.loads(request.httprequest.data)
        token = request.httprequest.headers.get('Authorization')
        # partner_id = request.httprequest.headers.get('partner_id')
        # print(partner_id)

        if not token:
            return data.get('result', {'error': 'Authorization token is missing'})

        # Validate the token
        if not self.validate_token(token):
            return data.get('result', {'error': 'Invalid authorization token'})

        pdata = data.get('customer', {})
        customer_id = data.get('customer_id')
        name = pdata.get('name')
        phone_number = pdata.get('phone_number')
        phonecode = pdata.get('phonecode')
        gender_format = pdata.get('gender')
        gender = gender_format.lower() if gender_format else None

        dob_format = pdata.get('date_of_birth')
        dob = datetime.strptime(dob_format, '%m-%d-%Y').date()
        print(dob)
        # phone_number = pdata['phone']
        if not phone_number:
            return {'error': 'Phone number is required.'}

        partner_model = request.env['res.partner'].sudo()
        partner = partner_model.search([('id', '=', customer_id)], limit=1)
        loyalty_card = request.env['loyalty.card'].sudo().search([('partner_id', '=', customer_id)], limit=1)

        # print('fetch partner id',partner)
        if customer_id and partner:
            partner.write({
                'name': pdata.get('name'),
                'phone': pdata.get('phone_number'),
                'dob': dob,
                'gender': gender
            })
        if partner:
            return data.get('result', {'message': 'Customer updated successfully', })
        else:
            partner = partner_model.search([('phone', '=', phone_number)], limit=1)
            # for existing users
            loyalty_card = request.env['loyalty.card'].sudo().search([('partner_id', '=', partner.id)], limit=1)
            if partner:
                return data.get('result',
                                {'message': 'This Customer is Already Registered With This Phone Number.', 'customer': {
                                    'customer_id': partner.id,
                                    'name': partner.name,
                                    'phone': partner.phone,
                                    'phonecode': partner.phonecode,
                                    'date_of_birth': partner.dob,
                                    'gender': partner.gender,
                                    'leaf_points': loyalty_card.points
                                }})
            partner_id = partner_model.create(
                {'name': name, 'phone': phone_number, 'phonecode': phonecode, 'gender': gender, 'dob': dob})
            print('partner_id', partner_id)
            return data.get('result',
                            {'message': 'Customer Registered Successfully!', 'customer': {
                                'customer_id': partner_id.id,
                                'name': partner_id.name,
                                'phone': partner_id.phone,
                                'phonecode': partner_id.phonecode,
                                'date_of_birth': partner_id.dob,
                                'gender': partner_id.gender,
                                'leaf_points': loyalty_card.points
                            }})


    @http.route('/api/getauth', type='json', auth="none",methods=['GET'], csrf=False, save_session=False, cors="*")
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
            return data.get('result', {'message': 'Token Generated Sucessfully', 'Authorization': {
                'token': token,
            }})
        else:
            return data.get('result', {'message': 'Issue on the token generation'})
