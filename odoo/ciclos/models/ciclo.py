from odoo import models, fields, api, _
from odoo.exceptions import ValidationError  
import logging
_logger = logging.getLogger(__name__)

class ciclo(models.Model):
    _name = 'ciclos.ciclo'
    _description = 'Ciclos Agrícolas'

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
        _logger.warning("REQ[uid=%s] user.id=%s login=%s sudo?=%s",
                self.env.uid, self.env.user.id, self.env.user.login,
                'YES' if self.env.su else 'NO')

        # Exigir permiso y empresa definidos (truena con ValidationError si no)
        rec._get_perm('editar_ciclo', raise_if_false=True, message=_(
            "No puedes editar ciclos: falta Empresa actual o no tienes permiso."
        ))
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
        _logger.info("PERM-CHECK[IN]: user=%s modulo=%s perm=%s arg.emp=%s arg.suc=%s arg.bod=%s", self.env.user.id, modulo_code, permiso_code, getattr(empresa_id, 'id', empresa_id), getattr(sucursal_id, 'id', sucursal_id), getattr(bodega_id, 'id', bodega_id))

        u = self.env.user
        Permiso = self.env['permisos.permiso'].sudo()
        p = Permiso.search([('code', '=', permiso_code),
                            ('modulo_id.code', '=', modulo_code)], limit=1)
        p_id = p.id or False
        _logger.info("PERM-CHECK[PERM]: target_perm_id=%s", p_id)
        if not p:
            _logger.warning("PERM-CHECK[NO-PERM]: permiso inexistente %s/%s", modulo_code, permiso_code)
            if raise_if_false:
                raise ValidationError(_("Permiso inexistente: %(m)s/%(p)s", m=modulo_code, p=permiso_code))
            return False
        scope = p.scope or 'empresa'
        # Foto del usuario y su contexto actual
        _logger.info("PERM-CHECK[USR]: uid=%s login=%s emp_act=%s suc_act=%s bod_act=%s emp_m2m=%s",
                     u.id, u.login, (u.empresa_actual_id.id if u.empresa_actual_id else False),
                     (u.sucursal_actual_id.id if u.sucursal_actual_id else False),
                     (getattr(u, 'bodega_actual_id', False) and u.bodega_actual_id.id or False),
                     u.sudo().empresas_ids.ids)

        def _id(v):
            return getattr(v, 'id', v) or False

        # Resolver IDs efectivamente usados
        if scope in ('empresa', 'empresa_sucursal', 'empresa_sucursal_bodega'):
            emp_id = _id(empresa_id) or (u.empresa_actual_id.id or (u.sudo().empresas_ids[:1].id) or False)
        else:
            emp_id = False

        if scope in ('empresa_sucursal', 'empresa_sucursal_bodega'):
            suc_id = _id(sucursal_id) or (u.sucursal_actual_id.id or False)
        else:
            suc_id = False

        if scope == 'empresa_sucursal_bodega':
            bod_id = _id(bodega_id) or (getattr(u, 'bodega_actual_id', False) and u.bodega_actual_id.id) or False
        else:
            bod_id = False

        _logger.info("PERM-CHECK[CTX]: scope=%s -> emp_id=%s suc_id=%s bod_id=%s | REQ[uid=%s login=%s]",
                     scope, emp_id, suc_id, bod_id, self.env.uid, self.env.user.login)

        # ---- ERROR EXPLÍCITO SI FALTA EMPRESA (cuando el permiso la requiere) ----
        if scope in ('empresa', 'empresa_sucursal', 'empresa_sucursal_bodega') and not emp_id:
            _logger.error("PERM-CHECK[ERR]: Falta empresa en contexto para %s/%s (uid=%s login=%s)",
                          modulo_code, permiso_code, self.env.uid, self.env.user.login)
            msg = message or _("Falta empresa en contexto para evaluar el permiso: %(m)s/%(p)s",
                               m=modulo_code, p=permiso_code)
            if raise_if_false:
                raise ValidationError(msg)
            return False

        ok = bool(u.has_perm(modulo_code, permiso_code,
                             empresa_id=emp_id, sucursal_id=suc_id, bodega_id=bod_id))

        _logger.info("PERM-CHECK[RESULT]: %s/%s -> ok=%s", modulo_code, permiso_code, ok)

        if raise_if_false and not ok:
            raise ValidationError(message or _(
                "No cuentas con el permiso requerido: %(m)s/%(p)s",
                m=modulo_code, p=permiso_code
            ))
        return ok
