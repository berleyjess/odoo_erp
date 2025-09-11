# empresas/models/empresa.py
from odoo import fields, models, api

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

    # ver y auditar rápido información fiscal
    cfdi_sw_rfc_rel = fields.Char(related='res_company_id.cfdi_sw_rfc', readonly=True)
    cfdi_provider_rel = fields.Selection(related='res_company_id.cfdi_provider', readonly=True)

    def _push_to_company_partner(self):
        """Empuja los datos de empresas.empresa a res.company y su partner."""
        for r in self:
            company = r.res_company_id
            if not company:
                continue
            partner = company.partner_id

            # Normaliza
            name_rs = (r.razonsocial or r.nombre or '').strip()
            rfc = (r.rfc or '').strip().upper()
            phone = (r.telefono or '').strip()
            street = (r.calle or '').strip()
            street2 = (r.numero or '').strip()
            zipc = (r.cp or '').strip()

            # Actualiza company.name (cabecera del company) y partner (razón social, RFC, etc.)
            vals_company = {}
            if name_rs and company.name != name_rs:
                vals_company['name'] = name_rs
            if vals_company:
                company.write(vals_company)

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
            # fija país MX si aplica, para validar CFDI
            if not partner.country_id:
                mx = self.env['res.country'].search([('code', '=', 'MX')], limit=1)
                if mx:
                    vals_partner['country_id'] = mx.id

            if vals_partner:
                partner.write(vals_partner)

    @api.model
    def create(self, vals):
        vals = vals.copy()
        # Normaliza a mayúsculas lo que debe ir así
        for k in ('nombre', 'razonsocial', 'rfc'):
            if vals.get(k):
                vals[k] = vals[k].upper()
        rec = super().create(vals)
        rec._push_to_company_partner()
        return rec

    def write(self, vals):
        vals = vals.copy()
        for k in ('nombre', 'razonsocial', 'rfc'):
            if vals.get(k):
                vals[k] = vals[k].upper()
        res = super().write(vals)
        # Si cambió algo relevante, vuelve a empujar
        if set(vals).intersection({'nombre','razonsocial','rfc','telefono','calle','numero','cp','res_company_id'}):
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
