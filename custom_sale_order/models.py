import json
import requests
import logging

_logger = logging.getLogger(__name__)

from odoo import models, fields, api
from odoo.exceptions import UserError

# Define the global URL
#API_URL = "https://stage-admin.applligentdemo.com/api/v1/odoo/"

SECRETKEY = "sk_e2a2d95a-34d4-4c58-8adf-21d7822f13f0"
API_URL = "https://console.ashjar.sa/api/v1/odoo/"

class ReturnPicking(models.Model):
    _name = 'return.picking'
    _description = 'Return Temporary Picking'

    picking_id = fields.Many2one('stock.picking', string='Picking')

    def return_pick(self):
        return_pickings = self.env['return.picking'].search([])
        for return_picking2 in return_pickings:
            picking_id = return_picking2.picking_id.id
            print('picking_id', picking_id)

            picking = self.env['stock.picking'].browse(picking_id)

            #print('picking.id', picking.id)

            # Assuming there's a method like `action_return` in `stock.picking` model
            if picking.state == 'done':
                return_picking = self.env['stock.return.picking'].create({
                    'picking_id': picking.id
                    # Add any other necessary fields for the wizard
                })
            return_picking2.unlink()
            return_wizard = return_picking._create_returns()
            picking = self.env['stock.picking'].browse(return_wizard[0])
            # Validate the picking object
            if picking:
                picking.button_validate()
                #print(f"Validated stock.picking with ID {return_wizard[0]}")
            else:
                print(f"Could not find stock.picking with ID {return_wizard[0]}")

            # Log success message or perform additional actions if needed
            _logger.info('Return action called for picking ID: %s', picking_id)


class TempPicking(models.Model):
    _name = 'temp.picking'
    _description = 'Temporary Picking'

    picking_id = fields.Many2one('stock.picking', string='Picking')
    sale_order_id = fields.Many2one('sale.order', string='Sale Order')


    def _validate_temp_pickings(self):
        temp_pickings = self.env['temp.picking'].search([])
        for temp_picking in temp_pickings:
            picking = temp_picking.picking_id
            # picking.button_validate()
            # _logger.info('Picking validated: %s', picking.id)
            if picking.state == 'assigned':
                picking.button_validate()
                _logger.info('Picking validated: %s', picking.id)
            else:
                _logger.warning('Picking not in "assigned" state: %s', picking.id)
                continue

            # Retrieve the sale order using sale_order_id
            sale_order = temp_picking.sale_order_id
            if sale_order:
                # Create invoices for the sale order
                user = sale_order.env['crm.team'].search([('name', '=', 'Online Sales')], limit=1)
                sale_order.write({'team_id': user.id})
                invoices = sale_order._create_invoices()

                #journal update
                journal = self.env['account.journal'].search([('name', '=', 'Online Sales')], limit=1)
                if invoices:
                    for invoice in invoices:
                        #update journal
                        invoice.write({'journal_id': journal.id})
                        invoice.action_post()
                        _logger.info('Invoice posted: %s', invoice.id)
                        # Register and confirm the payment
                        self.register_and_confirm_payment(invoice)
                        temp_picking.unlink()  # Remove entry after validation
                else:
                    raise UserError("No invoices were created for Sale Order: %s" % sale_order.name)
            else:
                _logger.error('Sale Order not found for Temp Picking: %s', temp_picking.id)

    def register_and_confirm_payment(self, invoice):
        if invoice.state != 'posted':
            raise UserError("The invoice must be posted before registering a payment.")

        # Open the register payment wizard
        # Check if the remaining amount to be paid is greater than zero
        if invoice.amount_residual > 0:
            # Search for the journal based on the invoice reference name
            journal = self.env['account.journal'].search([('name', '=', invoice.ref)], limit=1)

            # If no journal is found, search for the TAP journal
            if not journal:
                journal = self.env['account.journal'].search([('name', '=', 'TAP')], limit=1)

            # Create the payment register
            payment_register = self.env['account.payment.register'].with_context(
                active_model='account.move', active_ids=[invoice.id]
            ).create({
                'amount': invoice.amount_residual,  # The remaining amount to be paid
                'journal_id': journal.id,  # Use the found or TAP journal
                'payment_date': fields.Date.today(),
            })

            # Confirm the payment
            payment_register.action_create_payments()
        else:
            # Skip payment registration as the amount to be paid is zero
            _logger.info("Skipping payment registration for invoice %s as there is nothing left to pay.", invoice.name)

        _logger.info('Payment registered and confirmed for Invoice: %s', invoice.id)



