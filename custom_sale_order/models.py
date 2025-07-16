import json
import requests
import logging

_logger = logging.getLogger(__name__)

from odoo import models, fields, api
from odoo.exceptions import UserError

# Define the global URL
API_URL = "https://stage-admin.applligentdemo.com/api/v1/odoo/"

SECRETKEY = "sk_e2a2d95a-34d4-4c58-8adf-21d7822f13f0"


# API_URL = "https://console.ashjar.sa/api/v1/odoo/"

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

            # print('picking.id', picking.id)

            # Assuming there's a method like `action_return` in `stock.picking` model
            if picking.state == 'done':
                return_picking = self.env['stock.return.picking'].create({
                    'picking_id': picking.id
                    # Add any other necessary fields for the wizard
                })

            return_wizard = return_picking._create_returns()
            picking = self.env['stock.picking'].browse(return_wizard[0])
            # Validate the picking object
            if picking:
                picking.button_validate()
                return_picking2.unlink()
            else:
                print(f"Could not find stock.picking with ID {return_wizard[0]}")

            # Log success message or perform additional actions if needed
            _logger.info('Return action called for picking ID: %s', picking_id)


class TempPicking(models.Model):
    _name = 'temp.picking'
    _description = 'Temporary Picking'

    picking_id = fields.Many2one('stock.picking', string='Picking')
    sale_order_id = fields.Many2one('sale.order', string='Sale Order')
    location_name = fields.Char(string='Location Name')
    ecom_sale_id = fields.Char(string='Ecom Sale Id')
    picking_validated = fields.Boolean(string='Picking Validated', default=False)
    invoice_processed = fields.Boolean(string='Invoice Processed', default=False)

    def _validate_temp_pickings(self):

        temp_pickings = self.env['temp.picking'].search([])
        for temp_picking in temp_pickings:
            try:
                picking = temp_picking.picking_id
                location = self.env['stock.location'].search([('name', '=', temp_picking.location_name)], limit=1)

                # Ensure the location exists
                if not location:
                    _logger.warning('Location "%s" not found for Temp Picking ID %s', temp_picking.location_name,
                                    temp_picking.id)
                    continue

                # Fetch the warehouse associated with the location
                warehouse = self.env['stock.warehouse'].search([('view_location_id', 'parent_of', location.id)],
                                                               limit=1)
                if not warehouse:
                    _logger.warning('Warehouse not found for location "%s" (Temp Picking ID %s)',
                                    temp_picking.location_name,
                                    temp_picking.id)
                    continue
                    # Fetch the Delivery Orders picking type for the warehouse
                picking_type = self.env['stock.picking.type'].search([
                    ('warehouse_id', '=', warehouse.id),
                    ('code', '=', 'outgoing'),  # Explicitly look for Delivery Orders
                    ('name', '=', 'Delivery Orders')  # Ensure the name matches "Delivery Orders"
                ], limit=1)
                if not picking_type:
                    _logger.warning(
                        'Delivery Orders picking type not found for warehouse "%s" (Temp Picking ID %s)',
                        warehouse.name, temp_picking.id)
                    continue
                if picking.state != 'done' and picking.state != 'draft':
                    picking.state = 'draft'  # Reset to draft if not already draft or done

                    # Update the picking's location and picking type
                    picking.write({
                        'location_id': location.id,
                        'picking_type_id': picking_type.id
                    })

                # picking.write({'location_id': location.id})
                # Update the stock.move.line source location
                for move_line in picking.move_line_ids:
                    move_line.write({'location_id': location.id})
                _logger.info('Updated location for Picking: %s', picking.location_id.name)
                if picking.state != 'done':
                    picking.action_assign()
                    picking.state = 'assigned'
                if picking.state == 'confirmed':  # Ensure it's ready for transfer
                    picking.action_assign()

                # Validate Picking if in 'assigned' state
                print('picking.state', picking.id)
                print('picking.state', picking.state)
                if picking.state == 'done':
                    temp_picking.write({'picking_validated': True})

                if picking.state == 'assigned':

                    picking.action_assign()
                    picking.button_validate()

                    _logger.info('Picking validated: %s', picking.id)
                    # temp_picking.write({'picking_validated': True})  # Custom field to track validation
                elif picking.state == 'done':
                    _logger.info('Picking already validated: %s', picking.id)

                    temp_picking.write({'picking_validated': True})


                else:
                    _logger.warning('Skipping Picking ID %s; Current State: %s', picking.id, picking.state)

                # Process Sale Order and Invoice
                sale_order = temp_picking.sale_order_id
                if sale_order:
                    if not self._check_existing_invoices(sale_order):
                        self._process_sale_order_and_invoice(sale_order, temp_picking)
                    else:
                        _logger.info('Invoice already exists for Sale Order: %s. Skipping invoice creation.',
                                     sale_order.name)
                        temp_picking.write({'invoice_processed': True})

                # Unlink record if both delivery and invoice are validated
                if temp_picking.picking_validated and temp_picking.invoice_processed:
                    _logger.info('Unlinking Temp Picking ID %s after successful delivery and invoice.', temp_picking.id)
                    temp_picking.unlink()

            except Exception as e:
                _logger.exception('Error processing Temp Picking ID %s: %s', temp_picking.id, str(e))

    def _check_existing_invoices(self, sale_order):
        """
        Check if invoices already exist for the given sale order.
        """

        existing_invoices = self.env['account.move'].search([
            ('invoice_origin', '=', sale_order.name),
            ('move_type', '=', 'out_invoice'),
            ('state', '!=', 'cancel'),
            ('invoice_line_ids.sale_line_ids.order_id', '=', sale_order.id)  # Cross-check via invoice lines

        ])
        return bool(existing_invoices)

    def _process_sale_order_and_invoice(self, sale_order, temp_picking):
        crm_team = self.env['crm.team'].search([('name', '=', 'Online Sales')], limit=1)
        location_to_journal = {
            'Rabie Stock': 'Riyadh Customer Sales',
            'Khobar Stock': 'Khobar Customer Sales',
            'Jeddah Stock': 'Jeddah Customer Sales',
        }
        journal_name = location_to_journal.get(temp_picking.location_name)
        _logger.info('journal_name', journal_name)
        # If a matching journal name is found, search for the journal
        if journal_name:
            journal = self.env['account.journal'].search([('name', '=', journal_name)], limit=1)
        else:
            # Default to 'Online Sales' if no match is found
            journal = self.env['account.journal'].search([('name', '=', 'Online Sales')], limit=1)
            # journal = self.env['account.journal'].search([('name', '=', 'Online Sales')], limit=1)

        if not crm_team or not journal:
            raise UserError('CRM Team or Journal "Online Sales" not configured.')

        sale_order.write({'team_id': crm_team.id})

        invoices = sale_order._create_invoices()
        if invoices:
            for invoice in invoices:
                invoice.write({'journal_id': journal.id})
                invoice.action_post()
                _logger.info('Invoice posted: %s', invoice.id)
                self.register_and_confirm_payment(invoice)
                share_link = self.env['account.move'].get_invoice_share_link(invoice.id)
                if self.attach_single_sale_invoice(temp_picking.ecom_sale_id, share_link):
                    _logger.info('Invoice Share Link: %s', share_link)
                else:
                    _logger.warning('Share Link not created for Invoice ID: %s', invoice.id)

            # Mark invoice as processed in Temp Picking
            temp_picking.write({'invoice_processed': True})  # Custom field to track invoice status
        else:
            _logger.warning('No invoices created for Sale Order: %s', sale_order.name)

    # Cron will reprocess records where picking is not validated or invoice is not processed

    def _validate_temp_pickings1(self):
        temp_pickings = self.env['temp.picking'].search([])

        for temp_picking in temp_pickings:
            picking = temp_picking.picking_id
            ecom_sale_id = temp_picking.ecom_sale_id
            location = self.env['stock.location'].search([('name', '=', temp_picking.location_name)], limit=1)
            if not location:
                _logger.warning('Location with name "%s" not found', 'Rabie Stock')
                continue
            picking.write({'location_id': location.id})
            # picking.button_validate()
            # _logger.info('Picking validated: %s', picking.id)
            if picking.state == 'assigned':
                print('here bossssssssss1')
                print(picking.action_assign())
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

                # journal update
                journal = self.env['account.journal'].search([('name', '=', 'Online Sales')], limit=1)
                if invoices:
                    for invoice in invoices:
                        # update journal
                        invoice.write({'journal_id': journal.id})
                        invoice.action_post()
                        _logger.info('Invoice posted: %s', invoice.id)
                        # Register and confirm the payment
                        self.register_and_confirm_payment(invoice)
                        invoice_id = invoice.id  # Replace with the actual invoice ID
                        share_link = self.env['account.move'].get_invoice_share_link(invoice_id)
                        attach_invoice = self.attach_single_sale_invoice(ecom_sale_id, share_link)

                        if attach_invoice:
                            _logger.info('Invoice Share Link: %s', share_link)
                        else:
                            _logger.warning('No share link found for Invoice ID: %s', invoice_id)
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

            concatenated_value = invoice.ref
            extracted_values = concatenated_value.split('|')
            journal1 = extracted_values[0]
            invoice.write({'ref': journal1})
            journal = self.env['account.journal'].search([('name', '=', journal1)], limit=1)
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

    def attach_single_sale_invoice(self, sale_order_id, invoice_attachement):

        # Api 6
        # Mohammad
        url = API_URL + "attach_single_sale_invoice"
        body = {
            "secret_key": SECRETKEY,
            "sale_order_id": sale_order_id,
            "invoice_attachement": invoice_attachement
        }

        response = requests.post(url, json=body)
        if response.status_code == 200:
            return response.json()
        else:
            raise UserError(f"Failed to Attach Invoice: {response.status_code} {response.text}")


