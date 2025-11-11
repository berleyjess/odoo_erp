from odoo import models, fields, api, _
from odoo.exceptions import ValidationError  
import logging
_logger = logging.getLogger(__name__)

class ciclo(models.Model):
    _name = 'ciclos.ciclo'
    _description = 'Ciclos Agrícolas'
    modulo_code = 'ciclos'

    periodo = fields.Selection(selection=
                               [
                                  ("OI", "Otoño-Invierno"),
                                  ("PV", "Primavera-Verano")
                               ], string="Periodo", required=True)
    finicio = fields.Date(string="Fecha de Inicio", required=True)
    ffinal = fields.Date(string="Fecha Final", required=True)

    label = fields.Char(compute='_deflabel', store = True, string="Ciclo")
    
    @api.depends('periodo', 'finicio', 'ffinal')
    def _deflabel(self):
        
        for record in self:
            #_logger.info("=================================Permiso para editar un ciclo: ", record._get_perm('editar_ciclo'))
            periodo = record.periodo or ''
            anio_inicio = record.finicio.year if record.finicio else ''
            anio_final = record.ffinal.year if record.ffinal else ''
            if periodo and anio_inicio and anio_final:
                record.label = f"{periodo} {anio_inicio}-{anio_final}"
            else:
                record.label = ''

    @api.constrains('finicio', 'ffinal')
    def _check_dates(self):
        for rec in self:
            #_logger.info("=================================Permiso para editar un ciclo: ", rec._get_perm('editar_ciclo'))
            # Permite igualdad; cambia < por <= si quieres obligar que sea estrictamente mayor
            if rec.finicio and rec.ffinal and rec.ffinal < rec.finicio:
                raise ValidationError(
                    #El "_" sirve para traducir el mensaje, simplemente se puede poner la cadena sin el "_" si no se quiere traducir.
                    _("La Fecha Final (%s) no puede ser menor que la Fecha de Inicio (%s).") %
                    (rec.ffinal, rec.finicio)
                )
            
    _sql_constraints = [
        ('unique_label', 'unique(label)', 'Ya existe un ciclo con ese periodo y rango de años.')
    ]



    def action_open_edit(self):
        """Abrir este registro en el form editable."""
        self.env.user.check_perm('ciclos', 'editar_ciclo')
        
        rec = self[:1]  # evitar ensure_one
        """_logger.warning("REQ[uid=%s] user.id=%s login=%s sudo?=%s",
                self.env.uid, self.env.user.id, self.env.user.login,
                'YES' if self.env.su else 'NO')

        # Exigir permiso y empresa definidos (truena con ValidationError si no)
        rec._get_perm('editar_ciclo', raise_if_false=True, message=_(
            "No puedes editar ciclos: falta Empresa actual o no tienes permiso."
        ))"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Editar Ciclo',
            'res_model': 'ciclos.ciclo',
            'res_id': rec.id,
            'view_mode': 'form',
            'views': [(self.env.ref('ciclos.view_ciclo_form').id, 'form')],
            'target': 'current',
            'context': {**self.env.context, 'form_view_initial_mode': 'edit'},
        }

    def action_back_to_list(self):
        """Regresa al listado de productos."""
        _logger.info(f"=== Regresando al listado de ciclos: {self._get_perm('editar_ciclo')}")
        _logger.info(f"=================================Permiso negativo: {self._get_perm('edit_cicl000')}")
        return {
            'type': 'ir.actions.act_window',
            'name': _('ciclo'),
            'res_model': 'ciclos.ciclo',
            'view_mode': 'list,form',
            'target': 'current',
        }
    
    tiene_editar = fields.Boolean(
        string='Puede editar',
        compute='_compute_perms',
        compute_sudo=True,  # para evitar recortes por reglas
        store=False         # no lo guardes; se calcula al pintar
    )

    @api.depends_context('uid')  # recalcula por usuario (cuando cambias de usuario)
    def _compute_perms(self):
        user = self.env.user
        for r in self:
            r.tiene_editar = user.has_perm('ciclos', 'editar_ciclo')
