import requests
from odoo import models, fields, api

class ShopifyIntegration(models.Model):
    _name = "shopify.integration"
    _description = "Shopify Integration Configuration"

    name = fields.Char(string="Instance Name", required=True)
    shop_url = fields.Char(string="Shopify Store URL", required=True)
    api_key = fields.Char(string="API Key", required=True)
    password = fields.Char(string="Password", required=True)
    api_version = fields.Char(string="API Version", default="2023-10")

    def fetch_products(self):
        for record in self:
            url = f"https://{record.shop_url}/admin/api/{record.api_version}/products.json"
            headers = {
                "X-Shopify-Access-Token": record.password,
                "Content-Type": "application/json",
            }

            response = requests.get(url, headers=headers)

            if response.status_code == 200:
                products = response.json().get("products", [])
                for prod in products:
                    vals = {
                        "name": prod["title"],
                        "default_code": prod["id"],
                        "list_price": float(prod["variants"][0]["price"]) if prod["variants"] else 0.0,
                    }
                    existing = self.env['product.product'].search([('default_code', '=', prod["id"])], limit=1)
                    if existing:
                        existing.write(vals)
                    else:
                        self.env['product.product'].create(vals)
            else:
                # Raise error to see immediately
                raise Exception(f"Shopify API Error {response.status_code}: {response.text}")

    def fetch_customers(self):
        for record in self:
            url = f"https://{record.api_key}:{record.password}@{record.shop_url}/admin/api/{record.api_version}/customers.json"
            response = requests.get(url)
            if response.status_code == 200:
                customers = response.json().get("customers", [])
                for cust in customers:
                    vals = {
                        "name": f"{cust['first_name']} {cust['last_name']}",
                        "email": cust["email"],
                    }
                    existing = self.env['res.partner'].search([('email', '=', cust["email"])], limit=1)
                    if existing:
                        existing.write(vals)
                    else:
                        self.env['res.partner'].create(vals)
            # else:
            #     _logger = self.env['ir.logging']
            #     _logger.sudo().create({
            #         'name': 'Shopify Sync Error',
            #         'type': 'server',
            #         'message': f"Failed to fetch customers: {response.text}",
            #         'level': 'ERROR',
            #     })
