/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, onMounted, useState, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";

class SaleAgencyDashboard extends Component {

    setup() {

        this.orm = useService("orm");
        this.action = useService("action");

        this.commissionSplitChart = useRef("commissionSplitChart");
        this.monthlyTrendChart = useRef("monthlyTrendChart");

        this.state = useState({
            total_agencies: 0,
            total_agents: 0,
            total_customers: 0,
            total_commission_due: 0,
            total_commission_paid: 0,
            outstanding_commission: 0,

            total_commission_due_fmt: "₹0",
            total_commission_paid_fmt: "₹0",
            outstanding_commission_fmt: "₹0",

            monthly_labels: [],
            monthly_due: [],
            monthly_paid: [],

            top_agencies: [],
        });

        onWillStart(async () => {

            await loadJS("/web/static/lib/Chart/Chart.js");

            await this.loadDashboard();

        });

        onMounted(() => {

            this._renderCommissionSplitChart();
            this._renderMonthlyTrendChart();

        });
    }

    //----------------------------------------------------------
    // Load Dashboard
    //----------------------------------------------------------

    async loadDashboard() {

        const data = await this.orm.call(
            "sale.agency.dashboard",
            "get_dashboard_data",
            []
        );

        Object.assign(this.state, data);

        this._formatCurrency();

    }

    //----------------------------------------------------------
    // Refresh
    //----------------------------------------------------------

    async onRefresh() {

        await this.loadDashboard();

        this._renderCommissionSplitChart();
        this._renderMonthlyTrendChart();

    }

    //----------------------------------------------------------
    // Currency
    //----------------------------------------------------------

    _formatCurrency() {

        const format = (value) => {

            return new Intl.NumberFormat("en-IN", {

                style: "currency",
                currency: "INR",
                maximumFractionDigits: 0,

            }).format(value || 0);

        };

        this.state.total_commission_due_fmt =
            format(this.state.total_commission_due);

        this.state.total_commission_paid_fmt =
            format(this.state.total_commission_paid);

        this.state.outstanding_commission_fmt =
            format(this.state.outstanding_commission);

        this.state.top_agencies =
            (this.state.top_agencies || []).map((agency) => ({

                ...agency,

                commission_due_fmt:
                    format(agency.commission_due),

                commission_paid_fmt:
                    format(agency.commission_paid),

            }));

    }

    //----------------------------------------------------------
    // Charts
    //----------------------------------------------------------

    _renderCommissionSplitChart() {

        if (!this.commissionSplitChart.el) {
            return;
        }

        if (this.commissionChart) {
            this.commissionChart.destroy();
        }

        this.commissionChart = new Chart(
            this.commissionSplitChart.el,
            {
                type: "doughnut",

                data: {

                    labels: [
                        "Paid",
                        "Due",
                    ],

                    datasets: [
                        {

                            data: [

                                this.state.total_commission_paid,
                                this.state.total_commission_due,

                            ],

                            backgroundColor: [
                                "#28a745",
                                "#ffc107",
                            ],

                            borderWidth: 0,

                        },
                    ],
                },

                options: {

                    responsive: true,
                    maintainAspectRatio: false,

                    plugins: {

                        legend: {
                            position: "bottom",
                        },

                    },

                },

            }

        );

    }

    _renderMonthlyTrendChart() {

        if (!this.monthlyTrendChart.el) {
            return;
        }

        if (this.monthlyChart) {
            this.monthlyChart.destroy();
        }

        this.monthlyChart = new Chart(
            this.monthlyTrendChart.el,
            {

                type: "bar",

                data: {

                    labels: this.state.monthly_labels,

                    datasets: [

                        {

                            label: "Commission Due",

                            data: this.state.monthly_due,

                            backgroundColor: "#ffc107",

                        },

                        {

                            label: "Commission Paid",

                            data: this.state.monthly_paid,

                            backgroundColor: "#28a745",

                        },

                    ],

                },

                options: {

                    responsive: true,

                    maintainAspectRatio: false,

                    scales: {

                        y: {

                            beginAtZero: true,

                        },

                    },

                },

            }

        );

    }

    //----------------------------------------------------------
    // Navigation
    //----------------------------------------------------------

    async openAgencies() {
        await this.action.doAction(
            "custom_sales_agency.action_sale_agency"
        );
    }

    async openCustomers() {
        await this.action.doAction(
            "custom_sales_agency.action_agency_customers"
        );
    }

    async openCommissionDue() {
        await this.action.doAction(
            "custom_sales_agency.action_commission_due"
        );
    }   

    async openCommissionPaid() {
        await this.action.doAction(
            "custom_sales_agency.action_commission_paid"
        );
    }

    async openAgency(id) {

        await this.action.doAction({

            type: "ir.actions.act_window",

            res_model: "sale.agency",

            res_id: id,

            views: [
                [false, "form"],
            ],

            target: "current",

        });

    }

}

SaleAgencyDashboard.template = "custom_sales_agency.Dashboard";

registry.category("actions").add(
    "sale_agency_dashboard",
    SaleAgencyDashboard
);