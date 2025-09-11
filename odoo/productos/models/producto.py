#producto-models-producto.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class producto(models.Model):
    _name = 'productos.producto'
    _description = 'Catálogo de productos.'

    name = fields.Char(string="Nombre", required=True)
    description = fields.Char(string="Descripción", size=30)
    
    unidad = fields.Selection(   # Unidades de medida disponibles para los productos
        selection = [
            ("KGM", "Kilogramo"),
            ("TON", "Tonelada"),
            ("LTR", "Litro"),
            ("H87", "Pieza"),
            ("E48", "Servicio")
        ], string="Unidad de medida", required=True
    )
    costo = fields.Float(string="Costo", digits=(14, 2), default=0.0)
    contado = fields.Float(string="Precio de contado", digits=(14, 2), default=0.0)
    credito = fields.Float(string="Precio de crédito", digits=(14, 2), default=0.0)

    # Iva: entre 0.0 y 1.0, válidos sólo 0.0, 0.08 y 0.16
    iva = fields.Float(
        string="Iva %",
        required=True,
        default='0.0'
    )

    # Tipo de Producto: Insumos, Ferretería, Granos
    # Se usa para categorizar los productos y aplicar reglas específicas
    tipoProducto = fields.Selection(
        selection=[("0", "Insumos"), ("1", "Granos"),("2", "Ferretería")],
        string="Categoría del Producto",
        required=True,
        default='0'
    )

    # IEPS: entre 0.0 y 1.0
    ieps = fields.Float(string="Ieps %", default=0.0)

    #Clase del Producto
    linea = fields.Many2one(
        'lineasdeproducto',
        string="Linea de Producto",
        required=True,
        ondelete='restrict'
    )
  
    #----
    #Propiedades del Producto
    venta = fields.Boolean(string="Producto para venta", default = True)
    produccion = fields.Boolean(string="De producción", default = False)
    compra = fields.Boolean(string="Producto para compra", default = False)
    materiaprima = fields.Boolean(string="Producto para Materia Prima", default = False)
    consumible = fields.Boolean(string="Producto consumible (Envases, etiquetas, etc)", default = False)
    servicio = fields.Boolean(string="Servicio", default=False, store = True)

    # Enlace con product.product estándar (para facturación/account.move)
    product_id = fields.Many2one('product.product', string='Producto Odoo', copy=False)

    # Datos SAT opcionales (catálogos estándar si están instalados)
    sat_unspsc_id = fields.Many2one('product.unspsc.category', string='Clave ProdServ (UNSPSC)', help='Usado por EDI MX si está disponible')
    sat_uom_id = fields.Many2one('uom.uom', string='Unidad SAT (UoM)')
    
    #----
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

    
    @api.constrains('ieps', 'iva')
    def _check_ieps_range(self):
        for rec in self:
            if not (0.0 <= rec.ieps <= 1.0):
                raise ValidationError("El IEPS debe estar entre 0.0 y 1.0.")
            if not rec.iva in [0.0, 0.08, 0.16]:
                raise ValidationError("Seleccione entre 0.0, 0.08 ó 0.16")

    @api.constrains('costo', 'contado', 'credito')
    def _check_price_format(self):
        for rec in self:
            for fname in ['costo', 'contado', 'credito']:
                value = getattr(rec, fname)
                if value < 0:
                    raise ValidationError("Ningún precio puede ser negativo.")
                # Máximo 12 dígitos antes del punto
                s = str(int(value))
                if len(s) > 12:
                    raise ValidationError("El valor de '%s' es muy grande. Máximo 12 dígitos antes del punto decimal." % fname)

    state = fields.Selection([
    ('draft', 'Borrador'),
    ('confirmed', 'Confirmado')
    ], string="Estado", default='draft')

    def action_back_to_list(self):
        """Regresa al listado de productos."""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Productos'),
            'res_model': 'productos.producto',
            'view_mode': 'list,form',
            'target': 'current',
        }


    def action_manual_save(self):
        self.write({'state': 'confirmed'})  # Guarda solo al llamar esta función

    def _generate_code(self):
        sequence = self.env['ir.sequence'].next_by_code('seq_prod_code') or '/'
        number = sequence.split('/')[-1]
        return f"{number.zfill(6)}"

    # --- Helpers EDI/Facturación ---
    def _find_tax(self, percent):
        Tax = self.env['account.tax']
        return Tax.search([
            ('type_tax_use', '=', 'sale'),
            ('amount_type', '=', 'percent'),
            ('amount', '=', percent),
            ('company_id', '=', self.env.company.id),
            ('active', '=', True),
        ], limit=1)

    def ensure_product_product(self):
        """Crea o enlaza un product.product para este registro.
        - Busca por default_code == codigo, o por nombre.
        - Si no existe, crea un product.template/product.product con
          impuestos por IVA/IEPS, uom y UNSPSC si están disponibles.
        Devuelve product.product.
        """
        self.ensure_one()
        if self.product_id:
            return self.product_id
        Product = self.env['product.product']
        tmpl_model = self.env['product.template']

        p = Product.search([('default_code', '=', str(self.codigo))], limit=1)
        if not p:
            p = Product.search([('name', '=', self.name)], limit=1)
        if not p:
            # UoM defaults
            uom_unit = self.env.ref('uom.product_uom_unit', raise_if_not_found=False)
            uom_id = (self.sat_uom_id and self.sat_uom_id.id) or (uom_unit and uom_unit.id) or False

            # Taxes
            taxes = []
            if self.iva:
                t = self._find_tax(round(self.iva * 100, 2))
                if t:
                    taxes.append(t.id)
            if self.ieps:
                t = self._find_tax(round(self.ieps * 100, 2))
                if t:
                    taxes.append(t.id)

            t_vals = {
                'name': self.name,
                'default_code': str(self.codigo or ''),
                'type': 'service' if self.servicio else 'consu',
                'list_price': self.contado or 0.0,
                'standard_price': self.costo or 0.0,
                'uom_id': uom_id,
                'uom_po_id': uom_id,
                'taxes_id': [(6, 0, taxes)] if taxes else False,
            }
            # UNSPSC si existe el campo en template
            if 'unspsc_code_id' in tmpl_model._fields and self.sat_unspsc_id:
                t_vals['unspsc_code_id'] = self.sat_unspsc_id.id

            pt = tmpl_model.create(t_vals)
            p = pt.product_variant_id

        self.product_id = p.id
        return p
        
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
