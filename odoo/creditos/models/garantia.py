
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class Garantia(models.Model):
    _name = "creditos.garantia"
    _description = "Garantías de clientes"

    folio = fields.Char(
        string="Folio",
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: _('000000'),
        #help="Código único autogenerado con formato COD-000001"
    )

    currency_id=fields.Many2one(
        comodel_name="res.currency",
        string="Moneda",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )

    credito_id = fields.Many2one('creditos.credito', string="Crédito relacionado", store=True, readonly=True)
    
    status = fields.Selection(
        string="Estado", selection=[
            ('released', "Liberada"),
            ('retained', "Retenida")
        ], default='retained', store = True)

    # === DATOS DE LA GARANTÍA ===
    tipo = fields.Selection(
        [
            ("prendaria", "Prendaria"),
            ("hipotecaria", "Hipotecaria"),
            ("usufructuaria", "Usufructuaria"),
        ],
        string="Tipo de Garantía",
        required=True,
        store=True
    )

    descripcion = fields.Text(
        string="Descripción",
        store=True
    )

    valor = fields.Monetary(
        string="Valor Estimado",
        store =True
    )

    #Sustituir con un modelo de clientes
    titular = fields.Char(
        string="Titular de la garantía",
        store=True
    )

    RFC = fields.Char(
        string="RFC del titular",
        store=True
    )

    localidad = fields.Many2one(
        comodel_name="localidades.localidad",
        string="Localidad",
        store=True
    )
    ########################################

    fecha_entrega = fields.Date(
        string="Fecha de Recepción",
        store=True, default=fields.Date.context_today, readonly=True
    )

    fecha_liberacion = fields.Date(
        string="Fecha de Liberación", store=True, readonly=True
    )

    persona_entrega = fields.Char(
        string="Persona que entrega",
        help="Nombre de la persona que entrega la garantía."
    )

    persona_recibe = fields.Char(
        string="Persona que recibe",
        help="Nombre de la persona que recibe la garantía."
    )

    @api.model
    def create(self, vals):
        #self.ensure_one()
        """Asegura que siempre haya fecha de vencimiento y monto al crear"""
        #vals['is_editing'] = True
        
        if vals.get('folio', _('000000')) == _('000000'):
            vals['folio'] = self.env['ir.sequence'].next_by_code('creditos.garantia') or _('000000')
        return super(Garantia, self).create(vals)
            
    # === VALIDACIONES ===
    @api.constrains("valor")
    def _check_valor(self):
        for rec in self:
            if rec.valor <= 0:
                raise ValidationError("El valor de la garantía no puede ser negativo o $0.")

    
    def liberar_garantia(self):
        """Liberar la garantía (cambiar estado a 'released')."""
        for rec in self:
            rec.status = 'released'
            rec.fecha_liberacion = fields.Date.context_today(self)
