from odoo import models, fields, api, _
from odoo.exceptions import ValidationError  
import logging
_logger = logging.getLogger(__name__)

class ciclo(models.Model):
    _name = 'ciclos.ciclo'
    _description = 'Ciclos Agrícolas'
    _rec_name = 'label'

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
        
        rec = self[:1]  # evitar ensure_one
        #  result = rec._get_perm('editar_ciclo')
        #_logger.info(f"=================================Permiso para editar un ciclo: {result}")

        #_logger.info("=================================Permiso para editar un ciclo: 22222222222222222222")
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
    
    @api.model
    def _get_perm(self, permiso_code, *, modulo_code='ciclos', empresa_id=None, sucursal_id=None, bodega_id=None, raise_if_false=False, message=None):
        u = self.env.user
        Permiso = self.env['permisos.permiso'].sudo()
        p = Permiso.search([('code','=',permiso_code), ('modulo_id.code','=',modulo_code)], limit=1)
        scope = p.scope or 'empresa'

        # Completar contexto con “actuales” SOLO si aplica el scope y no se pasaron explícitos
        emp = empresa_id if empresa_id is not None else (u.empresa_actual_id.id if scope in ('empresa','empresa_sucursal','empresa_sucursal_bodega') else None)
        suc = sucursal_id if sucursal_id is not None else (u.sucursal_actual_id.id if scope in ('empresa_sucursal','empresa_sucursal_bodega') else None)
        bod = bodega_id if bodega_id is not None else (getattr(u, 'bodega_actual_id', False) and u.bodega_actual_id.id if scope == 'empresa_sucursal_bodega' else None)

        ok = bool(u.has_perm(modulo_code, permiso_code, empresa_id=emp, sucursal_id=suc, bodega_id=bod))
        _logger.info("PERM-CHECK: mod=%s perm=%s scope=%s -> emp=%s suc=%s bod=%s -> ok=%s",
                     modulo_code, permiso_code, scope, emp, suc, bod, ok)

        if raise_if_false and not ok:
            raise ValidationError(message or _(
                "No cuentas con el permiso requerido: %(m)s/%(p)s",
                m=modulo_code, p=permiso_code
            ))
        return ok
