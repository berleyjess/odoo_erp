from odoo import models, fields, api

class producto(models.Model):
    _name = 'productos.producto'
    _description = 'Catálogo de productos.'

    name = fields.Char(string="Nombre", required=True)
    description = fields.Char(string="Descripción", size=30)

    unidad = fields.Selection(
        selection = [
            ("KGM", "Kilogramo"),
            ("TON", "Tonelada"),
            ("LTR", "Litro"),
            ("H87", "Pieza"),
            ("E48", "Servicio")
        ], string="Unidad de medida", required=True
    )

    costo = fields.Float(string="Costo", digits=(12,4))
    contado = fields.Float(string="Precio de contado", digits=(12,4))
    credito = fields.Float(string="Precio de crédito", digits=(12,4))
    iva = fields.Float(string="iva", digits=(4,2))
    ieps = fields.Float(string="ieps", digits=(4,2))

    #Clase del Producto
    linea = fields.Many2one('lineasdeproducto', string="Linea de Producto", required=True, ondelete='restrict')
    
    #Propiedades del Producto
    ferreteria = fields.Boolean(string="Producto de Ferretería", default = False)
    venta = fields.Boolean(string="Producto para venta", default = True)
    produccion = fields.Boolean(string="De producción", default = False)
    compra = fields.Boolean(string="Producto para compra", default = False)
    materiaprima = fields.Boolean(string="Producto para Materia Prima", default = False)
    consumible = fields.Boolean(string="Producto consumible (Envases, etiquetas, etc)", default = False)

    codigo = fields.Char( #Código interno del producto
        string='Código',
        size=10,
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: self._generate_code()
        #help="Código único autogenerado con formato COD-000001"
    )

    codigosat = fields.Many2one('productos.codigoproductosat', string="Código SAT")

    cuenta = fields.Char(string = "Cuenta contable")

    def action_manual_save(self):
        self.write({'state': 'confirmed'})  # Guarda solo al llamar esta función

    def _generate_code(self):
        sequence = self.env['ir.sequence'].next_by_code('seq_prod_code') or '/'
        number = sequence.split('/')[-1]
        return f"{number.zfill(6)}"
    
    @api.model
    def create(self, vals):
        # Convertir a mayúsculas antes de crear
        if 'name' in vals:
            vals['name'] = vals['name'].upper() if vals['name'] else False
        if 'description' in vals:
            vals['description'] = vals['description'].upper() if vals['description'] else False
        return super().create(vals)
    
    def write(self, vals):
        # Convertir a mayúsculas antes de actualizar
        if 'name' in vals:
            vals['name'] = vals['name'].upper() if vals['name'] else False
        if 'description' in vals:
            vals['description'] = vals['description'].upper() if vals['description'] else False
        return super().write(vals)
