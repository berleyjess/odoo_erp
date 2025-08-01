# -*- coding: utf-8 -*-
"""
Modelo: garantias.garantia
Descripción: Versión mínima que **no guarda** referencias a cliente ni propietario.
Sólo contiene los campos que se muestran actualmente en las vistas XML.
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class Garantia(models.Model):
    """Modelo principal de garantías (sin relación a clientes)."""

    _name = "garantias.garantia"
    _description = "Garantías de clientes"

    # === DATOS DE LA GARANTÍA ===
    tipo = fields.Selection(
        [
            ("prendaria", "Prendaria"),
            ("hipotecaria", "Hipotecaria"),
            ("usufructuaria", "Usufructuaria"),
        ],
        string="Tipo de Garantía",
        required=True,
    )

    titular = fields.Char(
        string="Titular de la garantía",
        help="Nombre del titular de la garantía."
    )

    descripcion = fields.Text(
        string="Descripción",
        help="Descripción detallada del bien entregado como garantía."
    )

    valor = fields.Float(
        string="Valor de la garantía",
        help="Valor comercial estimado de la garantía."
    )

    fecha_entrega = fields.Date(
        string="Fecha de entrega",
        help="Fecha en la que se entrega la garantía."
    )

    # === RESPONSABLES ===
    persona_entrega = fields.Char(
        string="Persona que entrega",
        help="Nombre de la persona que entrega la garantía."
    )

    persona_recibe = fields.Char(
        string="Persona que recibe",
        help="Nombre de la persona que recibe la garantía."
    )

    RFC = fields.Char(
        string="RFC del titular",
        help="Registro Federal de Contribuyentes del titular de la garantía."
    )

    localidad = fields.Many2one(
        comodel_name="localidades.localidad",
        string="Localidad",
        help="Localidad donde se encuentra la garantía."
    )

    # === VALIDACIONES ===
    @api.constrains("valor")
    def _check_valor(self):
        for rec in self:
            if rec.valor < 0:
                raise ValidationError("El valor de la garantía no puede ser negativo.")

    # === ACCIÓN UTILITARIA ===
    def action_back_to_list(self):
        """Botón para volver al listado de garantías."""
        return {
            "type": "ir.actions.act_window",
            "name": _("Garantías"),
            "res_model": "garantias.garantia",
            "view_mode": "list,form",
            "target": "current",
        }
