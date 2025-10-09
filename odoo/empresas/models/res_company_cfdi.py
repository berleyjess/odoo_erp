from odoo import models, fields

REGIMEN_SAT = [
    ('601','601 - General de Ley Personas Morales'),
    ('603','603 - Personas Morales con Fines no Lucrativos'),
    ('620','620 - Sociedades Coop. (diferimiento)'),
    ('623','623 - Agrícolas, Ganaderas, Silvícolas y Pesqueras'),
    ('624','624 - Coordinados'),
    ('628','628 - Hidrocarburos'),
    ('605','605 - Sueldos y Salarios'),
    ('606','606 - Arrendamiento'),
    ('607','607 - Enajenación de Bienes'),
    ('608','608 - Demás ingresos'),
    ('611','611 - Dividendos'),
    ('612','612 - Actividades Empresariales y Profesionales'),
    ('614','614 - Intereses'),
    ('615','615 - Premios'),
    ('616','616 - Sin obligaciones fiscales'),
]

class ResPartner(models.Model):
    _inherit = 'res.partner'
    # Aquí sí creamos la columna real (fallback) en partner
    cfdi_regimen_fiscal = fields.Selection(
        REGIMEN_SAT, string='Régimen Fiscal SAT (CFDI)'
    )

class ResCompany(models.Model):
    _inherit = 'res.company'
    # En company NO creamos columna: usamos related al partner, sin store
    cfdi_regimen_fiscal = fields.Selection(
        REGIMEN_SAT,
        string='Régimen Fiscal SAT (CFDI)',
        related='partner_id.cfdi_regimen_fiscal',
        readonly=False,
        store=False,     # <- clave: evita la columna res_company.cfdi_regimen_fiscal
    )