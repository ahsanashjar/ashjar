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
        leaf_points = loyalty_card.points if loyalty_card else 0

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
                leaf_points = loyalty_card.points if loyalty_card else 0
                return data.get('result',
                                {'message': 'This Customer is Already Registered With This Phone Number.', 'customer': {
                                    'customer_id': partner.id,
                                    'name': partner.name,
                                    'phone': partner.phone,
                                    'phonecode': partner.phonecode,
                                    'date_of_birth': partner.dob,
                                    'gender': partner.gender,
                                    'leaf_points': leaf_points
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
                                'leaf_points': leaf_points
                            }})

    @http.route('/api/topupleaf', type='json', auth="none", methods=['POST'])
    def topup_leaf(self, **kwargs):
        # Load JSON data from the request
        try:
            data = json.loads(request.httprequest.data)
        except json.JSONDecodeError:
            return {'error': 'Invalid JSON data'}

        # Retrieve the authorization token from headers
        token = request.httprequest.headers.get('Authorization')

        if not token:
            return {'error': 'Authorization token is missing'}

        # Validate the token (you need to implement the validate_token method)
        if not self.validate_token(token):
            return {'error': 'Invalid authorization token'}

        # Get the customer ID and leaf points from the data
        customer_id = data.get('customer_id')
        leaf_points = data.get('leaf_points')
        partner_model = request.env['res.partner'].sudo()
        partner = partner_model.search([('id', '=', customer_id)], limit=1)
        if not partner:
            return {'error': 'Customer Not Registered,First Register Customer'}
        if not customer_id or not leaf_points:
            return {'error': 'customer_id or leaf_points is missing'}

        # Search for the loyalty card using the customer_id
        loyalty_card = request.env['loyalty.card'].sudo().search([('partner_id', '=', customer_id)], limit=1)
        program = request.env['loyalty.program'].sudo().search([('program_type', '=', 'loyalty')], limit=1)


        if not loyalty_card:
            loyalty_card = request.env['loyalty.card'].sudo().create({
                'partner_id': customer_id,
                'points': 0,  # or any default value
                'program_id': program.id,
            })
            if not loyalty_card:
                return {'error': 'Failed to create a new loyalty card'}


        # Assuming you want to top up leaf points on the loyalty card
        loyalty_card.write({
            'points': loyalty_card.points + leaf_points
        })


        # Respond with success message
        return {'success': 'Top-up successful', 'new_balance': loyalty_card.points}

    @http.route('/api/updateleaf', type='json', auth="none", methods=['POST'])
    def update_leaf(self, **kwargs):
        # Load JSON data from the request
        try:
            data = json.loads(request.httprequest.data)
        except json.JSONDecodeError:
            return {'error': 'Invalid JSON data'}

        # Retrieve the authorization token from headers
        token = request.httprequest.headers.get('Authorization')

        if not token:
            return {'error': 'Authorization token is missing'}

        # Validate the token (you need to implement the validate_token method)
        if not self.validate_token(token):
            return {'error': 'Invalid authorization token'}

        # Get the customer ID and leaf points from the data
        customer_id = data.get('customer_id')
        leaf_points = data.get('leaf_points')

        if not customer_id or not leaf_points:
            return {'error': 'customer_id or leaf_points is missing'}

        # Search for the loyalty card using the customer_id
        loyalty_card = request.env['loyalty.card'].sudo().search([('partner_id', '=', customer_id)], limit=1)

        if not loyalty_card:
            return {'error': 'No loyalty card found for this customer'}

        # Assuming you want to top up leaf points on the loyalty card

        loyalty_card.sudo().write({'points': leaf_points})

        # Respond with success message
        return {'result': 'Leaf points Updated successfully', 'leaf_points': leaf_points}

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

    @http.route('/api/topupleafv2', type='json', auth="none", methods=['POST'])
    def topup_leaf_final(self, **kwargs):
        # Load JSON data from the request
        try:
            data = json.loads(request.httprequest.data)
        except json.JSONDecodeError:
            return {'error': 'Invalid JSON data'}

        # Retrieve the authorization token from headers
        token = request.httprequest.headers.get('Authorization')

        if not token:
            return {'error': 'Authorization token is missing'}

        # Validate the token (you need to implement the validate_token method)
        if not self.validate_token(token):
            return {'error': 'Invalid authorization token'}

        # Get the customer IDs and leaf points from the data
        customer_ids = data.get('customer_id')
        leaf_points = data.get('leaf_points')

        # if not customer_ids or not isinstance(customer_ids, list):
        #     return {'error': 'customer_id should be a list of IDs'}

        if not leaf_points:
            return {'error': 'leaf_points is missing'}

        results = []
        success_count = 0

        # Loop through each customer_id and process the top-up
        for customer_id in customer_ids:
            partner_model = request.env['res.partner'].sudo()
            partner = partner_model.search([('id', '=', customer_id)], limit=1)

            if not partner:
                results.append(
                    {'customer_id': customer_id, 'error': 'Customer Not Registered, First Register Customer'})
                continue

            # Search for the loyalty card using the customer_id
            loyalty_card = request.env['loyalty.card'].sudo().search([('partner_id', '=', customer_id)], limit=1)
            program = request.env['loyalty.program'].sudo().search([('program_type', '=', 'loyalty')], limit=1)

            if not loyalty_card:
                loyalty_card = request.env['loyalty.card'].sudo().create({
                    'partner_id': customer_id,
                    'points': 0,  # Default value for new cards
                    'program_id': program.id,
                })
                if not loyalty_card:
                    results.append({'customer_id': customer_id, 'error': 'Failed to create a new loyalty card'})
                    continue

            # Top up leaf points on the loyalty card
            loyalty_card.write({
                'points': loyalty_card.points + leaf_points
            })

            # Append success result for this customer
            results.append({'customer_id': customer_id, 'status': 'success', 'updated_points': loyalty_card.points})
            success_count += 1

        # Return the result for all customers

        # return {'success': 'Top-up successful', 'results': results}
        return {'success': 'Top-up successful', 'customer counts': success_count}