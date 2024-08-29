from odoo import models,fields
import qrcode
import base64
from io import BytesIO


class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    qr_code = fields.Binary('Partner QR', readonly=1)

    def _generate_qr(self):
        for partner in self:
            mobile = partner.mobile or partner.phone
            if mobile:
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=10,
                    border=4,
                )
                qr.add_data(mobile)
                qr.make(fit=True)
    
                img = qr.make_image(fill_color="black", back_color="white")
                buffer = BytesIO()
                img.save(buffer, format="PNG")
                qr_code_image = base64.b64encode(buffer.getvalue())
                partner.qr_code = qr_code_image
            else:
                partner.qr_code = False
        