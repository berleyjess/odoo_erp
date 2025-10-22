#mx_cfdi_core/models/res_partner_regimen.py
from odoo import models, fields
"""
    Campo 'cfdi_regimen_fiscal' con el catálogo c_RegimenFiscal del SAT (solo el código).
    El engine lo lee cuando no está instalada la localización MX o como alternativa a
    'l10n_mx_edi_fiscal_regime' para construir el nodo Receptor en CFDI 4.0.
"""
class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Solo el código SAT (c_RegimenFiscal). Suficiente para el engine.
    cfdi_regimen_fiscal = fields.Selection([
        ('601', '601 - REGIMEN GENERAL DE LEY PERSONAS MORALES'),
        ('602', '602 - RÉGIMEN SIMPLIFICADO DE LEY PERSONAS MORALES'),
        ('603', '603 - PERSONAS MORALES CON FINES NO LUCRATIVOS'),
        ('604', '604 - RÉGIMEN DE PEQUEÑOS CONTRIBUYENTES'),
        ('605', '605 - RÉGIMEN DE SUELDOS Y SALARIOS E INGRESOS ASIMILADOS A SALARIOS'),
        ('606', '606 - RÉGIMEN DE ARRENDAMIENTO'),
        ('607', '607 - RÉGIMEN DE ENAJENACIÓN O ADQUISICIÓN DE BIENES'),
        ('608', '608 - RÉGIMEN DE LOS DEMÁS INGRESOS'),
        ('609', '609 - RÉGIMEN DE CONSOLIDACIÓN'),
        ('610', '610 - RÉGIMEN RESIDENTES EN EL EXTRANJERO SIN ESTABLECIMIENTO PERMANENTE EN MÉXICO'),
        ('611', '611 - RÉGIMEN DE INGRESOS POR DIVIDENDOS (SOCIOS Y ACCIONISTAS)'),
        ('612', '612 - RÉGIMEN DE LAS PERSONAS FÍSICAS CON ACTIVIDADES EMPRESARIALES Y PROFESIONALES'),
        ('613', '613 - RÉGIMEN INTERMEDIO DE LAS PERSONAS FÍSICAS CON ACTIVIDADES EMPRESARIALES'),
        ('614', '614 - RÉGIMEN DE LOS INGRESOS POR INTERESES'),
        ('615', '615 - RÉGIMEN DE LOS INGRESOS POR OBTENCIÓN DE PREMIOS'),
        ('616', '616 - SIN OBLIGACIONES FISCALES'),
        ('617', '617 - PEMEX'),
        ('618', '618 - RÉGIMEN SIMPLIFICADO DE LEY PERSONAS FÍSICAS'),
        ('619', '619 - INGRESOS POR LA OBTENCIÓN DE PRÉSTAMOS'),
        ('620', '620 - SOCIEDADES COOPERATIVAS DE PRODUCCIÓN QUE OPTAN POR DIFERIR SUS INGRESOS.'),
        ('621', '621 - RÉGIMEN DE INCORPORACIÓN FISCAL'),
        ('622', '622 - RÉGIMEN DE ACTIVIDADES AGRÍCOLAS, GANADERAS, SILVÍCOLAS Y PESQUERAS PM'),
        ('623', '623 - RÉGIMEN DE OPCIONAL PARA GRUPOS DE SOCIEDADES'),
        ('624', '624 - RÉGIMEN DE LOS COORDINADOS'),
        ('625', '625 - RÉGIMEN DE LAS ACTIVIDADES EMPRESARIALES CON INGRESOS A TRAVÉS DE PLATAFORMAS TECNOLÓGICAS.'),
        ('626', '626 - RÉGIMEN SIMPLIFICADO DE CONFIANZA'),
    ], string='Régimen Fiscal (CFDI)')