class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        # Call the super method first to ensure the stock picking is validated
        res = super(StockPicking, self).button_validate()
        #print('husen', res)
        # Now call the API method to update stock quantity
        self.update_stock_qty()


        # Return the result of the super call
        return res

    def update_stock_qty(self):
        stock_data = []
        products = self.env['product.product'].search([('default_code', '!=', False)])
        for product in products:
            default_code = product.default_code
            on_hand_qty = product.qty_available

            stock_data.append({
                'product_id': default_code,
                'new_stock_qty': on_hand_qty
            })

        # Call the API with dynamically fetched stock data
        update_stock = self.update_product_stock_qty_api(stock_data)
        print('update_stock', update_stock)

    def update_product_stock_qty_api(self, stock_data):

        url = API_URL + "update_product_stock_qty"
        body = {
            "secret_key": SECRETKEY,
            "stock_data": stock_data
        }

        response = requests.post(url, json=body)
        if response.status_code == 200:
            return response.json()
        else:
            raise UserError(f"Failed to update product stock qty: {response.status_code} {response.text}")


class ProductTemplate(models.Model):
    _inherit = 'product.product'
    # inherit and set product ecom id product master
    #default_code = fields.Char(string='Product Variant Ecom_id')

    def action_update_product_v_price(self):
        for product in self:
            product_id = product.default_code
            self.update_product_price_api(product_id, product.lst_price)

    @api.model
    def update_product_price_api(self, product_id, new_price):
        print(product_id, new_price)
        url = API_URL + "update_product_price"
        body = {
            "secret_key": SECRETKEY,
            "stock_data": [
                {
                    "product_id": product_id,
                    "new_price": new_price
                }
            ]
        }

        response = requests.post(url, json=body)
        if response.status_code == 200:
            return response.json()
        else:
            raise UserError(f"Failed to update product price: {response.status_code} {response.text}")


class ProductTemplate(models.Model):
    _inherit = 'product.template'
    # inherit and set product ecom id product master
    #ecom_product_id = fields.Char(string='E-commerce Product ID')
    #default_code = fields.Char(string='Product Variant Ecom_id')

    # Mohammad
    # Api 4
    # this is 4th api update product price from odoo to end server

    def action_update_product_price(self):
        for product in self:
            product_id = product.default_code
            self.update_product_price_api(product_id, product.list_price)

    @api.model
    def update_product_price_api(self, product_id, new_price):
        url = API_URL + "update_product_price"
        body = {
            "secret_key": SECRETKEY,
            "stock_data": [
                {
                    "product_id": product_id,
                    "new_price": new_price
                }
            ]
        }

        response = requests.post(url, json=body)
        if response.status_code == 200:
            return response.json()
        else:
            raise UserError(f"Failed to update product price: {response.status_code} {response.text}")


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    picking_policy = fields.Selection([
        ('direct', 'Deliver each product as soon as possible'),
        ('one', 'Deliver all products at once'),
        ('each', 'Deliver each product separately'),
    ], string='Picking Policy', default='direct')

    l10n_in_gst_treatment = fields.Selection([
        ('regular', 'Registered Business - Regular'),
        ('composition', 'Registered Business - Composition'),
        ('unregistered', 'Unregistered Business'),
        ('consumer', 'Consumer'),
        ('overseas', 'Overseas'),
        ('special_economic_zone', 'Special Economic Zone'),
        ('deemed_export', 'Deemed Export'),
    ], string="GST Treatment")