class CustomModule(models.Model):
    _inherit = 'account.move'  # Or any other model in your custom module

    @api.model
    def get_invoice_share_link(self, invoice_id):
        """Generate the share link for an invoice using its ID."""
        invoice = self.env['account.move'].browse(invoice_id)
        if not invoice or invoice.state == 'draft':
            return None  # Return None if the invoice doesn't exist or is still a draft

        # Construct the share link
        base_url = invoice.get_base_url()
        share_url = invoice._get_share_url(redirect=True)

        # Return the full share link
        return f"{base_url}{share_url}"


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        # Call the super method first to ensure the stock picking is validated
        res = super(StockPicking, self).button_validate()

        # print('husen', res)
        # Now call the API method to update stock quantity

        # Mohammad Malek 6 November Temporary Turn Off The Live Sync Update For Client Request
        if self.state == 'done':
            self.get_kit_boms_stock_as_json()

        # Return the result of the super call
        return res

    def get_kit_boms_stock_as_json(self):
        print('Calling get_kit_boms_stock_as_json...')
        _logger.info('Calling get_kit_boms_stock_as_json...')
        # Fetch all BOMs with type 'kit' (phantom) for the current company
        current_company = 1
        kit_boms = self.env['mrp.bom'].search([
            ('type', '=', 'phantom'),
            ('company_id', '=', current_company)
        ])
        if not kit_boms:
            raise ValueError(f"No BOMs with type 'kit' found ")

        # Fetch all warehouses belonging to the current company
        warehouses = self.env['stock.warehouse'].search([('company_id', '=', current_company)])
        if not warehouses:
            raise ValueError(f"No warehouses found ")

        # Initialize the final JSON structure
        location_stock_data = []

        for warehouse in warehouses:
            # print(f"Processing warehouse: {warehouse.name}")

            # Get the main stock location for this warehouse
            location = warehouse.lot_stock_id

            # Initialize data for this warehouse
            warehouse_data = {
                "location_name": location.name,
                "parent_location_name": location.location_id.name,
                "products": []
            }

            for bom in kit_boms:
                # print(f"Processing BOM for kit: {bom.product_tmpl_id.display_name}")

                # Initialize available quantity for this BOM as infinite
                available_qty = float('inf')

                for line in bom.bom_line_ids:
                    component = line.product_id
                    component_qty_needed = line.product_qty

                    # Get the on-hand quantity of the component in this warehouse location
                    component_qty_available = self.env['stock.quant']._get_available_quantity(component, location)

                    # Calculate how many kits can be made with this component
                    kits_possible_with_component = component_qty_available / component_qty_needed

                    # Update the available_qty to the minimum of the current value and kits possible
                    available_qty = min(available_qty, kits_possible_with_component)

                # Add product data to the warehouse's product list
                product_data = {
                    # "product_id": bom.product_tmpl_id.display_name,
                    "product_id": bom.product_id.default_code,
                    "new_stock_qty": float(available_qty)  # Ensure value is serialized correctly
                }
                warehouse_data["products"].append(product_data)

            # Append warehouse data to the final list
            location_stock_data.append(warehouse_data)
            # _logger.info('location_stock_data: %s', location_stock_data)

        # Return the JSON structure
        update_stock = self.update_product_stock_qty_api(location_stock_data)
        # print('update_stock', update_stock)
        _logger.info('called update_stock Api: %s', update_stock)
        return location_stock_data

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

        _logger.info('stock_data: %s', stock_data)
        # url = API_URL + "update_product_stock_qty"
        url = API_URL + "update_product_stock_qty_wrt_dp"
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
    # default_code = fields.Char(string='Product Variant Ecom_id')

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
    # ecom_product_id = fields.Char(string='E-commerce Product ID')
    # default_code = fields.Char(string='Product Variant Ecom_id')

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

    # picking_policy = fields.Selection([
    #     ('direct', 'Deliver each product as soon as possible'),
    #     ('one', 'Deliver all products at once'),
    #     ('each', 'Deliver each product separately'),
    # ], string='Picking Policy', default='direct')

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
        print('product', default_code)
        product = Product.search([('default_code', '=', default_code)], limit=1)
        if product:
            return product

        # If product doesn't exist, raise a warning message
        raise UserError('Please set up Odoo inventory with the Product Sku.')

    @api.model
    def create_sale_order_lines(self, sale_order_id, sale_order_lines_data, discount_amount,
                                charged_with_wallet_amount,delivery_charge2):
        # print('sale_order_lines_data',sale_order_lines_data)
        SaleOrderLine = self.env['sale.order.line']
        discount_product_name = "Discount"  # Replace with your actual discount product name
        discount_wallet = "Wallet Discount"  # Replace with your actual discount product name
        delivery_charge = "Delivery Charges"  # Replace with your actual discount product name
        discount_product = self.env['product.product'].search([('name', '=', discount_product_name)], limit=1)
        discount_product_wallet = self.env['product.product'].search([('name', '=', discount_wallet)], limit=1)
        delivery_charges = self.env['product.product'].search([('name', '=', delivery_charge)], limit=1)

        for line_data in sale_order_lines_data:
            # ,line_data.get('product_color_name'),line_data.get('default_code')
            product = self.create_product_if_not_exists(line_data.get('product_sku'))
            # product = self.create_product_variant_if_not_exists(line_data.get('product_name'), line_data.get('product_id'))
            print('md_product', product)
            _logger.info('product: %s', product)
            _logger.info('test1:%s ',product.get_product_multiline_description_sale())  # Expected sale order line name
            _logger.info('test1: %s',product.display_name)  # Product display name
            _logger.info('test1: %s',product.name)  # Raw product name

            SaleOrderLine.create({
                'order_id': sale_order_id,
                'product_id': product.id,
                'product_uom_qty': line_data.get('quantity', 1),
                'price_unit': line_data.get('unit_price', 0),
                'name': product.get_product_multiline_description_sale() or product.display_name or product.name or "Unnamed Product",

            })
        charged_with_wallet = charged_with_wallet_amount
        if charged_with_wallet:
            SaleOrderLine.create({
                'order_id': sale_order_id,
                'product_id': discount_product_wallet.id,
                'price_unit': -charged_with_wallet,
                'product_uom_qty': 1
            })
        discount_value = discount_amount
        if discount_value:
            SaleOrderLine.create({
                'order_id': sale_order_id,
                'product_id': discount_product.id,
                'price_unit': -discount_value,
                'product_uom_qty': 1
            })
        delivery_charge = delivery_charge2
        if delivery_charge > 0:
            SaleOrderLine.create({
                'order_id': sale_order_id,
                'product_id': delivery_charges.id,
                'price_unit': delivery_charge,
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
        # _logger = self.env['ir.logging']

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
        print('sale_order.invoice_ids', sale_order.invoice_ids)
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
        _logger.info('active_id: %s', active_id)
        # Fetch sales data from the API
        sales_data = self.fetch_sales_data_from_api(active_id)
        _logger.info('sales_data: %s', sales_data)
        # print('sales_data', sales_data)

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
        order_id = order_data["sale_order"]["payment_id"]
        concatenated_value = f"{payment_method}|{order_id}"

        sale_id = order_data["sale_order"]["id"]
        customer_data = order_data["customer"]
        sale_voucher = order_data["sale_order"]["sale_order_no"]
        discount_amount = order_data["sale_order"]["discount_amount"]
        charged_with_wallet_amount = order_data["sale_order"]["charged_with_wallet_amount"]
        delivery_charge = order_data["sale_order"]["delivery_charge"]
        location_name = order_data["sale_order"]["location"]

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
            'client_order_ref': concatenated_value,
            # 'user_id': salesperson_id.id  # Set the salesperson
        })

        if not new_sale_order:
            raise UserError("Sale Order could not be created for customer: %s" % existing_customer.name)

        # Create sale order lines using the JSON data
        # print('hi i am mohammad')
        self.create_sale_order_lines(new_sale_order.id, order_data["sale_order_lines"], discount_amount,
                                     charged_with_wallet_amount,delivery_charge)

        # create sale order
        new_sale_order.action_confirm()

        pickings = new_sale_order.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel'))
        for picking in pickings:
            self.env['temp.picking'].create({
                'picking_id': picking.id,
                'sale_order_id': new_sale_order.id,
                'location_name': location_name,
                'ecom_sale_id': sale_id
            })
        # print('invoices',invoices)

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
            charged_with_wallet_amount = order_data["sale_order"]["charged_with_wallet_amount"]
            delivery_charge = order_data["sale_order"]["delivery_charge"]

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
            self.create_sale_order_lines(new_sale_order.id, order_data["sale_order_lines"], discount_amount,
                                         charged_with_wallet_amount,delivery_charge)
            update_flag_data = self.update_odoo_flag_api(sale_id)

            # Create record for the processed sale order
            self.create({
                'json_data': json.dumps(order_data),
                'status': 'done'
            })
