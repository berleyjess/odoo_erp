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


    # (opcional conservar)
    #usuario_id = fields.Many2one('res.users', string='Usuario', required=True, ondelete='restrict', index=True,
    #                             default=lambda self: self.env.user.id)

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
    _sql_constraints = [
        ('emp_rfc_unique', 'unique(rfc)', 'El RFC ya existe en otra empresa.'),
        ('emp_codigo_unique', 'unique(codigo)', 'El código ya existe en otra empresa.'),
    ]



    regimen_fiscal = fields.Selection(
        REGIMEN_SAT, string='Régimen Fiscal SAT', required=True,
        help="Régimen fiscal del emisor según catálogo SAT (c_RegimenFiscal)."
    )
    # Campos de configuración CFDI (mismo que tenías en res.company)
    cfdi_provider = fields.Selection([
        ('mx.cfdi.engine.provider.dummy', 'Dummy (pruebas)'),
        ('mx.cfdi.engine.provider.sw', 'SW Sapien (REST)'),
    ], default='mx.cfdi.engine.provider.sw')
    
    cfdi_sw_sandbox = fields.Boolean(default=True)
    cfdi_sw_base_url = fields.Char()
    cfdi_sw_token = fields.Char()
    cfdi_sw_user = fields.Char()
    cfdi_sw_password = fields.Char()
    cfdi_sw_key_password = fields.Char()
    cfdi_sw_cer_file = fields.Binary(string="CSD Cert (.cer/.pem)", attachment=True)
    cfdi_sw_key_file = fields.Binary(string="CSD Key (.key/.pem)", attachment=True)
    cfdi_sw_rfc = fields.Char(string="RFC para timbrado SW")

    
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
        return rec

    def write(self, vals):
        vals = vals.copy()
        for k in ('nombre','razonsocial','rfc'):
            if vals.get(k):
                vals[k] = vals[k].upper()
        res = super().write(vals)
        if set(vals).intersection({'nombre','razonsocial','rfc','telefono','calle','numero','cp','regimen_fiscal','auto_sync_cfdi'}):
            self._validate_fiscal()
        return res

    def _generate_code(self):
        sequence = self.env['ir.sequence'].next_by_code('seq_emp_code') or '/'
        number = sequence.split('/')[-1]
        return f"{number.zfill(2)}"
    



    def action_sw_upload_csd(self):
        self.ensure_one()
        self.env['mx.cfdi.engine.provider.sw'].with_context(empresa_id=self.id)._upload_cert_from_company()
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': 'SW Sapien', 'message': 'CSD cargado correctamente en SW.',
                           'type': 'success', 'sticky': False}}

    def action_sw_check_cert(self):
        self.ensure_one()
        ok = self.env['mx.cfdi.engine.provider.sw'].with_context(empresa_id=self.id)._has_cert()
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': 'SW Sapien',
                           'message': ('CSD encontrado' if ok else 'CSD NO encontrado'),
                           'type': ('success' if ok else 'warning'), 'sticky': False}}
