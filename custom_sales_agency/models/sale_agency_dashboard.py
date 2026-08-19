from odoo import api, fields, models
from dateutil.relativedelta import relativedelta


class SaleAgencyDashboard(models.AbstractModel):
    _name = 'sale.agency.dashboard'
    _description = 'Agency Dashboard'

    @api.model
    def get_dashboard_data(self):
        agencies = self.env['sale.agency'].search([])
        agents = self.env['res.partner'].search_count([
            ('is_agentt', '=', True)
        ])
        customers = self.env['res.partner'].search_count([
            ('x_agency_id', '!=', False)
        ])

        commissions = self.env['sale.agency.commission'].search([])

        total_due = sum(
            agencies.mapped('total_commission_due')
        )

        total_paid = sum(
            agencies.mapped('total_commission_paid')
        )

        total_rev = sum(
            agencies.mapped('total_commission_negative')
        )
        paid_commissions = commissions.filtered(
            lambda c: c.state == 'commission_paid'
        )
        total_paid = sum(paid_commissions.mapped('commission_amount'))
        total = sum(commissions.mapped('commission_amount'))

        return {
            'total_agencies': len(agencies),
            'total_agents': agents,
            'total_customers': customers,
            'total_commission_due': round(total_due, 2),
            'total_commission_paid': round(total_paid, 2),
            'outstanding_commission': round(total_rev, 2),
            'top_agencies': self._get_top_agencies(agencies, commissions),
            **self._get_monthly_trend(commissions),
        }

    # def _get_top_agencies(self, agencies, commissions):
    #     """Top 5 agencies by commission due, with order count."""
    #     commission_fields = self.env['sale.agency.commission']._fields
    #     order_field = None
    #     for candidate in ('order_id', 'sale_order_id', 'sale_id', 'sale_order'):
    #         if candidate in commission_fields:
    #             order_field = candidate
    #             break

    #     result = []
    #     for agency in agencies:
    #         agency_commissions = commissions.filtered(
    #             lambda c: c.agency_id == agency
    #         )
    #         due = sum(agency_commissions.mapped('commission_amount'))
    #         paid = sum(
    #             agency_commissions.filtered(
    #                 lambda c: c.state == 'commission_paid'
    #             ).mapped('commission_amount')
    #         )
    #         order_count = (
    #             len(agency_commissions.mapped(order_field))
    #             if order_field else len(agency_commissions)
    #         )

    #         result.append({
    #             'id': agency.id,
    #             'name': agency.name,
    #             'order_count': order_count,
    #             'commission_due': due,
    #             'commission_paid': paid,
    #         })

    #     result.sort(key=lambda r: r['commission_due'], reverse=True)
    #     return result[:5]
    
    def _get_top_agencies(self, agencies, commissions):
        """Top 5 agencies by outstanding commission."""

        commission_fields = self.env['sale.agency.commission']._fields
        order_field = None
        for candidate in ('sale_order_ids', 'order_id', 'sale_order_id', 'sale_id', 'sale_order'):
            if candidate in commission_fields:
                order_field = candidate
                break

        result = []

        for agency in agencies:
            agency_commissions = commissions.filtered(
                lambda c: c.agency_id == agency
            )

            due = sum(
                agency_commissions.filtered(
                    lambda c: c.state == 'payment_received'
                ).mapped('commission_amount')
            )

            paid = sum(
                agency_commissions.filtered(
                    lambda c: c.state == 'commission_paid'
                ).mapped('commission_amount')
            )

            reversed_amount = sum(
                agency_commissions.filtered(
                    lambda c: c.state == 'commission_reversed'
                ).mapped('commission_amount')
            )

            outstanding = due - paid - reversed_amount

            order_count = (
                len(agency_commissions.mapped(order_field))
                if order_field
                else len(agency_commissions)
            )

            result.append({
                'id': agency.id,
                'name': agency.name,
                'order_count': order_count,
                'commission_due': due,
                'commission_paid': paid,
                'outstanding': outstanding,
            })

        result.sort(
            key=lambda r: r['outstanding'],
            reverse=True,
        )

        return result[:5]
    
    def _get_monthly_trend(self, commissions):
        months = []
        due_vals = []
        paid_vals = []
        outstanding_vals = []

        today = fields.Date.today()

        for i in range(5, -1, -1):
            month_start = (
                today.replace(day=1)
                - relativedelta(months=i)
            )

            month_end = (
                month_start
                + relativedelta(months=1)
                - relativedelta(days=1)
            )

            month_commissions = commissions.filtered(
                lambda c:
                c.commission_date and
                month_start <= c.commission_date <= month_end
            )

            due = sum(
                month_commissions.filtered(
                    lambda c: c.state == 'payment_received'
                ).mapped('commission_amount')
            )

            paid = sum(
                month_commissions.filtered(
                    lambda c: c.state == 'commission_paid'
                ).mapped('commission_amount')
            )

            reversed_amount = sum(
                month_commissions.filtered(
                    lambda c: c.state == 'commission_reversed'
                ).mapped('commission_amount')
            )

            # if reversed commissions are positive
            outstanding = due - paid - reversed_amount

            # if reversed commissions are negative:
            # outstanding = due - paid + reversed_amount

            months.append(month_start.strftime('%b %Y'))
            due_vals.append(due)
            paid_vals.append(paid)
            outstanding_vals.append(outstanding)

        return {
            'monthly_labels': months,
            'monthly_due': due_vals,
            'monthly_paid': paid_vals,
            'monthly_outstanding': outstanding_vals,
        }