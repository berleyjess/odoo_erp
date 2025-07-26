# ejidos/models/ejido.py

"""
Modelo de Ejidos.

Define el catálogo de ejidos y su relación con el módulo de localidades.
Incluye:
- Nombre normalizado (capitaliza cada palabra en create/write y en onchange).
- Display name calculado como: "<Nombre Ejido> (<Localidad, Municipio, Estado>)".
- Relación One2many inversa desde `localidades.localidad`.
"""

from odoo import models, fields, api, _

class Ejido(models.Model):

    """
    Modelo principal para almacenar ejidos.

    _rec_name apunta a ``display_name`` para mostrar el formato:
    ``NombreEjido (Localidad, Municipio, Estado)``.
    """

    _name = "ejidos.ejido"
    _description = "Modelo de Ejidos, almacena el catálogo de ejidos."
    _rec_name = "display_name"
    _order = "nombre"

    # Campos básicos

    nombre = fields.Char(string="Nombre del ejido", required=True)

    # Una localidad puede tener muchos ejidos
    localidad_id = fields.Many2one(
        "localidades.localidad",
        string="Localidad",
        required=True,
        ondelete="restrict"
    )

    # Campos relacionados (para filtros y búsquedas rápidas)
    # Estos campos son de solo lectura y se calculan automáticamente a partir de la localidad asociada.

    municipio_id = fields.Many2one(
        related="localidad_id.municipio",
        string="Municipio",
        store=True,
        readonly=True,
    )
    estado = fields.Selection(
        selection=[
            ("AGU", "Aguascalientes"),
            ("BCN", "Baja California Norte"),
            ("BCS", "Baja California Sur"),
            ("CAM", "Campeche"),
            ("CHH", "Chihuahua"),
            ("CHP", "Chiapas"),
            ("COA", "Coahuila"),
            ("COL", "Colima"),
            ("DIF", "Ciudad de México"),
            ("DUR", "Durango"),
            ("GRO", "Guerrero"),
            ("GUA", "Guanajuato"),
            ("HID", "Hidalgo"),
            ("JAL", "Jalisco"),
            ("MEX", "Estado de México"),
            ("MIC", "Michoacán"),
            ("MOR", "Morelos"),
            ("NAY", "Nayarit"),
            ("NLE", "Nuevo León"),
            ("OAX", "Oaxaca"),
            ("PUE", "Puebla"),
            ("QUE", "Queretaro"),
            ("ROO", "Quintana Roo"),
            ("SIN", "Sinaloa"),
            ("SLP", "San Luis Potosí"),
            ("SON", "Sonora"),
            ("TAM", "Tamaulipas"),
            ("TAB", "Tabasco"),
            ("TLA", "Tlaxcala"),
            ("VER", "Veracruz"),
            ("YUC", "Yucatán"),
            ("ZAC", "Zacatecas")
        ],
        related="localidad_id.estado",
        string="Estado",
        store=True,
        readonly=True,
    )

    display_name = fields.Char(
        compute="_compute_display_name",
        store=True,
    )

    _sql_constraints = [
        ("uniq_nombre_localidad",
         "unique(nombre, localidad_id)",
         "Ya existe un ejido con ese nombre en esa localidad.")
    ]


    # Helpers
    # Normalizador
  
    def _normalize_nombre(self, nombre):
        """Capitaliza cada palabra por ejemplo: 'las quintas' -> 'Las Quintas'."""
        if not nombre:
            return nombre
        # Evita espacios dobles y capitaliza palabra por palabra
        return " ".join(part.capitalize() for part in nombre.strip().split())

    # onchange para vista

    @api.onchange('nombre')
    def _onchange_nombre(self):
         #Normaliza el campo nombre en la vista cuando el usuario lo modifica.
        if self.nombre:
            self.nombre = self._normalize_nombre(self.nombre)

    # Create / Write 

    @api.model_create_multi
    def create(self, vals_list):
        """
        Sobrescribe create para normalizar el nombre antes de crear.

        Parameters
        ----------
        vals_list : list[dict]
            Lista de diccionarios con los valores a crear.

        Returns
        -------
        recordset
            Registros creados.
        """
        for vals in vals_list:
            if 'nombre' in vals and vals['nombre']:
                vals['nombre'] = self._normalize_nombre(vals['nombre'])
        return super().create(vals_list)

    def write(self, vals):
        """
        Sobrescribe write para normalizar el nombre antes de escribir.

        Parameters
        ----------
        vals : dict
            Valores a actualizar.

        Returns
        -------
        bool
            True si la operación fue exitosa.
        """
        if 'nombre' in vals and vals['nombre']:
            vals['nombre'] = self._normalize_nombre(vals['nombre'])
        return super().write(vals)


    # Display name
    @api.depends("nombre", "localidad_id", "localidad_id.display_name")
    def _compute_display_name(self):
        """
        Calcula el `display_name` con el formato:
        '<Nombre Ejido> (<Localidad, Municipio, Estado>)'.
        """
        for rec in self:
            if rec.localidad_id:
                # localidad_id.display_name ya viene como: "Los Mochis, Ahome, Sinaloa"
                rec.display_name = f"{rec.nombre} ({rec.localidad_id.display_name})"
            else:
                rec.display_name = rec.nombre or ""

    def action_back_to_list(self):
        """Regresa al listado de ejidos."""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Ejidos'),
            'res_model': 'ejidos.ejido',
            'view_mode': 'list,form',
            'target': 'current',
        }

# Extensión del modelo de Localidad para ver los ejidos desde ahí.
class Localidad(models.Model):
    """
    Extiende `localidades.localidad` para añadir la relación inversa
    (One2many) hacia los ejidos.
    """
    _inherit = "localidades.localidad"
    ejido_ids = fields.One2many(
        "ejidos.ejido",
        "localidad_id",
        string="Ejidos"
    )

    
