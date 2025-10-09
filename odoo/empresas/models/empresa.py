# empresas/models/empresa.py
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)

class empresa(models.Model):
    _name = 'empresas.empresa'
    _description = "Modelo de Empresa, almacena el catálogo de empresas."
    _rec_name = 'nombre'

    nombre = fields.Char(string="Nombre", required=True, size=50)
    descripcion = fields.Char(string="Descripción", size=100)
    telefono = fields.Char(string="Teléfono", size=10)
    razonsocial = fields.Char(string="Razón Social", required=True)
    rfc = fields.Char(string="RFC", required=True, size=14)
    cp = fields.Char(string="Código Postal", required=True, size=5)
    calle = fields.Char(string="Calle")
    numero = fields.Char(string="Número")

    res_company_id = fields.Many2one(
        'res.company', string='Compañía fiscal (Odoo)',
        required=True, ondelete='restrict', index=True,
        help="Compañía de Odoo que emitirá los CFDI para esta empresa."
    )
    company_id = fields.Many2one('res.company', string='Compañía Odoo', required=True,
                                 default=lambda self: self.env.company)

    # (opcional conservar)
    usuario_id = fields.Many2one('res.users', string='Usuario', required=True, ondelete='restrict', index=True,
                                 default=lambda self: self.env.user.id)

    codigo = fields.Char(
        string='Código', size=10, required=True, readonly=True, copy=False,
        default=lambda self: self._generate_code(),
    )

    REGIMEN_SAT = [
        # PM
        ('601','601 - General de Ley Personas Morales'),
        ('603','603 - Personas Morales con Fines no Lucrativos'),
        ('620','620 - Sociedades Coop. (diferimiento)'),
        ('623','623 - Agrícolas, Ganaderas, Silvícolas y Pesqueras'),
        ('624','624 - Coordinados'),
        ('628','628 - Hidrocarburos'),
        # PF
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

    # ver y auditar rápido información fiscal
    cfdi_sw_rfc_rel = fields.Char(related='res_company_id.cfdi_sw_rfc', readonly=True)
    cfdi_provider_rel = fields.Selection(related='res_company_id.cfdi_provider', readonly=True)

    regimen_fiscal = fields.Selection(
        REGIMEN_SAT, string='Régimen Fiscal SAT', required=True,
        help="Régimen fiscal del emisor según catálogo SAT (c_RegimenFiscal)."
    )
    # opcional: permitir pausar la sincronización
    auto_sync_cfdi = fields.Boolean(string='Sincronizar a Compañía Odoo', default=True)

    def _push_to_company_partner(self):
        """Empuja datos de empresas.empresa a res.company y su partner (incluye régimen)."""
        for r in self:
            if not r.res_company_id or not r.auto_sync_cfdi:
                continue
            company = r.res_company_id
            partner = company.partner_id

            # Normaliza / fuentes
            name_rs = (r.razonsocial or r.nombre or '').strip().upper()
            rfc     = (r.rfc or '').strip().upper()
            phone   = (r.telefono or '').strip()
            street  = (r.calle or '').strip()
            street2 = (r.numero or '').strip()
            zipc    = (r.cp or '').strip()
            regimen = (r.regimen_fiscal or '').strip()

            # ---- res.company ----
            vals_company = {}
            if name_rs and company.name != name_rs:
                vals_company['name'] = name_rs
            if hasattr(company, 'l10n_mx_edi_legal_name') and company.l10n_mx_edi_legal_name != name_rs:
                vals_company['l10n_mx_edi_legal_name'] = name_rs

            if regimen:
                if hasattr(company, 'l10n_mx_edi_fiscal_regime'):
                    if company.l10n_mx_edi_fiscal_regime != regimen:
                        vals_company['l10n_mx_edi_fiscal_regime'] = regimen
                else:
                    if getattr(company, 'cfdi_regimen_fiscal', False) != regimen:
                        vals_company['cfdi_regimen_fiscal'] = regimen

            if hasattr(company, 'cfdi_sw_rfc') and rfc and company.cfdi_sw_rfc != rfc:
                vals_company['cfdi_sw_rfc'] = rfc
            if vals_company:
                company.write(vals_company)

            # ---- res.partner (de la company) ----
            vals_partner = {}
            if name_rs and partner.name != name_rs:
                vals_partner['name'] = name_rs
            if rfc and partner.vat != rfc:
                vals_partner['vat'] = rfc
            if phone and partner.phone != phone:
                vals_partner['phone'] = phone
            if street and partner.street != street:
                vals_partner['street'] = street
            if street2 and partner.street2 != street2:
                vals_partner['street2'] = street2
            if zipc and partner.zip != zipc:
                vals_partner['zip'] = zipc
            if hasattr(partner, 'l10n_mx_edi_legal_name') and partner.l10n_mx_edi_legal_name != name_rs:
                vals_partner['l10n_mx_edi_legal_name'] = name_rs
            
            # igual que en company: escribe estándar si existe; si no, fallback
            if regimen:
                if hasattr(partner, 'l10n_mx_edi_fiscal_regime'):
                    if partner.l10n_mx_edi_fiscal_regime != regimen:
                        vals_partner['l10n_mx_edi_fiscal_regime'] = regimen
                else:
                    if getattr(partner, 'cfdi_regimen_fiscal', False) != regimen:
                        vals_partner['cfdi_regimen_fiscal'] = regimen
            
            if not partner.country_id:
                mx = self.env['res.country'].search([('code','=','MX')], limit=1)
                if mx:
                    vals_partner['country_id'] = mx.id
            if vals_partner:
                partner.write(vals_partner)

            _logger.info("EMPRESA SYNC | empresa=%s -> company=%s partner=%s | company_vals=%s | partner_vals=%s",
                         r.id, company.id, partner.id, vals_company, vals_partner)
    def _validate_fiscal(self):
        """Valida CP y coherencia RFC (PF/PM) vs régimen."""
        PM_CODES = {'601','603','620','623','624','628'}
        PF_CODES = {'605','606','607','608','611','612','614','615','616'}
        for r in self:
            # CP
            if not ((r.cp or '').isdigit() and len((r.cp or '')) == 5):
                raise ValidationError(_("El C.P. debe ser numérico de 5 dígitos."))

            rfc = (r.rfc or '').strip().upper()
            reg = (r.regimen_fiscal or '').strip()
            if not rfc or not reg:
                continue
            is_moral = (len(rfc) == 12 and rfc not in ('XAXX010101000','XEXX010101000'))
            if is_moral and reg in PF_CODES:
                raise ValidationError(_("El RFC %s es de Persona Moral pero el régimen %s es de Persona Física.") % (rfc, reg))
            if (not is_moral) and reg in PM_CODES:
                raise ValidationError(_("El RFC %s es de Persona Física pero el régimen %s es de Persona Moral.") % (rfc, reg))
            
    @api.model
    def create(self, vals):
        vals = vals.copy()
        for k in ('nombre','razonsocial','rfc'):
            if vals.get(k):
                vals[k] = vals[k].upper()
        rec = super().create(vals)
        rec._validate_fiscal()
        rec._push_to_company_partner()
        return rec

    def write(self, vals):
        vals = vals.copy()
        for k in ('nombre','razonsocial','rfc'):
            if vals.get(k):
                vals[k] = vals[k].upper()
        res = super().write(vals)
        if set(vals).intersection({'nombre','razonsocial','rfc','telefono','calle','numero','cp','res_company_id','regimen_fiscal','auto_sync_cfdi'}):
            self._validate_fiscal()
            self._push_to_company_partner()
        return res

    def _generate_code(self):
        sequence = self.env['ir.sequence'].next_by_code('seq_emp_code') or '/'
        number = sequence.split('/')[-1]
        return f"{number.zfill(2)}"

    def action_open_res_company(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Compañía (fiscal)',
            'res_model': 'res.company',
            'view_mode': 'form',
            'res_id': self.res_company_id.id,
            'target': 'current',
        }