class CustomerCreator(models.Model):
    _name = 'customer.creator'
    _description = 'Customer Creator'
    _order = 'id desc'

    request_date = fields.Datetime(string='Request Date', default=fields.Datetime.now)
    json_data = fields.Text(string='JSON Data')
    status = fields.Selection([
        ('pending', 'Pending'),
        ('done', 'Done'),
    ], string='Status', default='pending')

    # this function will work create product if not exits if exists then return product id


    @api.model
    def create_product_if_not_exists(self, default_code):
        Product = self.env['product.product']
        # Search for existing product variant
        product = Product.search([('default_code', '=', default_code)], limit=1)
        if product:
            return product

        # If product doesn't exist, raise a warning message
        raise UserError('Please set up Odoo inventory with the Product Sku.')

    @api.model
    def create_sale_order_lines(self, sale_order_id, sale_order_lines_data, discount_amount):
        #print('sale_order_lines_data',sale_order_lines_data)
        SaleOrderLine = self.env['sale.order.line']
        discount_product_name = "Discount"  # Replace with your actual discount product name
        discount_product = self.env['product.product'].search([('name', '=', discount_product_name)], limit=1)

        for line_data in sale_order_lines_data:
            #,line_data.get('product_color_name'),line_data.get('default_code')
            product = self.create_product_if_not_exists(line_data.get('product_sku'))
            #product = self.create_product_variant_if_not_exists(line_data.get('product_name'), line_data.get('product_id'))
            print('md_product', product)
            SaleOrderLine.create({
                'order_id': sale_order_id,
                'product_id': product.id,
                'product_uom_qty': line_data.get('quantity', 1),
                'price_unit': line_data.get('unit_price', 0),
            })

        discount_value = discount_amount
        if discount_value:
            SaleOrderLine.create({
                'order_id': sale_order_id,
                'product_id': discount_product.id,
                'price_unit': -discount_value,
                'product_uom_qty': 1
            })


    # Api 1
    # this is first api fetch last sale order this will call via webhook
    @api.model
    def fetch_sales_data_from_api(self, sale_order_id):
        url = API_URL + "fetch_last_sale_order"
        body = {
            "secret_key": SECRETKEY,
            "sale_order_id": sale_order_id
        }

        response = requests.post(url, json=body)
        if response.status_code == 200:
            return response.json()
        else:
            raise UserError(f"Failed to fetch data: {response.status_code} {response.text}")


    # Mohammad
    # Api 2
    # this is second api fetch 150 sale order this will call on main page sale order log view {server} action button.
    @api.model
    def fetch_all_sales_data_from_api(self):
        url = API_URL + "fetch_sale_order_all"
        body = {
            "secret_key": SECRETKEY
        }

        response = requests.post(url, json=body)
        if response.status_code == 200:
            return response.json()
        else:
            raise UserError(f"Failed to fetch data: {response.status_code} {response.text}")


    # Mohammad
    # Api 3
    # this is 3rd api update the odoo tally sync status while calling number 1 and number 2 api call
    @api.model
    def update_odoo_flag_api(self, sale_order_id):
        url = API_URL + "update_odoo_flag"
        body = {
            "secret_key": SECRETKEY,
            "sale_order_id": sale_order_id
        }

        response = requests.post(url, json=body)
        if response.status_code == 200:
            return response.json()
        else:
            raise UserError(f"Failed to update odoo flag: {response.status_code} {response.text}")

    @api.model
    def return_sale_orders_from_data(self, sale_order_no):
        #_logger = self.env['ir.logging']

        # Log the input sale order number
        print(f'Sale Order Number: {sale_order_no}')

        # Search for the sale order with the given number, limit to 1
        sale_order = self.env['sale.order'].search([('name', '=', sale_order_no)], limit=1)

        if not sale_order:
            return f'No sale order found with the number: {sale_order_no}'

        # Log the found sale order
        print(f'Processing Sale Order: {sale_order.id}')

        # Process pickings
        pickings = sale_order.picking_ids
        print(f'Created return picking: {pickings.id}')
        for picking in pickings:
            return_picking = self.env['return.picking'].create({
                'picking_id': picking.id
            })
            print(f'Created return picking: {return_picking.id}')
            sale_order.write({'state': 'cancel'})

        # Process invoices
        print('sale_order.invoice_ids',sale_order.invoice_ids)
        # Process invoices
        invoices = sale_order.invoice_ids.filtered(lambda inv: inv.state == 'posted')
        for invoice in invoices:
            invoice.button_draft()
            invoice.button_cancel()
            print(f'Cancelled Invoice: {invoice.id}')
            # Find related payments
            payments = self.env['account.payment'].search([('ref', '=', invoice.name)])
            print(f'Cancelled payments: {payments.id}')
            for payment in payments:
                # Set the payment to draft and then cancel
                payment.write({'state': 'draft'})
                payment.action_cancel()  # Use the appropriate method for canceling payment

        return f'Sale Order {sale_order.id} processed successfully.'


    # this is function for call last sale order creating in system and also sale order log view
    @api.model
    def create_sale_orders_from_data(self, active_id):
        print('active_id', active_id)

        # Fetch sales data from the API
        sales_data = self.fetch_sales_data_from_api(active_id)
        #print('sales_data', sales_data)

        # Ensure that sales_data contains data
        if "data" not in sales_data:
            raise UserError("No sales data found in the response.")

        # Extract the order data
        order_data = sales_data["data"]

        # Ensure that order_data contains data
        if not order_data:
            raise UserError("No order data found in the response.")

        # Extract the first order data
        order_data = order_data[0]

        commitment_date = order_data["sale_order"]["order_date"]
        payment_method = order_data["sale_order"]["payment_method"]
        sale_id = order_data["sale_order"]["id"]
        customer_data = order_data["customer"]
        sale_voucher = order_data["sale_order"]["sale_order_no"]
        discount_amount = order_data["sale_order"]["discount_amount"]

        # print('commitment_date', commitment_date)
        # print('sale_id', sale_id)
        # print('customer_data', customer_data)
        # salesperson_id = self.env['res.users'].search([('name', '=', 'Online Sales')], limit=1)
        # print('salesperson_id',salesperson_id)
        # print('salesperson_id',salesperson_id.id)
        # if not salesperson_id:
        #     raise UserError("Salesperson 'Online Sales' not found")

        # Ensure existing_customer is set correctly
        existing_customer = self.env['res.partner'].search([('mobile', '=', customer_data["mobile"])], limit=1)

        if not existing_customer:
            country = self.env['res.country'].search([('name', '=', customer_data["country"])], limit=1)
            # state = self.env['res.country.state'].search(
            #     [('name', '=', customer_data["state"]), ('country_id', '=', country.id)],
            #     limit=1) if country else None
            #
            if not country:
                raise UserError("Country not found for customer: %s" % customer_data["name"])

            existing_customer = self.env['res.partner'].create({
                'name': customer_data["name"],
                'email': customer_data["email"],
                'mobile': customer_data["mobile"],
                'street': customer_data["street"],
                'street2': customer_data.get("street2", ""),
                # 'city': customer_data["city"],
                # 'state_id': state.id,
                # 'zip': customer_data["zip"],
                'country_id': country.id,
            })

        if not existing_customer:
            raise UserError("Customer could not be created or found for order data: %s" % order_data)

        # Create sale order
        SaleOrder = self.env['sale.order']
        new_sale_order = SaleOrder.create({
            'partner_id': existing_customer.id,
            'company_id': 1,
            'commitment_date': commitment_date,
            'state': 'draft',
            'l10n_in_gst_treatment': 'consumer',
            'name': sale_voucher,
            'payment_term_id': 1,
            'client_order_ref': payment_method,
            #'user_id': salesperson_id.id  # Set the salesperson
        })

        if not new_sale_order:
            raise UserError("Sale Order could not be created for customer: %s" % existing_customer.name)

        # Create sale order lines using the JSON data
        #print('hi i am mohammad')
        self.create_sale_order_lines(new_sale_order.id, order_data["sale_order_lines"], discount_amount)

        #create sale order
        new_sale_order.action_confirm()


        pickings = new_sale_order.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel'))
        for picking in pickings:
            self.env['temp.picking'].create({
                'picking_id': picking.id,
                'sale_order_id': new_sale_order.id,
            })
        #print('invoices',invoices)

        update_flag_data = self.update_odoo_flag_api(sale_id)
        # print('update_flag_data', update_flag_data)

        # Create record for the processed sale order
        self.create({
            'json_data': json.dumps(order_data),
            'status': 'done'
        })


    # this is function for call fetch all sale order creating in system and also sale order log view
    @api.model
    def create_sale_orders_from_api(self):
        # Fetch sales data from the API
        sales_data = self.fetch_all_sales_data_from_api()

        # Ensure that sales_data contains data
        if "data" not in sales_data:
            raise UserError("No sales data found in the response.")

        # Extract the order data
        orders_data = sales_data["data"]

        # Ensure that orders_data contains data
        if not orders_data:
            raise UserError("No order data found in the response.")

        for order_data in orders_data:
            commitment_date = order_data["sale_order"]["order_date"]
            sale_id = order_data["sale_order"]["id"]
            customer_data = order_data["customer"]
            sale_voucher = order_data["sale_order"]["sale_order_no"]
            discount_amount = order_data["sale_order"]["discount_amount"]

            # Ensure existing_customer is set correctly
            existing_customer = self.env['res.partner'].search([('mobile', '=', customer_data["mobile"])], limit=1)

            if not existing_customer:
                country = self.env['res.country'].search([('name', '=', customer_data["country"])], limit=1)
                if not country:
                    raise UserError("Country not found for customer: %s" % customer_data["name"])

                existing_customer = self.env['res.partner'].create({
                    'name': customer_data["name"],
                    'email': customer_data["email"],
                    'mobile': customer_data["mobile"],
                    'street': customer_data["street"],
                    'street2': customer_data.get("street2", ""),
                    'country_id': country.id,
                })

            if not existing_customer:
                raise UserError("Customer could not be created or found for order data: %s" % order_data)

            # Create sale order
            SaleOrder = self.env['sale.order']
            new_sale_order = SaleOrder.create({
                'partner_id': existing_customer.id,
                'commitment_date': commitment_date,
                'state': 'draft',
                'l10n_in_gst_treatment': 'consumer',
                'name': sale_voucher
            })

            if not new_sale_order:
                raise UserError("Sale Order could not be created for customer: %s" % existing_customer.name)

            # Create sale order lines using the JSON data
            print('hi i am mohammads 2')
            self.create_sale_order_lines(new_sale_order.id, order_data["sale_order_lines"], discount_amount)
            update_flag_data = self.update_odoo_flag_api(sale_id)

            # Create record for the processed sale order
            self.create({
                'json_data': json.dumps(order_data),
                'status': 'done'
            })